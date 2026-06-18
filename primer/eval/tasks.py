"""Task derivation — deterministic, no LLM calls.

derive_tasks() produces a list of Tasks with deterministic failing start states.
Priority order:
  Type 1: revert_reimplement — scan last ~200 commits for single-file changes with covering tests
  Type 2: stub_function      — replace a covered function body with raise NotImplementedError

Same (repo_commit, seed) → identical task list.
Raises InsufficientTasksError if validated tasks < min_tasks (honest refusal, never pads).
"""
from __future__ import annotations

import hashlib
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from primer.config import Settings

from primer.errors import InsufficientTasksError
from primer.eval.models import Task, TaskMutation
from primer.eval.preflight import validate_task

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def derive_tasks(
    profile,
    repo_path: str,
    config: "Settings",
    n: int = 5,
    min_tasks: int = 3,
    seed: int = 0,
) -> list[Task]:
    """Derive up to *n* deterministic, test-backed tasks from the repo.

    Contract:
    - Every emitted Task fails verify_cmd at start state.
    - A correct change makes verify_cmd pass.
    - verify_cmd is the repo's own test runner; exit code is the sole verdict.
    - No LLM calls; deterministic given (repo SHA, seed).

    Raises InsufficientTasksError if validated tasks < min_tasks.
    """
    rng = random.Random(seed)
    candidates: list[Task] = []

    # Type 1: revert_reimplement
    type1 = _derive_revert_candidates(repo_path, config, n, rng)
    candidates.extend(type1)
    log.debug("revert_reimplement candidates: %d", len(type1))

    # Type 2: stub_function (top-up to reach n)
    if len(candidates) < n:
        needed = n - len(candidates)
        type2 = _derive_stub_candidates(repo_path, config, needed, rng)
        candidates.extend(type2)
        log.debug("stub_function candidates: %d", len(type2))

    # Pre-flight validation: keep only tasks that pass both checks
    validated: list[Task] = []
    for task in candidates:
        if len(validated) >= n:
            break
        try:
            ok = validate_task(task, repo_path, config)
        except Exception as exc:
            log.warning("preflight raised for task %s: %s", task.id, exc)
            ok = False
        if ok:
            task.validated = True
            validated.append(task)
        else:
            log.debug("task %s failed preflight, discarding", task.id)

    if len(validated) < min_tasks:
        raise InsufficientTasksError(
            f"PRIMER derived only {len(validated)} deterministic, test-backed task(s); "
            f"a trustworthy before/after delta needs at least {min_tasks}. "
            f"This repo isn't eligible — it likely lacks an existing passing test suite. "
            f"Add tests, or point PRIMER at a repo that has them."
        )

    return validated[:n]


# ---------------------------------------------------------------------------
# Type 1: revert_reimplement
# ---------------------------------------------------------------------------

def _derive_revert_candidates(
    repo_path: str,
    config: "Settings",
    n: int,
    rng: random.Random,
) -> list[Task]:
    """Scan last ~200 commits for single-file source changes with covering tests."""
    depth = config.primer_commit_scan_depth
    candidates: list[Task] = []

    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={depth}", "--format=%H", "--no-merges"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            log.warning("git log failed: %s", result.stderr)
            return []
        commits = [c.strip() for c in result.stdout.splitlines() if c.strip()]
    except Exception as exc:
        log.warning("git log error: %s", exc)
        return []

    # Rank deterministically: recency first, then SHA
    for sha in commits:
        if len(candidates) >= n * 3:  # gather extras for preflight attrition
            break
        task = _make_revert_task(sha, repo_path)
        if task is not None:
            candidates.append(task)

    return candidates


def _make_revert_task(sha: str, repo_path: str) -> Task | None:
    """Try to build a revert_reimplement Task for the given commit SHA."""
    try:
        # Get the diff stat for this commit
        stat = subprocess.run(
            ["git", "show", "--stat", "--format=", sha],
            cwd=repo_path, capture_output=True, text=True, timeout=15,
        )
        if stat.returncode != 0:
            return None

        # Parse changed files from stat
        changed_files = _parse_stat_files(stat.stdout)

        # Keep only commits that touch exactly one non-test source file
        source_files = [
            f for f in changed_files
            if _is_source_file(f) and not _is_test_file(f)
        ]
        if len(source_files) != 1:
            return None
        source_file = source_files[0]

        # Check diff size ≤ ~40 lines changed
        diff = subprocess.run(
            ["git", "show", "--unified=0", sha, "--", source_file],
            cwd=repo_path, capture_output=True, text=True, timeout=15,
        )
        if diff.returncode != 0:
            return None
        changed_lines = sum(
            1 for line in diff.stdout.splitlines()
            if line.startswith("+") or line.startswith("-")
            and not line.startswith("+++") and not line.startswith("---")
        )
        if changed_lines > 40:
            return None

        # Find a covering test file
        test_file = _find_covering_test(source_file, repo_path)
        if test_file is None:
            return None

        # Build verify_cmd (run the specific test file)
        verify_cmd = _build_verify_cmd(test_file, repo_path)
        if verify_cmd is None:
            return None

        task_id = f"revert_{sha[:12]}_{Path(test_file).stem}"
        prompt = (
            f"The function(s) in `{source_file}` were recently changed. "
            f"Revert the change and re-implement the correct logic so that "
            f"the test `{test_file}` passes."
        )

        return Task(
            id=task_id,
            task_type="revert_reimplement",
            prompt=prompt,
            verify_cmd=verify_cmd,
            mutation=TaskMutation(
                kind="revert",
                target_commit=sha,
                target_file=source_file,
            ),
            source_ref=sha,
            validated=False,
        )
    except Exception as exc:
        log.debug("_make_revert_task(%s) error: %s", sha, exc)
        return None


# ---------------------------------------------------------------------------
# Type 2: stub_function
# ---------------------------------------------------------------------------

def _derive_stub_candidates(
    repo_path: str,
    config: "Settings",
    n: int,
    rng: random.Random,
) -> list[Task]:
    """Find covered functions and create stub tasks."""
    candidates: list[Task] = []

    # Walk source files
    py_files = sorted(Path(repo_path).rglob("*.py"))
    py_files = [
        f for f in py_files
        if not _is_test_file(str(f.relative_to(repo_path)))
        and ".git" not in f.parts
        and "__pycache__" not in f.parts
    ]
    rng.shuffle(py_files)

    for src_file in py_files:
        if len(candidates) >= n * 3:
            break
        rel = str(src_file.relative_to(repo_path))
        fns = _extract_stub_functions(src_file)
        rng.shuffle(fns)
        for fn_name in fns:
            test_file = _find_covering_test(rel, repo_path)
            if test_file is None:
                continue
            verify_cmd = _build_verify_cmd(test_file, repo_path)
            if verify_cmd is None:
                continue

            task_id = f"stub_{_short_hash(rel + fn_name)}"
            prompt = (
                f"The function `{fn_name}` in `{rel}` has been replaced with "
                f"`raise NotImplementedError`. Re-implement it so that "
                f"`{test_file}` passes."
            )
            candidates.append(Task(
                id=task_id,
                task_type="stub_function",
                prompt=prompt,
                verify_cmd=verify_cmd,
                mutation=TaskMutation(
                    kind="stub",
                    target_file=rel,
                    target_symbol=fn_name,
                ),
                source_ref=f"{rel}::{fn_name}",
                validated=False,
            ))
            if len(candidates) >= n * 3:
                break

    return candidates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_stat_files(stat_output: str) -> list[str]:
    """Extract file paths from git show --stat output."""
    files = []
    for line in stat_output.splitlines():
        # Lines look like: " path/to/file.py | 10 ++-"
        if "|" in line:
            path = line.split("|")[0].strip()
            if path:
                files.append(path)
    return files


def _is_source_file(path: str) -> bool:
    return path.endswith(".py") and "__init__" not in path


def _is_test_file(path: str) -> bool:
    p = Path(path)
    return (
        p.name.startswith("test_")
        or p.name.endswith("_test.py")
        or "tests" in p.parts
        or "test" in p.parts
    )


def _test_subject(name: str) -> str:
    """Strip the test_ prefix / _test suffix and .py from a test file name.

    `test_calculator.py` -> `calculator`; `agent_adapter_test.py` -> `agent_adapter`.
    """
    base = name[:-3] if name.endswith(".py") else name
    if base.startswith("test_"):
        base = base[len("test_"):]
    elif base.endswith("_test"):
        base = base[: -len("_test")]
    return base


def _find_covering_test(source_file: str, repo_path: str) -> str | None:
    """Select a test file with evidence of relevance to *source_file*.

    A test is only eligible if the source file's stem appears in the test's
    name (after stripping the test_/_test affixes). Two tiers, in order:

      1. Exact stem match:  test_<stem>.py / <stem>_test.py
      2. Fuzzy stem match:  every underscore-delimited token of <stem> is a
         token of the test's subject (e.g. test_<stem>_edge_cases.py).

    There is no arbitrary fallback: a test with no naming relationship to the
    source file is never selected (it would not exercise the target module and
    would be rejected by validate_task anyway). Returns None when nothing is
    relevant. Selection is deterministic — candidates are sorted by path and
    the first match in each tier wins.
    """
    stem = Path(source_file).stem
    repo = Path(repo_path)

    # All test files in the repo, sorted for deterministic selection.
    test_files = sorted(
        f
        for f in list(repo.rglob("test_*.py")) + list(repo.rglob("*_test.py"))
        if f.is_file() and ".git" not in f.parts and "__pycache__" not in f.parts
    )

    stem_tokens = stem.split("_")

    # Tier 1: exact stem match.
    for f in test_files:
        if f.name == f"test_{stem}.py" or f.name == f"{stem}_test.py":
            return str(f.relative_to(repo))

    # Tier 2: fuzzy stem match — all stem tokens present in the test subject.
    for f in test_files:
        subject_tokens = _test_subject(f.name).split("_")
        if all(tok in subject_tokens for tok in stem_tokens):
            return str(f.relative_to(repo))

    # No evidence of relevance — refuse rather than pick an arbitrary test.
    return None


def _build_verify_cmd(test_file: str, repo_path: str) -> str | None:
    """Build a pytest verify command for the given test file."""
    repo = Path(repo_path)
    # Check pytest is available via pyproject.toml or setup.cfg
    has_pyproject = (repo / "pyproject.toml").exists()
    has_setup = (repo / "setup.cfg").exists() or (repo / "setup.py").exists()
    if has_pyproject or has_setup:
        return f"python -m pytest {test_file} -x -q --tb=short"
    return None


def _extract_stub_functions(src_file: Path) -> list[str]:
    """Extract top-level function names from a Python source file."""
    try:
        source = src_file.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    fns = []
    for line in source.splitlines():
        m = re.match(r"^def (\w+)\s*\(", line)
        if m:
            name = m.group(1)
            if not name.startswith("_"):  # skip private helpers
                fns.append(name)
    return fns


def _short_hash(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:10]
