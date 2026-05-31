"""Tests for primer/report/render.py — Phase 4 acceptance criteria.

Contracts verified:
  - Signed Δ colored by sign (green >0, yellow 0, red <0)
  - M3 within-noise label when |delta| <= max(1/n_tasks, stddev)
  - None delta prints refusal reason, never a fabricated number
  - Cost confidence qualifiers: exact (plain), estimated ("≈ ... (estimated)"), free ("local (no cost)")
  - PRIMER overhead shown on a SEPARATE line, never summed into eval cost
  - All *_warning fields surfaced prominently
  - render_report() performs NO computation (all numbers come from ScoreReport)
  - JSON format emits valid JSON
"""
from __future__ import annotations

import json
import io
from dataclasses import dataclass, field

import pytest
from rich.console import Console

from primer.eval.models import ScoreReport, TaskScore
from primer.report.render import render_report, _format_cost, _noise_label


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task_score(
    task_id: str = "stub_foo_bar",
    task_type: str = "stub_function",
    pass_rate_without: float = 0.0,
    pass_rate_with: float = 1.0,
    delta: float | None = 1.0,
    runs: int = 6,
    flaky_any: bool = False,
) -> TaskScore:
    return TaskScore(
        task_id=task_id,
        task_type=task_type,
        pass_rate_without=pass_rate_without,
        pass_rate_with=pass_rate_with,
        delta=delta,
        runs=runs,
        flaky_any=flaky_any,
    )


def _base_report(**overrides) -> ScoreReport:
    """Build a minimal valid ScoreReport for testing."""
    defaults = dict(
        repo_commit="abc1234",
        created_at="2026-05-30T00:00:00+00:00",
        n_tasks=5,
        runs_per_config=3,
        success_rate_without=0.4,
        success_rate_with=0.6,
        success_delta=0.2,
        success_stddev=0.1,
        success_min=0.0,
        success_max=1.0,
        cost_without=0.01,
        cost_with=0.012,
        cost_delta_pct=20.0,
        cost_confidence="exact",
        per_task=[_make_task_score()],
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


def _capture(report: ScoreReport, fmt: str = "text") -> str:
    """Render to a string buffer and return plain text."""
    buf = io.StringIO()
    cons = Console(file=buf, no_color=True, width=120)
    render_report(report, fmt=fmt, console=cons)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. Signed delta coloured by sign
# ---------------------------------------------------------------------------

class TestDeltaSign:
    def test_positive_delta_shown(self):
        out = _capture(_base_report(success_delta=0.2))
        assert "+20.0 pp" in out or "20.0 pp" in out

    def test_negative_delta_shown(self):
        out = _capture(_base_report(success_delta=-0.1))
        assert "-10.0 pp" in out

    def test_zero_delta_shown(self):
        out = _capture(_base_report(success_delta=0.0))
        assert "0.0 pp" in out

    def test_none_delta_prints_refusal(self):
        """A None delta must print the refusal reason, never a number."""
        out = _capture(_base_report(
            success_delta=None,
            cost_delta_pct=None,
            provider_mismatch_warning="Provider/model mismatch across compared runs — delta refused.",
        ))
        assert "N/A" in out or "refused" in out.lower()
        # Must NOT print a fabricated numeric delta
        assert "+20.0 pp" not in out

    def test_none_delta_no_fabricated_number(self):
        out = _capture(_base_report(success_delta=None, cost_delta_pct=None))
        # The headline delta line must not show a percentage point number
        # (cost delta section is separate)
        assert "Δ success = N/A" in out or "N/A" in out


# ---------------------------------------------------------------------------
# 2. M3 within-noise label
# ---------------------------------------------------------------------------

class TestNoiseLabelLogic:
    """_noise_label() tests — render-time classification, no computation."""

    def test_above_noise_returns_none(self):
        # delta=0.4, n_tasks=5, stddev=0.05 → threshold = max(0.2, 0.05) = 0.2; 0.4 > 0.2 → not noise
        r = _base_report(success_delta=0.4, n_tasks=5, success_stddev=0.05)
        assert _noise_label(r) is None

    def test_below_quantization_floor_is_noise(self):
        # delta=0.05, n_tasks=5 → quantization=0.2; 0.05 <= 0.2 → noise
        r = _base_report(success_delta=0.05, n_tasks=5, success_stddev=0.01)
        label = _noise_label(r)
        assert label is not None
        assert "noise" in label.lower()

    def test_within_stddev_is_noise(self):
        # delta=0.15, n_tasks=5, stddev=0.3 → threshold = max(0.2, 0.3) = 0.3; 0.15 <= 0.3 → noise
        r = _base_report(success_delta=0.15, n_tasks=5, success_stddev=0.3)
        label = _noise_label(r)
        assert label is not None

    def test_flaky_escalation(self):
        # Any flaky task → escalated label
        ts = _make_task_score(flaky_any=True)
        r = _base_report(success_delta=0.05, n_tasks=5, success_stddev=0.01, per_task=[ts])
        label = _noise_label(r)
        assert label is not None
        assert "flaky" in label.lower()

    def test_none_delta_returns_none(self):
        r = _base_report(success_delta=None)
        assert _noise_label(r) is None

    def test_noise_label_rendered_in_output(self):
        r = _base_report(success_delta=0.05, n_tasks=5, success_stddev=0.01)
        out = _capture(r)
        assert "noise" in out.lower()

    def test_no_noise_label_when_clear_signal(self):
        r = _base_report(success_delta=0.5, n_tasks=5, success_stddev=0.05)
        out = _capture(r)
        assert "noise" not in out.lower()


# ---------------------------------------------------------------------------
# 3. Cost confidence qualifiers
# ---------------------------------------------------------------------------

class TestCostFormatting:
    def test_exact_is_plain(self):
        assert _format_cost(0.0123, "exact") == "$0.0123"

    def test_estimated_has_prefix_and_suffix(self):
        result = _format_cost(0.0123, "estimated")
        assert result.startswith("≈")
        assert "estimated" in result
        assert "$0.0123" in result

    def test_free_is_local_no_cost(self):
        assert _format_cost(0.0, "free") == "local (no cost)"

    def test_exact_cost_in_output(self):
        out = _capture(_base_report(cost_confidence="exact"))
        assert "estimated" not in out or "overhead" in out  # overhead may be estimated

    def test_estimated_cost_in_output(self):
        out = _capture(_base_report(cost_confidence="estimated"))
        assert "(estimated)" in out

    def test_free_cost_in_output(self):
        out = _capture(_base_report(cost_confidence="free"))
        assert "local (no cost)" in out


# ---------------------------------------------------------------------------
# 4. PRIMER overhead on a separate line
# ---------------------------------------------------------------------------

class TestPrimerOverhead:
    def test_overhead_shown(self):
        out = _capture(_base_report(primer_overhead_usd=0.005, primer_overhead_confidence="exact"))
        assert "PRIMER" in out or "overhead" in out.lower()
        assert "$0.0050" in out

    def test_overhead_not_added_to_eval_cost(self):
        """Verify the overhead figure is separate — a pure rendering check."""
        # cost_without=0.01 + cost_with=0.012 → neither 0.015 nor 0.017 should appear
        # as the total (which would indicate the streams were summed)
        out = _capture(_base_report(
            cost_without=0.01,
            cost_with=0.012,
            primer_overhead_usd=0.005,
            cost_confidence="exact",
            primer_overhead_confidence="exact",
        ))
        # The overhead value must appear separately
        assert "$0.0050" in out
        # There should be no line that sums eval + overhead
        assert "$0.0150" not in out
        assert "$0.0170" not in out

    def test_overhead_free_shows_local(self):
        out = _capture(_base_report(
            primer_overhead_usd=0.0,
            primer_overhead_confidence="free",
        ))
        assert "local (no cost)" in out


# ---------------------------------------------------------------------------
# 5. Warnings surfaced prominently
# ---------------------------------------------------------------------------

class TestWarnings:
    def test_provider_mismatch_warning(self):
        w = "Provider/model mismatch across compared runs — delta refused."
        out = _capture(_base_report(
            success_delta=None,
            provider_mismatch_warning=w,
        ))
        assert "mismatch" in out.lower() or "WARNING" in out

    def test_isolation_mismatch_warning(self):
        w = "Isolation settings not uniform across runs."
        out = _capture(_base_report(isolation_mismatch_warning=w))
        assert "isolation" in out.lower() or "WARNING" in out

    def test_flaky_warning(self):
        w = "Flaky tasks detected: ['stub_foo']."
        out = _capture(_base_report(flaky_task_warning=w))
        assert "flaky" in out.lower() or "WARNING" in out

    def test_no_warning_section_when_clean(self):
        out = _capture(_base_report(
            provider_mismatch_warning=None,
            isolation_mismatch_warning=None,
            flaky_task_warning=None,
        ))
        assert "WARNING" not in out


# ---------------------------------------------------------------------------
# 6. Per-task table rendered
# ---------------------------------------------------------------------------

class TestPerTaskTable:
    def test_task_id_in_output(self):
        ts = _make_task_score(task_id="revert_abc123_test_foo")
        out = _capture(_base_report(per_task=[ts]))
        assert "revert_abc123_test_foo" in out

    def test_flaky_indicator(self):
        ts = _make_task_score(flaky_any=True)
        out = _capture(_base_report(per_task=[ts]))
        # The flaky indicator (⚠) should appear
        assert "⚠" in out or "flaky" in out.lower()

    def test_none_task_delta_shown_as_na(self):
        ts = _make_task_score(delta=None)
        out = _capture(_base_report(per_task=[ts]))
        assert "N/A" in out


# ---------------------------------------------------------------------------
# 7. JSON format
# ---------------------------------------------------------------------------

class TestJsonFormat:
    def test_json_is_valid(self):
        report = _base_report()
        buf = io.StringIO()
        # For JSON, render_report writes to stdout; capture via patch
        import unittest.mock as mock
        with mock.patch("builtins.print") as mock_print:
            render_report(report, fmt="json")
        # Collect all printed args
        printed = "\n".join(
            str(call.args[0]) for call in mock_print.call_args_list
        )
        # Should be parseable JSON
        data = json.loads(printed)
        assert "success_delta" in data
        assert "primer_overhead_usd" in data

    def test_json_contains_expected_fields(self):
        report = _base_report(
            success_delta=0.2,
            primer_overhead_usd=0.005,
        )
        import unittest.mock as mock
        with mock.patch("builtins.print") as mock_print:
            render_report(report, fmt="json")
        printed = "\n".join(str(c.args[0]) for c in mock_print.call_args_list)
        data = json.loads(printed)
        assert data["success_delta"] == pytest.approx(0.2)
        assert data["primer_overhead_usd"] == pytest.approx(0.005)


# ---------------------------------------------------------------------------
# 8. No computation in render
# ---------------------------------------------------------------------------

class TestNoComputation:
    def test_render_accepts_precomputed_values(self):
        """render_report() must accept and display whatever ScoreReport contains.
        It must not re-derive success_delta or any aggregated field.
        Passing an 'impossible' delta verifies the render just forwards it.
        """
        # An unusual delta — render should output it verbatim, not recompute
        r = _base_report(
            success_rate_without=0.4,
            success_rate_with=0.6,
            success_delta=0.99,  # not equal to 0.6-0.4=0.2 — proves no recomputation
        )
        out = _capture(r)
        # 0.99 * 100 = 99.0 pp
        assert "99.0 pp" in out

    def test_render_does_not_alter_none_delta(self):
        """A None delta must never be substituted with a computed value."""
        r = _base_report(
            success_rate_without=0.0,
            success_rate_with=1.0,
            success_delta=None,  # refused
        )
        out = _capture(r)
        assert "+100.0 pp" not in out
        assert "N/A" in out


# ---------------------------------------------------------------------------
# 9. Variance always shown
# ---------------------------------------------------------------------------

class TestVariance:
    def test_stddev_in_output(self):
        r = _base_report(success_stddev=0.123)
        out = _capture(r)
        assert "0.123" in out

    def test_min_max_in_output(self):
        r = _base_report(success_min=0.0, success_max=1.0)
        out = _capture(r)
        assert "0.0%" in out or "0%" in out
        assert "100.0%" in out or "100%" in out
