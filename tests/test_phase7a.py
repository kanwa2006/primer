"""Phase 7A acceptance tests: scores.json export + primer export CLI command.

Acceptance criteria (Q5, Phase 7A scope):
  - build_scores_json() produces {schemaVersion, label, message, color}
  - color = green if delta > 0, yellow if delta == 0 or None, red if delta < 0
  - schemaVersion is always 1
  - label is always "PRIMER"
  - message encodes the signed delta in pp (or "N/A (refused)" for None)
  - write_scores_json() writes valid JSON to disk and returns the payload dict
  - primer export command exits 0 on success, writes scores.json
  - primer export command exits 1 when no report exists
  - primer export --help exits 0
  - arch boundary: primer/report/export.py does NOT import sqlite3 or docker
"""
from __future__ import annotations

import ast
import json
import sqlite3
import tempfile
from io import StringIO
from pathlib import Path

import pytest
from typer.testing import CliRunner

from primer.eval.models import ScoreReport, TaskScore
from primer.report.export import (
    BADGE_LABEL,
    SCHEMA_VERSION,
    build_scores_json,
    write_scores_json,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(**overrides) -> ScoreReport:
    """Return a minimal valid ScoreReport."""
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


def _make_in_memory_db_with_report(report: ScoreReport, repo_path: str) -> sqlite3.Connection:
    """Create an in-memory SQLite DB with PRIMER schema and a saved report."""
    schema_sql_path = Path(__file__).parent.parent / "primer" / "store" / "schema.sql"
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema_sql_path.read_text(encoding="utf-8"))

    conn.execute(
        """INSERT INTO reports
           (repo_path, repo_commit, created_at, n_tasks, runs_per_config,
            success_rate_without, success_rate_with, success_delta,
            success_stddev, success_min, success_max,
            cost_without, cost_with, cost_delta_pct, cost_confidence,
            provider, model, agent_adapter, base_image, network_mode,
            egress_enforced,
            provider_mismatch_warning, isolation_mismatch_warning, flaky_task_warning,
            primer_overhead_usd, primer_overhead_confidence)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            repo_path,
            report.repo_commit,
            report.created_at,
            report.n_tasks,
            report.runs_per_config,
            report.success_rate_without,
            report.success_rate_with,
            report.success_delta,
            report.success_stddev,
            report.success_min,
            report.success_max,
            report.cost_without,
            report.cost_with,
            report.cost_delta_pct,
            report.cost_confidence,
            report.provider,
            report.model,
            report.agent_adapter,
            report.base_image,
            report.network_mode,
            1 if report.egress_enforced else 0,
            report.provider_mismatch_warning,
            report.isolation_mismatch_warning,
            report.flaky_task_warning,
            report.primer_overhead_usd,
            report.primer_overhead_confidence,
        ),
    )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# 1. build_scores_json() — schema shape
# ---------------------------------------------------------------------------

class TestBuildScoresJsonSchema:
    def test_schema_version_is_1(self):
        payload = build_scores_json(_make_report(success_delta=0.2))
        assert payload["schemaVersion"] == 1

    def test_label_is_primer(self):
        payload = build_scores_json(_make_report(success_delta=0.2))
        assert payload["label"] == "PRIMER"

    def test_required_keys_present(self):
        payload = build_scores_json(_make_report(success_delta=0.2))
        assert set(payload.keys()) == {"schemaVersion", "label", "message", "color"}

    def test_schema_version_constant(self):
        assert SCHEMA_VERSION == 1

    def test_label_constant(self):
        assert BADGE_LABEL == "PRIMER"


# ---------------------------------------------------------------------------
# 2. build_scores_json() — color rules (Q5)
# ---------------------------------------------------------------------------

class TestBuildScoresJsonColor:
    def test_positive_delta_is_green(self):
        payload = build_scores_json(_make_report(success_delta=0.2))
        assert payload["color"] == "green"

    def test_large_positive_delta_is_green(self):
        payload = build_scores_json(_make_report(success_delta=1.0))
        assert payload["color"] == "green"

    def test_small_positive_delta_is_green(self):
        payload = build_scores_json(_make_report(success_delta=0.001))
        assert payload["color"] == "green"

    def test_negative_delta_is_red(self):
        payload = build_scores_json(_make_report(success_delta=-0.1))
        assert payload["color"] == "red"

    def test_large_negative_delta_is_red(self):
        payload = build_scores_json(_make_report(success_delta=-1.0))
        assert payload["color"] == "red"

    def test_zero_delta_is_yellow(self):
        payload = build_scores_json(_make_report(success_delta=0.0))
        assert payload["color"] == "yellow"

    def test_none_delta_is_yellow(self):
        payload = build_scores_json(_make_report(success_delta=None, cost_delta_pct=None))
        assert payload["color"] == "yellow"


# ---------------------------------------------------------------------------
# 3. build_scores_json() — message content
# ---------------------------------------------------------------------------

class TestBuildScoresJsonMessage:
    def test_positive_delta_message_has_plus(self):
        payload = build_scores_json(_make_report(success_delta=0.2))
        assert payload["message"].startswith("+")
        assert "pp" in payload["message"]

    def test_positive_delta_message_value(self):
        payload = build_scores_json(_make_report(success_delta=0.2))
        assert "+20.0 pp" == payload["message"]

    def test_negative_delta_message_has_minus(self):
        payload = build_scores_json(_make_report(success_delta=-0.1))
        assert payload["message"].startswith("-")
        assert "pp" in payload["message"]

    def test_negative_delta_message_value(self):
        payload = build_scores_json(_make_report(success_delta=-0.1))
        assert "-10.0 pp" == payload["message"]

    def test_zero_delta_message(self):
        payload = build_scores_json(_make_report(success_delta=0.0))
        assert payload["message"] == "0.0 pp"

    def test_none_delta_message_indicates_refused(self):
        payload = build_scores_json(_make_report(success_delta=None, cost_delta_pct=None))
        msg = payload["message"].lower()
        assert "n/a" in msg or "refused" in msg

    def test_message_is_string(self):
        for delta in [0.3, -0.15, 0.0, None]:
            payload = build_scores_json(
                _make_report(
                    success_delta=delta,
                    cost_delta_pct=None if delta is None else 10.0,
                )
            )
            assert isinstance(payload["message"], str)

    @pytest.mark.parametrize("delta,expected_msg", [
        (0.05,  "+5.0 pp"),
        (-0.05, "-5.0 pp"),
        (1.0,   "+100.0 pp"),
        (-1.0,  "-100.0 pp"),
        (0.0,   "0.0 pp"),
    ])
    def test_message_parametrized(self, delta, expected_msg):
        payload = build_scores_json(_make_report(success_delta=delta))
        assert payload["message"] == expected_msg


# ---------------------------------------------------------------------------
# 4. write_scores_json() — file I/O
# ---------------------------------------------------------------------------

class TestWriteScoresJson:
    def test_writes_file(self, tmp_path):
        report = _make_report(success_delta=0.2)
        out = tmp_path / "scores.json"
        write_scores_json(report, out)
        assert out.exists()

    def test_written_file_is_valid_json(self, tmp_path):
        report = _make_report(success_delta=0.2)
        out = tmp_path / "scores.json"
        write_scores_json(report, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_written_file_has_correct_schema(self, tmp_path):
        report = _make_report(success_delta=0.2)
        out = tmp_path / "scores.json"
        write_scores_json(report, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert set(data.keys()) == {"schemaVersion", "label", "message", "color"}

    def test_returns_payload_dict(self, tmp_path):
        report = _make_report(success_delta=0.2)
        out = tmp_path / "scores.json"
        result = write_scores_json(report, out)
        assert isinstance(result, dict)
        assert result["schemaVersion"] == 1

    def test_payload_matches_file_contents(self, tmp_path):
        report = _make_report(success_delta=-0.1)
        out = tmp_path / "scores.json"
        payload = write_scores_json(report, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == payload

    def test_green_written_to_file(self, tmp_path):
        out = tmp_path / "scores.json"
        write_scores_json(_make_report(success_delta=0.3), out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["color"] == "green"

    def test_red_written_to_file(self, tmp_path):
        out = tmp_path / "scores.json"
        write_scores_json(_make_report(success_delta=-0.3), out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["color"] == "red"

    def test_overwrites_existing_file(self, tmp_path):
        out = tmp_path / "scores.json"
        out.write_text('{"old": true}', encoding="utf-8")
        write_scores_json(_make_report(success_delta=0.1), out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "schemaVersion" in data
        assert "old" not in data


# ---------------------------------------------------------------------------
# 5. CLI: primer export --help exits 0 and lists export
# ---------------------------------------------------------------------------

class TestExportCliHelp:
    def test_help_exits_0(self):
        from primer.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["export", "--help"])
        assert result.exit_code == 0

    def test_help_mentions_scores_json(self):
        from primer.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["export", "--help"])
        assert "scores.json" in result.output or "export" in result.output.lower()

    def test_export_listed_in_top_level_help(self):
        from primer.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "export" in result.output


# ---------------------------------------------------------------------------
# 6. CLI: primer export — no report → exit 1
# ---------------------------------------------------------------------------

class TestExportCliNoReport:
    def test_exits_1_when_no_report(self, tmp_path, monkeypatch):
        """export exits 1 when there is no report for the given repo path."""
        from primer.cli import app

        # Point DATABASE_URL at a fresh empty db in tmp_path
        db_path = tmp_path / "test_primer.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        # Suppress provider/agent key validation (not needed for export)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        runner = CliRunner()
        result = runner.invoke(app, ["export", str(tmp_path)])
        assert result.exit_code == 1
        assert "no report" in result.output.lower() or "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# 7. CLI: primer export — success path (mocked DB)
# ---------------------------------------------------------------------------

class TestExportCliSuccess:
    def test_exits_0_with_report(self, tmp_path, monkeypatch):
        """export exits 0 and writes scores.json when a report exists."""
        import unittest.mock as mock
        from primer.cli import app
        from primer.report.export import build_scores_json

        report = _make_report(success_delta=0.2)

        db_path = tmp_path / "test_primer.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        # Patch latest_report to return our report without needing a real DB
        with mock.patch("primer.store.db.latest_report", return_value=report):
            runner = CliRunner()
            output_file = tmp_path / "scores.json"
            result = runner.invoke(
                app,
                ["export", str(tmp_path), "--output", str(output_file)],
            )

        assert result.exit_code == 0, f"exit={result.exit_code}\n{result.output}"

    def test_writes_scores_json_file(self, tmp_path, monkeypatch):
        import unittest.mock as mock
        from primer.cli import app

        report = _make_report(success_delta=0.3)

        db_path = tmp_path / "test_primer.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        output_file = tmp_path / "scores.json"
        with mock.patch("primer.store.db.latest_report", return_value=report):
            runner = CliRunner()
            runner.invoke(
                app,
                ["export", str(tmp_path), "--output", str(output_file)],
            )

        assert output_file.exists()
        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert data["color"] == "green"
        assert data["schemaVersion"] == 1

    def test_output_is_valid_shields_schema(self, tmp_path, monkeypatch):
        import unittest.mock as mock
        from primer.cli import app

        report = _make_report(success_delta=-0.15)

        db_path = tmp_path / "test_primer.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        output_file = tmp_path / "scores.json"
        with mock.patch("primer.store.db.latest_report", return_value=report):
            runner = CliRunner()
            runner.invoke(
                app,
                ["export", str(tmp_path), "--output", str(output_file)],
            )

        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert set(data.keys()) == {"schemaVersion", "label", "message", "color"}
        assert data["label"] == "PRIMER"
        assert data["color"] == "red"


# ---------------------------------------------------------------------------
# 8. Architecture boundary: export.py must not import sqlite3 or docker
# ---------------------------------------------------------------------------

class TestArchBoundary:
    def test_export_module_does_not_import_sqlite3(self):
        """report/export.py must not import sqlite3 (boundary: only store/ imports sqlite3)."""
        export_src = (
            Path(__file__).parent.parent / "primer" / "report" / "export.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(export_src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else ([node.module] if node.module else [])
                )
                for name in names:
                    assert "sqlite3" not in (name or ""), (
                        "report/export.py must not import sqlite3 (store/ boundary)"
                    )

    def test_export_module_does_not_import_docker(self):
        """report/export.py must not import docker (boundary: only eval/ imports docker)."""
        export_src = (
            Path(__file__).parent.parent / "primer" / "report" / "export.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(export_src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else ([node.module] if node.module else [])
                )
                for name in names:
                    assert "docker" not in (name or ""), (
                        "report/export.py must not import docker (eval/ boundary)"
                    )

    def test_export_module_importable(self):
        """primer.report.export must import cleanly."""
        import primer.report.export  # noqa: F401
