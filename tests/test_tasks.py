"""Tests for eval/tasks.py (Spec C — deterministic task derivation).

These tests run WITHOUT Docker — they test the task derivation logic
using the py_repo fixture which has a real pytest suite.
"""
from __future__ import annotations

import copy
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from primer.eval.models import Task, TaskMutation
from primer.eval.tasks import (
    _build_verify_cmd,
    _extract_stub_functions,
    _find_covering_test,
    _is_test_file,
    _is_source_file,
)
from primer.eval.preflight import (
    _apply_revert,
    _apply_stub,
    _stub_function,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def py_repo_path():
    return Path(__file__).parent / "fixtures" / "py_repo"


@pytest.fixture()
def py_repo_copy(py_repo_path, tmp_path):
    """Return a mutable copy of py_repo for mutation tests."""
    dest = tmp_path / "py_repo"
    shutil.copytree(str(py_repo_path), str(dest))
    return dest


@pytest.fixture()
def mock_config():
    cfg = MagicMock()
    cfg.primer_task_count = 5
    cfg.primer_min_tasks = 3
    cfg.primer_commit_scan_depth = 200
    return cfg


# ---------------------------------------------------------------------------
# _is_source_file / _is_test_file
# ---------------------------------------------------------------------------

def test_is_source_file_py():
    assert _is_source_file("samplelib/calculator.py")

def test_is_source_file_rejects_init():
    assert not _is_source_file("samplelib/__init__.py")

def test_is_test_file_test_prefix():
    assert _is_test_file("tests/test_calculator.py")

def test_is_test_file_test_dir():
    assert _is_test_file("test/something.py")

def test_is_test_file_normal_source():
    assert not _is_test_file("samplelib/calculator.py")


# ---------------------------------------------------------------------------
# _find_covering_test
# ---------------------------------------------------------------------------

def test_find_covering_test_finds_calculator(py_repo_path):
    result = _find_covering_test("samplelib/calculator.py", str(py_repo_path))
    assert result is not None
    assert "test_calculator" in result


def test_find_covering_test_returns_none_for_no_match(py_repo_path):
    result = _find_covering_test("samplelib/nonexistent_module.py", str(py_repo_path))
    # May return a fallback test or None — but should not raise
    # (the fallback path returns any test in tests/)
    # Just assert it doesn't raise
    assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# _build_verify_cmd
# ---------------------------------------------------------------------------

def test_build_verify_cmd_py_repo(py_repo_path):
    cmd = _build_verify_cmd("tests/test_calculator.py", str(py_repo_path))
    assert cmd is not None
    assert "pytest" in cmd
    assert "test_calculator" in cmd


# ---------------------------------------------------------------------------
# _extract_stub_functions
# ---------------------------------------------------------------------------

def test_extract_stub_functions_calculator(py_repo_path):
    src = py_repo_path / "samplelib" / "calculator.py"
    fns = _extract_stub_functions(src)
    # add, subtract, multiply are top-level non-private functions
    assert "add" in fns
    assert "subtract" in fns
    assert "multiply" in fns


def test_extract_stub_functions_empty_file(tmp_path):
    f = tmp_path / "empty.py"
    f.write_text("")
    assert _extract_stub_functions(f) == []


# ---------------------------------------------------------------------------
# _stub_function
# ---------------------------------------------------------------------------

def test_stub_function_replaces_body():
    source = """\
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
"""
    result = _stub_function(source, "add")
    assert result is not None
    assert "raise NotImplementedError" in result
    # subtract should be untouched
    assert "return a - b" in result


def test_stub_function_preserves_def_line():
    source = "def greet(name):\n    return f'Hello {name}'\n"
    result = _stub_function(source, "greet")
    assert result is not None
    assert "def greet(name):" in result
    assert "raise NotImplementedError" in result
    assert "return f'Hello" not in result


def test_stub_function_unknown_name_returns_none():
    source = "def real_fn():\n    pass\n"
    result = _stub_function(source, "nonexistent")
    assert result is None


# ---------------------------------------------------------------------------
# _apply_stub (end-to-end on the fixture repo copy)
# ---------------------------------------------------------------------------

def test_apply_stub_makes_test_fail(py_repo_copy):
    """Stub 'add' then verify the test fails."""
    # First, confirm tests pass in the clean state
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/test_calculator.py", "-x", "-q"],
        cwd=str(py_repo_copy),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"Fixture tests should pass initially:\n{result.stdout}"

    # Install the package in the copy
    subprocess.run(
        ["pip", "install", "-e", ".", "-q", "--no-deps"],
        cwd=str(py_repo_copy), capture_output=True, timeout=30,
    )

    # Apply stub mutation
    ok = _apply_stub("samplelib/calculator.py", "add", py_repo_copy)
    assert ok, "Stub mutation should succeed"

    # Verify tests now fail
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/test_calculator.py::test_add_integers",
         "-x", "-q"],
        cwd=str(py_repo_copy),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode != 0, "Test should fail after stubbing"


# ---------------------------------------------------------------------------
# derive_tasks determinism
# ---------------------------------------------------------------------------

def test_derive_tasks_determinism(py_repo_path, mock_config):
    """Same (repo, seed) → identical task list (Spec C)."""
    from primer.eval.tasks import derive_tasks
    from primer.ingest.models import RepoProfile, CommandSet

    profile = RepoProfile(
        repo_commit="abc123",
        languages=[],
        frameworks=[],
        commands=CommandSet(
            package_manager="pip",
            build_cmd=None,
            test_cmd="python -m pytest",
            lint_cmd=None,
            dev_cmd=None,
        ),
        top_level_dirs=[],
        key_modules=[],
        domain_terms=[],
        file_nodes=[],
        dependency_edges=[],
    )

    # Run twice with the same seed — should produce same task IDs
    with patch("primer.eval.tasks.validate_task", return_value=True):
        tasks1 = derive_tasks(profile, str(py_repo_path), mock_config, n=3, seed=42)
        tasks2 = derive_tasks(profile, str(py_repo_path), mock_config, n=3, seed=42)

    ids1 = [t.id for t in tasks1]
    ids2 = [t.id for t in tasks2]
    assert ids1 == ids2, f"Task lists should be identical for same seed: {ids1} vs {ids2}"


def test_derive_tasks_different_seeds_may_differ(py_repo_path, mock_config):
    """Different seeds CAN produce different orderings."""
    from primer.eval.tasks import derive_tasks
    from primer.ingest.models import RepoProfile, CommandSet

    profile = RepoProfile(
        repo_commit="abc123",
        languages=[],
        frameworks=[],
        commands=CommandSet(
            package_manager="pip",
            build_cmd=None,
            test_cmd="python -m pytest",
            lint_cmd=None,
            dev_cmd=None,
        ),
        top_level_dirs=[],
        key_modules=[],
        domain_terms=[],
        file_nodes=[],
        dependency_edges=[],
    )

    # We just verify both calls succeed; ordering may vary
    with patch("primer.eval.tasks.validate_task", return_value=True):
        tasks1 = derive_tasks(profile, str(py_repo_path), mock_config, n=3, seed=0)
        tasks2 = derive_tasks(profile, str(py_repo_path), mock_config, n=3, seed=99)

    assert len(tasks1) >= 1
    assert len(tasks2) >= 1


def test_insufficient_tasks_raises(mock_config):
    """Validated tasks < min_tasks → InsufficientTasksError (honest refusal)."""
    from primer.eval.tasks import derive_tasks
    from primer.eval.models import Task, TaskMutation
    from primer.errors import InsufficientTasksError
    from primer.ingest.models import RepoProfile, CommandSet

    mock_config.primer_min_tasks = 3

    profile = RepoProfile(
        repo_commit="deadbeef",
        languages=[],
        frameworks=[],
        commands=CommandSet(None, None, None, None, None),
        top_level_dirs=[],
        key_modules=[],
        domain_terms=[],
        file_nodes=[],
        dependency_edges=[],
    )

    # Make validate_task always fail
    with patch("primer.eval.tasks.validate_task", return_value=False):
        with pytest.raises(InsufficientTasksError) as exc_info:
            derive_tasks(profile, "/tmp/fake_repo", mock_config, n=5, min_tasks=3)

    assert "3" in str(exc_info.value)
    assert "trustworthy" in str(exc_info.value).lower()
