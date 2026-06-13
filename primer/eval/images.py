"""Eval image builder (AD-2, M5).

build_eval_image() builds (or reuses) a per-(repo, commit) Docker image with
deps pre-baked. Source is NOT baked — a fresh copy is mounted at run time.
The base image tag is resolved to a sha256 digest at build time (M5).

This is the ONLY step that uses host-level network (for pip install).
After this, all isolation steps in runner.py use no external network.
"""
from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import docker

if TYPE_CHECKING:
    from primer.config import Settings
    from primer.eval.agent_adapter import AgentAdapter

log = logging.getLogger(__name__)


def build_eval_image(
    repo_path: str,
    profile,
    config: "Settings",
    adapter: "AgentAdapter",
) -> str:
    """Build or reuse a deps-only eval image for the given repo and agent.

    Returns the image tag string (primer-eval-<repohash>-<agent>:<commit>).

    AD-2: deps are pre-baked so `pip install` costs no eval-timeout budget.
    M5: base image is built FROM the resolved sha256 digest.
    Source is NOT copied into the image — it is mounted per run.
    The agent name is included in the tag so that images built for different
    agents do not collide in the Docker cache (BLK-1).
    """
    repo = Path(repo_path)
    repo_commit = profile.repo_commit

    # Derive a short hash of the repo path for a stable image name.
    # Agent name is included to prevent cache collisions across different agents.
    repo_hash = hashlib.sha1(str(repo.resolve()).encode()).hexdigest()[:12]
    image_tag = f"primer-eval-{repo_hash}-{adapter.adapter_name}:{repo_commit[:12]}"

    client = docker.from_env(timeout=config.docker_client_timeout_s)

    # Reuse if already built
    try:
        client.images.get(image_tag)
        log.info("reusing existing eval image: %s", image_tag)
        return image_tag
    except docker.errors.ImageNotFound:
        pass

    log.info("building eval image: %s", image_tag)

    # Resolve base image tag to digest (M5)
    base_digest = _resolve_digest(client, config.docker_base_image)
    log.info("base image digest: %s", base_digest)

    # Build a minimal Dockerfile that installs deps and provisions the agent CLI
    dockerfile_content = _make_eval_dockerfile(repo, base_digest, profile, adapter)

    with tempfile.TemporaryDirectory(prefix="primer_build_") as build_ctx:
        ctx = Path(build_ctx)
        (ctx / "Dockerfile").write_text(dockerfile_content, encoding="utf-8")

        # Copy only manifest + lock files (not source)
        _copy_manifest_files(repo, ctx)

        image, build_logs = client.images.build(
            path=str(ctx),
            tag=image_tag,
            rm=True,
            forcerm=True,
            # host network for pip install (the ONLY networked build step)
            network_mode="host",
        )
        for entry in build_logs:
            if "stream" in entry:
                log.debug("docker build: %s", entry["stream"].rstrip())

    log.info("eval image built: %s", image_tag)
    return image_tag


def _resolve_digest(client: docker.DockerClient, image_ref: str) -> str:
    """Pull the image if needed and return its sha256 digest (M5).

    Returns a string like 'python:3.11-slim@sha256:abc123...' or just the
    ref if resolution fails (open-bridge fallback with a warning).
    """
    try:
        # Pull to ensure we have the latest
        log.debug("pulling base image %s to resolve digest...", image_ref)
        client.images.pull(image_ref)
        img = client.images.get(image_ref)
        # RepoDigests look like ["python@sha256:abc123..."]
        digests = img.attrs.get("RepoDigests", [])
        if digests:
            # Strip the repo part and append to our tag for clarity
            digest_part = digests[0].split("@", 1)[-1]
            # Return as "tag@sha256:..."
            tag_part = image_ref.split(":")[0] + ":" + (image_ref.split(":")[1] if ":" in image_ref else "latest")
            resolved = f"{tag_part}@{digest_part}"
            log.info("resolved base image to: %s", resolved)
            return resolved
        else:
            log.warning("could not resolve digest for %s — using tag", image_ref)
            return image_ref
    except Exception as exc:
        log.warning("digest resolution failed for %s: %s — using tag", image_ref, exc)
        return image_ref


def _make_eval_dockerfile(
    repo: Path,
    base_digest: str,
    profile,
    adapter: "AgentAdapter",
) -> str:
    """Generate Dockerfile content for the eval image.

    Installs project deps (pip) and pytest, then appends any agent-specific
    installation layers from adapter.image_layers() (BLK-1).
    """
    lines = [f"FROM {base_digest}"]
    lines.append("WORKDIR /work")

    # Install pytest (always needed for verify_cmd)
    # Also install any manifest-declared deps
    if (repo / "pyproject.toml").exists():
        lines.append("COPY pyproject.toml ./")
        # Copy lock file if present
        for lock in ["poetry.lock", "pdm.lock", "requirements.txt", "requirements-lock.txt"]:
            if (repo / lock).exists():
                lines.append(f"COPY {lock} ./")
        lines.append(
            "RUN pip install --no-cache-dir -e . 2>/dev/null || "
            "pip install --no-cache-dir pytest"
        )
    elif (repo / "requirements.txt").exists():
        lines.append("COPY requirements.txt ./")
        lines.append(
            "RUN pip install --no-cache-dir -r requirements.txt && "
            "pip install --no-cache-dir pytest"
        )
    else:
        lines.append("RUN pip install --no-cache-dir pytest")

    # Ensure pytest is installed even if the project install missed it
    lines.append("RUN pip install --no-cache-dir pytest pytest-timeout 2>/dev/null || true")

    # Append agent-specific installation layers (e.g. Claude Code CLI via apt).
    # For adapters with no provisioning requirements, image_layers() returns []
    # and no lines are added (backward-compatible, no-op for those adapters).
    for layer in adapter.image_layers():
        lines.append(layer)

    return "\n".join(lines) + "\n"


def _copy_manifest_files(repo: Path, ctx: Path) -> None:
    """Copy manifest and lock files (NOT source) to the build context."""
    import shutil
    manifest_names = [
        "pyproject.toml", "setup.py", "setup.cfg",
        "requirements.txt", "requirements-lock.txt",
        "poetry.lock", "pdm.lock",
        "package.json", "package-lock.json", "yarn.lock",
        "Pipfile", "Pipfile.lock",
    ]
    for name in manifest_names:
        src = repo / name
        if src.exists():
            shutil.copy2(str(src), str(ctx / name))
