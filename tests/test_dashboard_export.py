"""Tests for the full dashboard data export (build_dashboard_json and friends).

Covers:
  - build_dashboard_json() produces a dict with schema_version, verdict,
    and all ScoreReport fields using exact field names.
  - _compute_verdict() returns correct verdict label:
      positive      : delta > max(1/n_tasks, stddev)
      negative      : delta < 0
      within-noise  : abs(delta) <= max(1/n_tasks, stddev)
      refused       : delta is None
  - _compute_flip_state() returns correct per-task label:
      PASS_TO_PASS  : both > 0
      PASS_TO_FAIL  : without > 0, with == 0
      FAIL_TO_PASS  : without == 0, with > 0
      FAIL_TO_FAIL  : both == 0
  - write_dashboard_json() writes valid JSON to disk and returns the payload.
  - primer export --data-output writes data.json alongside scores.json.
  - Architecture boundary: export.py does NOT import sqlite3 or docker.
  - DASHBOARD_SCHEMA_VERSION constant is 1.
"""
from __future__ import annotations

import ast
import json
import unittest.mock as mock
from pathlib import Path

import pytest
from typer.testing import CliRunner

from primer.eval.models import ScoreReport, TaskScore
from primer.report.export import (
    DASHBOARD_SCHEMA_VERSION,
    _compute_flip_state,
    _compute_verdict,
    build_dashboard_json,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(**overrides) -> ScoreReport:
    defaults = dict(
        repo_commit="abc12345",
        created_at="2026-05-31T00:00:00Z",
        n_tasks=5,
        runs_per_config=3,
        success_rate_without=0.4,
        success_rate_with=0.6,
        success_delta=0.2,
        success_stddev=0.05,
        success_min=0.2,
        success_max=0.8,
        cost_without=0.01,
        cost_with=0.012,
        cost_delta_pct=20.0,
        cost_confidence="exact",
        per_task=[],
        provider="anthropic",
        model="claude-sonnet-4-6",
        agent_adapter="claude_code",
        base_image="python:3.11-slim@sha256:abc",
        network_mode="proxy-egress",
        egress_enforced=True,
        provider_mismatch_warning=None,
        isolation_mismatch_warning=None,
        flaky_task_warning=None,
        primer_overhead_usd=0.005,
        primer_overhead_confidence="exact",
    )
    defaults.update(overrides)
    return ScoreReport(**defaults)


def _make_task_score(**overrides) -> TaskScore:
    defaults = dict(
        task_id="task_1",
        task_type="revert_reimplement",
        pass_rate_without=0.0,
        pass_rate_with=1.0,
        delta=1.0,
        runs=3,
        flaky_any=False,
    )
    defaults.update(overrides)
    return TaskScore(**defaults)


# ---------------------------------------------------------------------------
# 1. DASHBOARD_SCHEMA_VERSION constant
# ---------------------------------------------------------------------------

class TestDashboardSchemaVersion:
    def test_schema_version_is_1(self):
        assert DASHBOARD_SCHEMA_VERSION == 1


# ---------------------------------------------------------------------------
# 2. _compute_verdict()
# ---------------------------------------------------------------------------

class TestComputeVerdict:
    def test_none_delta_is_refused(self):
        assert _compute_verdict(None, 5, 0.05) == "refused"

    def test_positive_above_noise_is_positive(self):
        # 1/5 = 0.2, stddev=0.05 → threshold=0.2; delta=0.3 > 0.2 → positive
        assert _compute_verdict(0.3, 5, 0.05) == "positive"

    def test_small_positive_within_noise(self):
        # 1/5 = 0.2, stddev=0.05 → threshold=0.2; delta=0.1 <= 0.2 → within-noise
        assert _compute_verdict(0.1, 5, 0.05) == "within-noise"

    def test_zero_delta_within_noise(self):
        assert _compute_verdict(0.0, 5, 0.05) == "within-noise"

    def test_negative_small_within_noise(self):
        # abs(-0.1) = 0.1 <= threshold(0.2) → within-noise
        assert _compute_verdict(-0.1, 5, 0.05) == "within-noise"

    def test_negative_large_is_negative(self):
        # abs(-0.3) = 0.3 > 0.2 → negative
        assert _compute_verdict(-0.3, 5, 0.05) == "negative"

    def test_stddev_threshold_used_when_larger(self):
        # 1/5=0.2, stddev=0.4 → threshold=0.4; delta=0.3 <= 0.4 → within-noise
        assert _compute_verdict(0.3, 5, 0.4) == "within-noise"

    def test_n_tasks_3_floor(self):
        # 1/3 ≈ 0.333, stddev=0.05 → threshold=0.333; delta=0.4 > 0.333 → positive
        assert _compute_verdict(0.4, 3, 0.05) == "positive"

    @pytest.mark.parametrize("delta,n_tasks,stddev,expected", [
        (0.5, 5, 0.05, "positive"),
        (-0.5, 5, 0.05, "negative"),
        (0.0, 5, 0.1, "within-noise"),
        (None, 5, 0.1, "refused"),
        (0.15, 5, 0.2, "within-noise"),   # abs(0.15) <= max(0.2, 0.2)
        (0.25, 5, 0.1, "positive"),       # abs(0.25) > max(0.2, 0.1)
    ])
    def test_parametrized(self, delta, n_tasks, stddev, expected):
        assert _compute_verdict(delta, n_tasks, stddev) == expected


# ---------------------------------------------------------------------------
# 3. _compute_flip_state() — per-task states
# ---------------------------------------------------------------------------

class TestComputeFlipState:
    def test_pass_to_pass(self):
        assert _compute_flip_state(1.0, 1.0) == "PASS_TO_PASS"

    def test_pass_to_fail(self):
        assert _compute_flip_state(1.0, 0.0) == "PASS_TO_FAIL"

    def test_fail_to_pass(self):
        assert _compute_flip_state(0.0, 1.0) == "FAIL_TO_PASS"

    def test_fail_to_fail(self):
        assert _compute_flip_state(0.0, 0.0) == "FAIL_TO_FAIL"

    def test_partial_pass_to_pass(self):
        # Partial pass rates both > 0 → PASS_TO_PASS
        assert _compute_flip_state(0.67, 0.33) == "PASS_TO_PASS"

    def test_partial_fail_to_pass(self):
        assert _compute_flip_state(0.0, 0.67) == "FAIL_TO_PASS"

    def test_partial_pass_to_fail(self):
        assert _compute_flip_state(0.67, 0.0) == "PASS_TO_FAIL"

    @pytest.mark.parametrize("without,with_ctx,expected", [
        (1.0, 1.0, "PASS_TO_PASS"),
        (0.5, 0.5, "PASS_TO_PASS"),
        (1.0, 0.0, "PASS_TO_FAIL"),
        (0.0, 1.0, "FAIL_TO_PASS"),
        (0.0, 0.0, "FAIL_TO_FAIL"),
    ])
    def test_parametrized(self, without, with_ctx, expected):
        assert _compute_flip_state(without, with_ctx) == expected


# ---------------------------------------------------------------------------
# 4. build_dashboard_json() — schema shape
# ---------------------------------------------------------------------------

class TestBuildDashboardJsonSchema:
    def test_schema_version_is_1(self):
        payload = build_dashboard_json(_make_report())
        assert payload["schema_version"] == 1

    def test_all_required_keys_present(self):
        payload = build_dashboard_json(_make_report())
        required = {
            "schema_version", "repo_commit", "created_at", "verdict",
            "n_tasks", "runs_per_config",
            "success_rate_without", "success_rate_with",
            "success_delta", "success_stddev", "success_min", "success_max",
            "cost_without", "cost_with", "cost_delta_pct", "cost_confidence",
            "provider", "model", "agent_adapter", "base_image",
            "network_mode", "egress_enforced",
            "provider_mismatch_warning", "isolation_mismatch_warning",
            "flaky_task_warning",
            "primer_overhead_usd", "primer_overhead_confidence",
            "per_task",
        }
        assert required.issubset(set(payload.keys()))

    def test_verdict_field_present(self):
        payload = build_dashboard_json(_make_report(success_delta=0.3))
        assert "verdict" in payload

    def test_success_delta_propagated(self):
        payload = build_dashboard_json(_make_report(success_delta=0.2))
        assert payload["success_delta"] == pytest.approx(0.2)

    def test_none_delta_propagated(self):
        payload = build_dashboard_json(_make_report(success_delta=None, cost_delta_pct=None))
        assert payload["success_delta"] is None

    def test_egress_enforced_bool(self):
        payload = build_dashboard_json(_make_report(egress_enforced=True))
        assert payload["egress_enforced"] is True


# ---------------------------------------------------------------------------
# 5. build_dashboard_json() — verdict values
# ---------------------------------------------------------------------------

class TestBuildDashboardJsonVerdict:
    def test_positive_delta_verdict(self):
        # success_delta=0.3, n_tasks=5, stddev=0.05 → threshold=0.2 → positive
        payload = build_dashboard_json(
            _make_report(success_delta=0.3, n_tasks=5, success_stddev=0.05)
        )
        assert payload["verdict"] == "positive"

    def test_negative_delta_verdict(self):
        payload = build_dashboard_json(
            _make_report(success_delta=-0.3, n_tasks=5, success_stddev=0.05)
        )
        assert payload["verdict"] == "negative"

    def test_within_noise_verdict(self):
        payload = build_dashboard_json(
            _make_report(success_delta=0.1, n_tasks=5, success_stddev=0.05)
        )
        assert payload["verdict"] == "within-noise"

    def test_refused_verdict_when_delta_none(self):
        payload = build_dashboard_json(
            _make_report(success_delta=None, cost_delta_pct=None)
        )
        assert payload["verdict"] == "refused"

    def test_zero_delta_within_noise(self):
        payload = build_dashboard_json(
            _make_report(success_delta=0.0, n_tasks=5, success_stddev=0.05)
        )
        assert payload["verdict"] == "within-noise"


# ---------------------------------------------------------------------------
# 6. build_dashboard_json() — per_task flip states
# ---------------------------------------------------------------------------

class TestBuildDashboardJsonPerTask:
    def test_empty_per_task(self):
        payload = build_dashboard_json(_make_report(per_task=[]))
        assert payload["per_task"] == []

    def test_fail_to_pass_flip_state(self):
        task = _make_task_score(pass_rate_without=0.0, pass_rate_with=1.0)
        report = _make_report(per_task=[task])
        payload = build_dashboard_json(report)
        assert payload["per_task"][0]["flip_state"] == "FAIL_TO_PASS"

    def test_pass_to_fail_flip_state(self):
        task = _make_task_score(pass_rate_without=1.0, pass_rate_with=0.0)
        report = _make_report(per_task=[task])
        payload = build_dashboard_json(report)
        assert payload["per_task"][0]["flip_state"] == "PASS_TO_FAIL"

    def test_pass_to_pass_flip_state(self):
        task = _make_task_score(pass_rate_without=1.0, pass_rate_with=1.0)
        report = _make_report(per_task=[task])
        payload = build_dashboard_json(report)
        assert payload["per_task"][0]["flip_state"] == "PASS_TO_PASS"

    def test_fail_to_fail_flip_state(self):
        task = _make_task_score(pass_rate_without=0.0, pass_rate_with=0.0)
        report = _make_report(per_task=[task])
        payload = build_dashboard_json(report)
        assert payload["per_task"][0]["flip_state"] == "FAIL_TO_FAIL"

    def test_task_id_propagated(self):
        task = _make_task_score(task_id="my_task_42")
        report = _make_report(per_task=[task])
        payload = build_dashboard_json(report)
        assert payload["per_task"][0]["task_id"] == "my_task_42"

    def test_task_type_propagated(self):
        task = _make_task_score(task_type="stub_function")
        report = _make_report(per_task=[task])
        payload = build_dashboard_json(report)
        assert payload["per_task"][0]["task_type"] == "stub_function"

    def test_flaky_any_propagated(self):
        task = _make_task_score(flaky_any=True)
        report = _make_report(per_task=[task])
        payload = build_dashboard_json(report)
        assert payload["per_task"][0]["flaky_any"] is True

    def test_multiple_tasks(self):
        tasks = [
            _make_task_score(task_id="t1", pass_rate_without=0.0, pass_rate_with=1.0),
            _make_task_score(task_id="t2", pass_rate_without=1.0, pass_rate_with=0.0),
            _make_task_score(task_id="t3", pass_rate_without=1.0, pass_rate_with=1.0),
        ]
        report = _make_report(per_task=tasks)
        payload = build_dashboard_json(report)
        assert len(payload["per_task"]) == 3
        flip_states = {t["task_id"]: t["flip_state"] for t in payload["per_task"]}
        assert flip_states["t1"] == "FAIL_TO_PASS"
        assert flip_states["t2"] == "PASS_TO_FAIL"
        assert flip_states["t3"] == "PASS_TO_PASS"


# ---------------------------------------------------------------------------
# 7. build_dashboard_json() — provenance fields
# ---------------------------------------------------------------------------

class TestBuildDashboardJsonProvenance:
    def test_provider_propagated(self):
        payload = build_dashboard_json(_make_report(provider="ollama"))
        assert payload["provider"] == "ollama"

    def test_model_propagated(self):
        payload = build_dashboard_json(_make_report(model="llama3.3"))
        assert payload["model"] == "llama3.3"

    def test_base_image_propagated(self):
        payload = build_dashboard_json(_make_report(base_image="python:3.11@sha256:xyz"))
        assert payload["base_image"] == "python:3.11@sha256:xyz"

    def test_warnings_null_when_clean(self):
        payload = build_dashboard_json(_make_report(
            provider_mismatch_warning=None,
            isolation_mismatch_warning=None,
            flaky_task_warning=None,
        ))
        assert payload["provider_mismatch_warning"] is None
        assert payload["isolation_mismatch_warning"] is None
        assert payload["flaky_task_warning"] is None

    def test_warnings_propagated_when_set(self):
        payload = build_dashboard_json(_make_report(
            flaky_task_warning="Task t1 flaky",
        ))
        assert payload["flaky_task_warning"] == "Task t1 flaky"

    def test_primer_overhead_separate(self):
        payload = build_dashboard_json(_make_report(
            primer_overhead_usd=0.007,
            primer_overhead_confidence="exact",
        ))
        assert payload["primer_overhead_usd"] == pytest.approx(0.007)
        assert payload["primer_overhead_confidence"] == "exact"


# ---------------------------------------------------------------------------
# 8. write_dashboard_json() — REMOVED
#    The legacy single-file data.json writer was deleted; the full site tree is
#    produced via --site-output. build_dashboard_json (the shared field-builder)
#    remains and is covered by sections 4–7 above.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 9. CLI: primer export --data-output — REMOVED
#    The --data-output flag + legacy data.json path were deleted. The dashboard
#    is now fed by --site-output (repository.json + evaluations/<id>.json),
#    covered by tests/test_site_export.py. Badge (scores.json) export unchanged.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 10. Architecture boundary: export.py must not import sqlite3 or docker
# ---------------------------------------------------------------------------

class TestArchBoundaryDashboard:
    def _load_export_ast(self):
        return ast.parse(
            (Path(__file__).parent.parent / "primer" / "report" / "export.py")
            .read_text(encoding="utf-8")
        )

    def test_no_sqlite3_import(self):
        tree = self._load_export_ast()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                for name in names:
                    assert "sqlite3" not in name, (
                        "report/export.py must not import sqlite3"
                    )

    def test_no_docker_import(self):
        tree = self._load_export_ast()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                for name in names:
                    assert "docker" not in name, (
                        "report/export.py must not import docker"
                    )

    def test_export_module_importable(self):
        import primer.report.export  # noqa: F401

    def test_dashboard_constants_importable(self):
        from primer.report.export import (  # noqa: F401
            DASHBOARD_SCHEMA_VERSION,
            build_dashboard_json,
        )
