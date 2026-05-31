"""PRIMER CLI -- composition root (Phase 4 + Phase 6).

Commands: init, eval, report, history, compare.
This is the ONLY orchestrator -- no other module imports cli.py.

Security invariant: no API key value ever appears in logs/output.
Two-stream rule: PRIMER overhead (generation) is always separate from eval cost.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(
    name="primer",
    help="PRIMER -- a measurement harness for AI coding agent context files.",
    add_completion=False,
)

_console = Console()


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

@app.command()
def init(
    path: str = typer.Argument(".", help="Path to the repository root."),
    provider: Optional[str] = typer.Option(None, help="LLM provider override."),
    model: Optional[str] = typer.Option(None, help="Model override."),
) -> None:
    """Analyse the repo and generate a lean context file (CLAUDE.md / AGENTS.md).

    The filename written is determined by the configured agent adapter (M7).
    Prints the PRIMER overhead cost on a separate line.
    """
    from primer.config import Settings
    from primer.errors import ConfigError, GenerationError
    from primer.ingest.analyzer import analyze_repo
    from primer.llm.factory import get_provider
    from primer.generate.context_writer import write_context
    from primer.eval.adapters import get_adapter

    # Load config + apply overrides
    overrides: dict = {}
    if provider:
        overrides["primer_llm_provider"] = provider
    if model:
        overrides["primer_default_model"] = model

    try:
        config = Settings(**overrides)
        config.validate_runtime()
    except ConfigError as exc:
        msg = str(exc)
        if "_API_KEY" in msg and "to be set" in msg:
            typer.echo(
                "primer init: not yet implemented -- configure API keys first "
                "(see .env.example).",
            )
            raise typer.Exit(code=2)
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1)

    repo_path = str(Path(path).resolve())

    _console.print(f"[bold]Analysing[/bold] {repo_path} ...")
    try:
        profile = analyze_repo(repo_path, config)
    except Exception as exc:
        typer.echo(f"Repo analysis failed: {exc}", err=True)
        raise typer.Exit(code=1)

    _console.print(f"  Languages: {[ls.name for ls in profile.languages]}")
    _console.print(f"  Commit:    {profile.repo_commit}")

    # Determine output filename from the configured adapter (M7)
    try:
        adapter = get_adapter(config.primer_agent)
        filename = adapter.context_filename()
    except ValueError as exc:
        typer.echo(f"Adapter error: {exc}", err=True)
        raise typer.Exit(code=1)

    out_path = Path(repo_path) / filename

    # Safe-write guard: don't clobber an existing file
    if out_path.exists():
        typer.echo(
            f"  {filename} already exists at {out_path}. "
            "Remove it first or use 'primer eval' directly.",
            err=True,
        )
        raise typer.Exit(code=1)

    _console.print(f"[bold]Generating[/bold] {filename} via {config.primer_llm_provider} ...")
    try:
        llm_provider = get_provider(config)
        result = asyncio.run(
            write_context(profile, llm_provider, filename=filename)
        )
    except GenerationError as exc:
        typer.echo(f"Generation failed: {exc}", err=True)
        raise typer.Exit(code=1)
    except Exception as exc:
        typer.echo(f"Unexpected error during generation: {exc}", err=True)
        raise typer.Exit(code=1)

    out_path.write_text(result.content, encoding="utf-8")
    _console.print(f"[green]Wrote {out_path} ({result.lines} lines)[/green]")

    # PRIMER overhead -- shown on a separate line, never confused with eval cost
    from primer.report.render import _format_cost
    overhead_str = _format_cost(result.usage.cost_usd, result.usage.cost_confidence)
    _console.print(f"\n[dim]PRIMER overhead (generation): {overhead_str}[/dim]")


# ---------------------------------------------------------------------------
# eval
# ---------------------------------------------------------------------------

@app.command()
def eval(  # noqa: A001
    path: str = typer.Argument(".", help="Path to the repository root."),
    provider: Optional[str] = typer.Option(None, help="LLM provider override."),
    agent: Optional[str] = typer.Option(None, help="Eval agent override."),
    runs: Optional[int] = typer.Option(None, help="Runs per config override."),
    tasks: Optional[int] = typer.Option(None, help="Task count override."),
) -> None:
    """Run the Dockerised before/after evaluation harness and persist a ScoreReport."""
    from primer.config import Settings
    from primer.errors import (
        ConfigError,
        GenerationError,
        InsufficientTasksError,
    )
    from primer.ingest.analyzer import analyze_repo
    from primer.llm.factory import get_provider
    from primer.generate.context_writer import write_context
    from primer.eval.adapters import get_adapter
    from primer.eval.tasks import derive_tasks
    from primer.eval.images import build_eval_image
    from primer.eval.scorer import score as run_score
    from primer.store.db import init_db, save_report
    from primer.report.render import render_report

    # Load + override config
    overrides: dict = {}
    if provider:
        overrides["primer_llm_provider"] = provider
    if agent:
        overrides["primer_agent"] = agent
    if runs is not None:
        overrides["primer_eval_runs"] = runs
    if tasks is not None:
        overrides["primer_task_count"] = tasks

    try:
        config = Settings(**overrides)
        config.validate_runtime()
    except ConfigError as exc:
        msg = str(exc)
        if "_API_KEY" in msg and "to be set" in msg:
            typer.echo(
                "primer eval: not yet implemented -- configure API keys first "
                "(see .env.example).",
            )
            raise typer.Exit(code=2)
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1)

    repo_path = str(Path(path).resolve())
    _console.print(f"\n[bold]PRIMER eval[/bold] -> {repo_path}\n")

    # Step 1: Ingest
    _console.print("[bold]1/5  Analysing repo ...[/bold]")
    try:
        profile = analyze_repo(repo_path, config)
    except Exception as exc:
        typer.echo(f"Repo analysis failed: {exc}", err=True)
        raise typer.Exit(code=1)
    _console.print(
        f"     Commit {profile.repo_commit} | "
        f"langs {[ls.name for ls in profile.languages]}"
    )

    # Step 2: Generate context file (PRIMER overhead)
    try:
        eval_adapter = get_adapter(config.primer_agent)
    except ValueError as exc:
        typer.echo(f"Adapter error: {exc}", err=True)
        raise typer.Exit(code=1)

    filename = eval_adapter.context_filename()
    _console.print(f"[bold]2/5  Generating {filename} ...[/bold]")
    try:
        llm_provider = get_provider(config)
        gen_result = asyncio.run(
            write_context(profile, llm_provider, filename=filename)
        )
    except GenerationError as exc:
        typer.echo(f"Generation failed: {exc}", err=True)
        raise typer.Exit(code=1)

    from primer.report.render import _format_cost
    overhead_str = _format_cost(
        gen_result.usage.cost_usd, gen_result.usage.cost_confidence
    )
    _console.print(
        f"     Generated {gen_result.lines} lines  "
        f"[dim](overhead: {overhead_str})[/dim]"
    )

    # Step 3: Derive + validate tasks
    _console.print("[bold]3/5  Deriving tasks ...[/bold]")
    try:
        task_list = derive_tasks(
            profile=profile,
            repo_path=repo_path,
            n=config.primer_task_count,
            min_tasks=config.primer_min_tasks,
        )
    except InsufficientTasksError as exc:
        typer.echo(f"\n{exc}", err=True)
        raise typer.Exit(code=1)
    except Exception as exc:
        typer.echo(f"Task derivation failed: {exc}", err=True)
        raise typer.Exit(code=1)
    _console.print(f"     {len(task_list)} validated tasks ready")

    # Step 4: Build eval image
    _console.print("[bold]4/5  Building eval image ...[/bold]")
    try:
        image_tag = build_eval_image(repo_path, profile, config)
    except Exception as exc:
        typer.echo(f"Image build failed: {exc}", err=True)
        raise typer.Exit(code=1)
    _console.print(f"     Image: {image_tag}")

    # Step 5: Score
    _console.print(
        f"[bold]5/5  Running {len(task_list)} tasks x "
        f"{{without, with}} x {config.primer_eval_runs} runs (sequential) ...[/bold]"
    )
    try:
        score_report = run_score(
            profile=profile,
            repo_path=repo_path,
            tasks=task_list,
            config=config,
            adapter=eval_adapter,
            image_tag=image_tag,
            context_content=gen_result.content,
            provider=config.primer_llm_provider,
            model=config.primer_default_model,
            primer_overhead_usd=gen_result.usage.cost_usd,
            primer_overhead_confidence=gen_result.usage.cost_confidence,
            runs_per_config=config.primer_eval_runs,
        )
    except Exception as exc:
        typer.echo(f"Eval failed: {exc}", err=True)
        raise typer.Exit(code=1)

    # Persist
    try:
        conn = init_db(config)
        save_report(
            conn=conn,
            report=score_report,
            tasks=task_list,
            runs=[],  # scorer consumed the individual RunResults internally
            profile=profile,
            repo_path=repo_path,
        )
        conn.close()
    except Exception as exc:
        typer.echo(f"Warning: failed to persist report: {exc}", err=True)
        # Don't abort -- still render

    # Render
    render_report(score_report, fmt="text", console=_console)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@app.command()
def report(
    path: str = typer.Argument(".", help="Path to the repository root."),
    format: str = typer.Option("text", help="Output format: text or json."),
) -> None:
    """Render the latest persisted score report for a repository."""
    from primer.config import Settings
    from primer.errors import ConfigError
    from primer.store.db import init_db, latest_report as _latest
    from primer.report.render import render_report

    try:
        config = Settings()
        config.validate_runtime()
    except ConfigError as exc:
        msg = str(exc)
        if "_API_KEY" in msg and "to be set" in msg:
            typer.echo(
                "primer report: not yet implemented -- configure API keys first "
                "(see .env.example).",
            )
            raise typer.Exit(code=2)
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1)

    repo_path = str(Path(path).resolve())

    try:
        conn = init_db(config)
        score_report = _latest(conn, repo_path)
        conn.close()
    except Exception as exc:
        typer.echo(f"Database error: {exc}", err=True)
        raise typer.Exit(code=1)

    if score_report is None:
        typer.echo(
            f"No report found for {repo_path}. "
            "Run 'primer eval .' first.",
            err=True,
        )
        raise typer.Exit(code=1)

    fmt = format if format in ("text", "json") else "text"
    render_report(score_report, fmt=fmt, console=_console)


# ---------------------------------------------------------------------------
# history  (Phase 6)
# ---------------------------------------------------------------------------

@app.command()
def history(
    path: Optional[str] = typer.Argument(
        None,
        help="Path to the repository root (omit to list all repos).",
    ),
    limit: int = typer.Option(20, help="Maximum number of reports to show."),
) -> None:
    """List past evaluation reports stored in the database.

    Shows report ID, repo, commit, date, delta, provider/model, and agent.
    Use the report ID with 'primer compare' to diff two runs.
    """
    from primer.config import Settings
    from primer.errors import ConfigError
    from primer.store.db import init_db, list_reports
    from primer.report.render import render_history_table

    try:
        config = Settings()
        # history only needs DB access -- skip provider/agent key validation
    except ConfigError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1)

    repo_path = str(Path(path).resolve()) if path is not None else None

    try:
        conn = init_db(config)
        rows = list_reports(conn, repo_path=repo_path, limit=limit)
        conn.close()
    except Exception as exc:
        typer.echo(f"Database error: {exc}", err=True)
        raise typer.Exit(code=1)

    if not rows:
        msg = (
            f"No reports found for {repo_path}."
            if repo_path
            else "No reports found. Run 'primer eval .' first."
        )
        typer.echo(msg)
        raise typer.Exit(code=0)

    render_history_table(rows, console=_console)


# ---------------------------------------------------------------------------
# compare  (Phase 6)
# ---------------------------------------------------------------------------

@app.command()
def compare(
    report_a: int = typer.Argument(help="ID of the first report (baseline)."),
    report_b: int = typer.Argument(help="ID of the second report (new)."),
) -> None:
    """Compare two persisted reports side by side.

    Mismatch guard (Q9d): if the two reports used different providers or models,
    the cross-report delta is refused and a warning is shown instead.
    Isolation mismatches are also flagged.
    """
    from primer.config import Settings
    from primer.errors import ConfigError
    from primer.store.db import init_db, get_report_by_id
    from primer.report.render import render_compare

    try:
        config = Settings()
    except ConfigError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1)

    try:
        conn = init_db(config)
        ra = get_report_by_id(conn, report_a)
        rb = get_report_by_id(conn, report_b)
        conn.close()
    except Exception as exc:
        typer.echo(f"Database error: {exc}", err=True)
        raise typer.Exit(code=1)

    if ra is None:
        typer.echo(f"Report ID {report_a} not found.", err=True)
        raise typer.Exit(code=1)
    if rb is None:
        typer.echo(f"Report ID {report_b} not found.", err=True)
        raise typer.Exit(code=1)

    render_compare(
        report_a=ra,
        report_b=rb,
        id_a=report_a,
        id_b=report_b,
        console=_console,
    )
