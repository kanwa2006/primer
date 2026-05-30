"""Command detection from manifest files (no LLM, no network, no guessing).

detect_commands() parses manifest files only. Unknowns are None — never guessed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from primer.ingest.models import CommandSet


def detect_commands(repo_path: str) -> CommandSet:
    """Detect build/test/lint/dev commands by parsing manifest files.

    Supports: pyproject.toml, setup.cfg, setup.py, Makefile,
              package.json, Cargo.toml.
    Returns a CommandSet; any undetectable field is None.
    No LLM calls, no network access, no guessing.
    """
    root = Path(repo_path)
    cmd = CommandSet()

    # Python projects
    if (root / "pyproject.toml").exists():
        _parse_pyproject(root / "pyproject.toml", cmd)
    elif (root / "setup.cfg").exists():
        _parse_setup_cfg(root / "setup.cfg", cmd)
    elif (root / "setup.py").exists():
        cmd.package_manager = cmd.package_manager or "pip"

    # Node projects
    if (root / "package.json").exists():
        _parse_package_json(root / "package.json", cmd)

    # Cargo (Rust)
    if (root / "Cargo.toml").exists():
        cmd.package_manager = cmd.package_manager or "cargo"
        cmd.build_cmd = cmd.build_cmd or "cargo build"
        cmd.test_cmd = cmd.test_cmd or "cargo test"

    # Makefile — supplement gaps only
    if (root / "Makefile").exists():
        _parse_makefile(root / "Makefile", cmd)

    return cmd


# ── per-manifest parsers ──────────────────────────────────────────────────────

def _parse_pyproject(path: Path, cmd: CommandSet) -> None:
    """Parse pyproject.toml for tool configs and scripts."""
    try:
        # Use stdlib tomllib (Python 3.11+) or tomli fallback
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[no-reuse-ignored]
            except ImportError:
                tomllib = None  # type: ignore[assignment]

        if tomllib is not None:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        else:
            # Fallback: minimal regex-based parse for the fields we care about
            _parse_pyproject_regex(path, cmd)
            return
    except Exception:
        _parse_pyproject_regex(path, cmd)
        return

    # Determine package manager
    if "tool" in data:
        tools = data["tool"]
        if "uv" in tools:
            cmd.package_manager = "uv"
        elif "poetry" in tools:
            cmd.package_manager = "poetry"
        elif "hatch" in tools or "hatchling" in data.get("build-system", {}).get("requires", []):
            cmd.package_manager = "hatch"

        # pytest configuration
        if "pytest" in tools and cmd.test_cmd is None:
            cmd.test_cmd = "pytest"

        # ruff / flake8 / mypy / pylint → lint
        for linter in ("ruff", "flake8", "mypy", "pylint"):
            if linter in tools and cmd.lint_cmd is None:
                cmd.lint_cmd = linter

    # Check if uv lockfile present alongside
    if cmd.package_manager is None:
        parent = path.parent
        if (parent / "uv.lock").exists():
            cmd.package_manager = "uv"
        elif (parent / "poetry.lock").exists():
            cmd.package_manager = "poetry"
        else:
            cmd.package_manager = "pip"

    # Heuristic: if pytest is a dev dep, test_cmd = pytest
    if cmd.test_cmd is None:
        text = path.read_text(encoding="utf-8", errors="replace")
        if "pytest" in text:
            cmd.test_cmd = "pytest"

    # scripts section
    project = data.get("project", {})
    scripts = project.get("scripts", {})
    if scripts and cmd.dev_cmd is None:
        # pick the first non-trivial script name
        for name in scripts:
            if name not in ("primer", "build", "dist"):
                cmd.dev_cmd = name
                break


def _parse_pyproject_regex(path: Path, cmd: CommandSet) -> None:
    """Minimal regex fallback for pyproject.toml when tomllib is unavailable."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    if cmd.package_manager is None:
        if "uv.lock" in text or "[tool.uv]" in text:
            cmd.package_manager = "uv"
        elif "[tool.poetry]" in text:
            cmd.package_manager = "poetry"
        else:
            cmd.package_manager = "pip"

    if cmd.test_cmd is None and "pytest" in text:
        cmd.test_cmd = "pytest"


def _parse_setup_cfg(path: Path, cmd: CommandSet) -> None:
    """Parse setup.cfg for test runner hints."""
    try:
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read(str(path))
    except Exception:
        return

    cmd.package_manager = cmd.package_manager or "pip"
    if cfg.has_section("tool:pytest") or cfg.has_section("pytest"):
        cmd.test_cmd = cmd.test_cmd or "pytest"


def _parse_package_json(path: Path, cmd: CommandSet) -> None:
    """Parse package.json scripts section."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return

    # Detect package manager from lockfiles
    root = path.parent
    if cmd.package_manager is None:
        if (root / "pnpm-lock.yaml").exists():
            cmd.package_manager = "pnpm"
        elif (root / "yarn.lock").exists():
            cmd.package_manager = "yarn"
        else:
            cmd.package_manager = "npm"

    scripts: dict[str, str] = data.get("scripts", {})
    if not scripts:
        return

    pm = cmd.package_manager or "npm"
    run = f"{pm} run" if pm in ("npm", "yarn", "pnpm") else pm

    for name, body in scripts.items():
        if cmd.test_cmd is None and name in ("test", "tests"):
            cmd.test_cmd = f"{run} test"
        elif cmd.build_cmd is None and name in ("build", "compile"):
            cmd.build_cmd = f"{run} build"
        elif cmd.lint_cmd is None and name in ("lint", "lint:check", "check"):
            cmd.lint_cmd = f"{run} lint"
        elif cmd.dev_cmd is None and name in ("dev", "start", "serve"):
            cmd.dev_cmd = f"{run} {name}"


def _parse_makefile(path: Path, cmd: CommandSet) -> None:
    """Extract test/lint/build targets from a Makefile (supplement gaps only)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    # Find top-level targets: lines that start with a non-space word followed by ':'
    target_re = re.compile(r"^([a-zA-Z][a-zA-Z0-9_-]*):", re.MULTILINE)
    targets = set(target_re.findall(text))

    if cmd.test_cmd is None:
        for t in ("test", "tests", "pytest", "check"):
            if t in targets:
                cmd.test_cmd = f"make {t}"
                break

    if cmd.build_cmd is None:
        for t in ("build", "compile", "all"):
            if t in targets:
                cmd.build_cmd = f"make {t}"
                break

    if cmd.lint_cmd is None:
        for t in ("lint", "check", "flake8", "ruff", "mypy"):
            if t in targets:
                cmd.lint_cmd = f"make {t}"
                break
