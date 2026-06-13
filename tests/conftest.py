"""Shared fixtures for PRIMER test suite (Phase 0)."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


# -- Project root -------------------------------------------------------------

@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the PRIMER project root directory."""
    return Path(__file__).parent.parent


# -- Env-var injection / cleanup ----------------------------------------------

@pytest.fixture()
def clean_env(monkeypatch):
    """Remove all PRIMER_* and *_API_KEY vars so tests start from a known baseline."""
    vars_to_remove = [
        "PRIMER_LLM_PROVIDER", "PRIMER_DEFAULT_MODEL",
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
        "OPENROUTER_API_KEY", "OLLAMA_BASE_URL", "OLLAMA_MODEL",
        "PRIMER_AGENT", "PRIMER_AGENT_API_HOST",
        "PRIMER_TASK_COUNT", "PRIMER_MIN_TASKS", "PRIMER_EVAL_RUNS",
        "PRIMER_EVAL_TIMEOUT_S", "PRIMER_COMMIT_SCAN_DEPTH",
        "PRIMER_EVAL_MEM_LIMIT", "DOCKER_BASE_IMAGE",
        "PROXY_IMAGE", "DATABASE_URL",
    ]
    for var in vars_to_remove:
        monkeypatch.delenv(var, raising=False)

    # Prevent pydantic-settings from reading .env so file-based values don't
    # leak into tests that expect a clean environment.
    from primer.config import Settings
    monkeypatch.setattr(Settings, "model_config", {**Settings.model_config, "env_file": None})

    yield


@pytest.fixture()
def env_with_keys(monkeypatch):
    """Inject valid-looking (fake) API keys so validate_runtime() passes."""
    monkeypatch.setenv("PRIMER_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-000000000000")
    monkeypatch.setenv("PRIMER_AGENT", "claude_code")
    yield


# -- Temporary git repo with pre-commit hooks installed -----------------------

@pytest.fixture()
def temp_git_repo_with_hooks():
    """Create a temporary git repo in /tmp and install the project pre-commit hooks.

    Uses /tmp directly to avoid permission issues with mounted filesystems.
    Used by test_security_scaffold to verify the hooks actually reject secrets.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="primer_test_", dir="/tmp"))
    repo = tmp_dir / "testrepo"
    repo.mkdir()

    try:
        subprocess.run(["git", "init", "--initial-branch=main", str(repo)],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@test.com"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"],
                       check=True, capture_output=True)

        primer_root = Path(__file__).parent.parent
        pre_commit_cfg = primer_root / ".pre-commit-config.yaml"
        secrets_baseline = primer_root / ".secrets.baseline"

        shutil.copy(pre_commit_cfg, repo / ".pre-commit-config.yaml")
        shutil.copy(secrets_baseline, repo / ".secrets.baseline")

        subprocess.run(
            ["pre-commit", "install"],
            cwd=str(repo), check=True, capture_output=True,
            env={**os.environ, "PATH": os.environ.get("PATH", "") +
                 ":/sessions/bold-tender-cray/.local/bin"},
        )

        yield repo
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
