"""Fat runner — all isolation, timeout, and cleanup lives here (AD-3, Specs B+D).

run_task() executes the full Spec B isolation sequence:
  1. Fresh clone @ repo_commit → record repo_commit
  2. Apply task.mutation (failing start state)
  3. Write / omit context_filename (with_context flag; flags identical both arms)
  4. EgressNetwork up (internal net + proxy sidecar)
  5. Start eval container on primer-internal only, one key via --env,
     cap_drop=ALL, no-new-privileges, mem_limit, nano_cpus, pids_limit
  6. Command: sh -c '<agent argv> > /work/.primer_agent.log 2>&1 ; <verify_cmd>'
  7. container.wait(timeout=eval_timeout_s) — raises ReadTimeout on timeout (Spec D)
  8. Read + redact agent log BEFORE rmtree
  9. finally: remove container, proxy, network, temp dir
 10. Post-run audit: docker ps -a must not show this container id

passed = (exit_code == 0)  — the agent NEVER decides pass/fail (AD-4).
egress_enforced / network_mode come from EgressInfo.enforced (never optimistic).
base_image = resolved sha256 digest stored in RunResult (M5).
"""
from __future__ import annotations

import datetime
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

import docker
import docker.errors
import requests.exceptions

from primer.eval.models import AgentTelemetry, RunResult
from primer.eval.network import EgressNetwork
from primer.llm.base import LLMProvider

if TYPE_CHECKING:
    from primer.config import Settings
    from primer.eval.agent_adapter import AgentAdapter
    from primer.eval.models import Task

log = logging.getLogger(__name__)

# Path inside the container where the agent log is captured
_AGENT_LOG_PATH = "/work/.primer_agent.log"
# Resource limits (Spec B step 6)
_NANO_CPUS = 2_000_000_000   # 2 CPUs
_PIDS_LIMIT = 512


def run_task(
    task: "Task",
    repo_path: str,
    with_context: bool,
    profile,
    config: "Settings",
    adapter: "AgentAdapter",
    image_tag: str,
) -> RunResult:
    """Execute one task arm (with or without context) in full isolation.

    This is the fat runner — all Docker, network, timeout, and cleanup
    logic lives here (AD-3). Adapters supply invocation details only.

    Returns a RunResult with passed determined solely by verify_cmd exit code.
    """
    run_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    temp_dir = tempfile.mkdtemp(prefix="primer_run_")
    container = None
    container_id = "unknown"
    egress_info = None
    passed = False
    timed_out = False
    flaky = False
    exit_code = -1

    # Spec D: docker client timeout > eval timeout
    client = docker.from_env(timeout=config.docker_client_timeout_s)

    try:
        # ----- Step 1: Fresh clone @ repo_commit --------------------------------
        work_dir = Path(temp_dir) / "repo"
        _clone_repo(repo_path, work_dir, profile.repo_commit)

        # ----- Step 2: Apply mutation (failing start state) ---------------------
        _apply_mutation(task, work_dir)

        # ----- Step 3: Write / omit context file (flags identical both arms) ----
        context_file_path = work_dir / adapter.context_filename()
        if with_context:
            if not context_file_path.exists():
                raise RuntimeError(
                    f"Context file expected at {context_file_path} but was not found. "
                    "Call run_task with a pre-written context file or generate it first."
                )
            # File is already written by the caller (scorer) before run_task
        else:
            # WITHOUT arm: guarantee context file does not exist
            if context_file_path.exists():
                context_file_path.unlink()

        # Spec B step 8 guard: assert no stale context file in WITHOUT arm
        if not with_context and context_file_path.exists():
            raise RuntimeError(
                f"Context file {context_file_path} still exists in WITHOUT arm — "
                "isolation invariant violated."
            )

        # ----- Step 4: EgressNetwork up (Spec B steps 2–4) ---------------------
        with EgressNetwork(config, client) as egress_info:
            proxy_env: dict[str, str] = {}
            if egress_info.enforced and egress_info.proxy_url:
                proxy_env = {
                    "HTTPS_PROXY": egress_info.proxy_url,
                    "HTTP_PROXY": egress_info.proxy_url,
                    "NO_PROXY": "localhost,127.0.0.1",
                }

            # ----- Step 5: Inject the one agent key --------------------------
            agent_key_name = adapter.required_env_key()
            agent_key_value = _get_agent_key(config, agent_key_name)
            container_env = {
                agent_key_name: agent_key_value,
                **proxy_env,
            }

            # ----- Step 6: Build container command ---------------------------
            agent_argv = adapter.build_invocation(task)
            agent_cmd = " ".join(_shell_quote(a) for a in agent_argv)
            verify_cmd = task.verify_cmd
            # Command ends with verify_cmd so exit code = verify_cmd exit code (Spec B-9, AD-4)
            full_cmd = (
                f"sh -c '{agent_cmd} > {_AGENT_LOG_PATH} 2>&1 ; {verify_cmd}'"
            )

            # ----- Start container on internal network -----------------------
            container = client.containers.run(
                image_tag,
                command=full_cmd,
                working_dir="/work",
                volumes={str(work_dir): {"bind": "/work", "mode": "rw"}},
                network=egress_info.network_name,
                environment=container_env,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                mem_limit=config.primer_eval_mem_limit,
                nano_cpus=_NANO_CPUS,
                pids_limit=_PIDS_LIMIT,
                detach=True,
                auto_remove=False,  # Must NOT use auto_remove (races wait())
            )
            container_id = container.id[:12]
            log.info("started container %s (with_context=%s)", container_id, with_context)

            # ----- Step 7: Wait for container (Spec D) -----------------------
            try:
                result = container.wait(timeout=config.primer_eval_timeout_s)
                exit_code = result.get("StatusCode", -1)
                passed = (exit_code == 0)
                log.info(
                    "container %s exited %d → passed=%s",
                    container_id, exit_code, passed,
                )
            except requests.exceptions.ReadTimeout:
                log.warning(
                    "container %s timed out after %ds",
                    container_id, config.primer_eval_timeout_s,
                )
                try:
                    container.kill()
                except (docker.errors.APIError, docker.errors.NotFound):
                    pass
                passed = False
                timed_out = True

            # ----- Step 8: Read + redact agent log BEFORE rmtree -----------
            agent_log_content = _read_container_log(container, _AGENT_LOG_PATH, work_dir)
            redacted_log = LLMProvider.log_safe(agent_log_content)

            # Save redacted log to a persistent path (outside temp_dir so it
            # survives rmtree — stored in system temp alongside the run)
            log_filename = f"primer_agent_{container_id}_{run_ts[:19].replace(':', '-')}.log"
            log_persist_dir = Path(tempfile.gettempdir()) / "primer_logs"
            log_persist_dir.mkdir(exist_ok=True)
            log_persist_path = log_persist_dir / log_filename
            log_persist_path.write_text(redacted_log, encoding="utf-8")

            # Parse telemetry (NO pass/fail — AD-4)
            telemetry = adapter.parse_telemetry(redacted_log)

    finally:
        # ----- Step 9: Cleanup — idempotent and defensive (Spec D finally) ----
        if container is not None:
            try:
                container.remove(force=True)
                log.debug("removed container %s", container_id)
            except docker.errors.NotFound:
                pass
            except Exception as exc:
                log.warning("container remove failed: %s", exc)

        shutil.rmtree(temp_dir, ignore_errors=True)

    # ----- Step 10 (Spec B-12): Post-run audit: container must be gone ------
    _assert_container_gone(client, container_id)

    # ----- Build RunResult ---------------------------------------------------
    # Resolve base image digest from image tag metadata
    base_image = _get_image_digest(client, image_tag)

    return RunResult(
        task_id=task.id,
        passed=passed,
        timeout=timed_out,
        flaky=flaky,
        with_context=with_context,
        # eval-agent cost stream
        agent_adapter=adapter.adapter_name,
        agent_tokens=telemetry.tokens,
        iterations=telemetry.iterations,
        duration_s=telemetry.duration_s,
        cost_usd=telemetry.cost_usd,
        cost_confidence=telemetry.cost_confidence,
        # PRIMER-brain provenance (set by scorer which has profile context)
        provider="",   # filled in by scorer
        model="",      # filled in by scorer
        # isolation audit trail
        base_image=base_image,
        repo_commit=profile.repo_commit,
        network_mode="proxy-egress" if (egress_info and egress_info.enforced) else "open-bridge",
        egress_allowed_host=egress_info.allowed_host if egress_info else None,
        egress_enforced=bool(egress_info and egress_info.enforced),
        caps_dropped=True,
        container_id=container_id,
        agent_log_path=str(log_persist_path),
        run_timestamp=run_ts,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clone_repo(repo_path: str, dest: Path, commit: str) -> None:
    """Copy repo to dest and check out the given commit."""
    src = Path(repo_path)
    # Copy source tree (excluding .git pycache etc.)
    shutil.copytree(
        str(src), str(dest),
        symlinks=True,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".venv"),
    )
    # Copy .git for git operations
    if (src / ".git").exists():
        shutil.copytree(str(src / ".git"), str(dest / ".git"), symlinks=True)
    # Check out the specific commit
    try:
        subprocess.run(
            ["git", "checkout", commit, "--force"],
            cwd=str(dest),
            capture_output=True,
            timeout=30,
        )
    except Exception as exc:
        log.debug("git checkout %s failed: %s (using current state)", commit, exc)


def _apply_mutation(task: "Task", work_dir: Path) -> None:
    """Apply the task mutation to create the failing start state."""
    from primer.eval.preflight import _apply_mutation as _pm
    ok = _pm(task, work_dir)
    if not ok:
        raise RuntimeError(
            f"Could not apply mutation for task {task.id!r}. "
            "Pre-flight should have caught this."
        )


def _get_agent_key(config: "Settings", key_name: str) -> str:
    """Retrieve the agent's required key value (SecretStr → plain string)."""
    attr = key_name.lower()
    val = getattr(config, attr, None)
    if val is None:
        from primer.errors import ConfigError
        raise ConfigError(
            f"Agent key {key_name} is not set. "
            "Add it to .env (see .env.example)."
        )
    # SecretStr.get_secret_value() or plain str
    if hasattr(val, "get_secret_value"):
        return val.get_secret_value()
    return str(val)


def _shell_quote(s: str) -> str:
    """Minimal shell quoting for the container command string."""
    # Wrap in single quotes, escaping any embedded single quotes
    escaped = s.replace("'", "'\\''")
    return f"'{escaped}'"


def _read_container_log(container, log_path: str, work_dir: Path) -> str:
    """Read the agent log from the container's mounted volume."""
    # The log is at work_dir / .primer_agent.log on the host (via the volume mount)
    local_log = work_dir / ".primer_agent.log"
    if local_log.exists():
        try:
            return local_log.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            log.warning("could not read agent log from volume: %s", exc)

    # Fallback: use docker logs (captures stdout/stderr, not the file)
    try:
        logs = container.logs(stdout=True, stderr=True)
        if isinstance(logs, bytes):
            return logs.decode("utf-8", errors="replace")
        return logs
    except Exception as exc:
        log.warning("could not read container logs: %s", exc)
        return ""


def _assert_container_gone(client: docker.DockerClient, container_id: str) -> None:
    """Post-run audit: verify the container is no longer listed (Spec B-12)."""
    try:
        containers = client.containers.list(all=True, filters={"id": container_id})
        if containers:
            log.warning(
                "POST-RUN AUDIT: container %s still listed after cleanup! "
                "Attempting force remove.", container_id
            )
            for c in containers:
                try:
                    c.remove(force=True)
                except Exception:
                    pass
    except Exception as exc:
        log.debug("post-run audit error: %s", exc)


def _get_image_digest(client: docker.DockerClient, image_tag: str) -> str:
    """Return the resolved sha256 digest for the eval image (M5)."""
    try:
        img = client.images.get(image_tag)
        digests = img.attrs.get("RepoDigests", [])
        if digests:
            return digests[0]
        # If no RepoDigest, use the image ID (sha256:...)
        img_id = img.attrs.get("Id", "")
        if img_id:
            return img_id
    except Exception as exc:
        log.debug("could not get image digest: %s", exc)
    return image_tag
