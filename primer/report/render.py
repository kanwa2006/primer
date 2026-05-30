"""Report rendering — pure output module (Phase 4).

render_report() receives a fully-computed ScoreReport and writes to stdout.

Contracts (Session 2 §4.12, Decision Addendum M3):
  - NO computation. All numbers come from the ScoreReport.
  - Signed Δ colored by sign (green >0, yellow ~0/noise, red <0).
  - M3 within-noise label: flag when |delta| ≤ max(1/n_tasks, stddev).
  - None delta prints the refusal reason, never a fabricated number.
  - Variance (stddev/min/max) always shown, never hidden.
  - Cost displayed with the correct confidence qualifier:
      exact   → plain  (e.g. "$0.0123")
      estimated → "≈ $0.0123 (estimated)"
      free    → "local (no cost)"
  - PRIMER overhead on a SEPARATE line, never added to eval cost.
  - All *_warning fields surfaced prominently.
  - JSON format available as an alternative.
"""
from __future__ import annotations

import json
import dataclasses
from typing import Literal

from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text

from primer.eval.models import ScoreReport

_console = Console()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_report(
    report: ScoreReport,
    fmt: Literal["text", "json"] = "text",
    *,
    console: Console | None = None,
) -> None:
    """Render a ScoreReport to stdout.

    Args:
        report: Fully-computed ScoreReport (no computation performed here).
        fmt:    "text" (rich, default) or "json".
        console: Override rich Console (used in tests).
    """
    if fmt == "json":
        _render_json(report)
        return
    _render_text(report, console=console or _console)


# ---------------------------------------------------------------------------
# JSON rendering
# ---------------------------------------------------------------------------

def _render_json(report: ScoreReport) -> None:
    """Emit ScoreReport as JSON to stdout."""
    def _default(obj):
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        return str(obj)

    print(json.dumps(dataclasses.asdict(report), default=_default, indent=2))


# ---------------------------------------------------------------------------
# Rich text rendering
# ---------------------------------------------------------------------------

def _render_text(report: ScoreReport, *, console: Console) -> None:
    """Render a full rich text report."""
    console.print()
    console.rule("[bold]PRIMER Score Report[/bold]")
    console.print()

    # ── Provenance ──────────────────────────────────────────────────────────
    console.print(f"[dim]Repo commit:[/dim]  {report.repo_commit}")
    console.print(f"[dim]Evaluated:[/dim]    {report.created_at}")
    console.print(f"[dim]Provider:[/dim]     {report.provider} / {report.model}")
    console.print(f"[dim]Agent:[/dim]        {report.agent_adapter}")
    console.print(f"[dim]Base image:[/dim]   {report.base_image}")
    console.print(f"[dim]Network:[/dim]      {report.network_mode}"
                  + (" [green](egress enforced)[/green]" if report.egress_enforced
                     else " [yellow](egress NOT enforced)[/yellow]"))
    console.print(f"[dim]Tasks / runs:[/dim] {report.n_tasks} tasks × {report.runs_per_config} runs each")
    console.print()

    # ── Warnings ─────────────────────────────────────────────────────────────
    warnings = [
        report.provider_mismatch_warning,
        report.isolation_mismatch_warning,
        report.flaky_task_warning,
    ]
    for w in warnings:
        if w:
            console.print(f"[bold yellow]⚠  WARNING:[/bold yellow] {w}")
    if any(warnings):
        console.print()

    # ── Headline delta ───────────────────────────────────────────────────────
    console.rule("[bold]Headline Result[/bold]")
    console.print()

    if report.success_delta is None:
        # Refused (mismatch) — never fabricate a number
        console.print(
            "[bold red]Δ success = N/A[/bold red]  "
            "(delta refused — provider/model mismatch across compared runs)"
        )
    else:
        delta_text = _format_delta(report.success_delta)
        noise_label = _noise_label(report)
        console.print(f"  Success  WITHOUT file: {report.success_rate_without:.1%}")
        console.print(f"  Success  WITH    file: {report.success_rate_with:.1%}")
        console.print(f"  {delta_text}", end="")
        if noise_label:
            console.print(f"  [yellow]{noise_label}[/yellow]", end="")
        console.print()

    # Variance — never collapsed
    console.print(
        f"\n  Variance: stddev={report.success_stddev:.3f}  "
        f"min={report.success_min:.1%}  max={report.success_max:.1%}"
    )
    console.print()

    # ── Cost (eval stream only) ───────────────────────────────────────────────
    console.rule("[bold]Eval Cost  [dim](agent tokens only)[/dim][/bold]")
    console.print()
    console.print(f"  Without file: {_format_cost(report.cost_without, report.cost_confidence)}")
    console.print(f"  With    file: {_format_cost(report.cost_with, report.cost_confidence)}")
    if report.cost_delta_pct is None:
        console.print("  Cost Δ%:      N/A (refused — mismatch)")
    else:
        sign = "+" if report.cost_delta_pct > 0 else ""
        console.print(f"  Cost Δ%:      {sign}{report.cost_delta_pct:.1f}%")
    console.print()

    # ── PRIMER overhead — SEPARATE LINE, never summed into eval cost ─────────
    console.rule("[bold]PRIMER Overhead  [dim](file generation; NOT eval cost)[/dim][/bold]")
    console.print()
    console.print(
        f"  Generation cost: "
        f"{_format_cost(report.primer_overhead_usd, report.primer_overhead_confidence)}"
    )
    console.print()

    # ── Per-task breakdown ───────────────────────────────────────────────────
    if report.per_task:
        console.rule("[bold]Per-Task Breakdown[/bold]")
        console.print()
        _render_per_task_table(report, console=console)
        console.print()

    console.rule()
    console.print()


# ---------------------------------------------------------------------------
# Per-task table
# ---------------------------------------------------------------------------

def _render_per_task_table(report: ScoreReport, *, console: Console) -> None:
    """Render the per-task pass-rate table."""
    table = Table(box=box.SIMPLE_HEAD, show_footer=False)
    table.add_column("Task ID", style="dim", no_wrap=False, max_width=40)
    table.add_column("Type", style="dim", no_wrap=True)
    table.add_column("Without", justify="right")
    table.add_column("With", justify="right")
    table.add_column("Δ", justify="right")
    table.add_column("Runs", justify="right", style="dim")
    table.add_column("Flaky?", justify="center", style="dim")

    # When the report-level delta is refused (None), per-task deltas are also
    # meaningless — show N/A to avoid displaying fabricated numbers.
    delta_refused = report.success_delta is None
    for ts in report.per_task:
        if ts.delta is None or delta_refused:
            delta_cell = Text("N/A", style="yellow")
        else:
            delta_cell = _delta_text(ts.delta)

        table.add_row(
            ts.task_id,
            ts.task_type,
            f"{ts.pass_rate_without:.1%}",
            f"{ts.pass_rate_with:.1%}",
            delta_cell,
            str(ts.runs),
            "⚠" if ts.flaky_any else "—",
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Formatting helpers (NO computation — only presentation)
# ---------------------------------------------------------------------------

def _format_delta(delta: float) -> str:
    """Format signed headline delta with rich colour markup."""
    pct = delta * 100.0
    sign = "+" if pct > 0 else ""
    if pct > 0:
        colour = "green"
    elif pct < 0:
        colour = "red"
    else:
        colour = "yellow"
    return f"[bold {colour}]Δ success = {sign}{pct:.1f} pp[/bold {colour}]"


def _delta_text(delta: float) -> Text:
    """Rich Text for a per-task delta cell."""
    pct = delta * 100.0
    sign = "+" if pct > 0 else ""
    label = f"{sign}{pct:.1f} pp"
    if pct > 0:
        return Text(label, style="green")
    elif pct < 0:
        return Text(label, style="red")
    else:
        return Text(label, style="yellow")


def _format_cost(cost_usd: float, confidence: str) -> str:
    """Format a cost value with the appropriate confidence qualifier.

    exact     → "$0.0123"
    estimated → "≈ $0.0123 (estimated)"
    free      → "local (no cost)"
    """
    if confidence == "free":
        return "local (no cost)"
    formatted = f"${cost_usd:.4f}"
    if confidence == "estimated":
        return f"≈ {formatted} (estimated)"
    # exact
    return formatted


def _noise_label(report: ScoreReport) -> str | None:
    """M3 within-noise label.

    Flag the headline when |success_delta| ≤ max(1/n_tasks, success_stddev).
    Escalate to "driven by flaky task(s)" if contributing flips are flaky.
    Returns None if outside noise (i.e., clearly meaningful).
    """
    if report.success_delta is None:
        return None

    n = report.n_tasks if report.n_tasks > 0 else 1
    quantization_floor = 1.0 / n
    noise_threshold = max(quantization_floor, report.success_stddev)

    if abs(report.success_delta) <= noise_threshold:
        # Check if any per-task flips coincide with flaky tasks
        flaky_any = any(ts.flaky_any for ts in report.per_task)
        if flaky_any:
            return "⚑ within measurement noise — driven by flaky task(s)"
        return "⚑ within measurement noise — not distinguishable from zero"
    return None
