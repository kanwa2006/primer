"""Report rendering — pure output module.

render_report() receives a fully-computed ScoreReport and writes to stdout.

Contracts:
  - NO computation. All numbers come from the ScoreReport.
  - Signed delta colored by sign (green >0, yellow ~0/noise, red <0).
  - Within-noise label: flag when |delta| <= max(1/n_tasks, stddev).
  - None delta prints the refusal reason, never a fabricated number.
  - Variance (stddev/min/max) always shown, never hidden.
  - Cost displayed with the correct confidence qualifier:
      exact     -> plain  (e.g. "$0.0123")
      estimated -> "≈ $0.0123 (estimated)"
      free      -> "local (no cost)"
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

    # -- Provenance --
    console.print(f"[dim]Repo commit:[/dim]  {report.repo_commit}")
    console.print(f"[dim]Evaluated:[/dim]    {report.created_at}")
    console.print(f"[dim]Provider:[/dim]     {report.provider} / {report.model}")
    console.print(f"[dim]Agent:[/dim]        {report.agent_adapter}")
    console.print(f"[dim]Base image:[/dim]   {report.base_image}")
    console.print(
        f"[dim]Network:[/dim]      {report.network_mode}"
        + (
            " [green](egress enforced)[/green]"
            if report.egress_enforced
            else " [yellow](egress NOT enforced)[/yellow]"
        )
    )
    console.print(
        f"[dim]Tasks / runs:[/dim] {report.n_tasks} tasks x {report.runs_per_config} runs each"
    )
    console.print()

    # -- Warnings --
    warnings = [
        report.provider_mismatch_warning,
        report.isolation_mismatch_warning,
        report.flaky_task_warning,
    ]
    for w in warnings:
        if w:
            console.print(f"[bold yellow]WARNING:[/bold yellow] {w}")
    if any(warnings):
        console.print()

    # -- Headline delta --
    console.rule("[bold]Headline Result[/bold]")
    console.print()

    if report.success_delta is None:
        # Refused (mismatch) -- never fabricate a number
        console.print(
            "[bold red]delta success = N/A[/bold red]  "
            "(delta refused -- provider/model mismatch across compared runs)"
        )
    else:
        delta_text = _format_delta(report.success_delta)
        noise_label = _noise_label(report)
        console.print(f"  Success  WITHOUT file: {report.success_rate_without:.1%}")
        console.print(f"  Success  WITH    file: {report.success_rate_with:.1%}")
        console.print(f"  {delta_text}", end="")
        if noise_label:
            console.print(f"  [cyan]{noise_label}[/cyan]", end="")
        console.print()

    # Variance -- never collapsed
    console.print(
        f"\n  Variance: stddev={report.success_stddev:.3f}  "
        f"min={report.success_min:.1%}  max={report.success_max:.1%}"
    )
    console.print()

    # -- Cost (eval stream only) --
    console.rule("[bold]Eval Cost  [dim](agent tokens only)[/dim][/bold]")
    console.print()
    console.print(
        f"  Without file: {_format_cost(report.cost_without, report.cost_confidence)}"
    )
    console.print(
        f"  With    file: {_format_cost(report.cost_with, report.cost_confidence)}"
    )
    if report.cost_delta_pct is None:
        console.print("  Cost delta%:  N/A (refused -- mismatch)")
    else:
        sign = "+" if report.cost_delta_pct > 0 else ""
        console.print(f"  Cost delta%:  {sign}{report.cost_delta_pct:.1f}%")
    console.print()

    # -- PRIMER overhead -- SEPARATE LINE, never summed into eval cost --
    console.rule(
        "[bold]PRIMER Overhead  [dim](file generation; NOT eval cost)[/dim][/bold]"
    )
    console.print()
    console.print(
        f"  Generation cost: "
        f"{_format_cost(report.primer_overhead_usd, report.primer_overhead_confidence)}"
    )
    console.print()

    # -- Per-task breakdown --
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
    table.add_column("Delta", justify="right")
    table.add_column("Runs", justify="right", style="dim")
    table.add_column("Flaky?", justify="center", style="dim")

    # When the report-level delta is refused (None), per-task deltas are also
    # meaningless -- show N/A to avoid displaying fabricated numbers.
    delta_refused = report.success_delta is None
    for ts in report.per_task:
        if ts.delta is None or delta_refused:
            delta_cell = Text("N/A", style="grey62")
        else:
            delta_cell = _delta_text(ts.delta)

        table.add_row(
            ts.task_id,
            ts.task_type,
            f"{ts.pass_rate_without:.1%}",
            f"{ts.pass_rate_with:.1%}",
            delta_cell,
            str(ts.runs),
            "!" if ts.flaky_any else "-",
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Formatting helpers (NO computation -- only presentation)
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
        colour = "cyan"
    return f"[bold {colour}]delta success = {sign}{pct:.1f} pp[/bold {colour}]"


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
        return Text(label, style="cyan")


def _format_cost(cost_usd: float, confidence: str) -> str:
    """Format a cost value with the appropriate confidence qualifier.

    exact     -> "$0.0123"
    estimated -> "≈ $0.0123 (estimated)"
    free      -> "local (no cost)"
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

    Flag the headline when |success_delta| <= max(1/n_tasks, success_stddev).
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
            return "within measurement noise -- driven by flaky task(s)"
        return "within measurement noise -- not distinguishable from zero"
    return None


# ---------------------------------------------------------------------------
# History table
# ---------------------------------------------------------------------------

def render_history_table(
    rows: list[dict],
    *,
    console: "Console | None" = None,
) -> None:
    """Render a summary table of past reports (output of list_reports()).

    Columns: ID, repo_path, commit, evaluated_at, tasks, runs_per_cfg,
             delta, provider/model, agent.
    """
    con = console or _console
    if not rows:
        con.print("[dim]No reports found.[/dim]")
        return

    table = Table(box=box.SIMPLE_HEAD, show_footer=False, title="Report History")
    table.add_column("ID", justify="right", style="dim", no_wrap=True)
    table.add_column("Repo", no_wrap=False, max_width=30)
    table.add_column("Commit", style="dim", no_wrap=True, max_width=10)
    table.add_column("Evaluated At", style="dim", no_wrap=True)
    table.add_column("Tasks", justify="right", style="dim")
    table.add_column("Runs/cfg", justify="right", style="dim")
    table.add_column("Delta", justify="right")
    table.add_column("Provider/Model", no_wrap=True, max_width=30)
    table.add_column("Agent", style="dim", no_wrap=True)

    for r in rows:
        delta = r.get("success_delta")
        if delta is None:
            delta_cell = Text("N/A", style="grey62")
        else:
            delta_cell = _delta_text(float(delta))

        commit = str(r.get("repo_commit", ""))[:8]
        provider_model = f"{r.get('provider', '')} / {r.get('model', '')}"

        table.add_row(
            str(r.get("id", "")),
            str(r.get("repo_path", "")),
            commit,
            str(r.get("created_at", "")),
            str(r.get("n_tasks", "")),
            str(r.get("runs_per_config", "")),
            delta_cell,
            provider_model,
            str(r.get("agent_adapter", "")),
        )

    con.print(table)


# ---------------------------------------------------------------------------
# Compare two reports
# ---------------------------------------------------------------------------

def render_compare(
    report_a: "ScoreReport",
    report_b: "ScoreReport",
    id_a: int,
    id_b: int,
    *,
    console: "Console | None" = None,
) -> None:
    """Render a side-by-side comparison of two ScoreReports.

    Q9d mismatch guard: if provider/model differ, cross-report delta is refused
    (success_delta shown as N/A, a prominent warning is printed).
    Isolation mismatch: flag if network_mode/egress_enforced/base_image differ.
    """
    from typing import TYPE_CHECKING

    con = console or _console

    con.print()
    con.rule(f"[bold]PRIMER Compare: Report #{id_a} vs #{id_b}[/bold]")
    con.print()

    # -- Provenance table --
    prov = Table(box=box.SIMPLE_HEAD, show_footer=False)
    prov.add_column("Field", style="dim")
    prov.add_column(f"Report #{id_a} (baseline)", no_wrap=True)
    prov.add_column(f"Report #{id_b} (new)", no_wrap=True)

    def _cmp(a_val, b_val) -> tuple[str, str]:
        sa, sb = str(a_val), str(b_val)
        if sa != sb:
            return f"[yellow]{sa}[/yellow]", f"[yellow]{sb}[/yellow]"
        return sa, sb

    for field, va, vb in [
        ("Repo commit", report_a.repo_commit, report_b.repo_commit),
        ("Evaluated at", report_a.created_at, report_b.created_at),
        ("Provider", report_a.provider, report_b.provider),
        ("Model", report_a.model, report_b.model),
        ("Agent", report_a.agent_adapter, report_b.agent_adapter),
        ("Base image", report_a.base_image, report_b.base_image),
        ("Network mode", report_a.network_mode, report_b.network_mode),
        ("Egress enforced", str(report_a.egress_enforced), str(report_b.egress_enforced)),
        ("Tasks", str(report_a.n_tasks), str(report_b.n_tasks)),
        ("Runs/config", str(report_a.runs_per_config), str(report_b.runs_per_config)),
    ]:
        ca, cb = _cmp(va, vb)
        prov.add_row(field, ca, cb)

    con.print(prov)
    con.print()

    # -- Q9d mismatch guard: refuse cross-report delta if provider/model differ --
    provider_mismatch = (
        report_a.provider != report_b.provider
        or report_a.model != report_b.model
    )
    isolation_mismatch = (
        report_a.network_mode != report_b.network_mode
        or report_a.egress_enforced != report_b.egress_enforced
        or report_a.base_image != report_b.base_image
    )

    if provider_mismatch:
        con.print(
            "[bold red]WARNING:[/bold red] Provider/model mismatch between reports. "
            "Cross-report success delta is refused -- comparison would be meaningless."
        )
        con.print()

    if isolation_mismatch:
        con.print(
            "[bold yellow]WARNING:[/bold yellow] Isolation mismatch between reports "
            "(network_mode, egress_enforced, or base_image differ). "
            "Results may not be comparable."
        )
        con.print()

    # -- Headline comparison --
    con.rule("[bold]Headline Results[/bold]")
    con.print()

    con.print(f"  Report #{id_a}  success without: {report_a.success_rate_without:.1%}  "
              f"with: {report_a.success_rate_with:.1%}  "
              f"delta: {_format_delta(report_a.success_delta) if report_a.success_delta is not None else '[grey62]N/A[/grey62]'}")
    con.print(f"  Report #{id_b}  success without: {report_b.success_rate_without:.1%}  "
              f"with: {report_b.success_rate_with:.1%}  "
              f"delta: {_format_delta(report_b.success_delta) if report_b.success_delta is not None else '[grey62]N/A[/grey62]'}")
    con.print()

    if provider_mismatch:
        con.print("  Cross-report delta: [bold red]N/A[/bold red] (refused -- provider/model mismatch)")
    else:
        if report_a.success_delta is not None and report_b.success_delta is not None:
            cross_delta = report_b.success_delta - report_a.success_delta
            pct = cross_delta * 100.0
            sign = "+" if pct > 0 else ""
            colour = "green" if pct > 0 else ("red" if pct < 0 else "cyan")
            con.print(
                f"  Cross-report delta (B minus A): "
                f"[bold {colour}]{sign}{pct:.1f} pp[/bold {colour}]"
            )
        else:
            con.print("  Cross-report delta: [grey62]N/A[/grey62] (one or both reports refused delta)")
    con.print()

    # -- Variance comparison --
    con.print(
        f"  Variance A: stddev={report_a.success_stddev:.3f}  "
        f"min={report_a.success_min:.1%}  max={report_a.success_max:.1%}"
    )
    con.print(
        f"  Variance B: stddev={report_b.success_stddev:.3f}  "
        f"min={report_b.success_min:.1%}  max={report_b.success_max:.1%}"
    )
    con.print()

    # -- Cost comparison --
    con.rule("[bold]Eval Cost[/bold]")
    con.print()
    con.print(f"  Report #{id_a}:  without={_format_cost(report_a.cost_without, report_a.cost_confidence)}  "
              f"with={_format_cost(report_a.cost_with, report_a.cost_confidence)}")
    con.print(f"  Report #{id_b}:  without={_format_cost(report_b.cost_without, report_b.cost_confidence)}  "
              f"with={_format_cost(report_b.cost_with, report_b.cost_confidence)}")
    con.print()

    con.rule()
    con.print()
