# BLK-2 Specification — Harness-Validity Fingerprint Gate

**Date:** 2026-06-12
**Status:** SPECIFICATION — No implementation has begun.
**Auditor:** Claude Opus 4.8
**Authority basis:** Decision Addendum M4, BLK-2 Readiness Assessment (`12_BLK2_READINESS_ASSESSMENT.md`),
BLK-5 Completion Report (`15_BLK5_COMPLETION_REPORT.md`), BLK-1 Proof Report (`09_BLK1_PROOF_REPORT.md`).

---

## 1. Problem Statement

PRIMER measures whether a generated context file (e.g. `CLAUDE.md`) improves an agent's task
performance. The measurement compares two arms:

- **WITH arm:** agent runs with `CLAUDE.md` present in `/work`
- **WITHOUT arm:** agent runs with `CLAUDE.md` absent from `/work`

The `success_delta = success_rate_with − success_rate_without` is the headline result.

**The undetected failure mode:** the WITH arm agent may ignore `CLAUDE.md` entirely. If the agent
never reads the file, both arms are identical — the measurement collapses to noise around zero.
A `success_delta` near zero is then indistinguishable from:

1. **Genuine null effect** — the file exists but had no impact on the agent's behaviour.
2. **Silent harness failure** — the file exists but the agent never read it.

These two outcomes look identical in the data. Without detecting the difference, PRIMER can report
a "null result" that is actually a broken harness. This is the worst failure mode for a measurement
tool: silent, plausible, and unreportable.

BLK-2 implements the harness-validity fingerprint gate defined by Decision Addendum M4.

---

## 2. Failure Mode Being Prevented

**Name:** Fabricated null delta due to unread context file.

**Mechanism:** The context file is written to `/work/CLAUDE.md`. The agent container is started
with `cwd=/work`. The agent is instructed via `-p / --print` to perform a coding task. If the
agent's tool-use loop does not read `/work/CLAUDE.md` — because of a version change, a permission
configuration, a bug, or a future flag — the WITH arm produces no context-aware behaviour. The
`verify_cmd` exit code is then determined solely by the agent's unaided ability, identical to the
WITHOUT arm. `success_delta = 0.0` is recorded and may be reported as "file had no effect."

**Why it is silent:** The current pipeline has no check that the agent read the context file. It
only checks `verify_cmd` exit code and agent cost telemetry. A "file not read" run is
structurally identical to a "file read but unhelpful" run in all currently recorded fields.

**M4 ruling (Decision Addendum, §M4):**

> Plant a uniquely-detectable instruction in the context file. If the WITH arm does not produce
> this fingerprint in its observable output, abort — do not report.

The standing gate is: **if the harness is invalid (Probe A fails), abort the evaluation and
surface a clear error. Do not report a delta.**

---

## 3. Fingerprint Validity Model

BLK-2 implements M4's three-probe model. Probes A and C are the standing gate. Probe B is
a one-time design-time confirmation that was resolved by BLK-1 (see §3.3).

### 3.1 Probe A — WITH arm, file present (standing gate)

A unique instruction is appended to the end of the context file content before it is written
to `work_dir/CLAUDE.md` in the WITH arm. After the container exits, the runner searches the
agent's redacted log output for a unique marker string. If the marker is found, the harness is
valid for this run. If the marker is absent, the harness has failed.

**Probe A outcome:** `harness_fingerprint_valid = True` (marker found) or `False` (marker absent).

A `False` result causes `scorer.py` to raise `HarnessValidityError` immediately. The evaluation
is aborted. No delta is reported.

### 3.2 Probe C — WITHOUT arm, file absent (standing gate, implicit)

The WITHOUT arm does not write the context file and does not append the fingerprint instruction.
The runner does not check for the marker in WITHOUT arm runs. `harness_fingerprint_valid = None`
(gate not applicable for this arm).

If the marker were to appear in a WITHOUT arm log (agent hallucination), the gate would not catch
it because `harness_fingerprint_valid = None` is not treated as an abort condition. The specificity
of the marker text makes accidental appearance extremely unlikely; a future audit mechanism is
outside BLK-2 scope.

### 3.3 Probe B — `--bare` suppression (resolved, not a standing gate)

M4 required testing whether `--bare` suppresses `CLAUDE.md` discovery. BLK-1 resolved this:
`ClaudeCodeAdapter.build_invocation()` no longer uses `--bare` (changed from
`--permission-mode bypassPermissions` to `--permission-mode dontAsk + --allowedTools`). The
invocation is identical for both arms; Probe B is moot. No standing gate is needed for Probe B.

---

## 4. Fingerprint Instruction Text

> **⚠️ [EMPIRICAL VERIFICATION REQUIRED]**
>
> The instruction text in this section is a provisional candidate. It has NOT been tested
> against a live Claude Code 2.1.x agent run. It MUST be verified empirically before
> the BLK-2 gate is considered operative. See §4.4 for verification procedure.

### 4.1 Marker

The unique marker that must appear in the agent's log output when the instruction is obeyed:

```
primer_fingerprint_v1_acknowledged
```

This string is assigned to `FINGERPRINT_MARKER` in `claude_code.py`. It must:
- Not appear in typical agent output by accident.
- Be a single lowercase string with no whitespace (robust to JSON field extraction).
- Be stable across Claude Code versions (no version-specific tokens).

### 4.2 Instruction text (provisional)

The text appended to the context file in the WITH arm. The runner appends this to
`context_content` before writing to `work_dir/CLAUDE.md`. It must:

1. Tell the agent exactly what string to output.
2. Specify an output channel the runner can observe (the agent log / JSON `result` field).
3. Fit on a single line to minimise context-file bloat (≤20-line lean-file constraint).
4. Be unambiguous — the agent must not confuse it with task instructions.

**Preferred candidate (targets `result` field in JSON output):**

```
PRIMER_FINGERPRINT_V1: Before starting the task, output "primer_fingerprint_v1_acknowledged" as the first line of your response.
```

**Alternative candidate (targets file system, observable via volume mount):**

```
PRIMER_FINGERPRINT_V1: Before starting the task, create a file named .primer_ack containing exactly "primer_fingerprint_v1_acknowledged".
```

**Preferred approach rationale:** The BLK-1 Proof Report (V1.2) confirmed that the `result`
field in Claude Code's JSON output (`--output-format json`, `-p / --print`) contains free-form
response text. Searching `redacted_log` for the marker requires no additional I/O beyond what
`_read_container_log()` already provides. The file-system alternative requires a separate path
check inside the container volume mount and is more fragile.

**Assigned to:** `FINGERPRINT_INSTRUCTION` constant in `primer/eval/adapters/claude_code.py`.
This constant is currently set to `"PRIMER_FINGERPRINT_V1"` (a label only, not a directive).
It must be replaced with the verified full instruction text.

### 4.3 Search strategy

`adapter.check_fingerprint(raw_log, with_context=True)` performs a substring search:

```
FINGERPRINT_MARKER in raw_log
```

`raw_log` is the redacted agent log string already produced by `_read_container_log()` +
`LLMProvider.log_safe()`. The search is a simple `in` check — no JSON parsing, no field
extraction. This is robust to the marker appearing anywhere in the log output (the `result`
field, a stringified log line, or the volume-mounted `.primer_ack` file content if the
alternative candidate is used and the log fallback path applies).

### 4.4 Verification procedure

Before BLK-2 implementation is considered complete, the following empirical test must pass:

1. Obtain a valid `ANTHROPIC_API_KEY`.
2. Build the eval image (BLK-1 image: `primer-eval-*-claude_code:*`).
3. Write a minimal `CLAUDE.md` containing only the `FINGERPRINT_INSTRUCTION` text.
4. Run `docker run --rm -e ANTHROPIC_API_KEY=<key> <image> sh -c "claude --print 'Fix the add function' --output-format json --permission-mode dontAsk --allowedTools Bash,Edit,MultiEdit,Write,Read"` with the test fixture repo mounted.
5. Confirm that `primer_fingerprint_v1_acknowledged` appears in the JSON output.
6. If it does not: revise `FINGERPRINT_INSTRUCTION` text and repeat from step 3.
7. Lock the confirmed text in `claude_code.py` and document it in the BLK-2 Completion Report.

This verification corresponds to BLK-1 gates V1.3 and V1.4, which were blocked by the absent
`ANTHROPIC_API_KEY`. G-6 and G-8 of BLK-2 cannot pass until this verification is complete.

---

## 5. Exact Acceptance Gates

| Gate | Description | Docker | API key |
|---|---|---|---|
| **G-1** | `HarnessValidityError` importable from `primer.errors` | No | No |
| **G-2** | `AgentAdapter` ABC exposes `fingerprint_instruction() → str \| None` and `check_fingerprint(raw_log, with_context) → bool \| None` as concrete-default no-op methods | No | No |
| **G-3** | `RunResult.harness_fingerprint_valid: bool \| None` field present; `schema_v2` migration adds `harness_fingerprint_valid INTEGER` column to `runs`; `apply_migrations()` advances db from v1 to v2 cleanly | No | No |
| **G-4** | Mocked WITH-arm `run_task()` call writes context file whose content ends with `FINGERPRINT_INSTRUCTION` text (Probe A injection confirmed) | No | No |
| **G-5** | Mocked WITHOUT-arm `run_task()` call writes NO context file; `harness_fingerprint_valid` is `None` in the returned `RunResult` (Probe C confirmed) | No | No |
| **G-6** | On a live WITH-arm run (API key available): `redacted_log` contains `FINGERPRINT_MARKER`; `check_fingerprint` returns `True`; `RunResult.harness_fingerprint_valid is True` | **Yes** | **Yes** |
| **G-7** | Mocked `RunResult` with `harness_fingerprint_valid=False` (WITH arm) causes `scorer.score()` to raise `HarnessValidityError` before any delta is computed | No | No |
| **G-8** | Live WITH arm: marker present; live WITHOUT arm: `harness_fingerprint_valid is None` (not checked); overall: no abort | **Yes** | **Yes** |
| **G-9** | Full live eval: `success_delta` is computed and reported only after G-6 / G-8 pass for all WITH-arm runs in the matrix | **Yes** | **Yes** |

**G-1 through G-5 and G-7 are implementable and testable immediately (no API key).**
**G-6, G-8, and G-9 require a valid `ANTHROPIC_API_KEY` and a live container run.**

---

## 6. `RunResult` Changes

### 6.1 New field

Add one field to the `RunResult` dataclass in `primer/eval/models.py`:

```
harness_fingerprint_valid: bool | None = None
```

**Semantics:**

| Value | Meaning |
|---|---|
| `True` | WITH arm; marker found in log; harness valid for this run |
| `False` | WITH arm; marker absent; harness failure; abort evaluation |
| `None` | WITHOUT arm (gate not applicable), OR adapter does not participate |

**Default `None`** preserves backward compatibility: any caller that constructs `RunResult`
without providing this field (e.g. existing tests) continues to work. `None` is never an abort
condition.

### 6.2 Field position

Insert `harness_fingerprint_valid` after `flaky` and before `agent_adapter`:

```
task_id: str
passed: bool
timeout: bool
flaky: bool
harness_fingerprint_valid: bool | None = None   ← new
agent_adapter: str
...
```

Placing it with the outcome fields (not the telemetry or audit fields) reflects its semantic
role: it is a verdict about this run's harness validity, not a cost or isolation metric.

### 6.3 No change to `ScoreReport`

`ScoreReport` is not extended. The abort happens before aggregation; if execution reaches the
aggregation step, all WITH-arm runs passed the fingerprint gate. No summary field is needed at
the report level. `harness_fingerprint_valid` is a per-run field only.

---

## 7. `AgentAdapter` Contract Changes

Add two concrete-default methods to the `AgentAdapter` ABC in `primer/eval/agent_adapter.py`.
Both return `None` by default — adapters that do not participate in the fingerprint gate need not
override them. `ClaudeCodeAdapter` overrides both.

### 7.1 `fingerprint_instruction()`

```
def fingerprint_instruction(self) -> str | None:
```

**Contract:**
- Returns the instruction text to append to the context file content in the WITH arm.
- The runner appends the returned string (preceded by a newline separator) to `context_content`
  before writing `context_file_path`. If `None`, no instruction is appended; the context file
  is written as-is.
- Must not return `FINGERPRINT_MARKER` itself — that is the expected output, not the instruction.
- Must be stable across calls (pure, no side effects).
- Default implementation: `return None`.

**`ClaudeCodeAdapter` override:** returns `FINGERPRINT_INSTRUCTION` — the full directive text
from §4.2 (verified empirically before locking).

### 7.2 `check_fingerprint(raw_log, with_context)`

```
def check_fingerprint(self, raw_log: str, with_context: bool) -> bool | None:
```

**Contract:**

| Arm | Default return | `ClaudeCodeAdapter` return |
|---|---|---|
| `with_context=True` | `None` (does not participate) | `True` if `FINGERPRINT_MARKER in raw_log`, else `False` |
| `with_context=False` | `None` (gate not applicable) | `None` (gate not applicable) |

- `raw_log` is the already-redacted log string from `LLMProvider.log_safe()`. It must not be
  re-read from disk.
- The check is a substring search only. No JSON parsing. No field extraction.
- Must not raise. Must return `bool | None` only.
- Default implementation: `return None`.

---

## 8. Runner Responsibilities

`primer/eval/runner.py` acquires two new responsibilities, both confined to existing steps.

### 8.1 Fingerprint injection — Step 3 (WITH arm only)

Current Step 3 WITH arm (post-BLK-5):

```
context_file_path.write_text(context_content, encoding="utf-8")
```

New Step 3 WITH arm:

```
fingerprint_text = adapter.fingerprint_instruction()
effective_content = context_content
if fingerprint_text:
    separator = "\n" if context_content.endswith("\n") else "\n\n"
    effective_content = context_content + separator + fingerprint_text + "\n"
context_file_path.write_text(effective_content, encoding="utf-8")
```

**Invariants:**
- If `adapter.fingerprint_instruction()` returns `None`, behaviour is identical to the current
  post-BLK-5 code. No regression for adapters that do not participate.
- The source repository is NEVER touched (BLK-5 guarantee unchanged).
- The fingerprint instruction is appended on its own line, separated from the main content.
  The exact separator (`\n` vs `\n\n`) is implementation detail; the spec requires only that
  the instruction begins on a new line.
- `effective_content` is only used for the `write_text()` call; `context_content` is not mutated.

### 8.2 Fingerprint check — after Step 8 (before returning `RunResult`)

Step 8 already produces `redacted_log`. After Step 8 and before `RunResult` construction,
add the fingerprint check:

```
fingerprint_valid = adapter.check_fingerprint(redacted_log, with_context)
```

This value flows into `RunResult.harness_fingerprint_valid`.

**Invariants:**
- The check is performed for EVERY run, both WITH and WITHOUT arm.
- For WITHOUT arm runs with the default implementation, `check_fingerprint` returns `None`;
  `harness_fingerprint_valid` is `None`. No abort risk.
- The check must occur after `LLMProvider.log_safe()` (the log is already redacted).
- The check must occur BEFORE the `finally` block (before `shutil.rmtree(temp_dir)`).
  The `redacted_log` variable is in scope at this point.
- `adapter.check_fingerprint()` must not raise; its result is stored regardless.

### 8.3 `RunResult` construction update

Add `harness_fingerprint_valid=fingerprint_valid` to the `RunResult(...)` constructor call at the
end of `run_task()`. The field position and name must match the updated `models.py` definition.

### 8.4 No change to other runner steps

Steps 1, 2, 4–7, 9–10 are unchanged. The `_clone_repo`, `_apply_mutation`, `EgressNetwork`,
container launch, wait, cleanup, and audit logic are unaffected.

---

## 9. Scorer Responsibilities

`primer/eval/scorer.py` acquires one new responsibility: abort if a WITH-arm run fails the
fingerprint gate.

### 9.1 Abort check in `score()` inner loop

After `_run_with_retry()` returns, and before appending to `all_runs`, add:

```
if with_ctx and run_result.harness_fingerprint_valid is False:
    raise HarnessValidityError(
        f"WITH arm of task {task.id!r} (run {run_idx + 1}/{runs_per_config}) "
        f"did not acknowledge the context file — harness integrity failure. "
        f"No delta will be reported. "
        f"Verify the fingerprint instruction text (see 16_BLK2_SPECIFICATION.md §4)."
    )
```

**Semantics:**
- `False` (not `None`) is the abort condition. `None` (adapter does not participate) is NOT
  an abort condition and must not be treated as one.
- The abort is immediate: on the first WITH-arm run that fails the gate, the scorer raises
  without completing the remaining runs in the matrix.
- The `HarnessValidityError` propagates out of `score()` to the CLI, which must catch it,
  print the error message, and exit non-zero. No `ScoreReport` is returned.
- The abort does NOT trigger the Q2 retry logic. `_run_with_retry()` applies the Q2 policy
  based on `result.passed`. The fingerprint check in `scorer.py` inspects the result returned
  by `_run_with_retry()`, after Q2 has already resolved.

### 9.2 No change to `_run_with_retry()`

`_run_with_retry()` is not modified. It is unaware of fingerprint validity. The Q2 retry is
based on `result.passed and result.timeout`, not on harness validity. A WITH-arm run that
passes the task but fails the fingerprint gate will have `passed=True` and
`harness_fingerprint_valid=False`; the abort occurs in `score()`, not inside `_run_with_retry()`.

### 9.3 No change to aggregation

`_aggregate()` is not modified. If execution reaches `_aggregate()`, all WITH-arm runs had
`harness_fingerprint_valid=True` (or `None` for non-participating adapters). The aggregation
logic is unchanged.

---

## 10. Database and Schema Changes

### 10.1 Schema change — `runs` table

Add one nullable column to the `runs` table in `primer/store/schema.sql`:

```sql
harness_fingerprint_valid INTEGER   -- NULL = not checked; 1 = valid; 0 = failed
```

Add the column declaration after `flaky INTEGER NOT NULL` in the `CREATE TABLE IF NOT EXISTS runs`
block. New databases created from `schema.sql` will include this column from the start.

**Encoding:**

| Python | SQLite |
|---|---|
| `True` | `1` |
| `False` | `0` |
| `None` | `NULL` |

### 10.2 Migration — v1 → v2

Bump `CURRENT_SCHEMA_VERSION` from `1` to `2` in `primer/store/migrations.py`.

Add `_migration_v2()`:

```
def _migration_v2(conn: sqlite3.Connection) -> None:
    """v1 → v2: add harness_fingerprint_valid column to runs (BLK-2).

    Additive, backward-compatible. Existing rows have NULL (= not checked).
    Idempotent: safe to re-run on a db that already has the column.
    """
    try:
        conn.execute(
            "ALTER TABLE runs ADD COLUMN harness_fingerprint_valid INTEGER"
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            pass  # already applied — idempotent
        else:
            raise
```

Add the migration call to `apply_migrations()`:

```
if current < 2:
    _migration_v2(conn)
    set_schema_version(conn, 2)
    log.info("applied migration v2")
```

**Backward compatibility:** existing databases at v1 receive a new nullable column. All
existing rows read `NULL` for `harness_fingerprint_valid`. No reader breaks because `NULL`
is already the Python-side default (`None`) of the new `RunResult` field.

### 10.3 `db.py` — `save_report()` update

The `INSERT INTO runs (...)` statement in `save_report()` must include `harness_fingerprint_valid`:

- Add `harness_fingerprint_valid` to the column list.
- Add the parameter: `1 if run.harness_fingerprint_valid else (0 if run.harness_fingerprint_valid is False else None)`.

The encoding expression handles all three states (`True` → 1, `False` → 0, `None` → `None`/SQL NULL).

`_row_to_score_report()` does not reconstruct `RunResult` objects from the database (it builds
`ScoreReport` and `TaskScore` only), so no change is required there.

---

## 11. Error Handling and `HarnessValidityError` Semantics

### 11.1 New exception

Add to `primer/errors.py`:

```python
class HarnessValidityError(PrimerError):
    """Raised when the WITH arm does not acknowledge the context file.

    The fingerprint instruction planted in the context file was not found in
    the agent's log output. The harness cannot certify that the agent read the
    file. No delta is reported (M4 standing gate).
    """
```

`errors.py` is a leaf module (imports nothing from PRIMER). Adding the exception here is
zero-risk.

### 11.2 Propagation path

```
run_task()          → RunResult.harness_fingerprint_valid = False
  ↓ returned to
_run_with_retry()   → passes RunResult up unchanged (unaware of fingerprint)
  ↓ returned to
score() inner loop  → checks harness_fingerprint_valid; raises HarnessValidityError
  ↓ propagates to
CLI (primer eval)   → catches HarnessValidityError, prints message, exits non-zero
```

The CLI catch is in `primer/cli.py`. The `score()` call is wrapped in an existing try/except
or the error propagates naturally to the CLI's top-level error handler. The exact CLI handling
is not specified here; the minimum requirement is that `HarnessValidityError` is not silently
swallowed and the process exits non-zero.

### 11.3 What the error message must contain

The `HarnessValidityError` message (constructed in `score()` per §9.1) must include:

1. The failing task ID.
2. The run number within the matrix.
3. A clear statement that no delta will be reported.
4. A pointer to this specification document for the fingerprint instruction verification procedure.

### 11.4 What the error must NOT do

- Must not report a `success_delta` of any kind. The `ScoreReport` must not be returned or
  persisted when `HarnessValidityError` is raised.
- Must not silently fall back to "report zero delta" or "skip the gate."
- Must not be catchable inside `score()` itself (it propagates out).

### 11.5 `harness_fingerprint_valid=None` is never an error

An adapter that returns `None` from `check_fingerprint()` (default) causes
`harness_fingerprint_valid=None` in every `RunResult`. This is not an abort condition. PRIMER
operates without the fingerprint gate for such adapters. The gate is opt-in per adapter.

---

## 12. Test Plan

All tests go in `tests/test_runner_isolation.py` (M4 fingerprint section already exists at line
670). Tests G-1 through G-5 and G-7 require no Docker and no API key.

### 12.1 Probe A — Fingerprint injection into context file (G-4)

**Test name:** `test_fingerprint_appended_to_with_arm_context_file`

**Method:** Mock `_clone_repo` to create `work_dir`. Call `run_task()` with `with_context=True`,
a non-empty `context_content`, and the full Docker/egress mock stack. Capture the content of
`work_dir / adapter.context_filename()` at container-launch time (via a `containers.run`
side effect, before the `finally` rmtree). Assert that `FINGERPRINT_INSTRUCTION` text appears
in the captured file content, and that the original `context_content` also appears (the
instruction is appended, not replacing).

**Failure mode caught:** Regression where the runner writes `context_content` without appending
the fingerprint instruction.

### 12.2 Probe C — No fingerprint in WITHOUT arm (G-5)

**Test name:** `test_no_fingerprint_in_without_arm_run_result`

**Method:** Call `run_task()` with `with_context=False`, full mocks. Assert that
`result.harness_fingerprint_valid is None`. Assert that no context file is written to `work_dir`.

**Failure mode caught:** Regression where the WITHOUT arm incorrectly appends a fingerprint
instruction or returns a non-None fingerprint validity value.

### 12.3 Abort path — mocked `False` → `HarnessValidityError` (G-7)

**Test name:** `test_abort_on_harness_fingerprint_false`

**Method:** Mock `run_task` to return a `RunResult` with `passed=True`, `with_context=True`,
`harness_fingerprint_valid=False`. Call `scorer.score()` with one task, `runs_per_config=1`.
Assert that `HarnessValidityError` is raised. Assert that `score()` does NOT return a
`ScoreReport`.

**Failure mode caught:** Regression where `score()` ignores `harness_fingerprint_valid=False`
and reports a delta as if the harness were valid.

### 12.4 `HarnessValidityError` importability (G-1)

**Test name:** (already satisfiable as an import check)

```python
from primer.errors import HarnessValidityError
assert issubclass(HarnessValidityError, Exception)
```

Can be added as a single assertion inside any of the above tests or as a standalone smoke test.

### 12.5 ABC concrete defaults (G-2)

**Test name:** `test_agent_adapter_fingerprint_defaults`

**Method:** Instantiate any concrete adapter (e.g. `ClaudeCodeAdapter`). Confirm that
`adapter.fingerprint_instruction()` is callable and that the ABC base-class default returns
`None`. Confirm that `adapter.check_fingerprint("some log", True)` does not raise, and that
calling `super().check_fingerprint(...)` returns `None`.

### 12.6 `RunResult` schema + migration (G-3)

**Test name:** `test_migration_v2_adds_fingerprint_column`

**Method:** Create an in-memory SQLite database. Apply schema.sql (simulating a fresh v0 db).
Set `schema_version = 1` in `_meta`. Call `apply_migrations()`. Assert `schema_version == 2`.
Assert `harness_fingerprint_valid` column exists in the `runs` table. Assert that an INSERT
into `runs` without the column succeeds (NULL default). Assert idempotency by calling
`apply_migrations()` again (no error).

### 12.7 Live tests (G-6, G-8, G-9) — requires API key

These tests are gated behind the existing `PRIMER_RUN_DOCKER_TESTS=1` environment variable.
They cannot be specified precisely until G-4's empirical verification (§4.4) is complete and
the `FINGERPRINT_INSTRUCTION` text is locked.

**Expected test names:**
- `test_live_with_arm_fingerprint_found_in_log`
- `test_live_without_arm_fingerprint_not_checked`
- `test_live_full_eval_delta_computed_after_fingerprint_gate`

---

## 13. Risks

| Risk | Severity | Description | Mitigation |
|---|---|---|---|
| **R1 — Instruction text does not produce the marker** | **Critical** | The `FINGERPRINT_INSTRUCTION` text may not cause Claude Code to output `FINGERPRINT_MARKER` in the log. If every WITH arm run fails the gate, all evals abort. | Empirical verification (§4.4) is mandatory before locking text. Draft two candidates; test both. |
| **R2 — Agent version drift changes behaviour** | High | A future Claude Code version may parse or obey the instruction differently. The gate could fail after a version bump. | The instruction is a simple output directive; resistance to version drift favours explicit over implicit phrasing. Re-verify on each major Claude Code version. |
| **R3 — Marker appears in WITHOUT arm log** | Medium | If the agent hallucinates the marker string (unlikely but possible), the gate does not catch it (WITHOUT arm returns `None`, not checked). A false "clean" WITHOUT run would not cause an abort. | Specificity of the marker string. Post-MVP: consider a random-nonce fingerprint per run. |
| **R4 — `dontAsk` mode restricts marker output** | Medium | With `--permission-mode dontAsk`, tool calls not in `--allowedTools` are silently denied. If outputting the marker requires a tool not in the allowed set, it would fail silently. The `result` field approach (response text, not a tool call) avoids this. | Prefer instruction targeting the `result` field. Confirm in empirical verification (§4.4). |
| **R5 — `check_fingerprint` raises unexpectedly** | Low | If `check_fingerprint()` raises instead of returning `bool \| None`, it propagates out of `run_task()` and aborts the run with an unhandled exception rather than a clean `HarnessValidityError`. | Spec requires `check_fingerprint()` must not raise. Implementation must use `try/except`. |
| **R6 — Migration fails on production db** | Low | If a database was somehow written with a `harness_fingerprint_valid` column already (e.g. partial earlier attempt), the `ALTER TABLE ADD COLUMN` fails with a duplicate-column error. | Migration must be idempotent: catch and swallow `"duplicate column name"` `OperationalError` (specified in §10.2). |
| **R7 — `save_report()` encoding of `None`** | Low | Python `None` must map to SQL `NULL`, not `0`. The expression `1 if x else (0 if x is False else None)` evaluates `None` correctly via the `is False` test rather than truthiness. | Encoding expression explicitly specified in §10.3; must be tested in `test_migration_v2_adds_fingerprint_column`. |
| **R8 — `score()` aborts on `None` from non-participating adapter** | Low | If the abort check uses `not run_result.harness_fingerprint_valid` instead of `run_result.harness_fingerprint_valid is False`, it would incorrectly abort on `None`. | Abort condition is strictly `is False`, never truthiness. Specified in §9.1. |

---

## 14. Rollback Plan

BLK-2 touches 9 files. Rollback is:

```
git revert <BLK-2 commits> -- \
  primer/errors.py \
  primer/eval/agent_adapter.py \
  primer/eval/models.py \
  primer/store/schema.sql \
  primer/store/migrations.py \
  primer/eval/adapters/claude_code.py \
  primer/eval/runner.py \
  primer/eval/scorer.py \
  tests/test_runner_isolation.py
```

**Database rollback:** reverting the code does not remove the `harness_fingerprint_valid`
column from existing databases. The reverted code will not write to or read from that column.
Existing rows are unaffected. If the column must be removed, a manual `ALTER TABLE` is required
in SQLite (which does not support `DROP COLUMN` before version 3.35.0; on older SQLite, a
table-recreation migration is required). For most rollback scenarios, leaving the column with
`NULL` values is harmless and the preferred approach.

**Behavioural rollback:** after reverting the code, PRIMER returns to the pre-BLK-2 state:
no fingerprint gate, no abort on harness failure, `success_delta` always computed. This is
strictly less safe than BLK-2, but operationally identical to the current state.

---

## 15. Implementation Order

BLK-2 must be implemented in this strict sequence. Each step validates before the next begins.

```
Step 1 — primer/errors.py
         Add HarnessValidityError.
         Validate: importable; issubclass(HarnessValidityError, PrimerError).

Step 2 — primer/eval/agent_adapter.py
         Add fingerprint_instruction() and check_fingerprint() concrete defaults (return None).
         Validate: ClaudeCodeAdapter still passes all existing adapter tests (no regression);
         confirm ABC methods are callable on any concrete instance.

Step 3 — primer/eval/models.py
         Add harness_fingerprint_valid: bool | None = None to RunResult.
         Validate: all existing tests that construct RunResult pass without modification
         (new field has a default).

Step 4 — primer/store/schema.sql + primer/store/migrations.py + primer/store/db.py
         Add column to schema.sql; add _migration_v2(); bump CURRENT_SCHEMA_VERSION to 2;
         update save_report() INSERT.
         Validate: test_store_round_trip passes; test_migration_v2_adds_fingerprint_column
         passes; existing db round-trips without error.

Step 5 — primer/eval/adapters/claude_code.py
         Replace FINGERPRINT_INSTRUCTION label with provisional directive text (§4.2, marked
         [EMPIRICAL VERIFICATION REQUIRED]). Implement fingerprint_instruction() override
         (returns FINGERPRINT_INSTRUCTION). Implement check_fingerprint() override (substring
         search for FINGERPRINT_MARKER in raw_log when with_context=True; None otherwise).
         Validate: adapter-level unit tests for both methods; test_m4_fingerprint_constant_exists
         still passes.

Step 6 — primer/eval/runner.py
         Step 3 WITH arm: append fingerprint instruction before write_text().
         After Step 8: call adapter.check_fingerprint(); store in local variable.
         RunResult construction: add harness_fingerprint_valid=fingerprint_valid.
         Validate: test_fingerprint_appended_to_with_arm_context_file (G-4 Probe A);
         test_no_fingerprint_in_without_arm_run_result (G-5 Probe C);
         test_source_repo_not_mutated still passes (BLK-5 regression check);
         all 31+ existing runner tests pass.

Step 7 — primer/eval/scorer.py
         Add HarnessValidityError import.
         Add abort check in score() inner loop (§9.1).
         Validate: test_abort_on_harness_fingerprint_false (G-7);
         all existing scorer tests pass (mocked run_task returns harness_fingerprint_valid=None
         by default, which is never an abort condition).

Step 8 — tests/test_runner_isolation.py
         Add Probe A test (G-4), Probe C test (G-5), abort test (G-7), ABC defaults test
         (G-2), migration test (G-3), importability check (G-1).
         Validate: full BLK-2 target suite green.

Step 9 — Empirical verification (when ANTHROPIC_API_KEY available)
         Execute §4.4 verification procedure.
         Lock FINGERPRINT_INSTRUCTION text in claude_code.py.
         Run live G-6 and G-8 tests.
         Author BLK-2 Completion Report.
```

Steps 1–8 can be implemented in a single session without Docker or an API key. Step 9 requires
the API key and is the only step gated on an external resource.

---

## Scope Boundary

BLK-2 is a **pure addition** of the harness-validity gate. It does not:

- Change evaluation semantics (pass/fail, scoring, or aggregation logic).
- Affect the WITHOUT arm's behaviour in any observable way.
- Modify the context file content for adapters that return `None` from `fingerprint_instruction()`.
- Change the `ScoreReport` schema.
- Affect `cli.py` beyond ensuring `HarnessValidityError` propagates to a non-zero exit (which
  requires only that the exception is not caught and swallowed inside `score()`).
- Begin BLK-3 (eligibility predicate) or BLK-4 (runs persistence completeness).

---

*Specification only. No implementation, no code, no patches.*
*All file paths, line numbers, and field names are grounded in the codebase as of 2026-06-12.*
*Authority: Decision Addendum M4 is the governing ruling. This document refines it into exact*
*implementation contracts. Conflicts with earlier documents yield to this specification.*
