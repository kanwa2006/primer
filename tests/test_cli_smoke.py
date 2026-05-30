"""CLI smoke tests -- in-process via Typer CliRunner (Phase 0)."""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from primer.cli import app

runner = CliRunner()


class TestHelp:
    def test_top_level_help_exits_0(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_top_level_help_lists_init(self):
        result = runner.invoke(app, ["--help"])
        assert "init" in result.output

    def test_top_level_help_lists_eval(self):
        result = runner.invoke(app, ["--help"])
        assert "eval" in result.output

    def test_top_level_help_lists_report(self):
        result = runner.invoke(app, ["--help"])
        assert "report" in result.output

    def test_init_help_exits_0(self):
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0

    def test_eval_help_exits_0(self):
        result = runner.invoke(app, ["eval", "--help"])
        assert result.exit_code == 0

    def test_report_help_exits_0(self):
        result = runner.invoke(app, ["report", "--help"])
        assert result.exit_code == 0


class TestStubs:
    """Each stub command exits 2 and prints a 'not yet implemented' notice."""

    def test_init_exits_2(self):
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 2

    def test_init_prints_notice(self):
        result = runner.invoke(app, ["init"])
        assert "not yet implemented" in result.output.lower()

    def test_eval_exits_2(self):
        result = runner.invoke(app, ["eval"])
        assert result.exit_code == 2

    def test_eval_prints_notice(self):
        result = runner.invoke(app, ["eval"])
        assert "not yet implemented" in result.output.lower()

    def test_report_exits_2(self):
        result = runner.invoke(app, ["report"])
        assert result.exit_code == 2

    def test_report_prints_notice(self):
        result = runner.invoke(app, ["report"])
        assert "not yet implemented" in result.output.lower()
