-- PRIMER SQLite schema
-- Booleans stored as INTEGER (0/1); timestamps TEXT ISO-8601 UTC.
-- raw_output/logs are REDACTED (log_safe()) before any write.
-- base_image stores the resolved sha256 digest.

CREATE TABLE IF NOT EXISTS _meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_path           TEXT NOT NULL,
    repo_commit         TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    profile_json        TEXT NOT NULL,
    agents_md           TEXT,
    agents_md_lines     INTEGER,
    gen_provider        TEXT,
    gen_model           TEXT,
    gen_tokens          INTEGER,
    gen_cost_usd        REAL,
    gen_cost_confidence TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_path                   TEXT NOT NULL,
    repo_commit                 TEXT NOT NULL,
    created_at                  TEXT NOT NULL,
    n_tasks                     INTEGER NOT NULL,
    runs_per_config             INTEGER NOT NULL,
    success_rate_without        REAL NOT NULL,
    success_rate_with           REAL NOT NULL,
    success_delta               REAL,
    success_stddev              REAL NOT NULL,
    success_min                 REAL NOT NULL,
    success_max                 REAL NOT NULL,
    cost_without                REAL NOT NULL,
    cost_with                   REAL NOT NULL,
    cost_delta_pct              REAL,
    cost_confidence             TEXT NOT NULL,
    provider                    TEXT NOT NULL,
    model                       TEXT NOT NULL,
    agent_adapter               TEXT NOT NULL,
    base_image                  TEXT NOT NULL,
    network_mode                TEXT NOT NULL,
    egress_enforced             INTEGER NOT NULL,
    provider_mismatch_warning   TEXT,
    isolation_mismatch_warning  TEXT,
    flaky_task_warning          TEXT,
    primer_overhead_usd         REAL NOT NULL,
    primer_overhead_confidence  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id   INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    task_key    TEXT NOT NULL,
    task_type   TEXT NOT NULL,
    prompt      TEXT NOT NULL,
    verify_cmd  TEXT NOT NULL,
    source_ref  TEXT,
    validated   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id           INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    task_id             TEXT NOT NULL,
    repo_commit         TEXT NOT NULL,
    with_context        INTEGER NOT NULL,
    passed              INTEGER NOT NULL,
    timeout             INTEGER NOT NULL,
    flaky               INTEGER NOT NULL,
    harness_fingerprint_valid INTEGER,
    agent_adapter       TEXT NOT NULL,
    agent_tokens        INTEGER NOT NULL,
    iterations          INTEGER NOT NULL,
    duration_s          REAL NOT NULL,
    cost_usd            REAL NOT NULL,
    cost_confidence     TEXT NOT NULL,
    provider            TEXT NOT NULL,
    model               TEXT NOT NULL,
    base_image          TEXT NOT NULL,
    network_mode        TEXT NOT NULL,
    egress_allowed_host TEXT,
    egress_enforced     INTEGER NOT NULL,
    caps_dropped        INTEGER NOT NULL,
    container_id        TEXT NOT NULL,
    agent_log_path      TEXT NOT NULL,
    run_timestamp       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_report   ON runs(report_id);
CREATE INDEX IF NOT EXISTS idx_runs_task     ON runs(task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_report  ON tasks(report_id);
CREATE INDEX IF NOT EXISTS idx_reports_repo  ON reports(repo_path);
