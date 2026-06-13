# BLK-5 Completion Report — Source-Repository Mutation Fix

**Date:** 2026-06-12
**Status:** COMPLETE
**Implemented by:** Claude Opus 4.8 (implementation) / Claude Sonnet 4.6 (specification + plan)
**Specification authority:** `13_BLK5_SPECIFICATION.md`, `14_BLK5_IMPLEMENTATION_PLAN.md`

---

## 1. Files Modified

| File | Change type | Net lines |
|---|---|---|
| `primer/eval/runner.py` | Step 3 body rewrite + docstring update | +13 / −8 |
| `primer/eval/scorer.py` | Remove source-repo write/unlink block; thread `context_content`; remove `_prepare_context`; remove stale `Path` import; update module docstring | +16 / −49 |
| `tests/test_runner_isolation.py` | Update stale comment; add `test_source_repo_not_mutated`; add `test_context_file_written_to_clone`; add `_build_docker_mock_stack` helper | +145 / −2 |

**No other files were touched.** `cli.py`, `test_scorer.py`, and all other files are unchanged, consistent with the specification's scope.

---

## 2. Exact Changes Made

### `primer/eval/runner.py`

**Change 1 (pre-existing):** `context_content: str = ""` parameter added to `run_task()` signature.

**Change 2 (this session):** Step 3 body rewritten. The old WITH-arm logic checked `context_file_path.exists()` and raised `RuntimeError` if absent (relying on the scorer having pre-staged the file in the source repo). The new WITH-arm logic writes `context_content` directly to `work_dir / adapter.context_filename()` — the cloned directory created by `_clone_repo` in Step 1. The WITHOUT arm is unchanged.

**Change 3:** Module-level docstring Step 3 description updated to "Write / omit context_filename from the context_content parameter … source repo never touched (BLK-5)".

**Removed:** The comment `# File is already written by the caller (scorer) before run_task` and the `RuntimeError("Context file expected … but was not found")`.

### `primer/eval/scorer.py`

**Change 4:** Module docstring updated to reflect that the runner, not the scorer, manages the context file.

**Change 5:** `score()` inner loop — the entire source-repo write/unlink block removed:
```python
# REMOVED:
context_path = _prepare_context(repo_path, adapter, context_content, with_ctx)
source_context = Path(repo_path) / adapter.context_filename()
try:
    if with_ctx and context_content:
        source_context.write_text(context_content, encoding="utf-8")
    else:
        if source_context.exists():
            source_context.unlink()
    run_result = _run_with_retry(...)
finally:
    if source_context.exists():
        source_context.unlink()
```
Replaced with a direct `_run_with_retry(...)` call passing `context_content=context_content`.

**Change 6:** `_run_with_retry()` signature extended with `context_content: str = ""`; both internal `run_task()` calls (initial + Q2 retry) now pass `context_content=context_content`.

**Change 7 (cleanup):** `_prepare_context()` removed — the function was vestigial; its return value was already unused in the current scorer. The plan advised retaining it as dead code, but `Path` was its only unique dependency and became an unused import once the function was removed. Removing both avoids a `ruff` F401 violation (the project enforces `ruff check .` per its own generated conventions). This is a bounded, in-scope cleanup with no callers and no semantic change.

### `tests/test_runner_isolation.py`

**Change 8:** Stale comment on line 292 updated from `"We need a real repo path for the source_context write/delete"` to a correct post-BLK-5 description.

**Change 9:** `_build_docker_mock_stack()` helper added to deduplicate mock setup across the two new tests.

**Change 10:** `test_source_repo_not_mutated()` added — the primary BLK-5 acceptance gate. Records the source repo's directory listing before a WITH-arm `run_task()` call (with `_clone_repo` mocked to only create `work_dir`). Asserts that `CLAUDE.md` does NOT exist in the source repo after the call, and that the directory listing is byte-for-byte identical.

**Change 11:** `test_context_file_written_to_clone()` added — validates the positive case: that the runner correctly writes `context_content` into `work_dir` during a WITH-arm run. Uses a `containers.run` side effect to capture the file content at the moment the container is launched (before the `finally` rmtree clears it).

---

## 3. Validation Results

### Step 1 validation (after `runner.py` changes)
```
pytest tests/test_runner_isolation.py tests/test_arch_boundaries.py
32 passed, 1 skipped — 86.08s
```

### Step 2 validation (after `scorer.py` changes)
```
pytest tests/test_scorer.py tests/test_arch_boundaries.py
22 passed — 2.39s
```

### Step 3 validation (new tests only)
```
pytest -k "source_repo_not_mutated or context_file_written_to_clone or ..."
5 passed — 2.14s
```

### Final targeted validation (all three acceptance files)
```
pytest tests/test_runner_isolation.py tests/test_scorer.py tests/test_arch_boundaries.py -v
53 passed, 1 skipped — 63.24s
```

The 1 skip is `test_run_task_real_docker_without_context` — a pre-existing Docker integration test gated behind `PRIMER_RUN_DOCKER_TESTS=1`. Expected and unchanged.

---

## 4. Acceptance Gate Status

| Gate | Description | Status |
|---|---|---|
| **G1** | `run_task()` signature includes `context_content: str = ""` | **PASS** — confirmed by `inspect.signature(run_task)` |
| **G2** | `_run_with_retry()` threads `context_content` to both `run_task()` calls | **PASS** — 3 occurrences of `context_content=context_content` in scorer (score() call + both run_task calls inside _run_with_retry) |
| **G3** | `score()` inner loop contains NO `source_context.write_text()` or `source_context.unlink()` | **PASS** — `grep source_context primer/eval/scorer.py` returns no matches |
| **G4** | `test_source_repo_not_mutated`: `py_repo/CLAUDE.md` does not appear after WITH-arm `run_task()` | **PASS** — test added and passes |
| **G5** | All pre-existing `test_runner_isolation.py` tests pass | **PASS** — 31 passed, 1 skipped (Docker gate); 0 regressions |
| **G6** | All `test_scorer.py` tests pass | **PASS** — 19 passed, 0 regressions |
| **G7** | `cli.py` requires no change | **PASS** — confirmed by inspection; file not touched |

**All 7 gates: PASS.**

---

## 5. Remaining Risks

| Risk | Assessment |
|---|---|
| **R1 — Full suite against Phase 6/7 tests** | A background full-suite run (33 min) was terminated due to a hanging test with a `CloseWait` HTTPS socket to a Google (Gemini API) endpoint. This hang is pre-existing and unrelated to BLK-5 — it is a live-network dependency in Phase 6/7 tests, not in any BLK-5 file. The three BLK-5 target files (`test_runner_isolation.py`, `test_scorer.py`, `test_arch_boundaries.py`) all passed cleanly. |
| **R2 — Docker integration path** | The real WITH-arm path (runner writing into a live Docker container's `/work`) is not exercised in mocked tests. This is by design per the specification; the mocked tests are authoritative for BLK-5 correctness. |
| **R3 — `_prepare_context` removal** | Removed rather than kept as dead code (deviation from plan option B). Confirmed no callers before removal. The `Path` import removal avoids a ruff F401 regression. Risk: none found. |
| **R4 — Eligibility guard** | If a repo has `CLAUDE.md` committed, `_clone_repo`'s `git checkout --force` restores it, and the runner then overwrites it (WITH) or deletes it (WITHOUT). This was documented in the specification as a separate concern (A2), unchanged by BLK-5. |

---

## 6. Final Verdict

**BLK-5 is complete.**

The source-repository mutation defect is eliminated. `CLAUDE.md` is now written exclusively inside the cloned `work_dir` by `run_task()`, never in the caller's source tree. All 7 acceptance gates pass. Zero regressions in the BLK-5 target test files. The implementation matches the specification exactly, with one minor in-scope cleanup (`_prepare_context` + unused `Path` import removed rather than retained as dead code).

**BLK-2 is now unblocked.** The clean injection point in `run_task()` (the `context_content` parameter + `context_file_path.write_text()` in Step 3) is the correct site for fingerprint injection.
