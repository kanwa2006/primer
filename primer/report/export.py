"""Scores.json badge export and full dashboard data export.

scores.json:
  CI writes scores.json to gh-pages; README uses a shields.io endpoint badge.
  Schema: {schemaVersion, label, message, color}
    - green  if success_delta > 0
    - yellow if success_delta == 0 or within noise (None/refused also yellow)
    - red    if success_delta < 0

Dashboard export:
  Full dashboard data export for the Next.js scorecard.
  Schema: all ScoreReport fields + verdict label + per-task flip states.

Module DAG boundary: report/ does no aggregation; all numbers come from ScoreReport.
No imports of sqlite3 or docker (store/ and eval/ boundaries).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from primer.eval.models import ScoreReport, TaskScore

# shields.io endpoint badge schema version (always 1)
SCHEMA_VERSION = 1

# Label displayed on the left half of the badge
BADGE_LABEL = "PRIMER"

# dashboard.json schema version
DASHBOARD_SCHEMA_VERSION = 1

# M3 verdict labels (primer-dashboard skill)
VerdictLabel = Literal["positive", "negative", "within-noise", "refused"]

# Per-task flip state labels (primer-dashboard skill)
FlipState = Literal["PASS_TO_PASS", "PASS_TO_FAIL", "FAIL_TO_PASS", "FAIL_TO_FAIL"]


def build_scores_json(report: "ScoreReport") -> dict:
    """Build the shields.io endpoint badge payload from a ScoreReport.

    Schema (Q5):
        {
            "schemaVersion": 1,
            "label":         "PRIMER",
            "message":       "<delta string>",
            "color":         "green" | "yellow" | "red"
        }

    Color rules (Q5):
        - green  : success_delta > 0
        - yellow : success_delta == 0 or None (refused / within noise)
        - red    : success_delta < 0

    Args:
        report: A fully-computed ScoreReport. No computation performed here;
                all values are read directly from the report.

    Returns:
        dict suitable for json.dumps().
    """
    delta = report.success_delta

    if delta is None:
        # Refused (provider/model mismatch) — muted/desaturated, not caution-yellow (§13).
        message = "N/A (refused)"
        color = "71717a"
    elif delta > 0:
        pct = delta * 100.0
        message = f"+{pct:.1f} pp"
        color = "green"
    elif delta < 0:
        pct = delta * 100.0
        message = f"{pct:.1f} pp"
        color = "red"
    else:
        # Exactly zero / within-noise — calm slate-blue, not caution-yellow (§13).
        message = "0.0 pp"
        color = "64748b"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "label": BADGE_LABEL,
        "message": message,
        "color": color,
    }


def write_scores_json(report: "ScoreReport", output_path: Path) -> dict:
    """Build and write scores.json to output_path.

    Args:
        report:      A fully-computed ScoreReport.
        output_path: Destination path (e.g. Path("scores.json") or a gh-pages dir).

    Returns:
        The payload dict that was written (for callers that want to inspect or log it).
    """
    payload = build_scores_json(report)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


# ---------------------------------------------------------------------------
# Dashboard data export
# ---------------------------------------------------------------------------

def _compute_verdict(
    success_delta: float | None,
    n_tasks: int,
    success_stddev: float,
) -> VerdictLabel:
    """Compute M3 verdict label.

    Rules (from Decision Addendum M3):
      - refused      : success_delta is None (provider/model mismatch)
      - within-noise : abs(delta) <= max(1/n_tasks, success_stddev)
      - positive     : delta > noise threshold
      - negative     : delta < 0 (below noise threshold)
    """
    if success_delta is None:
        return "refused"
    noise_threshold = max(1 / n_tasks, success_stddev) if n_tasks > 0 else success_stddev
    if abs(success_delta) <= noise_threshold:
        return "within-noise"
    if success_delta > 0:
        return "positive"
    return "negative"


def _compute_flip_state(
    pass_rate_without: float,
    pass_rate_with: float,
) -> FlipState:
    """Compute per-task flip state (primer-dashboard skill).

    Uses pass_rate > 0 as the threshold for "passing".
    """
    was_passing = pass_rate_without > 0
    is_passing = pass_rate_with > 0
    if was_passing and is_passing:
        return "PASS_TO_PASS"
    if was_passing and not is_passing:
        return "PASS_TO_FAIL"
    if not was_passing and is_passing:
        return "FAIL_TO_PASS"
    return "FAIL_TO_FAIL"


def build_dashboard_json(report: "ScoreReport") -> dict:
    """Build the full dashboard data payload from a ScoreReport.

    Used by the Next.js scorecard dashboard. All field names match the
    primer-dashboard specification exactly. No computation beyond what is
    already present in the report; only verdict and flip states are derived.

    Schema version: DASHBOARD_SCHEMA_VERSION (1).

    Args:
        report: A fully-computed ScoreReport.

    Returns:
        dict suitable for json.dumps(). Contains all ScoreReport fields plus
        computed verdict and per-task flip_state.
    """
    verdict = _compute_verdict(
        report.success_delta,
        report.n_tasks,
        report.success_stddev,
    )

    per_task = []
    for ts in report.per_task:
        per_task.append({
            "task_id": ts.task_id,
            "task_type": ts.task_type,
            "pass_rate_without": ts.pass_rate_without,
            "pass_rate_with": ts.pass_rate_with,
            "delta": ts.delta,
            "flip_state": _compute_flip_state(ts.pass_rate_without, ts.pass_rate_with),
            "runs": ts.runs,
            "flaky_any": ts.flaky_any,
        })

    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        # report identity
        "repo_commit": report.repo_commit,
        "created_at": report.created_at,
        # M3 computed verdict
        "verdict": verdict,
        # core metrics
        "n_tasks": report.n_tasks,
        "runs_per_config": report.runs_per_config,
        "success_rate_without": report.success_rate_without,
        "success_rate_with": report.success_rate_with,
        "success_delta": report.success_delta,
        "success_stddev": report.success_stddev,
        "success_min": report.success_min,
        "success_max": report.success_max,
        # cost (eval stream only)
        "cost_without": report.cost_without,
        "cost_with": report.cost_with,
        "cost_delta_pct": report.cost_delta_pct,
        "cost_confidence": report.cost_confidence,
        # provenance / isolation
        "provider": report.provider,
        "model": report.model,
        "agent_adapter": report.agent_adapter,
        "base_image": report.base_image,
        "network_mode": report.network_mode,
        "egress_enforced": report.egress_enforced,
        # honesty warnings
        "provider_mismatch_warning": report.provider_mismatch_warning,
        "isolation_mismatch_warning": report.isolation_mismatch_warning,
        "flaky_task_warning": report.flaky_task_warning,
        # PRIMER overhead (separate stream — never added to cost_with/without)
        "primer_overhead_usd": report.primer_overhead_usd,
        "primer_overhead_confidence": report.primer_overhead_confidence,
        # per-task breakdown
        "per_task": per_task,
    }


# NOTE: the legacy single-file `write_dashboard_json` writer + `--data-output` path was
# removed; the full site tree is produced via `--site-output` (repository.json +
# evaluations/<id>.json). `build_dashboard_json` above remains the shared
# field-builder for `build_evaluation_json`.


# ---------------------------------------------------------------------------
# Site export builders
# ---------------------------------------------------------------------------

def build_evaluation_json(
    report_id: int,
    report: "ScoreReport",
    repo_name: str,
    repo_url: "str | None",
) -> dict:
    """Build the evaluations/<id>.json payload.

    Returns build_dashboard_json(report) merged with additional site fields.
    schema_version is overridden to 2; build_dashboard_json is not mutated.
    No DB access; accepts plain dataclasses/ints (boundary invariant held).
    """
    payload = build_dashboard_json(report)
    payload["schema_version"] = 2
    payload["kind"] = "evaluation"
    payload["id"] = report_id
    payload["repo"] = {"name": repo_name, "url": repo_url}
    return payload


def build_repository_json(
    repo_name: str,
    repo_url: "str | None",
    items: "list[tuple[int, ScoreReport]]",
    generated_at: str,
) -> dict:
    """Build the repository.json payload.

    items: newest-first list of (reports.id, ScoreReport).
    No DB access; accepts plain dataclasses/ints (boundary invariant held).
    """
    evaluations = []
    for eval_id, report in items:
        n = report.n_tasks
        noise_threshold = max(1 / n, report.success_stddev) if n > 0 else report.success_stddev
        evaluations.append({
            "id": eval_id,
            "repo_commit": report.repo_commit,
            "created_at": report.created_at,
            "verdict": _compute_verdict(report.success_delta, n, report.success_stddev),
            "success_delta": report.success_delta,
            "success_stddev": report.success_stddev,
            "n_tasks": n,
            "runs_per_config": report.runs_per_config,
            "noise_threshold": noise_threshold,
            "provider": report.provider,
            "model": report.model,
            "agent_adapter": report.agent_adapter,
            "egress_enforced": report.egress_enforced,
        })

    if items:
        latest_id: "int | None" = items[0][0]
        latest_report = items[0][1]
        latest_verdict: "str | None" = _compute_verdict(
            latest_report.success_delta,
            latest_report.n_tasks,
            latest_report.success_stddev,
        )
        latest_commit = latest_report.repo_commit
    else:
        latest_id = None
        latest_verdict = None
        latest_commit = ""

    return {
        "schema_version": 2,
        "kind": "repository",
        "repo": {
            "name": repo_name,
            "url": repo_url,
            "latest_commit": latest_commit,
        },
        "latest_evaluation_id": latest_id,
        "latest_verdict": latest_verdict,
        "evaluation_count": len(items),
        "evaluations": evaluations,
        "generated_at": generated_at,
    }


def write_evaluation_json(payload: dict, output_path: Path) -> dict:
    """Write an evaluation payload to output_path; mkdir parents as needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def write_repository_json(payload: dict, output_path: Path) -> dict:
    """Write a repository payload to output_path; mkdir parents as needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
