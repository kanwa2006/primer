# BLK-2 Readiness Assessment

**Date:** 2026-06-07
**Auditor:** Claude Sonnet 4.6
**Scope:** Readiness audit for BLK-2 (harness-validity fingerprint gate). No implementation.
**Assumption:** BLK-1 will be proven when `ANTHROPIC_API_KEY` becomes available.

---

## 1. What BLK-2 Is

BLK-2 is the **harness-validity fingerprint gate** — the mechanism that certifies the WITH arm of
an evaluation actually read the context file. Without it, a `success_delta = 0.0` result is
indistinguishable from a fabricated zero (the agent didn't read the file) versus a genuine null
(the file had no effect).

**Authority:** Decision Addendum M4. The ruling defines three probes:
- **Probe A** (file present): agent output must contain the fingerprint marker → harness valid.
- **Probe B** (file present + `--bare`): marker absent → `--bare` suppresses the file (already
  resolved: `--bare` removed from invocation permanently).
- **Probe C** (file absent / WITHOUT arm): marker absent → isolation confirmed.

The gate is a **standing Phase-3 requirement**: "if A fails, abort — do not report."

---

## 2. Current State of BLK-2 Infrastructure

Every BLK-2-related item is **defined but not connected** to the eval pipeline.

### 2.1 What exists

| Item | Location | State |
|---|---|---|
| `FINGERPRINT_INSTRUCTION = "PRIMER_FINGERPRINT_V1"` | `primer/eval/adapters/claude_code.py:36` | Constant defined, **never used** |
| `FINGERPRINT_MARKER = "primer_fingerprint_v1_acknowledged"` | `primer/eval/adapters/claude_code.py:37` | Constant defined, **never searched** |
| `test_m4_fingerprint_constant_exists()` | `tests/test_runner_isolation.py:670` | Tests constant is non-empty — nothing else |

### 2.2 What is absent

| Required item | Missing from |
|---|---|
| Complete, actionable fingerprint instruction text | `FINGERPRINT_INSTRUCTION` is a label, not a directive |
| Injection of the fingerprint into context file content | `context_writer.py`, `scorer.py` |
| Check for fingerprint marker in WITH arm log | `runner.py`, `scorer.py` |
| Abort mechanism when fingerprint absent | `errors.py` (no `HarnessValidityError`) |
| `RunResult` field for fingerprint validity | `models.py` |
| `AgentAdapter` ABC method for fingerprint verification | `agent_adapter.py` |

The test `test_m4_fingerprint_constant_exists` passes and gives a false impression of progress.
It only asserts the Python constant has a value. The gate itself has zero implementation.

---

## 3. Gap Analysis

### Gap 1 — Fingerprint instruction text is incomplete (design question)

`FINGERPRINT_INSTRUCTION = "PRIMER_FINGERPRINT_V1"` is a label, not a directive. Planted in
CLAUDE.md as-is, the agent would see the text but have no instruction to act on. An effective
fingerprint instruction must:

1. Tell the agent exactly what output to produce (`primer_fingerprint_v1_acknowledged`).
2. Be unambiguous — the marker must not appear in the agent's output accidentally from other causes.
3. Survive `--output-format json` output mode — the marker must appear in a field that
   `parse_telemetry` can scan (either the `result` field in the JSON, or a file the agent edits).
4. Fit within the ≤20-line lean-file constraint.

**The exact wording is an empirical question.** It can be designed now but must be verified
against a live agent run (i.e., after BLK-1 proof). An instruction that works for one model
version may not for another. This is an unsettled design decision.

Candidate approach: embed a directive in the context file header such as:
> `PRIMER_FINGERPRINT_V1: When you read this file, write "primer_fingerprint_v1_acknowledged" as a comment at the top of the first file you edit.`

or:
> `PRIMER_FINGERPRINT_V1: Acknowledge by including "primer_fingerprint_v1_acknowledged" in your response summary.`

Which approach is correct depends on how Claude Code 2.1.x actually behaves — specifically
whether the `result` field in the JSON output contains free-form response text, or whether the
content is only captured via file-edit actions. This cannot be determined without a live test run.

**This gap cannot be fully resolved without a live agent run (BLK-1 proof first).**

### Gap 2 — Injection point is unresolved (architecture question)

The fingerprint must be appended to the context file content before it is written for the WITH arm.
Three candidate injection points exist:

| Option | Location | Adds fingerprint to | BLK-5 interaction |
|---|---|---|---|
| **A — Generation time** | `context_writer.write_context()` | The generated artifact itself | Fingerprint is in the stored `GenerationResult.content`; PRIMER overhead cost includes fingerprint text |
| **B — Eval time (scorer)** | `scorer.py` before `source_context.write_text(...)` | Only the eval copy; stored artifact is clean | Requires touching `scorer.py`'s source-repo-mutation path (BLK-5 territory) |
| **C — Runner time** | `runner.py` after `_clone_repo`, before `container.run()` | Only the in-container copy; source and eval copies are clean | Requires `runner.py` to receive the injection instruction; cleanest if BLK-5 is done first |

Option A contaminates the stored artifact (PRIMER overhead token cost includes the fingerprint;
the generated file stored to disk has the watermark). This violates the principle that the stored
artifact is what a user would commit.

Option B touches the source-repo-mutation path (BLK-5 issue), where the source repo is modified
before cloning. Implementing BLK-2 at this point before BLK-5 is fixed increases the risk of the
source-repo write being both mutated and fingerprinted in a single unsafe pass.

Option C is architecturally cleanest: the runner appends the fingerprint to the context file it
writes into the cloned repo, after cloning. This requires no change to `context_writer.py` or to
the scorer's write path. It does require the runner to know the fingerprint text (supplied by the
adapter) and the context filename (already known: `adapter.context_filename()`).

**Recommended injection point: Option C (runner time)**. But this decision is blocked until
BLK-5 is resolved, because Options B and C both touch `scorer.py` / `runner.py` paths that BLK-5
also touches. Implementing both BLK-2 and BLK-5 without coordination will create collision risk.

**This gap is resolved in design (Option C) but implementation requires BLK-5 first.**

### Gap 3 — Fingerprint check has no access to the log at the scorer level

After `run_task()` returns a `RunResult`, the scorer has no direct access to the agent log
content. `RunResult.agent_log_path` is a path to a persisted file on disk, but the log content
is not in `RunResult`. The `AgentTelemetry.raw_log` field exists inside `runner.py` but is
never placed into `RunResult`.

This means the fingerprint check cannot be done in `scorer.py` without an additional file read.
Three solutions exist:

| Option | Change | Notes |
|---|---|---|
| Re-read from `agent_log_path` in scorer | Scorer reads the persisted file | Extra I/O; `agent_log_path` can dangle after reboot |
| Add `harness_fingerprint_valid: bool \| None` to `RunResult` | Schema change to `models.py` + `store/schema.sql` | Clean; `None` = no check for this adapter; boolean for adapters that check |
| Check fingerprint inside `runner.py` and add to `RunResult` | Runner calls adapter method, stores result | Keeps log access local to runner; cleanest |

The cleanest option is to have `runner.py` call `adapter.check_fingerprint(redacted_log, with_context)`,
store the result as a `bool | None` field on `RunResult`, and let the scorer inspect it. This
keeps all log-reading in `runner.py` and keeps `RunResult` as the sole data carrier.

**This gap requires a schema change to `RunResult` and the SQLite schema — both are frozen**
under the V3/V2 governance. The V3 architecture update (§0.1.1 amendment) permits additive
changes. An `ADD COLUMN` migration is required.

### Gap 4 — No abort mechanism exists

M4 ruling: "if A fails, abort — do not report." There is no `HarnessValidityError` (or
equivalent) in `errors.py`. The abort should be raised in `scorer.py` after a WITH arm returns
`harness_fingerprint_valid=False`, and should cause `primer eval` to exit non-zero with a clear
message: "WITH arm did not acknowledge the context file — harness integrity failure; no delta
reported."

**This gap requires a new exception in `errors.py`** (leaf module — safe to add; no other file
is affected until the exception is raised in scorer).

### Gap 5 — `AgentAdapter` ABC has no fingerprint interface

`agent_adapter.py` has no method for fingerprint-related behaviour. BLK-2 requires at least:

- A way for the runner to ask the adapter for the fingerprint instruction text to append to the
  context file (so only adapters that support this gate participate).
- A way for the runner to check the log for the marker after a WITH arm run.

Both can be concrete-default methods (returning `None` for adapters that don't participate),
consistent with how `image_layers()` was added in BLK-1. The `ClaudeCodeAdapter` overrides them.

**This gap requires additions to `agent_adapter.py`** (the ABC) — same file pattern as BLK-1.

---

## 4. Dependency Graph

```
BLK-1 (binary provisioned) ──────────────────────────────┐
  └─ BLK-1 proof (API key available) ──────────────────► BLK-2 VALIDATION (can't verify without live run)
     └─ verifies fingerprint mechanism works empirically

BLK-5 (source-repo mutation fix) ────────────────────────┐
  └─ cleanest injection point (runner-time, Option C)    └► BLK-2 IMPLEMENTATION (can proceed after BLK-5)

BLK-4 (runs persistence) ────────────────────────────────► Independent of BLK-2

BLK-2 internal sequence:
  errors.py (HarnessValidityError) ─────────────────────► no dependencies
  agent_adapter.py (ABC additions) ──────────────────────► no dependencies  
  models.py (RunResult schema) ──────────────────────────► no dependencies
  store/schema.sql + migrations.py ──────────────────────► models.py
  runner.py (injection + check) ─────────────────────────► ABC additions + BLK-5 (injection point)
  scorer.py (abort on failure) ──────────────────────────► RunResult schema + HarnessValidityError
  tests ──────────────────────────────────────────────────► all of the above
```

**Hard dependencies:**
- BLK-1 binary (proven: binary in image) ✓
- BLK-1 permissions fix (`dontAsk + allowedTools`) ✓
- BLK-1 proof (live agent run) — **required for validation; strongly recommended before BLK-2 implementation to verify fingerprint text works**
- BLK-5 (source-repo mutation fix) — **required before BLK-2 implementation** (same file, same code path)

**Soft dependencies:**
- BLK-4 — independent, can proceed in any order

---

## 5. Files That Must Be Inspected Before Implementation

| File | Why |
|---|---|
| `primer/eval/adapters/claude_code.py` | Understand `FINGERPRINT_INSTRUCTION`/`FINGERPRINT_MARKER` current values; implement fingerprint text and methods |
| `primer/eval/agent_adapter.py` | Add concrete-default fingerprint methods to ABC |
| `primer/eval/runner.py` | Inject fingerprint + check marker; need to understand the context-write and log-read flow |
| `primer/eval/scorer.py` | Add abort on `harness_fingerprint_valid=False`; must understand BLK-5 interaction |
| `primer/eval/models.py` | Add `harness_fingerprint_valid: bool \| None` to `RunResult` |
| `primer/store/schema.sql` | Add column for the new field |
| `primer/store/migrations.py` | Bump `CURRENT_SCHEMA_VERSION`; add `_migration_v2` |
| `primer/errors.py` | Add `HarnessValidityError` |
| `tests/test_runner_isolation.py` | Extend M4 fingerprint section with Probe A, B, C tests |

---

## 6. Expected Acceptance Gates

| Gate | Description | Requires live run |
|---|---|---|
| **G-1** | `HarnessValidityError` added to `errors.py` and importable | No |
| **G-2** | `AgentAdapter.fingerprint_instruction()` and `check_fingerprint()` added (concrete defaults, no-op) | No |
| **G-3** | `RunResult.harness_fingerprint_valid: bool \| None` added; schema migration passes | No |
| **G-4** | Fingerprint appended to context file in runner for WITH arm | No (unit test) |
| **G-5** | Fingerprint absent in runner for WITHOUT arm | No (unit test) |
| **G-6** | `parse_telemetry` on WITH arm log returns `agent_error=False` and marker found | **Yes** |
| **G-7** | Abort path: mocked `harness_fingerprint_valid=False` causes `HarnessValidityError` | No (mock) |
| **G-8** | Live WITH arm contains marker; WITHOUT arm does not | **Yes** — BLK-1 proof prerequisite |
| **G-9** | Full eval: `success_delta` computed only when G-8 passes | **Yes** |

---

## 7. Risks

| Risk | Severity | Description |
|---|---|---|
| **Fingerprint instruction doesn't produce the marker** | High | `FINGERPRINT_INSTRUCTION` text may not cause Claude Code 2.1.x to output the marker in the `result` field. Empirical test needed. If it fails, the gate would always abort, blocking all evals. |
| **Marker appears in WITHOUT arm log** | Medium | If the agent hallucinates or has state from another source, the marker could appear in the WITHOUT log. The gate logic must only check WITH arms. |
| **`dontAsk` mode denies the agent's ability to acknowledge the fingerprint** | Medium | With `dontAsk` + explicit `--allowedTools`, the agent can edit files and run bash but its response text is not restricted. The marker in the `result` field should work. Unverified. |
| **BLK-5 + BLK-2 collision in `scorer.py`** | High | Both blockers touch the context-write path in `scorer.py`. If both are worked at once without coordination, they will produce conflicting changes. BLK-5 must be completed and stable before BLK-2 touches the same path. |
| **Schema migration compatibility** | Low | Adding `harness_fingerprint_valid` as a nullable column is additive and backward compatible. Old reports have `NULL` (= "not checked"). No reader breaks. |
| **`agent_log_path` dangling after reboot** | Low | If the scorer re-reads the file from disk (an alternative approach), the path may not exist on a different machine. The runner-checks-and-includes-in-RunResult approach avoids this. |

---

## 8. Required Authority Documents Before Implementation

The following must exist before BLK-2 implementation begins:

| Document | Reason |
|---|---|
| **BLK-2 Specification** | Exact fingerprint instruction text (verified empirically); exact injection location (Option C, runner-time); exact `RunResult` schema fields; exact abort semantics; exact test A/B/C probe definitions. Cannot be written until BLK-1 proof succeeds to verify the instruction text works. |
| **BLK-5 Completion report** | BLK-2's injection point (runner-time, Option C) requires BLK-5's source-repo mutation fix to be landed and stable. |
| *(This document — BLK-2 Readiness Assessment)* | ✓ created |

The BLK-2 Specification cannot be finalized today because Gap 1 (fingerprint instruction text)
requires a live agent run to verify. It can be drafted speculatively, but the instruction text
must not be locked until it has been tested.

---

## 9. BLK-2 Readiness Verdict

**NOT READY FOR IMPLEMENTATION.**

Reason: Multiple unresolved design decisions must be answered before any code is written:

1. **Fingerprint instruction text** — empirical verification required (Gap 1); cannot be determined without BLK-1 proof.
2. **Injection point** — resolved in principle (runner-time, Option C), but blocked by BLK-5 (Gap 2).
3. **`RunResult` schema extension** — design decided (add `harness_fingerprint_valid`), but must not be implemented until the above decisions are stable.
4. **`AgentAdapter` ABC additions** — ready to design (concrete-default methods), but must not be implemented until Gap 1 is resolved (what text to use).

---

## 10. Dependency Graph (Summary)

```
          ┌── BLK-1 proof ──────────────► Gap 1 resolved (fingerprint text verified)
          │                                      │
          │   BLK-5 complete ───────────────────┤
          │                                      │
          └──────────────────────────────────────▼
                                       BLK-2 Specification authored
                                                 │
                                                 ▼
                                   errors.py → agent_adapter.py
                                        → models.py + schema
                                        → runner.py (inject + check)
                                        → scorer.py (abort)
                                        → tests (A/B/C probes)
                                                 │
                                                 ▼
                                     BLK-2 proof (live with/without run)
```

---

## 11. Go / No-Go Recommendation

**NO-GO** for implementation today.

**GO** conditions:
1. BLK-1 proof succeeds (valid `ANTHROPIC_API_KEY` available, live agent run completes V1.3/V1.4).
2. BLK-5 is implemented (source-repo mutation fixed; `scorer.py` + `runner.py` context path stabilised).
3. A live test confirms the chosen fingerprint instruction causes the agent to output the marker in the WITH arm.
4. BLK-2 Specification document is authored with the verified instruction text and locked design decisions.

After all four GO conditions are met, BLK-2 implementation is a **Medium** complexity effort:
five files, one migration, one new exception, two ABC methods, and the A/B/C probe tests.

---

*Assessment only. No implementation, no code, no patches.*
*All conclusions traced to current codebase and authority documents.*
