# BLK-5 Specification — Source-Repository Mutation Fix

**Date:** 2026-06-07
**Status:** SPECIFICATION — No implementation has begun.
**Auditor:** Claude Sonnet 4.6
**Authority basis:** Architecture Audit §11 (verified findings), Execution Readiness Assessment §7,
Minimum Path §E, BLK-2 Readiness Assessment §4 (hard prerequisite).

---

## 1. Problem Statement

BLK-5 is the **source-repository mutation** issue. `scorer.py` currently writes the generated
context file (e.g. `CLAUDE.md`) directly into the caller's source repository before each WITH-arm
run, then deletes it in a `finally` block after the run.

This is a data-loss footgun, a measurement-validity risk, and a hard dependency blocker for BLK-2.

**Current execution path (WITH arm):**
```
scorer.py:89    source_context.write_text(context_content, ...)  ← writes to CALLER's repo
scorer.py:94    _run_with_retry(...)
  → run_task(...)
    runner.py:87   _clone_repo(repo_path, work_dir, commit)       ← copies source INCLUDING the file
    runner.py:94   with_context=True → checks file exists in clone ← passes because scorer pre-staged it
    ...container runs...
scorer.py:106   source_context.unlink()                           ← deletes from CALLER's repo
```

**Why this is wrong:**

| Risk | Consequence |
|---|---|
| Process killed between write (line 89) and finally-unlink (line 106) | `CLAUDE.md` left in user's working tree permanently |
| User has `CLAUDE.md` committed | PRIMER overwrites it silently, then deletes it |
| Concurrent future eval runs | Both write to the same path; race condition corrupts content |
| BLK-2 fingerprint injection | Would land on the source-repo mutation path; both BLK-2 and BLK-5 would touch the same dangerous code simultaneously |
| Git status during eval | User's `git status` shows a modified/untracked `CLAUDE.md` mid-run |

---

## 2. Root Cause

The runner's Step 3 was designed to check that the file exists in the cloned `work_dir`:

```python
# runner.py:94–100
if with_context:
    if not context_file_path.exists():
        raise RuntimeError("Context file expected at {context_file_path} but was not found.")
    # File is already written by the caller (scorer) before run_task
```

The comment says "already written by the caller." This design assumed the scorer would pre-stage
the file in the source repo before cloning. Since `_clone_repo` copies the source tree first,
the file appears in `work_dir` because it was written to the source before the copy.

**Root cause in one sentence:** the runner depends on the scorer having pre-mutated the source repo so that `_clone_repo` can pick up the context file; this is an indirect injection path through a shared mutable directory rather than a direct parameter.

**The fix:** pass `context_content` as a parameter to `run_task()`, which then writes the file
directly to `work_dir` after cloning — never touching the source repo.

---

## 3. Exact Scope

BLK-5 is **a pure refactor** of the context-file injection path. It changes no evaluation
semantics: the context file ends up in the same place (`/work/CLAUDE.md` inside the container),
the WITH/WITHOUT isolation is identical, and all `RunResult` fields remain unchanged.

**What changes:** WHERE the context file is written (cloned work directory, not source repo).
**What does not change:** the file content, the isolation guarantees, the pass/fail logic,
the agent invocation, the scoring, the data model.

---

## 4. Files Involved

| File | Role | Change type |
|---|---|---|
| `primer/eval/runner.py` | The fat runner; owns all isolation | Signature change + Step 3 rewrite |
| `primer/eval/scorer.py` | Orchestrates runs; currently mutates source | Remove 3-line write/unlink; thread parameter |
| `tests/test_runner_isolation.py` | Runner acceptance tests | Update call signatures + add repo-safety test |
| `tests/test_scorer.py` | Scorer tests (mock `run_task`) | **No change required** — `MagicMock` accepts any kwargs |
| `primer/cli.py` | Passes `context_content` to `score()` already | **No change required** |

---

## 5. Call Chain — Current vs Fixed

### Current (broken)
```
score(context_content=X)
  └─ source_context.write_text(X)              ← source repo mutated ⚠️
  └─ _run_with_retry(task, repo_path, with_ctx)   ← no content param
       └─ run_task(task, repo_path, with_ctx)      ← no content param
            └─ _clone_repo(repo_path, ...)         ← copies source + X
            └─ Step 3: assert X exists in clone    ← passes because scorer wrote it
```

### Fixed
```
score(context_content=X)
  └─ _run_with_retry(task, repo_path, with_ctx, context_content=X)
       └─ run_task(task, repo_path, with_ctx, context_content=X)
            └─ _clone_repo(repo_path, ...)         ← copies source; X NOT in source
            └─ Step 3 (WITH): write X to work_dir  ← runner writes directly ✓
            └─ Step 3 (WITHOUT): assert X absent   ← unchanged ✓
  └─ (no source-repo touch anywhere)
```

---

## 6. Precise Changes Required

### `primer/eval/runner.py` — `run_task()` function

**Change 1:** Add `context_content: str = ""` parameter to `run_task()` signature.

**Change 2:** Replace Step 3 body entirely:

*Current Step 3 (lines 92–111):*
```
WITH arm:  check context_file_path.exists() in work_dir → raise RuntimeError if absent
WITHOUT:   unlink if exists; assert absent
```

*New Step 3:*
```
WITH arm:  write context_content to context_file_path in work_dir (file is created here, never in source)
WITHOUT:   same as current (unlink if exists; assert absent)
```

The `RuntimeError("Context file expected … but was not found")` and its comment
`# File is already written by the caller (scorer) before run_task` are removed.

**Precondition note:** `work_dir` is created by `_clone_repo` (Step 1) and always exists when
Step 3 runs. No directory creation is needed before the `write_text()` call.

### `primer/eval/scorer.py` — `_run_with_retry()` and `score()` inner loop

**Change 3:** Add `context_content: str = ""` parameter to `_run_with_retry()`.

**Change 4:** Pass `context_content=context_content` to both `run_task()` calls inside
`_run_with_retry()` (the initial call and the Q2 retry call).

**Change 5:** In `score()` inner loop — remove the entire source-repo write/unlink block:

*Remove (lines 77–106 of the current scorer):*
```python
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

*Replace with:*
```python
run_result = _run_with_retry(
    task=task,
    repo_path=repo_path,
    with_context=with_ctx,
    profile=profile,
    config=config,
    adapter=adapter,
    image_tag=image_tag,
    context_content=context_content,
)
```

**Change 6 (optional cleanup):** `_prepare_context()` becomes vestigial (its return value
was already unused in the current code). It may be removed or retained with a deprecation
comment. Removing it is a minor risk-free cleanup; retaining it is zero-risk dead code.

### `tests/test_runner_isolation.py`

**Change 7:** Update the `run_task()` call signatures in all mocked tests that call it
directly. Since those tests use `with_context=False`, `context_content` defaults to `""` and
can be omitted — but the outdated comment on line 292 (`"We need a real repo path for the
source_context write/delete"`) must be updated: after BLK-5, no real repo path is needed for
source-repo management.

**Change 8:** Add a **repo-safety test** (see Acceptance Gates §7).

---

## 7. Hidden Assumptions

**A1 — `_clone_repo` creates `work_dir` before Step 3.**
`work_dir = Path(temp_dir) / "repo"` is populated by `_clone_repo` via `shutil.copytree`.
Step 3 writes to `work_dir / adapter.context_filename()`. This is safe because
`_clone_repo` runs at Step 1 and always creates the directory. The `finally` cleanup
(`shutil.rmtree(temp_dir)`) is at Step 9, so `work_dir` exists throughout Steps 2–8. ✓

**A2 — `git checkout commit --force` (inside `_clone_repo`) does not restore `CLAUDE.md`.**
If `CLAUDE.md` is NOT committed to the repo (the correct case — PRIMER generates it),
the checkout does not restore it. If it IS committed (the eligibility-guard case), the
checkout would restore it, and the runner would then overwrite it with `context_content`
in the WITH arm, or delete it in the WITHOUT arm. The eligibility guard (currently
documented but not enforced) would prevent this situation; BLK-5 is neutral on this —
the guard is a separate concern. ✓ for the intended case.

**A3 — `shutil.copytree` does not copy `CLAUDE.md` from the source after BLK-5.**
After the fix, `CLAUDE.md` is never written to the source repo, so `_clone_repo`'s copy
of the source tree will not include it. This is the intended behavior: the clone starts
clean, then the runner writes the file to the clone directly. ✓

**A4 — Mocked tests use `with_context=False`.**
All existing mocked `run_task()` tests use `with_context=False`. With `context_content=""`
(the default), the new Step 3 code for WITH arm is never reached in those tests. The
WITHOUT arm path (assert absence) is unchanged. ✓ — no mocked test regression.

**A5 — `test_scorer.py` mocks `run_task` at module level.**
`test_scorer.py` uses `MagicMock()` for `run_task`. `MagicMock` accepts any positional or
keyword arguments without asserting their names, so adding `context_content` to the call
does not break any scorer tests. ✓

**A6 — `cli.py` already passes `context_content` to `score()`.**
`cli.py:260` passes `context_content=gen_result.content` to `score()`. `score()` already
receives it. BLK-5 threads it further down through `_run_with_retry` and `run_task`.
`cli.py` itself needs no change. ✓

---

## 8. Dependency Graph

```
BLK-5 has NO inbound dependencies.
It can be implemented immediately and independently.

BLK-5 ──────► enables BLK-2 (fingerprint injection via runner, not source repo)
BLK-5 ──────► resolves data-loss risk regardless of BLK-2 status
BLK-5 ──────► independent of BLK-1, BLK-3, BLK-4
```

BLK-5 is the cleanest of all remaining blockers: pure refactor, self-contained, zero
external dependencies, immediately workable.

---

## 9. Rollback Strategy

BLK-5 touches three files (`runner.py`, `scorer.py`, `test_runner_isolation.py`). Rollback
is `git revert` of those three files. No schema changes, no config changes, no new
dependencies. The evaluation results remain identical with the old or new code for any
inputs that don't trigger the data-loss scenario.

The only observable difference to a user: the source repo's `CLAUDE.md` is no longer
written and deleted during eval. From the user's perspective this is strictly safer.

---

## 10. BLK-5 Independence

**Yes, BLK-5 can and should be implemented independently of BLK-2.**

BLK-2 depends on BLK-5 (it needs a clean injection point in the runner), but BLK-5 does not
depend on BLK-2 at all. BLK-5 fixes a standing correctness/safety defect regardless of
whether BLK-2 is ever implemented.

BLK-5 should be the **next implementation task** after BLK-1 is proven.
