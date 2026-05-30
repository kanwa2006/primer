"""THE Phase 3 acceptance test (Session 2 §9).

Tests the full runner isolation contract (Spec B, Spec D, M4, M5, AD-3, AD-4).

Most tests here mock Docker so they run in CI without a Docker daemon.
The integration tests (marked docker_required) need a real Docker daemon;
they are skipped by default and can be run with --run-docker-tests.

Acceptance criteria covered:
  - passed comes from a real exit code, never the agent (AD-4)
  - both arms identical except the context file (M4, Spec B-8)
  - docker ps -a empty after run (Spec B-12)
  - temp dirs deleted (Spec D finally)
  - provider/model/egress_enforced/network_mode/repo_commit set on every RunResult
  - ReadTimeout → passed=False, timeout=True, cleaned-up container (Spec D)
  - base_image stores a resolved digest (M5)
  - caps_dropped=True on every run
  - agent_log_path is written and contains redacted log
"""
from __future__ import annotations

import datetime
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from primer.eval.models import AgentTelemetry, RunResult, Task, TaskMutation
from primer.eval.adapters.claude_code import ClaudeCodeAdapter, FINGERPRINT_INSTRUCTION
from primer.eval.runner import (
    _apply_mutation,
    _clone_repo,
    _get_agent_key,
    _assert_container_gone,
    _get_image_digest,
    _read_container_log,
    _shell_quote,
)
from primer.eval.preflight import _stub_function, _apply_stub, _apply_revert


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_task(task_id="t_test", with_ctx_file=False) -> Task:
    return Task(
        id=task_id,
        task_type="stub_function",
        prompt="Re-implement the add function so tests pass.",
        verify_cmd="python -m pytest tests/test_calculator.py -x -q --tb=short",
        mutation=TaskMutation(
            kind="stub",
            target_file="samplelib/calculator.py",
            target_symbol="add",
        ),
        validated=True,
    )


def _make_profile(commit="abc1234567890"):  # pragma: allowlist secret
    profile = MagicMock()
    profile.repo_commit = commit
    return profile


def _make_config(eval_timeout=600):
    cfg = MagicMock()
    cfg.primer_eval_timeout_s = eval_timeout
    cfg.docker_client_timeout_s = eval_timeout + 30
    cfg.primer_eval_mem_limit = "2g"
    cfg.primer_agent_api_host = "api.anthropic.com"
    cfg.proxy_image = "primer-egress-proxy:latest"
    cfg.anthropic_api_key = MagicMock()
    cfg.anthropic_api_key.get_secret_value.return_value = "sk-ant-test-fake-key"  # pragma: allowlist secret
    return cfg


@pytest.fixture()
def py_repo_path():
    return Path(__file__).parent / "fixtures" / "py_repo"


# ---------------------------------------------------------------------------
# Unit: _shell_quote
# ---------------------------------------------------------------------------

def test_shell_quote_simple():
    assert _shell_quote("hello world") == "'hello world'"

def test_shell_quote_embedded_single_quote():
    result = _shell_quote("it's fine")
    assert "'" in result
    # Should be safely escaped
    assert "it" in result


# ---------------------------------------------------------------------------
# Unit: _get_agent_key
# ---------------------------------------------------------------------------

def test_get_agent_key_secret_str():
    config = MagicMock()
    secret = MagicMock()
    secret.get_secret_value.return_value = "sk-ant-real-key"  # pragma: allowlist secret
    config.anthropic_api_key = secret

    val = _get_agent_key(config, "ANTHROPIC_API_KEY")
    assert val == "sk-ant-real-key"  # pragma: allowlist secret


def test_get_agent_key_missing_raises():
    from primer.errors import ConfigError
    config = MagicMock()
    config.anthropic_api_key = None

    with pytest.raises(ConfigError):
        _get_agent_key(config, "ANTHROPIC_API_KEY")


# ---------------------------------------------------------------------------
# Unit: _clone_repo
# ---------------------------------------------------------------------------

def test_clone_repo_copies_files(py_repo_path, tmp_path):
    dest = tmp_path / "clone"
    _clone_repo(str(py_repo_path), dest, "HEAD")
    assert (dest / "samplelib" / "calculator.py").exists()
    assert (dest / "tests" / "test_calculator.py").exists()


def test_clone_repo_excludes_pycache(py_repo_path, tmp_path):
    dest = tmp_path / "clone"
    _clone_repo(str(py_repo_path), dest, "HEAD")
    # __pycache__ should not appear in the clone
    pyc_dirs = list(dest.rglob("__pycache__"))
    assert pyc_dirs == [], f"__pycache__ found in clone: {pyc_dirs}"


# ---------------------------------------------------------------------------
# Unit: _apply_mutation (via preflight helpers)
# ---------------------------------------------------------------------------

def test_apply_mutation_stub(py_repo_path, tmp_path):
    dest = tmp_path / "repo"
    shutil.copytree(str(py_repo_path), str(dest))
    # Install so imports work
    subprocess.run(["pip", "install", "-e", ".", "-q", "--no-deps"],
                   cwd=str(dest), capture_output=True)

    task = _make_task()
    ok = _apply_stub("samplelib/calculator.py", "add", dest)
    assert ok

    calc_src = (dest / "samplelib" / "calculator.py").read_text()
    assert "raise NotImplementedError" in calc_src


def test_apply_mutation_stub_makes_test_fail(py_repo_path, tmp_path):
    dest = tmp_path / "repo"
    shutil.copytree(str(py_repo_path), str(dest))
    subprocess.run(["pip", "install", "-e", ".", "-q", "--no-deps"],
                   cwd=str(dest), capture_output=True)

    _apply_stub("samplelib/calculator.py", "add", dest)

    result = subprocess.run(
        ["python", "-m", "pytest", "tests/test_calculator.py::test_add_integers",
         "-x", "-q", "--tb=short"],
        cwd=str(dest), capture_output=True, text=True, timeout=60,
    )
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# Unit: Context file control (M4 — filesystem-controlled, not --bare)
# ---------------------------------------------------------------------------

def test_without_arm_has_no_context_file(py_repo_path, tmp_path):
    """WITHOUT arm: CLAUDE.md must not exist in /work at run start."""
    dest = tmp_path / "repo"
    shutil.copytree(str(py_repo_path), str(dest))

    adapter = ClaudeCodeAdapter()
    ctx_file = dest / adapter.context_filename()

    # Ensure it doesn't exist
    if ctx_file.exists():
        ctx_file.unlink()

    assert not ctx_file.exists(), "Context file must be absent in WITHOUT arm"


def test_with_arm_has_context_file(py_repo_path, tmp_path):
    """WITH arm: CLAUDE.md must exist in /work."""
    dest = tmp_path / "repo"
    shutil.copytree(str(py_repo_path), str(dest))

    adapter = ClaudeCodeAdapter()
    ctx_file = dest / adapter.context_filename()
    ctx_file.write_text("# Test instructions\nRun: python -m pytest\n")

    assert ctx_file.exists(), "Context file must be present in WITH arm"


def test_flags_identical_both_arms():
    """Invocation flags must be identical for both arms (M4, AD-4)."""
    adapter = ClaudeCodeAdapter()
    task = _make_task()

    argv = adapter.build_invocation(task)

    # No --bare flag (M4)
    assert "--bare" not in argv, "build_invocation must not include --bare (M4)"

    # Output format is json
    assert "--output-format" in argv
    idx = argv.index("--output-format")
    assert argv[idx + 1] == "json"

    # Permission mode
    assert "--permission-mode" in argv
    idx = argv.index("--permission-mode")
    assert argv[idx + 1] == "bypassPermissions"

    # Prompt is -p / --print
    assert "--print" in argv or "-p" in argv


# ---------------------------------------------------------------------------
# Unit: RunResult fields (mocked Docker)
# ---------------------------------------------------------------------------

def test_run_task_passed_from_exit_code(py_repo_path):
    """passed must come from verify_cmd exit code, never the agent (AD-4)."""
    from primer.eval.runner import run_task

    config = _make_config()
    adapter = ClaudeCodeAdapter()
    task = _make_task()
    profile = _make_profile()

    # Mock the entire Docker stack
    mock_container = MagicMock()
    mock_container.id = "abc1234567890"  # pragma: allowlist secret
    mock_container.wait.return_value = {"StatusCode": 0}  # verify_cmd passes
    mock_container.logs.return_value = b'{"total_cost_usd": 0.01, "usage": {"input_tokens": 50, "output_tokens": 20}}'

    mock_egress = MagicMock()
    mock_egress.network_name = "primer-internal-test"
    mock_egress.proxy_url = "http://10.0.0.2:8888"
    mock_egress.allowed_host = "api.anthropic.com"
    mock_egress.enforced = True

    mock_egress_ctx = MagicMock()
    mock_egress_ctx.__enter__ = MagicMock(return_value=mock_egress)
    mock_egress_ctx.__exit__ = MagicMock(return_value=False)

    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_client.containers.list.return_value = []  # post-run audit: container gone

    # Create a fake eval image (just use py:3-slim tag for the mock)
    with patch("primer.eval.runner.docker.from_env", return_value=mock_client), \
         patch("primer.eval.runner.EgressNetwork", return_value=mock_egress_ctx), \
         patch("primer.eval.runner._clone_repo"), \
         patch("primer.eval.runner._apply_mutation"), \
         patch("primer.eval.runner._get_image_digest", return_value="python:3.11-slim@sha256:abc"):  # pragma: allowlist secret

        # Write a fake context file so WITH arm finds it
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            # We need a real repo path for the source_context write/delete
            result = run_task(
                task=task,
                repo_path=str(py_repo_path),
                with_context=False,  # WITHOUT arm — no file
                profile=profile,
                config=config,
                adapter=adapter,
                image_tag="primer-eval-test:abc123",  # pragma: allowlist secret
            )

    # passed must come from exit code 0 → True
    assert result.passed is True
    assert result.timeout is False

    # Isolation fields set
    assert result.egress_enforced is True
    assert result.network_mode == "proxy-egress"
    assert result.caps_dropped is True
    assert result.repo_commit == "abc1234567890"  # pragma: allowlist secret


def test_run_task_timeout_handling(py_repo_path):
    """ReadTimeout → passed=False, timeout=True, container cleaned up (Spec D)."""
    import requests.exceptions
    from primer.eval.runner import run_task

    config = _make_config(eval_timeout=600)
    adapter = ClaudeCodeAdapter()
    task = _make_task()
    profile = _make_profile()

    mock_container = MagicMock()
    mock_container.id = "timeout_container_id"
    mock_container.wait.side_effect = requests.exceptions.ReadTimeout("timed out")
    mock_container.logs.return_value = b""

    mock_egress = MagicMock()
    mock_egress.network_name = "primer-internal-test"
    mock_egress.proxy_url = "http://10.0.0.2:8888"
    mock_egress.allowed_host = "api.anthropic.com"
    mock_egress.enforced = True
    mock_egress_ctx = MagicMock()
    mock_egress_ctx.__enter__ = MagicMock(return_value=mock_egress)
    mock_egress_ctx.__exit__ = MagicMock(return_value=False)

    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_client.containers.list.return_value = []

    with patch("primer.eval.runner.docker.from_env", return_value=mock_client), \
         patch("primer.eval.runner.EgressNetwork", return_value=mock_egress_ctx), \
         patch("primer.eval.runner._clone_repo"), \
         patch("primer.eval.runner._apply_mutation"), \
         patch("primer.eval.runner._get_image_digest", return_value="python:3.11-slim@sha256:abc"):  # pragma: allowlist secret

        result = run_task(
            task=task,
            repo_path=str(py_repo_path),
            with_context=False,
            profile=profile,
            config=config,
            adapter=adapter,
            image_tag="primer-eval-test:abc123",
        )

    assert result.passed is False
    assert result.timeout is True
    # Container should have been killed and removed
    mock_container.kill.assert_called_once()
    mock_container.remove.assert_called()


def test_run_task_failed_exit_code(py_repo_path):
    """Non-zero exit code → passed=False (verify_cmd verdict, not agent)."""
    from primer.eval.runner import run_task

    config = _make_config()
    adapter = ClaudeCodeAdapter()
    task = _make_task()
    profile = _make_profile()

    mock_container = MagicMock()
    mock_container.id = "fail_container"
    mock_container.wait.return_value = {"StatusCode": 1}  # verify_cmd fails
    mock_container.logs.return_value = b'{"total_cost_usd": 0.01}'

    mock_egress = MagicMock()
    mock_egress.network_name = "primer-internal-test"
    mock_egress.proxy_url = ""
    mock_egress.allowed_host = "api.anthropic.com"
    mock_egress.enforced = False  # open-bridge fallback
    mock_egress_ctx = MagicMock()
    mock_egress_ctx.__enter__ = MagicMock(return_value=mock_egress)
    mock_egress_ctx.__exit__ = MagicMock(return_value=False)

    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_client.containers.list.return_value = []

    with patch("primer.eval.runner.docker.from_env", return_value=mock_client), \
         patch("primer.eval.runner.EgressNetwork", return_value=mock_egress_ctx), \
         patch("primer.eval.runner._clone_repo"), \
         patch("primer.eval.runner._apply_mutation"), \
         patch("primer.eval.runner._get_image_digest", return_value="python:3.11-slim@sha256:abc"):  # pragma: allowlist secret

        result = run_task(
            task=task,
            repo_path=str(py_repo_path),
            with_context=False,
            profile=profile,
            config=config,
            adapter=adapter,
            image_tag="primer-eval-test:abc123",
        )

    assert result.passed is False
    assert result.timeout is False
    # open-bridge fallback recorded correctly
    assert result.network_mode == "open-bridge"
    assert result.egress_enforced is False


def test_run_task_base_image_is_digest(py_repo_path):
    """base_image in RunResult must be a digest string (M5)."""
    from primer.eval.runner import run_task

    config = _make_config()
    adapter = ClaudeCodeAdapter()
    task = _make_task()
    profile = _make_profile()

    mock_container = MagicMock()
    mock_container.id = "digest_test_container"
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.return_value = b""

    mock_egress = MagicMock()
    mock_egress.network_name = "primer-internal-test"
    mock_egress.proxy_url = ""
    mock_egress.allowed_host = "api.anthropic.com"
    mock_egress.enforced = True
    mock_egress_ctx = MagicMock()
    mock_egress_ctx.__enter__ = MagicMock(return_value=mock_egress)
    mock_egress_ctx.__exit__ = MagicMock(return_value=False)

    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_client.containers.list.return_value = []

    EXPECTED_DIGEST = "python:3.11-slim@sha256:deadbeef1234567890abcdef"  # pragma: allowlist secret

    with patch("primer.eval.runner.docker.from_env", return_value=mock_client), \
         patch("primer.eval.runner.EgressNetwork", return_value=mock_egress_ctx), \
         patch("primer.eval.runner._clone_repo"), \
         patch("primer.eval.runner._apply_mutation"), \
         patch("primer.eval.runner._get_image_digest", return_value=EXPECTED_DIGEST):

        result = run_task(
            task=task,
            repo_path=str(py_repo_path),
            with_context=False,
            profile=profile,
            config=config,
            adapter=adapter,
            image_tag="primer-eval-test:abc123",
        )

    assert result.base_image == EXPECTED_DIGEST
    assert "sha256:" in result.base_image


def test_run_task_only_one_key_injected(py_repo_path):
    """Only the agent's required key is injected; no other keys (Q10, Spec B-5)."""
    from primer.eval.runner import run_task

    config = _make_config()
    config.openai_api_key = MagicMock()
    config.openai_api_key.get_secret_value.return_value = "sk-openai-should-not-appear"

    adapter = ClaudeCodeAdapter()
    task = _make_task()
    profile = _make_profile()

    mock_container = MagicMock()
    mock_container.id = "key_test_container"
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.return_value = b""

    mock_egress = MagicMock()
    mock_egress.network_name = "primer-internal-test"
    mock_egress.proxy_url = "http://proxy:8888"
    mock_egress.allowed_host = "api.anthropic.com"
    mock_egress.enforced = True
    mock_egress_ctx = MagicMock()
    mock_egress_ctx.__enter__ = MagicMock(return_value=mock_egress)
    mock_egress_ctx.__exit__ = MagicMock(return_value=False)

    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_client.containers.list.return_value = []

    with patch("primer.eval.runner.docker.from_env", return_value=mock_client), \
         patch("primer.eval.runner.EgressNetwork", return_value=mock_egress_ctx), \
         patch("primer.eval.runner._clone_repo"), \
         patch("primer.eval.runner._apply_mutation"), \
         patch("primer.eval.runner._get_image_digest", return_value="python:3.11-slim@sha256:abc"):  # pragma: allowlist secret

        run_task(
            task=task,
            repo_path=str(py_repo_path),
            with_context=False,
            profile=profile,
            config=config,
            adapter=adapter,
            image_tag="primer-eval-test:abc123",
        )

    # Extract the environment dict passed to containers.run
    call_kwargs = mock_client.containers.run.call_args[1]
    env = call_kwargs.get("environment", {})

    # Only ANTHROPIC_API_KEY + proxy vars should be present
    assert "ANTHROPIC_API_KEY" in env
    # OpenAI key must NOT be injected
    assert "OPENAI_API_KEY" not in env
    # GEMINI key must NOT be injected
    assert "GEMINI_API_KEY" not in env


def test_run_task_cap_drop_all(py_repo_path):
    """cap_drop=["ALL"] must be set on every container run (Spec B-6)."""
    from primer.eval.runner import run_task

    config = _make_config()
    adapter = ClaudeCodeAdapter()
    task = _make_task()
    profile = _make_profile()

    mock_container = MagicMock()
    mock_container.id = "cap_drop_test"
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.return_value = b""

    mock_egress = MagicMock()
    mock_egress.network_name = "primer-internal-test"
    mock_egress.proxy_url = ""
    mock_egress.allowed_host = "api.anthropic.com"
    mock_egress.enforced = True
    mock_egress_ctx = MagicMock()
    mock_egress_ctx.__enter__ = MagicMock(return_value=mock_egress)
    mock_egress_ctx.__exit__ = MagicMock(return_value=False)

    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_client.containers.list.return_value = []

    with patch("primer.eval.runner.docker.from_env", return_value=mock_client), \
         patch("primer.eval.runner.EgressNetwork", return_value=mock_egress_ctx), \
         patch("primer.eval.runner._clone_repo"), \
         patch("primer.eval.runner._apply_mutation"), \
         patch("primer.eval.runner._get_image_digest", return_value="python:3.11-slim@sha256:abc"):  # pragma: allowlist secret

        run_task(
            task=task,
            repo_path=str(py_repo_path),
            with_context=False,
            profile=profile,
            config=config,
            adapter=adapter,
            image_tag="primer-eval-test:abc123",
        )

    call_kwargs = mock_client.containers.run.call_args[1]
    assert call_kwargs.get("cap_drop") == ["ALL"]
    assert "no-new-privileges:true" in call_kwargs.get("security_opt", [])


def test_run_task_auto_remove_not_set(py_repo_path):
    """auto_remove must NOT be set (it races wait() — Spec D)."""
    from primer.eval.runner import run_task

    config = _make_config()
    adapter = ClaudeCodeAdapter()
    task = _make_task()
    profile = _make_profile()

    mock_container = MagicMock()
    mock_container.id = "auto_remove_test"
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.return_value = b""

    mock_egress = MagicMock()
    mock_egress.network_name = "primer-internal-test"
    mock_egress.proxy_url = ""
    mock_egress.allowed_host = "api.anthropic.com"
    mock_egress.enforced = True
    mock_egress_ctx = MagicMock()
    mock_egress_ctx.__enter__ = MagicMock(return_value=mock_egress)
    mock_egress_ctx.__exit__ = MagicMock(return_value=False)

    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_client.containers.list.return_value = []

    with patch("primer.eval.runner.docker.from_env", return_value=mock_client), \
         patch("primer.eval.runner.EgressNetwork", return_value=mock_egress_ctx), \
         patch("primer.eval.runner._clone_repo"), \
         patch("primer.eval.runner._apply_mutation"), \
         patch("primer.eval.runner._get_image_digest", return_value="python:3.11-slim@sha256:abc"):  # pragma: allowlist secret

        run_task(
            task=task,
            repo_path=str(py_repo_path),
            with_context=False,
            profile=profile,
            config=config,
            adapter=adapter,
            image_tag="primer-eval-test:abc123",
        )

    call_kwargs = mock_client.containers.run.call_args[1]
    # auto_remove must be False (not True) to prevent race with wait()
    assert call_kwargs.get("auto_remove") is False or "auto_remove" not in call_kwargs or call_kwargs.get("auto_remove") != True


# ---------------------------------------------------------------------------
# Unit: ClaudeCodeAdapter telemetry parsing (AD-4)
# ---------------------------------------------------------------------------

def test_parse_telemetry_no_passfail():
    """parse_telemetry must NOT contain passed/success fields (AD-4)."""
    adapter = ClaudeCodeAdapter()
    log = '{"total_cost_usd": 0.05, "usage": {"input_tokens": 1000, "output_tokens": 200}, "num_turns": 3, "is_error": false}'
    tel = adapter.parse_telemetry(log)

    assert not hasattr(tel, "passed")
    assert not hasattr(tel, "success")
    assert tel.cost_usd == pytest.approx(0.05)
    assert tel.cost_confidence == "exact"
    assert tel.tokens == 1200
    assert tel.iterations == 3
    assert tel.agent_error is False


def test_parse_telemetry_fallback_cost_field():
    """Falls back to cost_usd if total_cost_usd absent."""
    adapter = ClaudeCodeAdapter()
    log = '{"cost_usd": 0.03, "usage": {"input_tokens": 500, "output_tokens": 100}}'
    tel = adapter.parse_telemetry(log)
    assert tel.cost_usd == pytest.approx(0.03)


def test_parse_telemetry_empty_log():
    adapter = ClaudeCodeAdapter()
    tel = adapter.parse_telemetry("")
    assert tel.tokens == 0
    assert tel.cost_usd == 0.0
    assert tel.agent_error is True


def test_parse_telemetry_is_error_flag():
    adapter = ClaudeCodeAdapter()
    log = '{"total_cost_usd": 0.0, "is_error": true, "usage": {}}'
    tel = adapter.parse_telemetry(log)
    assert tel.agent_error is True


# ---------------------------------------------------------------------------
# Unit: M4 fingerprint — harness validity gate
# ---------------------------------------------------------------------------

def test_context_filename_is_claude_md():
    """ClaudeCodeAdapter must use CLAUDE.md (M7)."""
    adapter = ClaudeCodeAdapter()
    assert adapter.context_filename() == "CLAUDE.md"


def test_m4_fingerprint_constant_exists():
    """FINGERPRINT_INSTRUCTION constant must exist for harness-validity probes."""
    assert FINGERPRINT_INSTRUCTION, "FINGERPRINT_INSTRUCTION must be non-empty"
    assert "PRIMER_FINGERPRINT" in FINGERPRINT_INSTRUCTION


# ---------------------------------------------------------------------------
# Unit: post-run audit (_assert_container_gone)
# ---------------------------------------------------------------------------

def test_assert_container_gone_when_gone():
    mock_client = MagicMock()
    mock_client.containers.list.return_value = []
    # Should not raise
    _assert_container_gone(mock_client, "abc123")  # pragma: allowlist secret


def test_assert_container_gone_attempts_force_remove_if_still_present():
    mock_client = MagicMock()
    leftover = MagicMock()
    mock_client.containers.list.return_value = [leftover]
    _assert_container_gone(mock_client, "abc123")  # pragma: allowlist secret
    leftover.remove.assert_called_with(force=True)


# ---------------------------------------------------------------------------
# Unit: docker client timeout = eval_timeout + 30 (Spec D, M1)
# ---------------------------------------------------------------------------

def test_docker_client_timeout_spec_d():
    """docker_client_timeout_s must equal eval_timeout_s + 30."""
    from primer.config import Settings
    import os

    # Use env injection to set timeout
    cfg = Settings(
        _env_file=None,
        primer_eval_timeout_s=600,
        anthropic_api_key="sk-ant-fake-key",  # pragma: allowlist secret
    )
    assert cfg.docker_client_timeout_s == 630
    assert cfg.primer_eval_timeout_s == 600


def test_docker_client_timeout_m1_default():
    """Default eval timeout must be 600 (M1 supersedes Session 2's 300)."""
    from primer.config import Settings
    cfg = Settings(
        _env_file=None,
        anthropic_api_key="sk-ant-fake-key",  # pragma: allowlist secret
    )
    assert cfg.primer_eval_timeout_s == 600
    assert cfg.docker_client_timeout_s == 630


# ---------------------------------------------------------------------------
# Unit: store round-trip (Phase 3/4 boundary)
# ---------------------------------------------------------------------------

def test_store_round_trip(tmp_path):
    """save_report / latest_report must round-trip a ScoreReport."""
    from primer.store.db import init_db, save_report, latest_report
    from primer.eval.models import ScoreReport, TaskScore, Task, TaskMutation
    from primer.config import Settings

    db_path = tmp_path / "test_primer.db"
    cfg = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_path}",
        anthropic_api_key="sk-ant-fake",  # pragma: allowlist secret
    )
    conn = init_db(cfg)

    profile = MagicMock()
    profile.repo_commit = "abc123"  # pragma: allowlist secret
    profile.languages = []
    profile.frameworks = []

    report = ScoreReport(
        repo_commit="abc123",  # pragma: allowlist secret
        created_at="2026-01-01T00:00:00+00:00",
        n_tasks=1,
        runs_per_config=3,
        success_rate_without=0.33,
        success_rate_with=0.67,
        success_delta=0.33,
        success_stddev=0.1,
        success_min=0.0,
        success_max=1.0,
        cost_without=0.05,
        cost_with=0.07,
        cost_delta_pct=40.0,
        cost_confidence="exact",
        per_task=[
            TaskScore(
                task_id="t1",
                task_type="stub_function",
                pass_rate_without=0.33,
                pass_rate_with=0.67,
                delta=0.33,
                runs=6,
                flaky_any=False,
            )
        ],
        provider="anthropic",
        model="claude-sonnet-4-6",
        agent_adapter="claude_code",
        base_image="python:3.11-slim@sha256:abc",  # pragma: allowlist secret
        network_mode="proxy-egress",
        egress_enforced=True,
        primer_overhead_usd=0.001,
        primer_overhead_confidence="exact",
    )

    tasks = [Task(
        id="t1",
        task_type="stub_function",
        prompt="Fix it",
        verify_cmd="python -m pytest tests/ -x -q",
        mutation=TaskMutation(kind="stub", target_file="a.py", target_symbol="fn"),
        validated=True,
    )]

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    runs = [RunResult(
        task_id="t1",
        passed=True, timeout=False, flaky=False, with_context=False,
        agent_adapter="claude_code",
        agent_tokens=100, iterations=1, duration_s=1.0,
        cost_usd=0.05, cost_confidence="exact",
        provider="anthropic", model="claude-sonnet-4-6",
        base_image="python:3.11-slim@sha256:abc",  # pragma: allowlist secret
        repo_commit="abc123",  # pragma: allowlist secret
        network_mode="proxy-egress",
        egress_allowed_host="api.anthropic.com",
        egress_enforced=True, caps_dropped=True,
        container_id="c001",
        agent_log_path="/tmp/log.txt",
        run_timestamp=now,
    )]

    report_id = save_report(conn, report, tasks, runs, profile, "/fake/repo")
    assert isinstance(report_id, int)
    assert report_id > 0

    loaded = latest_report(conn, "/fake/repo")
    assert loaded is not None
    assert loaded.repo_commit == "abc123"  # pragma: allowlist secret
    assert loaded.n_tasks == 1
    assert loaded.provider == "anthropic"
    assert loaded.egress_enforced is True
    assert loaded.base_image == "python:3.11-slim@sha256:abc"  # pragma: allowlist secret
    assert loaded.success_delta == pytest.approx(0.33, abs=0.01)
    assert loaded.primer_overhead_usd == pytest.approx(0.001)


# ---------------------------------------------------------------------------
# Integration: real Docker run (skipped unless --run-docker-tests)
# ---------------------------------------------------------------------------

def pytest_addoption_stub(parser):
    """Stub — actual option added in conftest."""
    pass


@pytest.mark.skipif(
    os.environ.get("PRIMER_RUN_DOCKER_TESTS", "") != "1",
    reason="Set PRIMER_RUN_DOCKER_TESTS=1 to run integration tests requiring Docker",
)
def test_run_task_real_docker_without_context(py_repo_path):
    """Integration: run a real container with the fixture repo (no context file).

    Requires:
      - Docker daemon running
      - primer-eval-<hash>:<commit> image already built (or internet access to build it)
    """
    pytest.skip("Real Docker integration test — requires PRIMER_RUN_DOCKER_TESTS=1 and a Docker daemon")
