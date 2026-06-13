# BLK-2 Completion Report — Harness-Validity Fingerprint Gate

**Date:** 2026-06-12
**Status:** G-1 through G-7 COMPLETE. G-6, G-8, G-9 blocked on ANTHROPIC_API_KEY.
**Implemented by:** Claude Opus 4.8
**Specification authority:** `16_BLK2_SPECIFICATION.md`

---

## 1. Files Modified

| File | Change type |
|---|---|
| `primer/errors.py` | Add `HarnessValidityError` |
| `primer/eval/agent_adapter.py` | Add `fingerprint_instruction()` and `check_fingerprint()` concrete defaults |
| `primer/eval/models.py` | Add `harness_fingerprint_valid: bool \| None = None` to `RunResult` |
| `primer/store/schema.sql` | Add `harness_fingerprint_valid INTEGER` column to `runs` table |
| `primer/store/migrations.py` | Bump `CURRENT_SCHEMA_VERSION` to 2; add `_migration_v2()` |
| `primer/store/db.py` | Include `harness_fingerprint_valid` in `save_report()` INSERT |
| `primer/eval/adapters/claude_code.py` | Replace label with provisional instruction text; add `fingerprint_instruction()` and `check_fingerprint()` overrides |
| `primer/eval/runner.py` | Init `fingerprint_valid`; inject in Step 3 WITH arm; check after Step 8; thread to `RunResult` |
| `primer/eval/scorer.py` | Import `HarnessValidityError`; add abort check in `score()` inner loop |
| `tests/test_runner_isolation.py` | Fix stale `test_context_file_written_to_clone`; add 6 new BLK-2 tests |

---

## 2. Exact Changes Made

### `primer/errors.py`
Added `HarnessValidityError(PrimerError)` after `IsolationError`. Leaf module — no inbound dependency risk.

### `primer/eval/agent_adapter.py`
Added two concrete-default methods to the `AgentAdapter` ABC:
- `fingerprint_instruction() -> str | None` — returns `None` (opt-in per adapter).
- `check_fingerprint(raw_log, with_context) -> bool | None` — returns `None` (does not participate).

Both are concrete (not abstract); existing adapters need not override them. `ClaudeCodeAdapter` does override both.

### `primer/eval/models.py`
Added at the end of `RunResult` (after `run_timestamp`):
```python
harness_fingerprint_valid: bool | None = None
```
**Deviation from spec §6.2:** the spec shows this field inserted "after `flaky` and before `agent_adapter`". Python dataclass rules require fields with defaults to come after all required fields. Since all other `RunResult` fields are required, the field is placed at the end. The field name, type, default, and semantics exactly match the spec. No existing code broke because all callers use keyword arguments.

### `primer/store/schema.sql`
Added after `flaky INTEGER NOT NULL` in `runs` table:
```sql
harness_fingerprint_valid INTEGER,
```
Nullable (no `NOT NULL`): `NULL` = not checked; `1` = valid; `0` = failed.

### `primer/store/migrations.py`
- `CURRENT_SCHEMA_VERSION`: `1` → `2`
- Added `_migration_v2()`: idempotent `ALTER TABLE runs ADD COLUMN harness_fingerprint_valid INTEGER`; catches `"duplicate column name"` `OperationalError` silently.
- Added `if current < 2: _migration_v2(conn); set_schema_version(conn, 2)` to `apply_migrations()`.

### `primer/store/db.py`
Added `harness_fingerprint_valid` to the `INSERT INTO runs` column list and values tuple. Encoding: `1 if True`, `0 if False`, `None` (SQL NULL) if `None`.

### `primer/eval/adapters/claude_code.py`
- `FINGERPRINT_INSTRUCTION`: replaced `"PRIMER_FINGERPRINT_V1"` (label only) with the full provisional directive:
  ```
  PRIMER_FINGERPRINT_V1: Before starting the task, output "primer_fingerprint_v1_acknowledged" as the first line of your response.
  ```
  Marked `⚠️ [EMPIRICAL VERIFICATION REQUIRED]` in a comment. See `16_BLK2_SPECIFICATION.md §4.4`.
- `fingerprint_instruction()`: returns `FINGERPRINT_INSTRUCTION`.
- `check_fingerprint(raw_log, with_context)`: returns `None` for WITHOUT arm; `FINGERPRINT_MARKER in raw_log` for WITH arm; wraps in try/except per spec contract.

### `primer/eval/runner.py`
Three changes:

1. **Init at top of `run_task()`:** `fingerprint_valid: bool | None = None`

2. **Step 3 WITH arm injection** (replaces bare `write_text`):
   ```python
   fingerprint_text = adapter.fingerprint_instruction()
   effective_content = context_content
   if fingerprint_text:
       separator = "\n" if context_content.endswith("\n") else "\n\n"
       effective_content = context_content + separator + fingerprint_text + "\n"
   context_file_path.write_text(effective_content, encoding="utf-8")
   ```

3. **After Step 8** (after `telemetry = adapter.parse_telemetry(redacted_log)`):
   ```python
   fingerprint_valid = adapter.check_fingerprint(redacted_log, with_context)
   ```

4. **RunResult construction:** added `harness_fingerprint_valid=fingerprint_valid`.

### `primer/eval/scorer.py`
- Added `from primer.errors import HarnessValidityError` import.
- Added abort check between `run_result = _run_with_retry(...)` and `run_result.provider = provider`:
  ```python
  if with_ctx and run_result.harness_fingerprint_valid is False:
      raise HarnessValidityError(...)
  ```
  Abort condition is strictly `is False` — never triggered by `None`.

### `tests/test_runner_isolation.py`
- **Fixed** `test_context_file_written_to_clone`: replaced exact-equality assertion with presence checks (`CONTENT in written` and `FINGERPRINT_INSTRUCTION in written`), since BLK-2 appends the fingerprint instruction to the written file.
- **Added** 6 new BLK-2 tests:
  - `test_fingerprint_appended_to_with_arm_context_file` (G-4 / Probe A)
  - `test_no_fingerprint_in_without_arm_run_result` (G-5 / Probe C)
  - `test_abort_on_harness_fingerprint_false` (G-7)
  - `test_harness_fingerprint_none_does_not_abort` (G-7 complement: `None` must not abort)
  - `test_agent_adapter_fingerprint_defaults` (G-2)
  - `test_migration_v2_adds_fingerprint_column` (G-3)

---

## 3. Validation Results

### Step-by-step validation

| Step | File | Validation | Result |
|---|---|---|---|
| 1 | `errors.py` | `from primer.errors import HarnessValidityError; assert issubclass(HarnessValidityError, PrimerError)` | PASS |
| 2 | `agent_adapter.py` | Concrete defaults return `None`; ClaudeCodeAdapter still passes all adapter tests | PASS |
| 3 | `models.py` | `test_store_round_trip` — existing `RunResult` construction works | PASS |
| 4 | `schema.sql` + `migrations.py` + `db.py` | `test_store_round_trip` | PASS |
| 5 | `claude_code.py` | `fingerprint_instruction()` returns full text; `check_fingerprint()` correct; `test_m4_fingerprint_constant_exists` | PASS |
| 6 | `runner.py` | 30 existing runner tests + `test_source_repo_not_mutated` (BLK-5 regression) | PASS |
| 7 | `scorer.py` | All 19 `test_scorer.py` tests | PASS |
| 8 | `test_runner_isolation.py` | Full BLK-2 target suite | PASS |

### Final targeted suite

```
pytest tests/test_runner_isolation.py tests/test_scorer.py tests/test_arch_boundaries.py -v
59 passed, 1 skipped (Docker gate — pre-existing, expected)
```

---

## 4. Acceptance Gate Status

| Gate | Description | Status |
|---|---|---|
| **G-1** | `HarnessValidityError` importable from `primer.errors` | **PASS** |
| **G-2** | `AgentAdapter` ABC has `fingerprint_instruction()` and `check_fingerprint()` concrete defaults | **PASS** |
| **G-3** | `RunResult.harness_fingerprint_valid` field present; schema v2 migration passes; idempotent | **PASS** |
| **G-4** | Mocked WITH-arm `run_task()` writes file containing `FINGERPRINT_INSTRUCTION` (Probe A injection) | **PASS** |
| **G-5** | Mocked WITHOUT-arm `run_task()` returns `harness_fingerprint_valid=None`; no file written | **PASS** |
| **G-6** | Live WITH-arm: marker found in log; `harness_fingerprint_valid=True` | **BLOCKED** — `ANTHROPIC_API_KEY` absent |
| **G-7** | Mocked `RunResult(harness_fingerprint_valid=False, with_context=True)` causes `HarnessValidityError` | **PASS** |
| **G-8** | Live WITH arm: marker present; live WITHOUT arm: `harness_fingerprint_valid=None` | **BLOCKED** — `ANTHROPIC_API_KEY` absent |
| **G-9** | Full live eval: `success_delta` computed only after G-8 passes | **BLOCKED** — `ANTHROPIC_API_KEY` absent |

---

## 5. Remaining Blockers

| Blocker | Gates | Resolution |
|---|---|---|
| `ANTHROPIC_API_KEY` absent from environment | G-6, G-8, G-9 | Set a valid key; execute §4.4 verification procedure from `16_BLK2_SPECIFICATION.md`; verify `FINGERPRINT_INSTRUCTION` text causes agent to output `primer_fingerprint_v1_acknowledged`; lock confirmed text; update `FINGERPRINT_INSTRUCTION` constant in `claude_code.py` if needed |
| `FINGERPRINT_INSTRUCTION` text empirically unverified | G-6, G-8 | Same resolution path as above; text is marked `⚠️ [EMPIRICAL VERIFICATION REQUIRED]` |

---

## 6. BLK-2 Completion Status

**G-1 through G-5 and G-7: COMPLETE.** All implemented, all passing. The harness-validity gate is architecturally in place.

**G-6, G-8, G-9: BLOCKED** on `ANTHROPIC_API_KEY`. The gate will operate correctly the moment a live run completes with the verified instruction text. No further code changes are required beyond potentially updating `FINGERPRINT_INSTRUCTION` after empirical verification.

**The gate is operative** in the sense that it will correctly abort any eval where `harness_fingerprint_valid=False` is returned. Whether it returns `True` (valid) or `False` (abort) in a live run depends on the empirical correctness of the instruction text, which requires the API key to verify.
