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


class TestImplemented:
    """Commands init, eval, and report are real implementations.

    When API keys are configured (via .env), none of the commands should
    fall back to the legacy stub path (exit 2 / "not yet implemented").
    """

    def test_init_proceeds_past_stub_gate(self):
        result = runner.invoke(app, ["init"])
        assert result.exit_code != 2
        assert "not yet implemented" not in result.output.lower()

    def test_eval_proceeds_past_stub_gate(self):
        result = runner.invoke(app, ["eval"])
        assert result.exit_code != 2
        assert "not yet implemented" not in result.output.lower()

    def test_report_proceeds_past_stub_gate(self):
        result = runner.invoke(app, ["report"])
        assert result.exit_code != 2
        assert "not yet implemented" not in result.output.lower()
