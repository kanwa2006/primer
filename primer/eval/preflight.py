"""Task pre-flight validation (Spec C).

validate_task() checks two invariants in a throwaway temp directory:
  1. Known-good state → verify_cmd PASSES 3× consistently (discard if flaky).
  2. Broken/start state → verify_cmd FAILS.

Returns True only if both hold. Any exception → False (conservative).
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from primer.config import Settings
    from primer.eval.models import Task

log = logging.getLogger(__name__)

# How many times to confirm known-good state passes before accepting a task
_GOOD_RUNS = 3
# Seconds to wait between retries when a run is flaky
_FLAKY_RETRY_DELAY = 2.0


def validate_task(task: "Task", repo_path: str, config: "Settings") -> bool:
    """Validate a task candidate against both known-good and broken-state checks.

    Spec C pre-flight:
    - Known-good: verify_cmd passes 3× consistently.
    - Broken start state: after applying mutation, verify_cmd fails.

    Returns True if both hold, False otherwise (task is discarded).
    """
    tmp_dir = tempfile.mkdtemp(prefix="primer_preflight_")
    try:
        work = Path(tmp_dir) / "repo"
        # Copy the repo to a throwaway location
        shutil.copytree(repo_path, str(work), symlinks=True, ignore=shutil.ignore_patterns(".git"))

        # Copy .git for git operations (needed for revert tasks)
        src_git = Path(repo_path) / ".git"
        if src_git.exists():
            shutil.copytree(str(src_git), str(work / ".git"), symlinks=True)

        # Install deps if needed (lightweight: try pip install -e . quietly)
        _install_deps(work)

        # 1. Known-good state: verify_cmd must pass 3× consistently
        for i in range(_GOOD_RUNS):
            ok, _ = _run_verify(task.verify_cmd, work)
            if not ok:
                log.debug(
                    "task %s: known-good run %d/%d FAILED — discarding",
                    task.id, i + 1, _GOOD_RUNS,
                )
                return False
            if i < _GOOD_RUNS - 1:
                time.sleep(_FLAKY_RETRY_DELAY)
        log.debug("task %s: known-good passed %d×", task.id, _GOOD_RUNS)

        # 2. Apply mutation to create the failing start state
        applied = _apply_mutation(task, work)
        if not applied:
            log.debug("task %s: mutation could not be applied — discarding", task.id)
            return False

        # 3. Broken state: verify_cmd must fail
        ok, _ = _run_verify(task.verify_cmd, work)
        if ok:
            log.debug(
                "task %s: broken-state run PASSED (expected FAIL) — discarding",
                task.id,
            )
            return False

        log.debug("task %s: broken-state confirmed FAILED — task accepted", task.id)
        return True

    except Exception as exc:
        log.warning("validate_task(%s) raised: %s", task.id, exc)
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_verify(verify_cmd: str, work_dir: Path) -> tuple[bool, str]:
    """Run verify_cmd in work_dir; return (passed, output)."""
    try:
        result = subprocess.run(
            verify_cmd,
            shell=True,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as exc:
        return False, str(exc)


def _install_deps(work_dir: Path) -> None:
    """Lightweight dep install for the throwaway checkout."""
    pyproject = work_dir / "pyproject.toml"
    setup_py = work_dir / "setup.py"
    if pyproject.exists() or setup_py.exists():
        try:
            subprocess.run(
                ["python", "-m", "pip", "install", "-e", ".", "-q", "--no-deps"],
                cwd=str(work_dir),
                capture_output=True,
                timeout=60,
            )
        except Exception as exc:
            log.debug("dep install skipped: %s", exc)


def _apply_mutation(task: "Task", work_dir: Path) -> bool:
    """Apply task.mutation to create the failing start state.

    Returns True if the mutation was applied successfully.
    """
    from primer.eval.models import TaskMutation

    m = task.mutation
    if m.kind == "revert":
        return _apply_revert(m.target_commit, m.target_file, work_dir)
    elif m.kind == "stub":
        return _apply_stub(m.target_file, m.target_symbol, work_dir)
    else:
        log.warning("unknown mutation kind: %s", m.kind)
        return False


def _apply_revert(commit: str | None, target_file: str | None, work_dir: Path) -> bool:
    """Revert only the source change from the given commit."""
    if not commit or not target_file:
        return False
    try:
        result = subprocess.run(
            ["git", "checkout", f"{commit}^", "--", target_file],
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            log.debug("git checkout revert failed: %s", result.stderr)
            return False
        return True
    except Exception as exc:
        log.debug("_apply_revert error: %s", exc)
        return False


def _apply_stub(
    target_file: str | None,
    target_symbol: str | None,
    work_dir: Path,
) -> bool:
    """Replace function body with `raise NotImplementedError`."""
    if not target_file or not target_symbol:
        return False
    src = work_dir / target_file
    if not src.exists():
        return False
    try:
        original = src.read_text(encoding="utf-8")
        stubbed = _stub_function(original, target_symbol)
        if stubbed is None:
            log.debug("could not stub %s in %s", target_symbol, target_file)
            return False
        src.write_text(stubbed, encoding="utf-8")
        return True
    except Exception as exc:
        log.debug("_apply_stub error: %s", exc)
        return False


def _stub_function(source: str, fn_name: str) -> str | None:
    """Replace the body of fn_name with `raise NotImplementedError`.

    Simple line-based approach: find `def fn_name(`, detect body indentation,
    replace until the next same-or-lesser indented def/class or EOF.
    """
    import re

    lines = source.splitlines(keepends=True)
    # Find the function definition line
    fn_def_pat = re.compile(r"^(\s*)def\s+" + re.escape(fn_name) + r"\s*\(")
    fn_start = None
    fn_indent = ""
    for i, line in enumerate(lines):
        m = fn_def_pat.match(line)
        if m:
            fn_start = i
            fn_indent = m.group(1)
            break

    if fn_start is None:
        return None

    # Detect body indentation (first non-empty line after def)
    body_indent = fn_indent + "    "
    body_start = fn_start + 1
    # Skip over the docstring block if present
    while body_start < len(lines) and lines[body_start].strip() == "":
        body_start += 1

    if body_start >= len(lines):
        return None

    # Find the end of the function body
    body_end = body_start
    for j in range(body_start, len(lines)):
        stripped = lines[j].strip()
        if stripped == "":
            body_end = j + 1
            continue
        indent = len(lines[j]) - len(lines[j].lstrip())
        base_indent = len(fn_indent)
        if indent <= base_indent and stripped and not stripped.startswith("#"):
            break
        body_end = j + 1

    # Build the replacement
    stub_line = body_indent + "raise NotImplementedError\n"
    new_lines = lines[:body_start] + [stub_line] + lines[body_end:]
    return "".join(new_lines)
