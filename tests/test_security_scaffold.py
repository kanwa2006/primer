"""Security scaffold tests — pre-commit hooks, secrets baseline, and .env isolation."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
PRE_COMMIT_CFG = PROJECT_ROOT / ".pre-commit-config.yaml"
SECRETS_BASELINE = PROJECT_ROOT / ".secrets.baseline"
GITIGNORE = PROJECT_ROOT / ".gitignore"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"


class TestPreCommitConfig:
    def test_pre_commit_config_exists(self):
        assert PRE_COMMIT_CFG.exists(), ".pre-commit-config.yaml must exist"

    def test_references_gitleaks(self):
        content = PRE_COMMIT_CFG.read_text()
        assert "gitleaks" in content, ".pre-commit-config.yaml must reference gitleaks"

    def test_references_detect_secrets(self):
        content = PRE_COMMIT_CFG.read_text()
        assert "detect-secrets" in content, \
            ".pre-commit-config.yaml must reference detect-secrets"


class TestSecretsBaseline:
    def test_secrets_baseline_exists(self):
        assert SECRETS_BASELINE.exists(), ".secrets.baseline must exist (and be committed)"

    def test_secrets_baseline_not_gitignored(self):
        """git check-ignore must report .secrets.baseline is NOT ignored."""
        result = subprocess.run(
            ["git", "check-ignore", "-v", str(SECRETS_BASELINE)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        # exit code 1 = not ignored (what we want); 0 = ignored (bad)
        assert result.returncode != 0, (
            ".secrets.baseline must NOT be in .gitignore — it must be committed.\n"
            f"git check-ignore output: {result.stdout}"
        )


class TestDotEnv:
    def test_env_is_gitignored(self):
        """.env must be listed in .gitignore (git check-ignore exits 0)."""
        env_path = PROJECT_ROOT / ".env"
        result = subprocess.run(
            ["git", "check-ignore", "-v", str(env_path)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, (
            ".env must be git-ignored.\n"
            f"git check-ignore output: {result.stdout}"
        )

    def test_env_example_has_only_empty_values(self):
        """.env.example must contain only KEY= lines (no KEY=value)."""
        content = ENV_EXAMPLE.read_text()
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            assert "=" in line, f"Unexpected line in .env.example: {line!r}"
            key, _, value = line.partition("=")
            assert value == "", (
                f".env.example must only have empty values, "
                f"but found {key!r}={value!r}"
            )


class TestPositiveControl:
    """Positive control: a staged file containing a secret must be REJECTED."""

    def test_hook_rejects_staged_secret(self, temp_git_repo_with_hooks):
        """Plant a dummy sk-ant-… secret in a staged file; pre-commit must reject it."""
        repo = temp_git_repo_with_hooks
        secret_file = repo / "bad_secret.py"
        # Dummy key in the format detect-secrets and gitleaks both flag
        secret_file.write_text('API_KEY = "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAA"\n')

        subprocess.run(["git", "-C", str(repo), "add", "bad_secret.py"],
                       check=True, capture_output=True)

        result = subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "test: add secret"],
            capture_output=True,
            text=True,
            env={
                **__import__("os").environ,
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@test.com",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@test.com",
            },
        )
        assert result.returncode != 0, (
            "Pre-commit hook should have REJECTED the commit containing a secret, "
            "but it succeeded.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
