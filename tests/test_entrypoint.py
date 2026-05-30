"""Subprocess test of the installed console-script entrypoint (Phase 0).

Exercises [project.scripts] — which in-process CliRunner does NOT test.
"""
from __future__ import annotations

import subprocess
import sys


def test_installed_primer_help_exits_0():
    """The installed `primer` script must exit 0 for --help."""
    result = subprocess.run(
        ["primer", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Expected exit 0 from `primer --help`, got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_installed_primer_help_lists_commands():
    """--help output must list init, eval, report."""
    result = subprocess.run(
        ["primer", "--help"],
        capture_output=True,
        text=True,
    )
    for cmd in ("init", "eval", "report"):
        assert cmd in result.stdout, (
            f"Command {cmd!r} not found in `primer --help` output:\n{result.stdout}"
        )
