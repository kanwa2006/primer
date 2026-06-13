# BLK-5 Implementation Plan

**Date:** 2026-06-07
**Status:** PLAN — No implementation has begun.
**Depends on:** `13_BLK5_SPECIFICATION.md` (read first)

---

## 1. Implementation Order

BLK-5 is a strict 4-step sequence with no parallelism. Each step validates before the next
begins.

```
Step 1 → runner.py    (accept context_content; write to clone)
Step 2 → scorer.py    (remove source-repo mutation; thread parameter)
Step 3 → tests        (update call sites; add repo-safety test)
Step 4 → validation   (full suite green; repo-safety confirmed)
```

---

## 2. Step-by-Step Plan

### Step 1 — `primer/eval/runner.py`

**Objective:** `run_task()` writes the context file itself; never relies on source-repo state.

**Exact change — signature:**
Add `context_content: str = ""` as the eighth parameter of `run_task()`, after `image_tag`.
The default `""` preserves backward compatibility for any caller that doesn't pass it yet
(specifically: any existing test that calls `run_task()` directly).

**Exact change — Step 3 body (lines 92–111):**

Replace the current Step 3 entirely. New logic:

- `context_file_path = work_dir / adapter.context_filename()` (unchanged — line 93)
- **WITH arm** (`with_context=True`): write `context_content` to `context_file_path`.
  No existence check. No RuntimeError. The runner is now the authority on the file.
- **WITHOUT arm** (`with_context=False`): if the file exists in the clone (it shouldn't,
  but guard against it), delete it. Then assert it is absent. (Unchanged from current logic.)
- Remove the comment `# File is already written by the caller (scorer) before run_task`
  and the `RuntimeError` for "not found" in WITH arm.

**Docstring update:** update the module-level docstring Step 3 description to say
"Write / omit context_filename from the context_content parameter."

**Risk level:** Low. The clone exists before Step 3. `write_text()` on a path whose parent
exists is safe. The WITHOUT arm path is identical to the current code.

**Validation after Step 1:**
- `pytest tests/test_arch_boundaries.py` — no boundary violations
- `pytest tests/test_runner_isolation.py` — no test regression (all tests use `with_context=False`
  or mock `_clone_repo`; the new parameter defaults to `""`)
- Manual check: `from primer.eval.runner import run_task; import inspect; print(inspect.signature(run_task))`
  confirms `context_content` is present.

---

### Step 2 — `primer/eval/scorer.py`

**Objective:** Remove the source-repo mutation entirely; thread `context_content` into the
run path.

**Exact change A — `_run_with_retry()` signature:**
Add `context_content: str = ""` as the eighth parameter (after `image_tag`).

**Exact change B — `_run_with_retry()` body:**
Pass `context_content=context_content` to **both** `run_task()` call sites inside this
function (the initial call on line ~144 and the Q2 retry call on line ~157).

**Exact change C — `score()` inner loop:**
Remove the entire source-repo write/unlink block (lines 77–106 in the current scorer).
Replace the `_run_with_retry(...)` call with one that passes `context_content=context_content`.
The `context_content` variable already exists as a parameter of `score()`.

*Lines to remove:*
```python
context_path = _prepare_context(repo_path, adapter, context_content, with_ctx)
source_context = Path(repo_path) / adapter.context_filename()
try:
    if with_ctx and context_content:
        source_context.write_text(context_content, encoding="utf-8")
    else:
        if source_context.exists():
            source_context.unlink()
    run_result = _run_with_retry(
        task=task, repo_path=repo_path, with_context=with_ctx,
        profile=profile, config=config, adapter=adapter, image_tag=image_tag,
    )
finally:
    if source_context.exists():
        source_context.unlink()
```

*Replace with:*
```
run_result = _run_with_retry(
    task=task, repo_path=repo_path, with_context=with_ctx,
    profile=profile, config=config, adapter=adapter, image_tag=image_tag,
    context_content=context_content,
)
```

**Exact change D (optional cleanup) — `_prepare_context()`:**
This function is now vestigial (its return value was already unused). It may be removed
entirely or retained with a comment marking it dead code. Removal is cleaner; retention is
zero-risk. Treat as optional. The `Path` import at the top of scorer is still needed for
other path operations; do not remove it even if `_prepare_context` is deleted.

**Risk level:** Low. This is a subtraction of lines that were the problem. The `finally`
block that was protecting against leaving a stale file in the source repo disappears
correctly — the source repo is no longer touched at all.

**Validation after Step 2:**
- `pytest tests/test_arch_boundaries.py tests/test_scorer.py tests/test_runner_isolation.py`
- Confirm `test_scorer.py` still passes — it mocks `run_task` with `MagicMock`, which
  accepts the new `context_content` kwarg automatically.

---

### Step 3 — `tests/test_runner_isolation.py`

**Objective:** Update stale comment; add repo-safety test.

**Exact change A — Stale comment update (line ~292):**
The comment `# We need a real repo path for the source_context write/delete` is no longer
true after BLK-5. Update or remove it.

**Exact change B — Repo-safety test (new test):**
Add `test_source_repo_not_mutated()` to the "Context file control" section. This test:

1. Records the directory listing of `py_repo_path` before calling `run_task()`.
2. Calls `run_task()` with `with_context=True`, a non-empty `context_content`, and a
   mocked Docker/clone stack.
3. Asserts that `py_repo_path / "CLAUDE.md"` does NOT exist after the call.
4. Asserts that the directory listing of `py_repo_path` is identical to before the call.

This test is the primary acceptance gate for BLK-5: it proves the source repo is clean
after a WITH-arm run.

**Exact change C — WITH-arm context test (optional new test):**
Optionally add `test_context_file_written_to_clone()`: mock `_clone_repo` to actually create
`work_dir`, then call `run_task()` with `with_context=True` and `context_content="# test"`.
Assert the file appears in `work_dir / adapter.context_filename()`. This validates the
runner writes correctly to the clone.

**Note on mocking:** since `_clone_repo` is patched to do nothing in the mocked tests,
`work_dir` won't be created automatically. The new WITH-arm test must either:
(a) patch `_clone_repo` to create `work_dir` as a side effect, or
(b) create `work_dir` manually in the test fixture before calling `run_task()`.

**Risk level:** Low. Test-only change. No production code is touched in this step.

---

### Step 4 — Full Validation

Run the full test suite (excluding Docker integration tests) and confirm:

```bash
pytest tests/ -v --tb=short
```

Specific checks:
1. `test_source_repo_not_mutated` passes.
2. `test_runner_isolation.py` — all 32+ existing tests still pass.
3. `test_scorer.py` — all tests still pass.
4. `test_arch_boundaries.py` — all 3 boundary tests pass.
5. No new failures beyond the pre-existing KL-1 async ordering failures.

---

## 3. Acceptance Gates

| Gate | Description | Requires Docker |
|---|---|---|
| **G1** | `run_task()` signature includes `context_content: str = ""` | No |
| **G2** | `_run_with_retry()` threads `context_content` to both `run_task()` calls | No |
| **G3** | `score()` inner loop contains NO `source_context.write_text()` or `source_context.unlink()` | No |
| **G4** | `test_source_repo_not_mutated`: `py_repo/CLAUDE.md` does not appear after WITH-arm `run_task()` | No (mocked) |
| **G5** | All pre-existing `test_runner_isolation.py` tests pass | No (mocked) |
| **G6** | All `test_scorer.py` tests pass | No (mocked) |
| **G7** | `cli.py` requires no change | No (confirmed by inspection) |

G1–G6 are all achievable without Docker or an API key. BLK-5 can be fully validated in
the current environment.

---

## 4. Risks

| Risk | Severity | Description | Mitigation |
|---|---|---|---|
| **R1 — WITH-arm test regression** | Low | New Step 3 writes to `work_dir` rather than expecting it pre-staged. All mocked tests use `with_context=False`, so no existing test exercises the WITH path. | Explicitly add the WITH-arm clone test (Step 3, Change C) to catch any regressions. |
| **R2 — `work_dir` not created in mocked tests** | Low | If `_clone_repo` is mocked, `work_dir` doesn't exist. Writing to it would fail. | All mocked tests use `with_context=False`; new WITH-arm tests must create `work_dir` manually. |
| **R3 — `_prepare_context` removal breaks an unreachable caller** | Very low | If removed, no caller is broken (confirmed: return value was unused). | Search the codebase before removing. If any caller found, keep as dead code. |
| **R4 — Q2 retry path misses `context_content`** | Medium (without the fix) | `_run_with_retry()` calls `run_task()` twice; both must receive `context_content`. | Both call sites are explicitly updated in Step 2. |
| **R5 — Parallel future evals break** | Not applicable | PRIMER runs sequentially (Q1). | N/A |

---

## 5. Recommended Validation Sequence

```
Step 1 complete? → run pytest test_runner_isolation.py (no regression)
Step 2 complete? → run pytest test_scorer.py test_runner_isolation.py
Step 3 complete? → run full suite; confirm G4 (repo-safety) passes
```

All three steps complete → BLK-5 is done. No Docker, no API key required.

---

## 6. Go / No-Go Recommendation

**GO — immediately.**

BLK-5 has:
- No external dependencies
- No API key requirement
- No Docker requirement (all validation via mocked tests)
- Clear, bounded change surface (3 files, ~15 lines net added / ~25 lines removed)
- Full rollback via `git revert` on those 3 files
- Direct enablement of BLK-2

It is the next implementation task after BLK-1 is proven.

---

## 7. Estimated Complexity

**Small.** Net change: ~25 lines removed from `scorer.py`, ~8 lines changed in `runner.py`,
~30 lines added to `test_runner_isolation.py` (repo-safety test). No schema changes, no
dependency changes, no architecture changes. A focused engineer with this document completes
BLK-5 in one session.
