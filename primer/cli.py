"""PRIMER CLI — composition root.

Phase 0: stub commands only.
Each stub prints a "not yet implemented" notice and exits with code 2.
--help (top-level and per-subcommand) exits 0.
"""
from __future__ import annotations

import sys
from typing import Optional

import typer

app = typer.Typer(
    name="primer",
    help="PRIMER — a measurement harness for AI coding agent context files.",
    add_completion=False,
)


@app.command()
def init(
    path: str = typer.Argument(".", help="Path to the repository root."),
    provider: Optional[str] = typer.Option(None, help="LLM provider override."),
    model: Optional[str] = typer.Option(None, help="Model override."),
) -> None:
    """Generate a lean context file for the repository (Phase 2)."""
    typer.echo(
        "primer init: not yet implemented (Phase 2). "
        "Run after Phase 2 is complete."
    )
    raise typer.Exit(code=2)


@app.command()
def eval(
    path: str = typer.Argument(".", help="Path to the repository root."),
    provider: Optional[str] = typer.Option(None, help="LLM provider override."),
    agent: Optional[str] = typer.Option(None, help="Eval agent override."),
    runs: Optional[int] = typer.Option(None, help="Runs per config override."),
    tasks: Optional[int] = typer.Option(None, help="Task count override."),
) -> None:
    """Run the before/after evaluation harness (Phase 3)."""
    typer.echo(
        "primer eval: not yet implemented (Phase 3). "
        "Run after Phase 3 is complete."
    )
    raise typer.Exit(code=2)


@app.command()
def report(
    path: str = typer.Argument(".", help="Path to the repository root."),
    format: str = typer.Option("text", help="Output format: text or json."),
) -> None:
    """Render the latest score report (Phase 4)."""
    typer.echo(
        "primer report: not yet implemented (Phase 4). "
        "Run after Phase 4 is complete."
    )
    raise typer.Exit(code=2)
