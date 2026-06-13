"""SQLite persistence -- the ONLY module in PRIMER that imports sqlite3.

Boundary invariant: only primer/store/ imports sqlite3.
raw_output/logs are always redacted (log_safe()) before any write.
base_image stores the resolved sha256 digest (M5).
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from primer.config import Settings
    from primer.eval.models import RunResult, ScoreReport, Task
    from primer.ingest.models import RepoProfile

log = logging.getLogger(__name__)

_SCHEMA_VERSION = "1"
_SCHEMA_SQL = Path(__file__).parent / "schema.sql"


def init_db(config: "Settings") -> sqlite3.Connection:
    """Open (or create) the database, apply schema and migrations, return connection.

    Phase 6: calls apply_migrations() after schema.sql to handle version upgrades.
    Raises store.migrations.SchemaTooNewError if the db was written by a newer PRIMER.
    """
    from primer.store.migrations import apply_migrations

    db_path = _resolve_db_path(config.database_url)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    # Apply baseline schema (idempotent CREATE TABLE IF NOT EXISTS)
    schema_sql = _SCHEMA_SQL.read_text(encoding="utf-8")
    conn.executescript(schema_sql)

    # Apply any pending migrations and ensure schema_version is set
    apply_migrations(conn)

    log.debug("database ready at %s (schema v%s)", db_path, _SCHEMA_VERSION)
    return conn


def save_report(
    conn: sqlite3.Connection,
    report: "ScoreReport",
    tasks: list["Task"],
    runs: list["RunResult"],
    profile: "RepoProfile",
    repo_path: str,
) -> int:
    """Persist a ScoreReport + tasks + runs + profile; return the report_id."""
    cur = conn.cursor()

    # Upsert profile
    profile_json = _profile_to_json(profile)
    cur.execute(
        """INSERT INTO profiles
           (repo_path, repo_commit, created_at, profile_json,
            gen_provider, gen_model)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            repo_path,
            profile.repo_commit,
            report.created_at,
            profile_json,
            report.provider,
            report.model,
        ),
    )

    # Insert report
    cur.execute(
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
    report_id = cur.lastrowid

    # Insert tasks
    for task in tasks:
        cur.execute(
            """INSERT INTO tasks
               (report_id, task_key, task_type, prompt, verify_cmd, source_ref, validated)
               VALUES (?,?,?,?,?,?,?)""",
            (
                report_id,
                task.id,
                task.task_type,
                task.prompt,
                task.verify_cmd,
                task.source_ref,
                1 if task.validated else 0,
            ),
        )

    # Insert runs
    for run in runs:
        cur.execute(
            """INSERT INTO runs
               (report_id, task_id, repo_commit, with_context, passed, timeout, flaky,
                harness_fingerprint_valid,
                agent_adapter, agent_tokens, iterations, duration_s, cost_usd, cost_confidence,
                provider, model, base_image, network_mode, egress_allowed_host,
                egress_enforced, caps_dropped, container_id, agent_log_path, run_timestamp)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                report_id,
                run.task_id,
                run.repo_commit,
                1 if run.with_context else 0,
                1 if run.passed else 0,
                1 if run.timeout else 0,
                1 if run.flaky else 0,
                1 if run.harness_fingerprint_valid else (
                    0 if run.harness_fingerprint_valid is False else None
                ),
                run.agent_adapter,
                run.agent_tokens,
                run.iterations,
                run.duration_s,
                run.cost_usd,
                run.cost_confidence,
                run.provider,
                run.model,
                run.base_image,
                run.network_mode,
                run.egress_allowed_host,
                1 if run.egress_enforced else 0,
                1 if run.caps_dropped else 0,
                run.container_id,
                run.agent_log_path,
                run.run_timestamp,
            ),
        )

    conn.commit()
    log.info("saved report_id=%d for %s", report_id, repo_path)
    return report_id


def latest_report(conn: sqlite3.Connection, repo_path: str) -> "ScoreReport | None":
    """Return the most recent ScoreReport for the given repo, or None."""
    row = conn.execute(
        """SELECT * FROM reports WHERE repo_path = ?
           ORDER BY id DESC LIMIT 1""",
        (repo_path,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_score_report(conn, row)


def list_reports(
    conn: sqlite3.Connection,
    repo_path: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Return summary rows for recent reports.

    Each dict has: id, repo_path, repo_commit, created_at, n_tasks,
    runs_per_config, success_delta, provider, model, agent_adapter.

    Args:
        repo_path: If given, filter to this repo only.
        limit:     Max rows to return (default 20).
    """
    if repo_path is not None:
        rows = conn.execute(
            """SELECT id, repo_path, repo_commit, created_at, n_tasks,
                      runs_per_config, success_delta, provider, model, agent_adapter
               FROM reports WHERE repo_path = ?
               ORDER BY id DESC LIMIT ?""",
            (repo_path, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, repo_path, repo_commit, created_at, n_tasks,
                      runs_per_config, success_delta, provider, model, agent_adapter
               FROM reports
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_report_by_id(
    conn: sqlite3.Connection, report_id: int
) -> "ScoreReport | None":
    """Return a ScoreReport by its integer primary key, or None."""
    row = conn.execute(
        "SELECT * FROM reports WHERE id = ?", (report_id,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_score_report(conn, row)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _resolve_db_path(database_url: str) -> Path:
    """Convert sqlite:///path to a Path."""
    if database_url.startswith("sqlite:///"):
        return Path(database_url[len("sqlite:///"):])
    return Path(database_url)


def _profile_to_json(profile) -> str:
    """Serialize RepoProfile to JSON (best-effort)."""
    try:
        import dataclasses
        return json.dumps(dataclasses.asdict(profile), default=str)
    except Exception:
        return json.dumps({"repo_commit": getattr(profile, "repo_commit", "")})


def _row_to_score_report(conn: sqlite3.Connection, row: sqlite3.Row) -> "ScoreReport":
    """Reconstruct a ScoreReport from a reports row."""
    from primer.eval.models import ScoreReport, TaskScore

    # Load per-task scores
    task_rows = conn.execute(
        "SELECT * FROM tasks WHERE report_id = ?", (row["id"],)
    ).fetchall()

    run_rows = conn.execute(
        "SELECT * FROM runs WHERE report_id = ?", (row["id"],)
    ).fetchall()

    # Reconstruct TaskScore objects from task and run rows
    per_task: list[TaskScore] = []
    for tr in task_rows:
        task_runs = [r for r in run_rows if r["task_id"] == tr["task_key"]]
        without = [r for r in task_runs if not r["with_context"]]
        with_ = [r for r in task_runs if r["with_context"]]
        pr_w = sum(r["passed"] for r in without) / len(without) if without else 0.0
        pr_t = sum(r["passed"] for r in with_) / len(with_) if with_ else 0.0
        flaky_any = any(r["flaky"] for r in task_runs)
        # M7: if the report recorded a provider_mismatch_warning, delta was
        # refused at aggregation time and must remain None on reconstruction.
        task_delta = (
            None if row["provider_mismatch_warning"] is not None
            else pr_t - pr_w
        )
        per_task.append(TaskScore(
            task_id=tr["task_key"],
            task_type=tr["task_type"],
            pass_rate_without=pr_w,
            pass_rate_with=pr_t,
            delta=task_delta,
            runs=len(task_runs),
            flaky_any=bool(flaky_any),
        ))

    return ScoreReport(
        repo_commit=row["repo_commit"],
        created_at=row["created_at"],
        n_tasks=row["n_tasks"],
        runs_per_config=row["runs_per_config"],
        success_rate_without=row["success_rate_without"],
        success_rate_with=row["success_rate_with"],
        success_delta=row["success_delta"],
        success_stddev=row["success_stddev"],
        success_min=row["success_min"],
        success_max=row["success_max"],
        cost_without=row["cost_without"],
        cost_with=row["cost_with"],
        cost_delta_pct=row["cost_delta_pct"],
        cost_confidence=row["cost_confidence"],
        per_task=per_task,
        provider=row["provider"],
        model=row["model"],
        agent_adapter=row["agent_adapter"],
        base_image=row["base_image"],
        network_mode=row["network_mode"],
        egress_enforced=bool(row["egress_enforced"]),
        provider_mismatch_warning=row["provider_mismatch_warning"],
        isolation_mismatch_warning=row["isolation_mismatch_warning"],
        flaky_task_warning=row["flaky_task_warning"],
        primer_overhead_usd=row["primer_overhead_usd"],
        primer_overhead_confidence=row["primer_overhead_confidence"],
    )
