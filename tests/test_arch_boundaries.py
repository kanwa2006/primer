"""Architecture boundary tests — seed pass (Phase 0); gains teeth as modules land.

Mandatory by Phase 2. Three invariants (Session 2 §2):
  1. Vendor SDK imports only under primer/llm/
  2. docker imports only under primer/eval/
  3. sqlite3/aiosqlite imports only under primer/store/
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PRIMER_PKG = Path(__file__).parent.parent / "primer"

VENDOR_SDK_NAMES = {"anthropic", "openai", "google.generativeai"}
DOCKER_NAMES = {"docker"}
SQLITE_NAMES = {"sqlite3", "aiosqlite"}


def _collect_imports(path: Path) -> set[str]:
    """Return the set of top-level module names imported in a .py file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def _py_files_under(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.py"))


def _py_files_outside(directory: Path, subdir: str) -> list[Path]:
    """Python files under primer/ but NOT under primer/<subdir>/."""
    allowed = directory / subdir
    return [
        f for f in _py_files_under(directory)
        if not f.is_relative_to(allowed)
    ]


class TestVendorSDKBoundary:
    """Vendor SDK imports (anthropic, openai, google.generativeai) only in primer/llm/."""

    def test_no_vendor_sdk_outside_llm(self):
        violations = []
        for py_file in _py_files_outside(PRIMER_PKG, "llm"):
            imports = _collect_imports(py_file)
            bad = imports & VENDOR_SDK_NAMES
            if bad:
                violations.append((py_file.relative_to(PRIMER_PKG.parent), bad))
        assert not violations, (
            "Vendor SDK imports found outside primer/llm/:\n"
            + "\n".join(f"  {f}: {b}" for f, b in violations)
        )


class TestDockerBoundary:
    """docker imports only in primer/eval/."""

    def test_no_docker_outside_eval(self):
        violations = []
        for py_file in _py_files_outside(PRIMER_PKG, "eval"):
            imports = _collect_imports(py_file)
            bad = imports & DOCKER_NAMES
            if bad:
                violations.append((py_file.relative_to(PRIMER_PKG.parent), bad))
        assert not violations, (
            "docker imports found outside primer/eval/:\n"
            + "\n".join(f"  {f}: {b}" for f, b in violations)
        )


class TestSQLiteBoundary:
    """sqlite3/aiosqlite imports only in primer/store/."""

    def test_no_sqlite_outside_store(self):
        violations = []
        for py_file in _py_files_outside(PRIMER_PKG, "store"):
            imports = _collect_imports(py_file)
            bad = imports & SQLITE_NAMES
            if bad:
                violations.append((py_file.relative_to(PRIMER_PKG.parent), bad))
        assert not violations, (
            "sqlite3/aiosqlite imports found outside primer/store/:\n"
            + "\n".join(f"  {f}: {b}" for f, b in violations)
        )
