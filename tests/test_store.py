"""Tests for store migrations, run history, comparison, and mismatch guards."""
from __future__ import annotations

import sqlite3
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from primer.eval.models import ScoreReport, TaskScore
from primer.store.migrations import (
    CURRENT_SCHEMA_VERSION,
    SchemaTooNewError,
    apply_migrations,
    get_schema_version,
    set_schema_version,
)
from primer.report.render import render_history_table, render_compare


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_in_memory_db() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the PRIMER schema applied."""
    schema_sql_path = Path(__file__).parent.parent / "primer" / "store" / "schema.sql"
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema_sql_path.read_text(encoding="utf-8"))
    return conn


def _make_score_report(**overrides) -> ScoreReport:
    """Return a minimal valid ScoreReport."""
    defaults = dict(
        repo_commit="abc12345",
        created_at="2024-01-01T00:00:00Z",
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
        cost_confidence="estimated",
        per_task=[],
        provider="anthropic",
        model="claude-opus-4-6",
        agent_adapter="claude_code",
        base_image="sha256:abc123",
        network_mode="primer-internal",
        egress_enforced=True,
    )
    defaults.update(overrides)
    return ScoreReport(**defaults)


def _make_profile(repo_commit: str = "abc12345"):
    """Return a minimal RepoProfile."""
    from primer.ingest.models import RepoProfile
    return RepoProfile(repo_commit=repo_commit)


def _capture_console():
    """Return (Console, StringIO) for output capture."""
    buf = StringIO()
    console = Console(file=buf, width=120, highlight=False, markup=True)
    return console, buf


# ---------------------------------------------------------------------------
# Tests: get_schema_version
# ---------------------------------------------------------------------------

class TestGetSchemaVersion:
    def test_returns_zero_when_meta_table_missing(self):
        conn = sqlite3.connect(":memory:")
        assert get_schema_version(conn) == 0

    def test_returns_zero_when_meta_empty(self):
        conn = _make_in_memory_db()
        assert get_schema_version(conn) == 0

    def test_returns_stored_version(self):
        conn = _make_in_memory_db()
        set_schema_version(conn, 1)
        assert get_schema_version(conn) == 1

    def test_handles_non_integer_gracefully(self):
        conn = _make_in_memory_db()
        conn.execute(
            "INSERT INTO _meta (key, value) VALUES ('schema_version', 'banana')"
        )
        conn.commit()
        assert get_schema_version(conn) == 0


# ---------------------------------------------------------------------------
# Tests: set_schema_version
# ---------------------------------------------------------------------------

class TestSetSchemaVersion:
    def test_sets_version(self):
        conn = _make_in_memory_db()
        set_schema_version(conn, 1)
        assert get_schema_version(conn) == 1

    def test_upsert_updates_existing(self):
        conn = _make_in_memory_db()
        set_schema_version(conn, 1)
        set_schema_version(conn, 2)
        assert get_schema_version(conn) == 2


# ---------------------------------------------------------------------------
# Tests: apply_migrations
# ---------------------------------------------------------------------------

class TestApplyMigrations:
    def test_idempotent_on_fresh_db(self):
        conn = _make_in_memory_db()
        apply_migrations(conn)
        apply_migrations(conn)  # second call must not raise
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION

    def test_raises_schema_too_new(self):
        conn = _make_in_memory_db()
        future_version = CURRENT_SCHEMA_VERSION + 1
        set_schema_version(conn, future_version)
        with pytest.raises(SchemaTooNewError):
            apply_migrations(conn)

    def test_sets_schema_version_to_current(self):
        conn = _make_in_memory_db()
        apply_migrations(conn)
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION

    def test_schema_too_new_error_message(self):
        conn = _make_in_memory_db()
        set_schema_version(conn, 999)
        with pytest.raises(SchemaTooNewError, match="999"):
            apply_migrations(conn)


# ---------------------------------------------------------------------------
# Tests: store.db — list_reports, get_report_by_id
# ---------------------------------------------------------------------------

class TestListReports:
    def test_empty_db_returns_empty_list(self):
        from primer.store.db import list_reports
        conn = _make_in_memory_db()
        assert list_reports(conn) == []

    def test_returns_summary_rows(self):
        from primer.store.db import list_reports, save_report

        conn = _make_in_memory_db()
        report = _make_score_report()
        profile = _make_profile()
        save_report(conn, report, [], [], profile, "/tmp/repo")
        rows = list_reports(conn)
        assert len(rows) == 1
        row = rows[0]
        assert "id" in row
        assert row["repo_path"] == "/tmp/repo"
        assert row["n_tasks"] == 5
        assert row["provider"] == "anthropic"

    def test_filters_by_repo_path(self):
        from primer.store.db import list_reports, save_report

        conn = _make_in_memory_db()
        report = _make_score_report()
        save_report(conn, report, [], [], _make_profile(), "/repo/a")
        save_report(conn, report, [], [], _make_profile(), "/repo/b")

        rows_a = list_reports(conn, repo_path="/repo/a")
        assert len(rows_a) == 1
        assert rows_a[0]["repo_path"] == "/repo/a"

    def test_limit_respected(self):
        from primer.store.db import list_reports, save_report

        conn = _make_in_memory_db()
        report = _make_score_report()
        for _ in range(5):
            save_report(conn, report, [], [], _make_profile(), "/tmp/repo")

        rows = list_reports(conn, limit=3)
        assert len(rows) == 3

    def test_summary_row_has_expected_keys(self):
        from primer.store.db import list_reports, save_report

        conn = _make_in_memory_db()
        save_report(conn, _make_score_report(), [], [], _make_profile(), "/tmp/repo")
        rows = list_reports(conn)
        row = rows[0]
        for key in ("id", "repo_path", "repo_commit", "created_at", "n_tasks",
                    "runs_per_config", "success_delta", "provider", "model", "agent_adapter"):
            assert key in row, f"Missing key: {key}"


class TestGetReportById:
    def test_returns_none_for_missing(self):
        from primer.store.db import get_report_by_id
        conn = _make_in_memory_db()
        assert get_report_by_id(conn, 999) is None

    def test_returns_score_report(self):
        from primer.store.db import get_report_by_id, save_report

        conn = _make_in_memory_db()
        report = _make_score_report()
        rid = save_report(conn, report, [], [], _make_profile(), "/tmp/repo")
        fetched = get_report_by_id(conn, rid)
        assert fetched is not None
        assert fetched.provider == "anthropic"
        assert fetched.success_delta == pytest.approx(0.2, abs=1e-6)

    def test_round_trips_egress_enforced(self):
        from primer.store.db import get_report_by_id, save_report

        conn = _make_in_memory_db()
        report = _make_score_report(egress_enforced=True)
        rid = save_report(conn, report, [], [], _make_profile(), "/tmp/repo")
        fetched = get_report_by_id(conn, rid)
        assert fetched.egress_enforced is True


# ---------------------------------------------------------------------------
# Tests: render_history_table
# ---------------------------------------------------------------------------

class TestRenderHistoryTable:
    def test_empty_shows_no_reports(self):
        console, buf = _capture_console()
        render_history_table([], console=console)
        assert "No reports found" in buf.getvalue()

    def test_renders_rows(self):
        console, buf = _capture_console()
        rows = [
            {
                "id": 1,
                "repo_path": "/my/repo",
                "repo_commit": "deadbeef",
                "created_at": "2024-01-01T00:00:00Z",
                "n_tasks": 5,
                "runs_per_config": 3,
                "success_delta": 0.2,
                "provider": "anthropic",
                "model": "claude-opus-4-6",
                "agent_adapter": "claude_code",
            }
        ]
        render_history_table(rows, console=console)
        output = buf.getvalue()
        assert "1" in output
        assert "/my/r" in output  # Rich truncates long paths
        assert "anthropic" in output

    def test_none_delta_shows_na(self):
        console, buf = _capture_console()
        rows = [
            {
                "id": 2,
                "repo_path": "/repo",
                "repo_commit": "abc",
                "created_at": "2024-01-01",
                "n_tasks": 3,
                "runs_per_config": 3,
                "success_delta": None,
                "provider": "anthropic",
                "model": "claude-opus-4-6",
                "agent_adapter": "claude_code",
            }
        ]
        render_history_table(rows, console=console)
        assert "N/A" in buf.getvalue()

    def test_positive_delta_present(self):
        console, buf = _capture_console()
        rows = [{"id": 3, "repo_path": "/r", "repo_commit": "aa",
                 "created_at": "2024-01-01", "n_tasks": 5, "runs_per_config": 3,
                 "success_delta": 0.4, "provider": "anthropic",
                 "model": "claude-opus-4-6", "agent_adapter": "claude_code"}]
        render_history_table(rows, console=console)
        output = buf.getvalue()
        assert "40.0 pp" in output or "pp" in output


# ---------------------------------------------------------------------------
# Tests: render_compare — Q9d mismatch guard
# ---------------------------------------------------------------------------

class TestRenderCompare:
    def test_same_provider_shows_cross_delta(self):
        console, buf = _capture_console()
        ra = _make_score_report(success_delta=0.2)
        rb = _make_score_report(success_delta=0.4)
        render_compare(ra, rb, 1, 2, console=console)
        output = buf.getvalue()
        # Cross-delta = 0.4 - 0.2 = 0.2 = +20.0 pp
        assert "+20.0 pp" in output

    def test_provider_mismatch_refuses_cross_delta(self):
        console, buf = _capture_console()
        ra = _make_score_report(provider="anthropic", model="claude-opus-4-6")
        rb = _make_score_report(provider="openai", model="gpt-4o")
        render_compare(ra, rb, 1, 2, console=console)
        output = buf.getvalue()
        assert "mismatch" in output.lower()
        assert "refused" in output.lower()
        assert "N/A" in output

    def test_model_mismatch_refuses_cross_delta(self):
        console, buf = _capture_console()
        ra = _make_score_report(provider="anthropic", model="claude-opus-4-6")
        rb = _make_score_report(provider="anthropic", model="claude-haiku-4-5-20251001")
        render_compare(ra, rb, 1, 2, console=console)
        output = buf.getvalue()
        assert "mismatch" in output.lower()
        assert "N/A" in output

    def test_isolation_mismatch_shows_warning(self):
        console, buf = _capture_console()
        ra = _make_score_report(network_mode="primer-internal", egress_enforced=True)
        rb = _make_score_report(network_mode="host", egress_enforced=False)
        render_compare(ra, rb, 1, 2, console=console)
        output = buf.getvalue()
        assert "solation" in output  # "Isolation" or "isolation"

    def test_no_isolation_warning_when_same(self):
        console, buf = _capture_console()
        ra = _make_score_report()
        rb = _make_score_report()
        render_compare(ra, rb, 1, 2, console=console)
        output = buf.getvalue()
        assert "Isolation mismatch" not in output

    def test_shows_report_ids_in_header(self):
        console, buf = _capture_console()
        ra = _make_score_report()
        rb = _make_score_report()
        render_compare(ra, rb, 42, 99, console=console)
        output = buf.getvalue()
        assert "42" in output
        assert "99" in output

    def test_none_delta_in_both_shows_na(self):
        console, buf = _capture_console()
        ra = _make_score_report(success_delta=None)
        rb = _make_score_report(success_delta=None)
        render_compare(ra, rb, 1, 2, console=console)
        output = buf.getvalue()
        assert "N/A" in output

    def test_variance_always_shown(self):
        console, buf = _capture_console()
        ra = _make_score_report(success_stddev=0.123)
        rb = _make_score_report(success_stddev=0.456)
        render_compare(ra, rb, 1, 2, console=console)
        output = buf.getvalue()
        assert "0.123" in output
        assert "0.456" in output

    def test_cost_shown_for_both_reports(self):
        console, buf = _capture_console()
        ra = _make_score_report(cost_without=0.01, cost_with=0.02)
        rb = _make_score_report(cost_without=0.03, cost_with=0.04)
        render_compare(ra, rb, 1, 2, console=console)
        output = buf.getvalue()
        assert "0.0100" in output or "0.01" in output
        assert "0.0300" in output or "0.03" in output
