"""Schema version management and migration machinery for PRIMER store.

Phase 6 — Post-MVP SQLite history/compare UX.

Design principles:
  - Only primer/store/ imports sqlite3 (boundary invariant).
  - Migrations are additive (ALTER TABLE ADD COLUMN / CREATE TABLE).
  - Each migration is idempotent: safe to re-run on a db that already has it.
  - SCHEMA_VERSION in _meta is the authoritative version indicator.
  - If db schema_version < CURRENT_SCHEMA_VERSION, apply pending migrations.
  - If db schema_version > CURRENT_SCHEMA_VERSION, raise SchemaTooNewError.
"""
from __future__ import annotations

import logging
import sqlite3

log = logging.getLogger(__name__)

# Bump this when a new migration is added.
CURRENT_SCHEMA_VERSION = 2

# SchemaTooNewError: raised when the db was written by a newer PRIMER.
class SchemaTooNewError(Exception):
    """DB schema version is newer than this PRIMER build; upgrade PRIMER."""


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return the stored schema_version (int), or 0 if _meta is absent/empty."""
    try:
        row = conn.execute(
            "SELECT value FROM _meta WHERE key = 'schema_version'"
        ).fetchone()
    except sqlite3.OperationalError:
        # _meta table does not exist yet (brand-new db)
        return 0
    if row is None:
        return 0
    try:
        return int(row[0])
    except (ValueError, TypeError):
        return 0


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Upsert schema_version in _meta."""
    conn.execute(
        """INSERT INTO _meta (key, value) VALUES ('schema_version', ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
        (str(version),),
    )
    conn.commit()


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Bring the db up to CURRENT_SCHEMA_VERSION, applying any pending migrations.

    Raises SchemaTooNewError if db is ahead of this build.
    Idempotent: safe to call on an already-current db.
    """
    current = get_schema_version(conn)

    if current > CURRENT_SCHEMA_VERSION:
        raise SchemaTooNewError(
            f"Database schema version {current} is newer than this PRIMER build "
            f"(supports up to v{CURRENT_SCHEMA_VERSION}). "
            f"Please upgrade PRIMER."
        )

    if current == CURRENT_SCHEMA_VERSION:
        log.debug("schema already at v%d — no migrations needed", current)
        return

    # Apply migrations in order
    if current < 1:
        _migration_v1(conn)
        set_schema_version(conn, 1)
        log.info("applied migration v1")

    if current < 2:
        _migration_v2(conn)
        set_schema_version(conn, 2)
        log.info("applied migration v2")

    log.info("schema at v%d", CURRENT_SCHEMA_VERSION)


# ---------------------------------------------------------------------------
# Individual migration steps
# ---------------------------------------------------------------------------

def _migration_v2(conn: sqlite3.Connection) -> None:
    """v1 → v2: add harness_fingerprint_valid column to runs (BLK-2 / M4 gate).

    Additive, backward-compatible. Existing rows have NULL (= not checked).
    Idempotent: safe to re-run on a db that already has the column.
    """
    try:
        conn.execute(
            "ALTER TABLE runs ADD COLUMN harness_fingerprint_valid INTEGER"
        )
        conn.commit()
    except sqlite3.OperationalError as exc:
        if "duplicate column name" in str(exc).lower():
            pass  # already applied — idempotent
        else:
            raise


def _migration_v1(conn: sqlite3.Connection) -> None:
    """v0 -> v1: baseline schema (tables already applied via schema.sql).

    For a brand-new db, schema.sql creates all tables; this migration just
    records that the db is at v1. For pre-v1 dbs (hypothetically), it would
    create missing tables — but since v1 IS the initial schema, this is a no-op
    beyond the version bump.
    """
    # Ensure _meta exists (schema.sql creates it, but guard for safety)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    conn.commit()
