"""Data models for the ingest package (Phase 1, AD-1: no LLM).

All fields reflect heuristic analysis only. Unknown fields are None/empty,
never fabricated. No conventions/gotchas — those are generator output (AD-1).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class LanguageStat:
    """Language detected in the repo and estimated share."""
    name: str
    percent: float  # 0.0–100.0


@dataclass
class FileNode:
    """A single source file and the symbols extracted from it."""
    path: str                              # relative to repo root
    module: str                            # dotted module name, e.g. "primer.ingest.models"
    kind: Literal["file", "dir"]
    symbols: list[str] = field(default_factory=list)  # function/class names extracted


@dataclass
class DependencyEdge:
    """A heuristic import dependency between two modules."""
    src_module: str
    dst_module: str
    weight: int = 1  # number of import statements creating this edge


@dataclass
class CommandSet:
    """Commands detected from manifest files (no LLM, no guessing)."""
    package_manager: str | None = None   # e.g. "pip", "npm", "uv"
    build_cmd: str | None = None
    test_cmd: str | None = None
    lint_cmd: str | None = None
    dev_cmd: str | None = None


@dataclass
class RepoProfile:
    """Structural profile of a repository, built from heuristics only (AD-1).

    Notes:
    - repo_commit is the HEAD SHA at time of analysis (reproducibility anchor).
    - All unknown/undetectable fields are None or empty list — never fabricated.
    - No conventions/gotchas fields: those are produced by generate/ (AD-1).
    """
    repo_commit: str
    languages: list[LanguageStat] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    commands: CommandSet = field(default_factory=CommandSet)
    top_level_dirs: list[str] = field(default_factory=list)
    key_modules: list[str] = field(default_factory=list)
    domain_terms: list[str] = field(default_factory=list)   # frequent identifiers + README headings
    file_nodes: list[FileNode] = field(default_factory=list)
    dependency_edges: list[DependencyEdge] = field(default_factory=list)
