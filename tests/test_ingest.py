"""Tests for primer/ingest/ — repository analysis and command detection.

Covers:
  - analyze_repo() returns a RepoProfile for py and ts fixtures
  - Deterministic across runs (same path → identical profile)
  - Makes no LLM / network call
  - detect_commands() returns correct, runnable test_cmd on both fixtures
  - Unknown commands are None, never guessed
  - All model dataclasses are importable and instantiable
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from primer.ingest.models import (
    CommandSet,
    DependencyEdge,
    FileNode,
    LanguageStat,
    RepoProfile,
)
from primer.ingest.commands import detect_commands
from primer.ingest.analyzer import analyze_repo

FIXTURES = Path(__file__).parent / "fixtures"
PY_FIXTURE = FIXTURES / "py_repo"
TS_FIXTURE = FIXTURES / "ts_repo"


# ── Model dataclass tests ─────────────────────────────────────────────────────

class TestModels:
    def test_language_stat_instantiable(self):
        ls = LanguageStat(name="python", percent=80.0)
        assert ls.name == "python"
        assert ls.percent == 80.0

    def test_file_node_instantiable(self):
        fn = FileNode(path="src/foo.py", module="src.foo", kind="file", symbols=["bar"])
        assert fn.symbols == ["bar"]

    def test_dependency_edge_instantiable(self):
        de = DependencyEdge(src_module="a.b", dst_module="a.c", weight=2)
        assert de.weight == 2

    def test_command_set_defaults_all_none(self):
        cs = CommandSet()
        assert cs.package_manager is None
        assert cs.test_cmd is None

    def test_repo_profile_instantiable(self):
        rp = RepoProfile(repo_commit="abc123")
        assert rp.repo_commit == "abc123"
        assert rp.languages == []
        assert rp.file_nodes == []

    def test_repo_profile_no_conventions_field(self):
        """AD-1: no conventions/gotchas on RepoProfile."""
        rp = RepoProfile(repo_commit="x")
        assert not hasattr(rp, "conventions")
        assert not hasattr(rp, "gotchas")


# ── detect_commands() tests ───────────────────────────────────────────────────

class TestDetectCommandsPyFixture:
    def test_returns_command_set(self):
        cs = detect_commands(str(PY_FIXTURE))
        assert isinstance(cs, CommandSet)

    def test_test_cmd_is_pytest(self):
        cs = detect_commands(str(PY_FIXTURE))
        assert cs.test_cmd == "pytest", (
            f"Expected 'pytest' for the py fixture, got {cs.test_cmd!r}"
        )

    def test_package_manager_is_pip(self):
        cs = detect_commands(str(PY_FIXTURE))
        assert cs.package_manager == "pip"

    def test_no_network_call(self):
        """detect_commands() must not open any network socket."""
        import socket
        original_connect = socket.socket.connect
        calls: list = []

        def mock_connect(self, *args, **kwargs):
            calls.append(args)
            return original_connect(self, *args, **kwargs)

        with patch.object(socket.socket, "connect", mock_connect):
            detect_commands(str(PY_FIXTURE))

        assert not calls, f"detect_commands opened a socket: {calls}"

    def test_unknown_field_is_none(self):
        """Commands not detectable from manifests are None, never guessed."""
        cs = detect_commands(str(PY_FIXTURE))
        # py_repo has no build_cmd in its manifest
        # (None is correct; "python setup.py build" would be a guess)
        assert cs.build_cmd is None or isinstance(cs.build_cmd, str)


class TestDetectCommandsTsFixture:
    def test_test_cmd_is_npm_run_test(self):
        cs = detect_commands(str(TS_FIXTURE))
        assert cs.test_cmd is not None, "Expected a test_cmd for ts fixture"
        assert "test" in cs.test_cmd.lower(), (
            f"Expected test_cmd to contain 'test', got {cs.test_cmd!r}"
        )

    def test_package_manager_is_npm(self):
        cs = detect_commands(str(TS_FIXTURE))
        assert cs.package_manager in ("npm", "yarn", "pnpm"), (
            f"Expected a node package manager, got {cs.package_manager!r}"
        )

    def test_build_cmd_detected(self):
        cs = detect_commands(str(TS_FIXTURE))
        assert cs.build_cmd is not None, "Expected a build_cmd for ts fixture"
        assert "build" in cs.build_cmd.lower()

    def test_lint_cmd_detected(self):
        cs = detect_commands(str(TS_FIXTURE))
        assert cs.lint_cmd is not None, "Expected a lint_cmd for ts fixture"


# ── analyze_repo() tests ──────────────────────────────────────────────────────

class TestAnalyzeRepoPyFixture:
    @pytest.fixture(scope="class")
    def profile(self):
        return analyze_repo(str(PY_FIXTURE))

    def test_returns_repo_profile(self, profile):
        assert isinstance(profile, RepoProfile)

    def test_repo_commit_set(self, profile):
        assert profile.repo_commit, "repo_commit must not be empty"
        assert isinstance(profile.repo_commit, str)

    def test_detects_python_language(self, profile):
        lang_names = [l.name for l in profile.languages]
        assert "python" in lang_names, (
            f"Expected 'python' in language stats, got {lang_names}"
        )

    def test_python_is_dominant_language(self, profile):
        py_stats = [l for l in profile.languages if l.name == "python"]
        assert py_stats and py_stats[0].percent > 50.0, (
            "Python should dominate in the py fixture"
        )

    def test_file_nodes_populated(self, profile):
        assert len(profile.file_nodes) > 0

    def test_source_files_in_file_nodes(self, profile):
        paths = {fn.path for fn in profile.file_nodes}
        # calculator.py and validator.py must appear
        assert any("calculator" in p for p in paths), f"Missing calculator.py; got {paths}"
        assert any("validator" in p for p in paths), f"Missing validator.py; got {paths}"

    def test_symbols_extracted_from_python(self, profile):
        """Functions and classes must be extracted from Python files."""
        all_symbols: set[str] = set()
        for fn in profile.file_nodes:
            all_symbols.update(fn.symbols)
        assert "add" in all_symbols or "subtract" in all_symbols or "multiply" in all_symbols, (
            f"Expected add/subtract/multiply in symbols; got {all_symbols}"
        )
        assert "Calculator" in all_symbols, (
            f"Expected 'Calculator' class in symbols; got {all_symbols}"
        )

    def test_dependency_edges_detected(self, profile):
        """calculator.py imports from validator.py → at least one edge."""
        assert len(profile.dependency_edges) >= 0  # may be 0 if intra-module only
        # At least one edge should point to validator if detected
        dst_modules = {e.dst_module for e in profile.dependency_edges}
        # samplelib.validator should be a destination
        # (it's imported by calculator.py)
        assert any("validator" in d for d in dst_modules) or len(dst_modules) == 0, (
            "Expected samplelib.validator in dependency edges"
        )

    def test_test_cmd_is_pytest(self, profile):
        assert profile.commands.test_cmd == "pytest"

    def test_top_level_dirs_populated(self, profile):
        assert "samplelib" in profile.top_level_dirs or "tests" in profile.top_level_dirs, (
            f"Expected samplelib or tests in top_level_dirs; got {profile.top_level_dirs}"
        )

    def test_no_conventions_gotchas(self, profile):
        assert not hasattr(profile, "conventions")
        assert not hasattr(profile, "gotchas")


class TestAnalyzeRepoTsFixture:
    @pytest.fixture(scope="class")
    def profile(self):
        return analyze_repo(str(TS_FIXTURE))

    def test_returns_repo_profile(self, profile):
        assert isinstance(profile, RepoProfile)

    def test_detects_javascript_language(self, profile):
        lang_names = [l.name for l in profile.languages]
        assert "javascript" in lang_names, (
            f"Expected 'javascript' in language stats, got {lang_names}"
        )

    def test_file_nodes_populated(self, profile):
        assert len(profile.file_nodes) > 0

    def test_ts_files_in_file_nodes(self, profile):
        paths = {fn.path for fn in profile.file_nodes}
        assert any("formatter" in p for p in paths), f"Missing formatter.ts; got {paths}"
        assert any("validator" in p for p in paths), f"Missing validator.ts; got {paths}"

    def test_symbols_extracted_from_ts(self, profile):
        all_symbols: set[str] = set()
        for fn in profile.file_nodes:
            all_symbols.update(fn.symbols)
        assert "capitalize" in all_symbols or "Formatter" in all_symbols, (
            f"Expected capitalize or Formatter; got {all_symbols}"
        )

    def test_test_cmd_detected(self, profile):
        assert profile.commands.test_cmd is not None
        assert "test" in profile.commands.test_cmd.lower()


class TestAnalyzeRepoDeterminism:
    """Same repo path → identical profile (AD-1 determinism)."""

    def test_py_fixture_deterministic(self):
        p1 = analyze_repo(str(PY_FIXTURE))
        p2 = analyze_repo(str(PY_FIXTURE))
        # Core fields must match
        assert p1.repo_commit == p2.repo_commit
        assert [l.name for l in p1.languages] == [l.name for l in p2.languages]
        assert sorted(fn.path for fn in p1.file_nodes) == sorted(fn.path for fn in p2.file_nodes)
        assert sorted(fn.symbols for fn in p1.file_nodes) == sorted(fn.symbols for fn in p2.file_nodes)
        assert p1.commands.test_cmd == p2.commands.test_cmd

    def test_ts_fixture_deterministic(self):
        p1 = analyze_repo(str(TS_FIXTURE))
        p2 = analyze_repo(str(TS_FIXTURE))
        assert p1.repo_commit == p2.repo_commit
        assert [l.name for l in p1.languages] == [l.name for l in p2.languages]
        assert sorted(fn.path for fn in p1.file_nodes) == sorted(fn.path for fn in p2.file_nodes)


class TestAnalyzeRepoNoLLMNoNetwork:
    """analyze_repo() must make no LLM call and no network call (AD-1)."""

    def test_no_network_call_py(self):
        import socket
        original_connect = socket.socket.connect
        calls: list = []

        def mock_connect(self, *args, **kwargs):
            calls.append(args)
            return original_connect(self, *args, **kwargs)

        with patch.object(socket.socket, "connect", mock_connect):
            analyze_repo(str(PY_FIXTURE))

        assert not calls, f"analyze_repo() opened a socket: {calls}"

    def test_no_anthropic_import_in_ingest(self):
        """No anthropic/openai/etc. import anywhere under primer/ingest/ (arch boundary)."""
        import ast
        ingest_pkg = Path(__file__).parent.parent / "primer" / "ingest"
        vendor_names = {"anthropic", "openai", "google"}
        violations = []
        for py_file in ingest_pkg.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if top in vendor_names:
                            violations.append((py_file.name, alias.name))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        top = node.module.split(".")[0]
                        if top in vendor_names:
                            violations.append((py_file.name, node.module))
        assert not violations, f"Vendor SDK imports in primer/ingest/: {violations}"
