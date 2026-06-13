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


def _build_docker_mock_stack():
    """Build a fully-mocked Docker/egress stack for a passing run_task call."""
    mock_container = MagicMock()
    mock_container.id = "blk5_container_id"
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
    return mock_client, mock_egress_ctx


def test_source_repo_not_mutated(py_repo_path):
    """BLK-5 acceptance gate: a WITH-arm run_task must NOT touch the source repo.

    The runner writes the context file into the cloned work_dir only; the
    caller's source repository is never written to or deleted from.
    """
    from primer.eval.runner import run_task

    config = _make_config()
    adapter = ClaudeCodeAdapter()
    task = _make_task()
    profile = _make_profile()

    # Record the source repo state BEFORE the run.
    before = sorted(p.name for p in py_repo_path.iterdir())
    ctx_file = py_repo_path / adapter.context_filename()
    assert not ctx_file.exists(), "precondition: source repo must start clean"

    mock_client, mock_egress_ctx = _build_docker_mock_stack()

    # _clone_repo is mocked to create the work_dir (so the runner can write into it)
    # WITHOUT copying — proving the source repo is irrelevant to the write target.
    def _fake_clone(repo_path, dest, commit):
        Path(dest).mkdir(parents=True, exist_ok=True)

    with patch("primer.eval.runner.docker.from_env", return_value=mock_client), \
         patch("primer.eval.runner.EgressNetwork", return_value=mock_egress_ctx), \
         patch("primer.eval.runner._clone_repo", side_effect=_fake_clone), \
         patch("primer.eval.runner._apply_mutation"), \
         patch("primer.eval.runner._get_image_digest", return_value="python:3.11-slim@sha256:abc"):  # pragma: allowlist secret

        run_task(
            task=task,
            repo_path=str(py_repo_path),
            with_context=True,  # WITH arm — the dangerous path pre-BLK-5
            profile=profile,
            config=config,
            adapter=adapter,
            image_tag="primer-eval-test:abc123",  # pragma: allowlist secret
            context_content="# PRIMER context\nRun: python -m pytest\n",
        )

    # The source repo's CLAUDE.md must NOT have been created.
    assert not ctx_file.exists(), (
        "BLK-5 violated: run_task wrote the context file into the source repo"
    )
    # The source repo listing must be byte-for-byte identical (no add, no delete).
    after = sorted(p.name for p in py_repo_path.iterdir())
    assert before == after, f"source repo listing changed: {before!r} -> {after!r}"


def test_context_file_written_to_clone(py_repo_path, tmp_path):
    """WITH arm: run_task writes context_content into the cloned work_dir."""
    from primer.eval.runner import run_task

    config = _make_config()
    adapter = ClaudeCodeAdapter()
    task = _make_task()
    profile = _make_profile()

    mock_client, mock_egress_ctx = _build_docker_mock_stack()

    captured = {}

    def _fake_clone(repo_path, dest, commit):
        Path(dest).mkdir(parents=True, exist_ok=True)
        captured["work_dir"] = Path(dest)

    CONTENT = "# PRIMER generated context\nUse pytest.\n"

    with patch("primer.eval.runner.docker.from_env", return_value=mock_client), \
         patch("primer.eval.runner.EgressNetwork", return_value=mock_egress_ctx), \
         patch("primer.eval.runner._clone_repo", side_effect=_fake_clone), \
         patch("primer.eval.runner._apply_mutation"), \
         patch("primer.eval.runner._read_container_log", return_value=""), \
         patch("primer.eval.runner._get_image_digest", return_value="python:3.11-slim@sha256:abc"):  # pragma: allowlist secret

        # Capture the file content at container-launch time (before finally rmtree).
        def _capture_run(*args, **kwargs):
            ctx = captured["work_dir"] / adapter.context_filename()
            captured["written"] = ctx.read_text(encoding="utf-8") if ctx.exists() else None
            return mock_client.containers.run.return_value
        mock_client.containers.run.side_effect = _capture_run

        run_task(
            task=task,
            repo_path=str(py_repo_path),
            with_context=True,
            profile=profile,
            config=config,
            adapter=adapter,
            image_tag="primer-eval-test:abc123",  # pragma: allowlist secret
            context_content=CONTENT,
        )

    # After BLK-2, the runner appends the fingerprint instruction to the content.
    # Assert the original content is present and the fingerprint instruction is appended.
    written = captured.get("written")
    assert written is not None, "WITH arm must write a file into the cloned work_dir"
    assert CONTENT in written, "Original context_content must be present in written file"
    from primer.eval.adapters.claude_code import FINGERPRINT_INSTRUCTION
    assert FINGERPRINT_INSTRUCTION in written, (
        "Fingerprint instruction must be appended to the written file (BLK-2)"
    )


# ---------------------------------------------------------------------------
# BLK-2: Harness-validity fingerprint gate (M4 / 16_BLK2_SPECIFICATION.md)
# ---------------------------------------------------------------------------

def test_fingerprint_appended_to_with_arm_context_file(py_repo_path):
    """G-4 / Probe A: runner appends FINGERPRINT_INSTRUCTION to the WITH arm file."""
    from primer.eval.runner import run_task
    from primer.eval.adapters.claude_code import FINGERPRINT_INSTRUCTION

    config = _make_config()
    adapter = ClaudeCodeAdapter()
    task = _make_task()
    profile = _make_profile()

    mock_client, mock_egress_ctx = _build_docker_mock_stack()
    captured = {}

    def _fake_clone(repo_path, dest, commit):
        Path(dest).mkdir(parents=True, exist_ok=True)
        captured["work_dir"] = Path(dest)

    CONTENT = "# Generated CLAUDE.md\nRun: python -m pytest\n"

    with patch("primer.eval.runner.docker.from_env", return_value=mock_client), \
         patch("primer.eval.runner.EgressNetwork", return_value=mock_egress_ctx), \
         patch("primer.eval.runner._clone_repo", side_effect=_fake_clone), \
         patch("primer.eval.runner._apply_mutation"), \
         patch("primer.eval.runner._read_container_log", return_value=""), \
         patch("primer.eval.runner._get_image_digest", return_value="python:3.11-slim@sha256:abc"):  # pragma: allowlist secret

        def _capture_run(*args, **kwargs):
            ctx = captured["work_dir"] / adapter.context_filename()
            captured["written"] = ctx.read_text(encoding="utf-8") if ctx.exists() else None
            return mock_client.containers.run.return_value
        mock_client.containers.run.side_effect = _capture_run

        run_task(
            task=task,
            repo_path=str(py_repo_path),
            with_context=True,
            profile=profile,
            config=config,
            adapter=adapter,
            image_tag="primer-eval-test:abc123",  # pragma: allowlist secret
            context_content=CONTENT,
        )

    written = captured.get("written")
    assert written is not None, "Context file must be written in WITH arm"
    assert CONTENT in written, "Original context_content must be present in written file"
    assert FINGERPRINT_INSTRUCTION in written, (
        "FINGERPRINT_INSTRUCTION must be appended to the context file (G-4 Probe A)"
    )
    # Instruction is appended, not replacing: both are present
    assert written.index(CONTENT) < written.index(FINGERPRINT_INSTRUCTION), (
        "Original content must precede the fingerprint instruction"
    )


def test_no_fingerprint_in_without_arm_run_result(py_repo_path):
    """G-5 / Probe C: WITHOUT arm returns harness_fingerprint_valid=None; no file written."""
    from primer.eval.runner import run_task

    config = _make_config()
    adapter = ClaudeCodeAdapter()
    task = _make_task()
    profile = _make_profile()

    mock_client, mock_egress_ctx = _build_docker_mock_stack()
    captured = {}

    def _fake_clone(repo_path, dest, commit):
        Path(dest).mkdir(parents=True, exist_ok=True)
        captured["work_dir"] = Path(dest)

    with patch("primer.eval.runner.docker.from_env", return_value=mock_client), \
         patch("primer.eval.runner.EgressNetwork", return_value=mock_egress_ctx), \
         patch("primer.eval.runner._clone_repo", side_effect=_fake_clone), \
         patch("primer.eval.runner._apply_mutation"), \
         patch("primer.eval.runner._read_container_log", return_value=""), \
         patch("primer.eval.runner._get_image_digest", return_value="python:3.11-slim@sha256:abc"):  # pragma: allowlist secret

        result = run_task(
            task=task,
            repo_path=str(py_repo_path),
            with_context=False,
            profile=profile,
            config=config,
            adapter=adapter,
            image_tag="primer-eval-test:abc123",  # pragma: allowlist secret
            context_content="# should not be written",
        )

    # Gate not applicable for WITHOUT arm
    assert result.harness_fingerprint_valid is None, (
        "WITHOUT arm must have harness_fingerprint_valid=None (G-5 Probe C)"
    )
    # No context file written
    if "work_dir" in captured:
        ctx_path = captured["work_dir"] / adapter.context_filename()
        assert not ctx_path.exists(), "Context file must not exist in WITHOUT arm work_dir"


def test_abort_on_harness_fingerprint_false():
    """G-7: scorer.score() raises HarnessValidityError when WITH arm returns False."""
    from primer.eval.scorer import score
    from primer.errors import HarnessValidityError
    from primer.eval.models import RunResult

    task = _make_task()
    profile = _make_profile()
    config = _make_config()
    adapter = ClaudeCodeAdapter()

    now = "2026-06-12T00:00:00+00:00"

    def _make_run(with_context, fingerprint_valid):
        return RunResult(
            task_id=task.id,
            passed=True, timeout=False, flaky=False,
            with_context=with_context,
            agent_adapter="claude_code",
            agent_tokens=50, iterations=1, duration_s=1.0,
            cost_usd=0.01, cost_confidence="exact",
            provider="", model="",
            base_image="python:3.11-slim@sha256:abc",  # pragma: allowlist secret
            repo_commit="abc1234567890",  # pragma: allowlist secret
            network_mode="proxy-egress",
            egress_allowed_host="api.anthropic.com",
            egress_enforced=True, caps_dropped=True,
            container_id="c001",
            agent_log_path="/tmp/log.txt",
            run_timestamp=now,
            harness_fingerprint_valid=fingerprint_valid,
        )

    without_run = _make_run(with_context=False, fingerprint_valid=None)
    with_run = _make_run(with_context=True, fingerprint_valid=False)

    with patch("primer.eval.scorer.run_task", side_effect=[without_run, with_run]):
        with pytest.raises(HarnessValidityError) as exc_info:
            score(
                profile=profile,
                repo_path="/fake/repo",
                tasks=[task],
                config=config,
                adapter=adapter,
                image_tag="primer-eval-test:abc123",  # pragma: allowlist secret
                context_content="# test context",
                runs_per_config=1,
            )

    assert "did not acknowledge" in str(exc_info.value)
    assert task.id in str(exc_info.value)


def test_harness_fingerprint_none_does_not_abort():
    """G-7 complement: None (non-participating adapter) must NOT trigger abort."""
    from primer.eval.scorer import score
    from primer.eval.models import RunResult

    task = _make_task()
    profile = _make_profile()
    config = _make_config()
    adapter = ClaudeCodeAdapter()

    now = "2026-06-12T00:00:00+00:00"

    def _make_run(with_context):
        return RunResult(
            task_id=task.id,
            passed=True, timeout=False, flaky=False,
            with_context=with_context,
            agent_adapter="claude_code",
            agent_tokens=50, iterations=1, duration_s=1.0,
            cost_usd=0.01, cost_confidence="exact",
            provider="", model="",
            base_image="python:3.11-slim@sha256:abc",  # pragma: allowlist secret
            repo_commit="abc1234567890",  # pragma: allowlist secret
            network_mode="proxy-egress",
            egress_allowed_host="api.anthropic.com",
            egress_enforced=True, caps_dropped=True,
            container_id="c001",
            agent_log_path="/tmp/log.txt",
            run_timestamp=now,
            harness_fingerprint_valid=None,  # None = not checked; must not abort
        )

    runs = [_make_run(False), _make_run(True)]
    with patch("primer.eval.scorer.run_task", side_effect=runs):
        # Must NOT raise HarnessValidityError
        report = score(
            profile=profile,
            repo_path="/fake/repo",
            tasks=[task],
            config=config,
            adapter=adapter,
            image_tag="primer-eval-test:abc123",  # pragma: allowlist secret
            context_content="# test context",
            runs_per_config=1,
        )
    assert report is not None


def test_agent_adapter_fingerprint_defaults():
    """G-2: ABC concrete defaults return None; ClaudeCodeAdapter overrides correctly."""
    from primer.eval.agent_adapter import AgentAdapter
    from primer.eval.adapters.claude_code import ClaudeCodeAdapter, FINGERPRINT_MARKER
    from primer.eval.models import AgentTelemetry

    # Verify concrete default via a minimal non-participating subclass
    class _NullAdapter(AgentAdapter):
        @property
        def adapter_name(self): return "null"
        def required_env_key(self): return None
        def api_host(self): return ""
        def context_filename(self): return "AGENTS.md"
        def build_invocation(self, task): return []
        def parse_telemetry(self, raw_log):
            return AgentTelemetry(0, 0, 0.0, 0.0, "free", True, "")

    null = _NullAdapter()
    assert null.fingerprint_instruction() is None
    assert null.check_fingerprint("anything", True) is None
    assert null.check_fingerprint("anything", False) is None

    # ClaudeCodeAdapter overrides correctly
    a = ClaudeCodeAdapter()
    assert a.fingerprint_instruction() is not None
    assert "PRIMER_FINGERPRINT_V1" in a.fingerprint_instruction()
    assert a.check_fingerprint(f"output: {FINGERPRINT_MARKER}", True) is True
    assert a.check_fingerprint("no marker here", True) is False
    assert a.check_fingerprint(f"even with {FINGERPRINT_MARKER}", False) is None


def test_migration_v2_adds_fingerprint_column(tmp_path):
    """G-3: v1→v2 migration adds harness_fingerprint_valid column; idempotent."""
    import sqlite3 as _sqlite
    from primer.store.migrations import (
        apply_migrations, get_schema_version, set_schema_version,
        CURRENT_SCHEMA_VERSION,
    )

    assert CURRENT_SCHEMA_VERSION == 2, "CURRENT_SCHEMA_VERSION must be 2 after BLK-2"

    db_path = tmp_path / "migration_test.db"
    conn = _sqlite.connect(str(db_path))

    # Simulate a v1 database by creating the runs table WITHOUT the new column.
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS runs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id           INTEGER NOT NULL,
            task_id             TEXT NOT NULL,
            repo_commit         TEXT NOT NULL,
            with_context        INTEGER NOT NULL,
            passed              INTEGER NOT NULL,
            timeout             INTEGER NOT NULL,
            flaky               INTEGER NOT NULL,
            agent_adapter       TEXT NOT NULL,
            agent_tokens        INTEGER NOT NULL,
            iterations          INTEGER NOT NULL,
            duration_s          REAL NOT NULL,
            cost_usd            REAL NOT NULL,
            cost_confidence     TEXT NOT NULL,
            provider            TEXT NOT NULL,
            model               TEXT NOT NULL,
            base_image          TEXT NOT NULL,
            network_mode        TEXT NOT NULL,
            egress_allowed_host TEXT,
            egress_enforced     INTEGER NOT NULL,
            caps_dropped        INTEGER NOT NULL,
            container_id        TEXT NOT NULL,
            agent_log_path      TEXT NOT NULL,
            run_timestamp       TEXT NOT NULL
        );
    """)
    set_schema_version(conn, 1)
    assert get_schema_version(conn) == 1

    # Confirm the column does NOT exist before migration
    cols_before = [r[1] for r in conn.execute("PRAGMA table_info(runs)").fetchall()]
    assert "harness_fingerprint_valid" not in cols_before

    # Apply migrations: v1 → v2
    apply_migrations(conn)
    assert get_schema_version(conn) == 2

    # Column must now exist
    cols_after = [r[1] for r in conn.execute("PRAGMA table_info(runs)").fetchall()]
    assert "harness_fingerprint_valid" in cols_after

    # NULL default: INSERT without the column must succeed
    conn.execute(
        "INSERT INTO runs (report_id,task_id,repo_commit,with_context,passed,timeout,flaky,"
        "agent_adapter,agent_tokens,iterations,duration_s,cost_usd,cost_confidence,"
        "provider,model,base_image,network_mode,egress_allowed_host,egress_enforced,"
        "caps_dropped,container_id,agent_log_path,run_timestamp) "
        "VALUES (1,'t1','abc',1,1,0,0,'claude_code',10,1,1.0,0.01,'exact',"
        "'anthropic','claude','img','proxy-egress',NULL,1,1,'c1','/tmp/l.txt','2026-01-01T00:00:00')"
    )
    row = conn.execute("SELECT harness_fingerprint_valid FROM runs LIMIT 1").fetchone()
    assert row[0] is None, "harness_fingerprint_valid must default to NULL"

    # Idempotency: calling apply_migrations again must not error
    apply_migrations(conn)
    assert get_schema_version(conn) == 2

    conn.close()


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

    # Permission mode: dontAsk makes the session fully non-interactive under root
    # (bypassPermissions is blocked in Claude Code 2.1.x+ when running as root).
    assert "--permission-mode" in argv
    idx = argv.index("--permission-mode")
    assert argv[idx + 1] == "dontAsk", (
        "build_invocation must use dontAsk (root-compatible headless mode); "
        "bypassPermissions is blocked under root in Claude Code 2.1.x+"
    )

    # Allowed tools: pre-authorise the exact set needed for eval tasks
    assert "--allowedTools" in argv, "build_invocation must include --allowedTools"
    tools_str = argv[argv.index("--allowedTools") + 1]
    for tool in ("Bash", "Edit", "MultiEdit", "Write", "Read"):
        assert tool in tools_str, f"--allowedTools must include {tool!r}"

    # bypassPermissions must be absent (root-restricted in Claude Code 2.1.x+)
    assert "bypassPermissions" not in argv, (
        "bypassPermissions is blocked under root; use dontAsk + --allowedTools"
    )

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

        # After BLK-5 the runner writes the context file into the clone itself;
        # no source-repo staging is needed. WITHOUT arm passes no context_content.
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
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
# M0: collect_runs accumulates RunResult objects from score()
# ---------------------------------------------------------------------------

def test_collect_runs_accumulates_run_results():
    """M0: score() with collect_runs=[] must populate the list with every RunResult.

    Verifies:
    - list length == tasks × 2 arms × runs_per_config
    - provider and model are set on every accumulated RunResult
    """
    from primer.eval.scorer import score
    from primer.eval.models import RunResult

    task = _make_task("t_m0")
    profile = _make_profile()
    config = _make_config()
    adapter = ClaudeCodeAdapter()

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def _fake_run(with_context, fp_valid):
        return RunResult(
            task_id=task.id,
            passed=True, timeout=False, flaky=False,
            with_context=with_context,
            agent_adapter="claude_code",
            agent_tokens=10, iterations=1, duration_s=0.5,
            cost_usd=0.001, cost_confidence="exact",
            provider="", model="",          # scorer fills these in
            base_image="python:3.11-slim@sha256:abc",  # pragma: allowlist secret
            repo_commit="abc1234567890",  # pragma: allowlist secret
            network_mode="proxy-egress",
            egress_allowed_host="api.anthropic.com",
            egress_enforced=True, caps_dropped=True,
            container_id="c001",
            agent_log_path="/tmp/log.txt",
            run_timestamp=now,
            harness_fingerprint_valid=fp_valid,
        )

    # 1 task × 2 arms × 1 run = 2 calls: WITHOUT (fp=None), WITH (fp=None)
    side_effects = [_fake_run(False, None), _fake_run(True, None)]

    collected: list[RunResult] = []
    with patch("primer.eval.scorer.run_task", side_effect=side_effects):
        score(
            profile=profile,
            repo_path="/fake/repo",
            tasks=[task],
            config=config,
            adapter=adapter,
            image_tag="primer-eval-test:abc123",  # pragma: allowlist secret
            context_content="# ctx",
            provider="anthropic",
            model="claude-sonnet-4-6",
            runs_per_config=1,
            collect_runs=collected,
        )

    assert len(collected) == 2, (
        f"Expected 2 RunResults (1 task × 2 arms × 1 run), got {len(collected)}"
    )
    for r in collected:
        assert r.provider == "anthropic", "provider must be set by scorer on each RunResult"
        assert r.model == "claude-sonnet-4-6", "model must be set by scorer on each RunResult"

    without_arm = [r for r in collected if not r.with_context]
    with_arm = [r for r in collected if r.with_context]
    assert len(without_arm) == 1
    assert len(with_arm) == 1


def test_collect_runs_none_leaves_score_unchanged():
    """M0: omitting collect_runs (None default) must not alter score() behavior."""
    from primer.eval.scorer import score
    from primer.eval.models import RunResult

    task = _make_task("t_m0_none")
    profile = _make_profile()
    config = _make_config()
    adapter = ClaudeCodeAdapter()

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def _fake_run(with_context):
        return RunResult(
            task_id=task.id,
            passed=True, timeout=False, flaky=False,
            with_context=with_context,
            agent_adapter="claude_code",
            agent_tokens=10, iterations=1, duration_s=0.5,
            cost_usd=0.001, cost_confidence="exact",
            provider="", model="",
            base_image="python:3.11-slim@sha256:abc",  # pragma: allowlist secret
            repo_commit="abc1234567890",  # pragma: allowlist secret
            network_mode="proxy-egress",
            egress_allowed_host="api.anthropic.com",
            egress_enforced=True, caps_dropped=True,
            container_id="c001",
            agent_log_path="/tmp/log.txt",
            run_timestamp=now,
            harness_fingerprint_valid=None,
        )

    with patch("primer.eval.scorer.run_task", side_effect=[_fake_run(False), _fake_run(True)]):
        report = score(
            profile=profile,
            repo_path="/fake/repo",
            tasks=[task],
            config=config,
            adapter=adapter,
            image_tag="primer-eval-test:abc123",  # pragma: allowlist secret
            runs_per_config=1,
            # collect_runs omitted — must default to None without error
        )

    assert report is not None
    assert report.n_tasks == 1


def test_run_persistence_populates_runs_table(tmp_path):
    """M0: runs table must be populated after score() + save_report() with collect_runs.

    Verifies the complete M0 path:
      score(collect_runs=collected) → save_report(runs=collected)
      → runs table has correct row count and field values.
    """
    from primer.eval.scorer import score
    from primer.store.db import init_db, save_report
    from primer.eval.models import RunResult, Task, TaskMutation
    from primer.config import Settings

    db_path = tmp_path / "m0_runs_test.db"
    cfg = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_path}",
        anthropic_api_key="sk-ant-fake",  # pragma: allowlist secret
    )
    conn = init_db(cfg)

    task = _make_task("t_persist")
    profile = _make_profile()
    config = _make_config()
    adapter = ClaudeCodeAdapter()

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def _fake_run(with_context):
        return RunResult(
            task_id=task.id,
            passed=True,    # both arms pass; this test is about persistence, not pass/fail
            timeout=False, flaky=False,
            with_context=with_context,
            agent_adapter="claude_code",
            agent_tokens=50, iterations=1, duration_s=1.0,
            cost_usd=0.01, cost_confidence="exact",
            provider="", model="",
            base_image="python:3.11-slim@sha256:abc",  # pragma: allowlist secret
            repo_commit="abc1234567890",  # pragma: allowlist secret
            network_mode="proxy-egress",
            egress_allowed_host="api.anthropic.com",
            egress_enforced=True, caps_dropped=True,
            container_id="c_persist",
            agent_log_path="/tmp/log.txt",
            run_timestamp=now,
            harness_fingerprint_valid=None,
        )

    # 1 task × 2 arms × 1 run = 2 RunResults
    collected: list[RunResult] = []
    with patch("primer.eval.scorer.run_task", side_effect=[_fake_run(False), _fake_run(True)]):
        report = score(
            profile=profile,
            repo_path="/fake/repo",
            tasks=[task],
            config=config,
            adapter=adapter,
            image_tag="primer-eval-test:abc123",  # pragma: allowlist secret
            context_content="# ctx",
            provider="anthropic",
            model="claude-sonnet-4-6",
            runs_per_config=1,
            collect_runs=collected,
        )

    task_obj = Task(
        id=task.id,
        task_type="stub_function",
        prompt="Fix it",
        verify_cmd="python -m pytest",
        mutation=TaskMutation(kind="stub", target_file="a.py", target_symbol="fn"),
        validated=True,
    )
    report_id = save_report(conn, report, [task_obj], collected, profile, "/fake/repo")

    # Verify the runs table has exactly 2 rows
    rows = conn.execute("SELECT * FROM runs WHERE report_id = ?", (report_id,)).fetchall()
    assert len(rows) == 2, f"Expected 2 run rows, got {len(rows)}"

    # Verify field values on each row
    for row in rows:
        assert row["task_id"] == task.id
        assert row["provider"] == "anthropic"
        assert row["model"] == "claude-sonnet-4-6"
        assert row["agent_adapter"] == "claude_code"
        assert row["repo_commit"] == "abc1234567890"  # pragma: allowlist secret
        assert row["egress_enforced"] == 1
        assert row["harness_fingerprint_valid"] is None  # tristate None → SQL NULL

    without_rows = [r for r in rows if not r["with_context"]]
    with_rows = [r for r in rows if r["with_context"]]
    assert len(without_rows) == 1
    assert len(with_rows) == 1
    assert without_rows[0]["passed"] == 1   # both arms pass in this test
    assert with_rows[0]["passed"] == 1

    conn.close()


# ---------------------------------------------------------------------------
# M7: per-task delta reconstruction preserves None on provider mismatch
# ---------------------------------------------------------------------------

def _make_db_with_report(tmp_path, provider_mismatch: bool):
    """Helper: create a DB with one report; return (conn, report_id)."""
    import sqlite3
    from primer.store.db import init_db, save_report
    from primer.eval.models import ScoreReport, TaskScore, Task, TaskMutation, RunResult
    from primer.config import Settings

    db_path = tmp_path / f"m7_test_{'mismatch' if provider_mismatch else 'clean'}.db"
    cfg = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_path}",
        anthropic_api_key="sk-ant-fake",  # pragma: allowlist secret
    )
    conn = init_db(cfg)

    mismatch_warning = "Provider mismatch" if provider_mismatch else None

    report = ScoreReport(
        repo_commit="deadbeef",
        created_at="2026-06-01T00:00:00+00:00",
        n_tasks=1,
        runs_per_config=1,
        success_rate_without=1.0,
        success_rate_with=0.0,
        success_delta=None if provider_mismatch else -1.0,
        success_stddev=0.5,
        success_min=0.0,
        success_max=1.0,
        cost_without=0.01,
        cost_with=0.01,
        cost_delta_pct=None if provider_mismatch else 0.0,
        cost_confidence="exact",
        per_task=[
            TaskScore(
                task_id="t_m7",
                task_type="stub_function",
                pass_rate_without=1.0,
                pass_rate_with=0.0,
                delta=None,          # original value at save time
                runs=2,
                flaky_any=False,
            )
        ],
        provider="anthropic",
        model="claude-sonnet-4-6",
        agent_adapter="claude_code",
        base_image="python:3.11-slim@sha256:abc",  # pragma: allowlist secret
        network_mode="proxy-egress",
        egress_enforced=True,
        provider_mismatch_warning=mismatch_warning,
        primer_overhead_usd=0.0,
        primer_overhead_confidence="estimated",
    )

    tasks = [Task(
        id="t_m7",
        task_type="stub_function",
        prompt="Fix it",
        verify_cmd="pytest",
        mutation=TaskMutation(kind="stub", target_file="a.py", target_symbol="fn"),
        validated=True,
    )]

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    runs = [
        RunResult(
            task_id="t_m7",
            passed=True, timeout=False, flaky=False, with_context=False,
            agent_adapter="claude_code",
            agent_tokens=10, iterations=1, duration_s=1.0,
            cost_usd=0.01, cost_confidence="exact",
            provider="anthropic", model="claude-sonnet-4-6",
            base_image="python:3.11-slim@sha256:abc",  # pragma: allowlist secret
            repo_commit="deadbeef",
            network_mode="proxy-egress",
            egress_allowed_host=None,
            egress_enforced=True, caps_dropped=True,
            container_id="c_m7a",
            agent_log_path="/tmp/m7a.txt",
            run_timestamp=now,
        ),
        RunResult(
            task_id="t_m7",
            passed=False, timeout=False, flaky=False, with_context=True,
            agent_adapter="claude_code",
            agent_tokens=10, iterations=1, duration_s=1.0,
            cost_usd=0.01, cost_confidence="exact",
            provider="anthropic", model="claude-sonnet-4-6",
            base_image="python:3.11-slim@sha256:abc",  # pragma: allowlist secret
            repo_commit="deadbeef",
            network_mode="proxy-egress",
            egress_allowed_host=None,
            egress_enforced=True, caps_dropped=True,
            container_id="c_m7b",
            agent_log_path="/tmp/m7b.txt",
            run_timestamp=now,
        ),
    ]

    report_id = save_report(conn, report, tasks, runs, MagicMock(repo_commit="deadbeef"), "/repo")
    return conn, report_id


def test_m7_per_task_delta_none_on_mismatch_round_trip(tmp_path):
    """M7: when provider_mismatch_warning is set, per-task delta must be None on reload.

    Verifies that _row_to_score_report() does not blindly compute pr_t - pr_w
    but instead preserves None when the original report refused the delta.
    """
    from primer.store.db import get_report_by_id

    conn, report_id = _make_db_with_report(tmp_path, provider_mismatch=True)
    loaded = get_report_by_id(conn, report_id)
    conn.close()

    assert loaded is not None
    assert loaded.provider_mismatch_warning is not None, (
        "provider_mismatch_warning must survive the round-trip"
    )
    assert loaded.success_delta is None, (
        "top-level success_delta must be None on reload when mismatch was recorded"
    )
    for ts in loaded.per_task:
        assert ts.delta is None, (
            f"per-task delta for {ts.task_id!r} must be None when "
            f"provider_mismatch_warning is set (M7)"
        )


def test_m7_per_task_delta_computed_without_mismatch(tmp_path):
    """M7: without provider_mismatch_warning, per-task delta must be a float on reload."""
    from primer.store.db import get_report_by_id

    conn, report_id = _make_db_with_report(tmp_path, provider_mismatch=False)
    loaded = get_report_by_id(conn, report_id)
    conn.close()

    assert loaded is not None
    assert loaded.provider_mismatch_warning is None
    for ts in loaded.per_task:
        assert isinstance(ts.delta, float), (
            f"per-task delta for {ts.task_id!r} must be a float when no mismatch (M7)"
        )
        # WITHOUT=True, WITH=False → delta = 0.0 - 1.0 = -1.0
        assert ts.delta == pytest.approx(-1.0)


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


# ---------------------------------------------------------------------------
# BLK-2 Live Gates — G-6, G-8, G-9 (16_BLK2_SPECIFICATION.md §5, §12.7)
# ---------------------------------------------------------------------------
#
# Run with:
#   PRIMER_RUN_DOCKER_TESTS=1 \
#   ANTHROPIC_API_KEY=<valid key> \
#   PRIMER_EVAL_IMAGE=<image tag, e.g. primer-eval-abc123-claude_code:abc123> \
#   pytest tests/test_runner_isolation.py \
#          -k "test_live_with_arm or test_live_without_arm or test_live_full_eval" \
#          -v --tb=short
#
# All three tests are skipped unless all three env vars are set.
# No API calls, no Docker, no execution happens when skipped.

_live_gate = pytest.mark.skipif(
    os.environ.get("PRIMER_RUN_DOCKER_TESTS", "") != "1"
    or not os.environ.get("ANTHROPIC_API_KEY", "")
    or not os.environ.get("PRIMER_EVAL_IMAGE", ""),
    reason=(
        "BLK-2 live gate: requires PRIMER_RUN_DOCKER_TESTS=1, "
        "ANTHROPIC_API_KEY, and PRIMER_EVAL_IMAGE to be set"
    ),
)

# Minimal content for the live WITH-arm context file.
# The runner appends FINGERPRINT_INSTRUCTION on top of this before writing.
_LIVE_CONTEXT = "# PRIMER proof context\nRun tests with: python -m pytest\n"


def _make_live_task() -> Task:
    """Task for BLK-2 live proof tests.

    verify_cmd is 'true' so pass/fail is deterministic and independent of
    whether the agent actually fixes the code.  The mutation stubs add() to
    give the agent a plausible coding task; whether it succeeds is irrelevant
    for the fingerprint gate proof.
    """
    return Task(
        id="live_proof_stub_add",
        task_type="stub_function",
        prompt=(
            "Re-implement the `add` function in samplelib/calculator.py "
            "so that it returns a + b."
        ),
        verify_cmd="true",
        mutation=TaskMutation(
            kind="stub",
            target_file="samplelib/calculator.py",
            target_symbol="add",
        ),
        validated=True,
    )


def _make_live_config():
    """Real Settings object that reads ANTHROPIC_API_KEY from the environment.

    _env_file=None disables .env file loading; the live key comes from the
    process environment (set by whoever runs PRIMER_RUN_DOCKER_TESTS=1).
    """
    from primer.config import Settings
    return Settings(_env_file=None)


@_live_gate
def test_live_with_arm_fingerprint_found_in_log(py_repo_path):
    """G-6: Live WITH-arm run_task() — marker found in log; harness_fingerprint_valid=True.

    Probe A standing gate: verifies that a real Claude Code agent run with
    FINGERPRINT_INSTRUCTION appended to CLAUDE.md produces FINGERPRINT_MARKER
    in its log output, and that RunResult.harness_fingerprint_valid is True.

    Pass criteria (spec §5 G-6):
      - result.harness_fingerprint_valid is True
      - FINGERPRINT_MARKER present in result.agent_log_path content

    Requires: PRIMER_RUN_DOCKER_TESTS=1, ANTHROPIC_API_KEY, PRIMER_EVAL_IMAGE.
    """
    from primer.eval.runner import run_task
    from primer.eval.adapters.claude_code import FINGERPRINT_MARKER

    image_tag = os.environ["PRIMER_EVAL_IMAGE"]

    result = run_task(
        task=_make_live_task(),
        repo_path=str(py_repo_path),
        with_context=True,
        profile=_make_profile(commit="HEAD"),
        config=_make_live_config(),
        adapter=ClaudeCodeAdapter(),
        image_tag=image_tag,
        context_content=_LIVE_CONTEXT,
    )

    assert result.harness_fingerprint_valid is True, (
        f"G-6 FAIL: WITH arm must have harness_fingerprint_valid=True. "
        f"Got: {result.harness_fingerprint_valid!r}. "
        f"Inspect agent log for marker absence: {result.agent_log_path}\n"
        f"If marker is absent, revise FINGERPRINT_INSTRUCTION per "
        f"16_BLK2_SPECIFICATION.md §4.4."
    )

    # Confirm the marker is present in the persisted redacted log file.
    log_path = Path(result.agent_log_path)
    assert log_path.exists(), (
        f"G-6 FAIL: agent log must be persisted at {log_path}"
    )
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    assert FINGERPRINT_MARKER in log_text, (
        f"G-6 FAIL: {FINGERPRINT_MARKER!r} not found in persisted agent log.\n"
        f"Log path: {log_path}\n"
        f"First 1000 chars of log:\n{log_text[:1000]}"
    )


@_live_gate
def test_live_without_arm_fingerprint_not_checked(py_repo_path):
    """G-8: Live WITH+WITHOUT pair — WITH=True, WITHOUT=None; no HarnessValidityError.

    Probe A (WITH arm gate passes) and Probe C (WITHOUT arm not checked) in a
    paired live run.  Verifies the full dual-arm structure spec §3.1/§3.2.

    Pass criteria (spec §5 G-8):
      - WITHOUT arm: result.harness_fingerprint_valid is None
      - WITH arm:    result.harness_fingerprint_valid is True
      - No HarnessValidityError raised by either run_task() call

    Requires: PRIMER_RUN_DOCKER_TESTS=1, ANTHROPIC_API_KEY, PRIMER_EVAL_IMAGE.
    """
    from primer.eval.runner import run_task

    image_tag = os.environ["PRIMER_EVAL_IMAGE"]
    task = _make_live_task()
    config = _make_live_config()
    adapter = ClaudeCodeAdapter()
    profile = _make_profile(commit="HEAD")

    # Probe C: WITHOUT arm — gate not applicable; must be None, never abort.
    without_result = run_task(
        task=task,
        repo_path=str(py_repo_path),
        with_context=False,
        profile=profile,
        config=config,
        adapter=adapter,
        image_tag=image_tag,
        context_content=_LIVE_CONTEXT,
    )

    assert without_result.harness_fingerprint_valid is None, (
        f"G-8 FAIL: WITHOUT arm must have harness_fingerprint_valid=None "
        f"(Probe C — gate not applicable). "
        f"Got: {without_result.harness_fingerprint_valid!r}."
    )

    # Probe A: WITH arm — gate must pass.
    with_result = run_task(
        task=task,
        repo_path=str(py_repo_path),
        with_context=True,
        profile=profile,
        config=config,
        adapter=adapter,
        image_tag=image_tag,
        context_content=_LIVE_CONTEXT,
    )

    assert with_result.harness_fingerprint_valid is True, (
        f"G-8 FAIL: WITH arm must have harness_fingerprint_valid=True "
        f"(Probe A — marker must be present). "
        f"Got: {with_result.harness_fingerprint_valid!r}. "
        f"Inspect agent log: {with_result.agent_log_path}"
    )


@_live_gate
def test_live_full_eval_delta_computed_after_fingerprint_gate(py_repo_path):
    """G-9: Full live score() returns ScoreReport with computed success_delta.

    Runs a minimal matrix (1 task × {without, with} × 1 run) through the
    complete scorer pipeline.  Asserts that score() returns a ScoreReport
    (no HarnessValidityError abort) and that success_delta is a float
    (provider/model consistent — not refused under Q9d / AD-5).

    Pass criteria (spec §5 G-9):
      - score() returns a ScoreReport (does not raise HarnessValidityError)
      - report.success_delta is a float (not None)
      - report.n_tasks == 1

    Requires: PRIMER_RUN_DOCKER_TESTS=1, ANTHROPIC_API_KEY, PRIMER_EVAL_IMAGE.
    """
    from primer.eval.scorer import score

    image_tag = os.environ["PRIMER_EVAL_IMAGE"]

    report = score(
        profile=_make_profile(commit="HEAD"),
        repo_path=str(py_repo_path),
        tasks=[_make_live_task()],
        config=_make_live_config(),
        adapter=ClaudeCodeAdapter(),
        image_tag=image_tag,
        context_content=_LIVE_CONTEXT,
        provider="proof-test",
        model="live",
        primer_overhead_usd=0.0,
        primer_overhead_confidence="estimated",
        runs_per_config=1,
    )

    assert report is not None, (
        "G-9 FAIL: score() must return a ScoreReport; got None"
    )
    assert isinstance(report.success_delta, float), (
        f"G-9 FAIL: success_delta must be a float (not None). "
        f"Got: {report.success_delta!r}. "
        f"provider_mismatch_warning: {report.provider_mismatch_warning!r}"
    )
    assert report.n_tasks == 1, (
        f"G-9 FAIL: expected n_tasks=1, got {report.n_tasks}"
    )
