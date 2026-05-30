"""Tests for eval/scorer.py (AD-5, M3).

These tests mock run_task so they run without Docker.
"""
from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch, call

import pytest

from primer.eval.models import (
    AgentTelemetry,
    RunResult,
    ScoreReport,
    Task,
    TaskMutation,
    TaskScore,
)
from primer.eval.scorer import (
    _pass_rate,
    _stddev,
    _worst_confidence,
    _aggregate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_run(
    task_id="t1",
    passed=True,
    with_context=False,
    provider="anthropic",
    model="claude-sonnet-4-6",
    network_mode="proxy-egress",
    egress_enforced=True,
    base_image="python:3.11-slim@sha256:abc",
    cost_usd=0.01,
    cost_confidence="exact",
    flaky=False,
    timeout=False,
) -> RunResult:
    return RunResult(
        task_id=task_id,
        passed=passed,
        timeout=timeout,
        flaky=flaky,
        with_context=with_context,
        agent_adapter="claude_code",
        agent_tokens=100,
        iterations=1,
        duration_s=1.0,
        cost_usd=cost_usd,
        cost_confidence=cost_confidence,
        provider=provider,
        model=model,
        base_image=base_image,
        repo_commit="abc123",
        network_mode=network_mode,
        egress_allowed_host="api.anthropic.com",
        egress_enforced=egress_enforced,
        caps_dropped=True,
        container_id="c001",
        agent_log_path="/tmp/log.txt",
        run_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )


def _make_task(task_id="t1") -> Task:
    return Task(
        id=task_id,
        task_type="stub_function",
        prompt="Fix it",
        verify_cmd="python -m pytest tests/ -x -q",
        mutation=TaskMutation(kind="stub", target_file="a.py", target_symbol="fn"),
        validated=True,
    )


def _make_profile():
    profile = MagicMock()
    profile.repo_commit = "abc123"
    return profile


def _make_adapter():
    adapter = MagicMock()
    adapter.adapter_name = "claude_code"
    adapter.context_filename.return_value = "CLAUDE.md"
    return adapter


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def test_pass_rate_all_pass():
    runs = [_make_run(passed=True) for _ in range(3)]
    assert _pass_rate(runs) == 1.0

def test_pass_rate_all_fail():
    runs = [_make_run(passed=False) for _ in range(3)]
    assert _pass_rate(runs) == 0.0

def test_pass_rate_mixed():
    runs = [_make_run(passed=True), _make_run(passed=False)]
    assert _pass_rate(runs) == 0.5

def test_pass_rate_empty():
    assert _pass_rate([]) == 0.0

def test_stddev_uniform():
    assert _stddev([1.0, 1.0, 1.0]) == 0.0

def test_stddev_varied():
    sd = _stddev([0.0, 1.0])
    assert abs(sd - 0.5) < 1e-9

def test_worst_confidence_exact_wins():
    assert _worst_confidence(["exact", "exact"]) == "exact"

def test_worst_confidence_free_is_worst():
    assert _worst_confidence(["exact", "estimated", "free"]) == "free"

def test_worst_confidence_estimated():
    assert _worst_confidence(["exact", "estimated"]) == "estimated"


# ---------------------------------------------------------------------------
# _aggregate: success delta
# ---------------------------------------------------------------------------

def test_aggregate_positive_delta():
    tasks = [_make_task("t1")]
    profile = _make_profile()
    adapter = _make_adapter()

    # WITHOUT: all fail; WITH: all pass
    without_runs = [_make_run("t1", passed=False, with_context=False) for _ in range(3)]
    with_runs = [_make_run("t1", passed=True, with_context=True) for _ in range(3)]
    all_runs = without_runs + with_runs
    per_task = {"t1": all_runs}

    report = _aggregate(
        tasks=tasks,
        all_runs=all_runs,
        per_task_runs=per_task,
        runs_per_config=3,
        provider="anthropic",
        model="claude-sonnet-4-6",
        adapter=adapter,
        profile=profile,
        primer_overhead_usd=0.001,
        primer_overhead_confidence="exact",
    )

    assert report.success_rate_without == 0.0
    assert report.success_rate_with == 1.0
    assert report.success_delta == pytest.approx(1.0)
    assert report.primer_overhead_usd == pytest.approx(0.001)


def test_aggregate_negative_delta():
    tasks = [_make_task("t1")]
    profile = _make_profile()
    adapter = _make_adapter()

    # WITHOUT: all pass; WITH: all fail
    without_runs = [_make_run("t1", passed=True, with_context=False) for _ in range(3)]
    with_runs = [_make_run("t1", passed=False, with_context=True) for _ in range(3)]
    all_runs = without_runs + with_runs
    per_task = {"t1": all_runs}

    report = _aggregate(
        tasks=tasks, all_runs=all_runs, per_task_runs=per_task, runs_per_config=3,
        provider="anthropic", model="claude-sonnet-4-6",
        adapter=adapter, profile=profile,
        primer_overhead_usd=0.0, primer_overhead_confidence="exact",
    )
    assert report.success_delta == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# _aggregate: refuse-on-mismatch (Q9d / AD-5)
# ---------------------------------------------------------------------------

def test_aggregate_refuses_delta_on_provider_mismatch():
    """success_delta must be None when providers differ across runs (AD-5)."""
    tasks = [_make_task("t1")]
    profile = _make_profile()
    adapter = _make_adapter()

    without_runs = [_make_run("t1", passed=True, with_context=False,
                               provider="anthropic", model="claude-sonnet-4-6")]
    with_runs = [_make_run("t1", passed=False, with_context=True,
                            provider="openai", model="gpt-4o")]
    all_runs = without_runs + with_runs
    per_task = {"t1": all_runs}

    report = _aggregate(
        tasks=tasks, all_runs=all_runs, per_task_runs=per_task, runs_per_config=1,
        provider="mixed", model="mixed",
        adapter=adapter, profile=profile,
        primer_overhead_usd=0.0, primer_overhead_confidence="exact",
    )

    assert report.success_delta is None
    assert report.cost_delta_pct is None
    assert report.provider_mismatch_warning is not None
    assert "mismatch" in report.provider_mismatch_warning.lower()


def test_aggregate_refuses_delta_on_model_mismatch():
    tasks = [_make_task("t1")]
    profile = _make_profile()
    adapter = _make_adapter()

    without_runs = [_make_run("t1", passed=True, with_context=False,
                               provider="anthropic", model="claude-haiku-4-5")]
    with_runs = [_make_run("t1", passed=False, with_context=True,
                            provider="anthropic", model="claude-sonnet-4-6")]
    all_runs = without_runs + with_runs
    per_task = {"t1": all_runs}

    report = _aggregate(
        tasks=tasks, all_runs=all_runs, per_task_runs=per_task, runs_per_config=1,
        provider="anthropic", model="mixed",
        adapter=adapter, profile=profile,
        primer_overhead_usd=0.0, primer_overhead_confidence="exact",
    )

    assert report.success_delta is None
    assert report.provider_mismatch_warning is not None


# ---------------------------------------------------------------------------
# _aggregate: isolation consistency check
# ---------------------------------------------------------------------------

def test_aggregate_isolation_mismatch_warning():
    tasks = [_make_task("t1")]
    profile = _make_profile()
    adapter = _make_adapter()

    r1 = _make_run("t1", with_context=False, network_mode="proxy-egress", egress_enforced=True)
    r2 = _make_run("t1", with_context=True, network_mode="open-bridge", egress_enforced=False)
    all_runs = [r1, r2]
    per_task = {"t1": all_runs}

    report = _aggregate(
        tasks=tasks, all_runs=all_runs, per_task_runs=per_task, runs_per_config=1,
        provider="anthropic", model="claude-sonnet-4-6",
        adapter=adapter, profile=profile,
        primer_overhead_usd=0.0, primer_overhead_confidence="exact",
    )

    assert report.isolation_mismatch_warning is not None


def test_aggregate_egress_enforced_only_when_all_runs_enforced():
    tasks = [_make_task("t1")]
    profile = _make_profile()
    adapter = _make_adapter()

    # Mix of enforced and not-enforced
    r1 = _make_run("t1", with_context=False, egress_enforced=True)
    r2 = _make_run("t1", with_context=True, egress_enforced=False)
    all_runs = [r1, r2]
    per_task = {"t1": all_runs}

    report = _aggregate(
        tasks=tasks, all_runs=all_runs, per_task_runs=per_task, runs_per_config=1,
        provider="anthropic", model="claude-sonnet-4-6",
        adapter=adapter, profile=profile,
        primer_overhead_usd=0.0, primer_overhead_confidence="exact",
    )

    # Must be False because not ALL runs were enforced (honesty gate)
    assert report.egress_enforced is False


def test_aggregate_egress_enforced_true_when_all_enforced():
    tasks = [_make_task("t1")]
    profile = _make_profile()
    adapter = _make_adapter()

    r1 = _make_run("t1", with_context=False, egress_enforced=True)
    r2 = _make_run("t1", with_context=True, egress_enforced=True)
    all_runs = [r1, r2]
    per_task = {"t1": all_runs}

    report = _aggregate(
        tasks=tasks, all_runs=all_runs, per_task_runs=per_task, runs_per_config=1,
        provider="anthropic", model="claude-sonnet-4-6",
        adapter=adapter, profile=profile,
        primer_overhead_usd=0.0, primer_overhead_confidence="exact",
    )

    assert report.egress_enforced is True


# ---------------------------------------------------------------------------
# _aggregate: cost streams never mixed
# ---------------------------------------------------------------------------

def test_primer_overhead_never_added_to_eval_cost():
    tasks = [_make_task("t1")]
    profile = _make_profile()
    adapter = _make_adapter()

    r1 = _make_run("t1", with_context=False, cost_usd=0.05)
    r2 = _make_run("t1", with_context=True, cost_usd=0.07)
    all_runs = [r1, r2]
    per_task = {"t1": all_runs}

    report = _aggregate(
        tasks=tasks, all_runs=all_runs, per_task_runs=per_task, runs_per_config=1,
        provider="anthropic", model="claude-sonnet-4-6",
        adapter=adapter, profile=profile,
        primer_overhead_usd=999.0,   # large value — must NOT appear in cost_with/without
        primer_overhead_confidence="exact",
    )

    # Eval cost streams are correct
    assert report.cost_without == pytest.approx(0.05)
    assert report.cost_with == pytest.approx(0.07)
    # PRIMER overhead is separate — total eval cost should not include it
    assert report.primer_overhead_usd == pytest.approx(999.0)
    # The eval totals must NOT include overhead
    assert report.cost_without + report.cost_with < 1.0  # 0.12, not 999+


# ---------------------------------------------------------------------------
# _aggregate: variance never collapsed (M3)
# ---------------------------------------------------------------------------

def test_variance_reported():
    tasks = [_make_task("t1")]
    profile = _make_profile()
    adapter = _make_adapter()

    # Mixed pass/fail so variance > 0
    r1 = _make_run("t1", passed=True, with_context=False)
    r2 = _make_run("t1", passed=False, with_context=True)
    all_runs = [r1, r2]
    per_task = {"t1": all_runs}

    report = _aggregate(
        tasks=tasks, all_runs=all_runs, per_task_runs=per_task, runs_per_config=1,
        provider="anthropic", model="claude-sonnet-4-6",
        adapter=adapter, profile=profile,
        primer_overhead_usd=0.0, primer_overhead_confidence="exact",
    )

    # success_stddev, min, max must all be present (never None)
    assert isinstance(report.success_stddev, float)
    assert isinstance(report.success_min, float)
    assert isinstance(report.success_max, float)
    assert report.success_stddev >= 0.0


# ---------------------------------------------------------------------------
# Flaky annotation
# ---------------------------------------------------------------------------

def test_flaky_task_warning_set_when_flaky_runs():
    tasks = [_make_task("t1")]
    profile = _make_profile()
    adapter = _make_adapter()

    r1 = _make_run("t1", with_context=False, flaky=True)
    r2 = _make_run("t1", with_context=True)
    all_runs = [r1, r2]
    per_task = {"t1": all_runs}

    report = _aggregate(
        tasks=tasks, all_runs=all_runs, per_task_runs=per_task, runs_per_config=1,
        provider="anthropic", model="claude-sonnet-4-6",
        adapter=adapter, profile=profile,
        primer_overhead_usd=0.0, primer_overhead_confidence="exact",
    )

    assert report.flaky_task_warning is not None
    assert "t1" in report.flaky_task_warning
