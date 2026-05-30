"""Repo analyzer — tree-sitter 0.25, heuristics only, no LLM, no network (AD-1).

analyze_repo() walks the repository respecting .gitignore patterns, parses
supported languages with tree-sitter 0.25, builds a coarse module map and
dependency edges, and extracts candidate domain terms.

tree-sitter 0.25 API note:
  - Language(lang_obj.language()); Parser(LANG)
  - No .captures() on Query — tree is walked manually with a recursive helper.
  - Node.text returns bytes; decode with errors="replace".
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterator

from primer.ingest.commands import detect_commands
from primer.ingest.models import (
    CommandSet,
    DependencyEdge,
    FileNode,
    LanguageStat,
    RepoProfile,
)

# Supported language extensions and their tree-sitter loader
_LANG_EXT: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "javascript",  # use JS parser for TS (best-effort)
    ".jsx": "javascript",
    ".tsx": "javascript",
}

# Directories to always skip
_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".next", "dist", "build",
    ".venv", "venv", "env", ".env", ".tox", ".mypy_cache", ".pytest_cache",
    "*.egg-info", ".eggs", "coverage", ".coverage",
}

# Framework detection heuristics: dep name → framework label
_FRAMEWORK_DEPS: dict[str, str] = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "starlette": "Starlette",
    "tornado": "Tornado",
    "aiohttp": "aiohttp",
    "react": "React",
    "vue": "Vue",
    "angular": "Angular",
    "next": "Next.js",
    "express": "Express",
    "nestjs": "NestJS",
    "pytest": "pytest",
    "sqlalchemy": "SQLAlchemy",
    "pydantic": "Pydantic",
    "typer": "Typer",
    "click": "Click",
}


def analyze_repo(path: str, config=None) -> RepoProfile:  # type: ignore[type-arg]
    """Analyze a repository and return a RepoProfile.

    Pure heuristics; no LLM calls; no network access (AD-1).
    Deterministic: same repo state + same path → identical profile.
    Records repo_commit (HEAD SHA) as reproducibility anchor.

    Args:
        path: absolute or relative path to the repository root.
        config: Settings instance (used for future config-driven limits; unused now).
    """
    root = Path(path).resolve()
    repo_commit = _get_repo_commit(root)

    # Collect gitignore patterns
    gitignore_patterns = _load_gitignore(root)

    # Walk the repo and collect files
    py_files: list[Path] = []
    js_files: list[Path] = []
    all_source: list[Path] = []
    top_level_dirs: list[str] = []
    lang_byte_counts: Counter[str] = Counter()

    for entry in sorted(root.iterdir()):
        if entry.is_dir() and not entry.name.startswith(".") and entry.name not in _SKIP_DIRS:
            top_level_dirs.append(entry.name)

    for fpath in _walk_repo(root, gitignore_patterns):
        ext = fpath.suffix.lower()
        lang = _LANG_EXT.get(ext)
        if lang:
            try:
                size = fpath.stat().st_size
                lang_byte_counts[lang] += size
                all_source.append(fpath)
                if lang == "python":
                    py_files.append(fpath)
                elif lang == "javascript":
                    js_files.append(fpath)
            except OSError:
                pass

    # Language stats
    total_bytes = sum(lang_byte_counts.values()) or 1
    languages = [
        LanguageStat(name=lang, percent=round(100.0 * count / total_bytes, 1))
        for lang, count in lang_byte_counts.most_common()
    ]

    # Parse source files
    file_nodes: list[FileNode] = []
    dependency_edges: list[DependencyEdge] = []
    all_identifiers: Counter[str] = Counter()
    edge_counter: Counter[tuple[str, str]] = Counter()

    for fpath in all_source:
        rel = fpath.relative_to(root)
        lang = _LANG_EXT.get(fpath.suffix.lower(), "unknown")
        module = _path_to_module(rel)

        symbols: list[str] = []
        imports: list[str] = []

        try:
            src = fpath.read_bytes()
            if lang == "python":
                symbols, imports, idents = _parse_python(src)
            elif lang == "javascript":
                symbols, imports, idents = _parse_javascript(src)
            else:
                symbols, imports, idents = [], [], []
            all_identifiers.update(idents)
        except Exception:
            symbols, imports = [], []

        file_nodes.append(FileNode(
            path=str(rel).replace("\\", "/"),
            module=module,
            kind="file",
            symbols=symbols,
        ))

        # Build dependency edges
        for imp in imports:
            imp_module = _normalize_import(imp, module, root)
            if imp_module and imp_module != module:
                edge_counter[(module, imp_module)] += 1

    for (src_mod, dst_mod), weight in edge_counter.items():
        dependency_edges.append(DependencyEdge(
            src_module=src_mod,
            dst_module=dst_mod,
            weight=weight,
        ))

    # Key modules: files with the most symbols, up to 10
    key_modules = [
        fn.module for fn in sorted(file_nodes, key=lambda n: len(n.symbols), reverse=True)
        if fn.symbols
    ][:10]

    # Domain terms: frequent multi-char identifiers + README headings
    domain_terms = _extract_domain_terms(root, all_identifiers)

    # Frameworks
    frameworks = _detect_frameworks(root)

    # Commands
    commands = detect_commands(path)

    return RepoProfile(
        repo_commit=repo_commit,
        languages=languages,
        frameworks=frameworks,
        commands=commands,
        top_level_dirs=sorted(top_level_dirs),
        key_modules=key_modules,
        domain_terms=domain_terms,
        file_nodes=file_nodes,
        dependency_edges=dependency_edges,
    )


# ── tree-sitter parsing helpers ───────────────────────────────────────────────

def _parse_python(src: bytes) -> tuple[list[str], list[str], Counter[str]]:
    """Extract (symbols, imports, identifier_counter) from Python source."""
    try:
        import tree_sitter_python
        from tree_sitter import Language, Parser
        PY_LANG = Language(tree_sitter_python.language())
        parser = Parser(PY_LANG)
    except Exception:
        return [], [], Counter()

    tree = parser.parse(src)
    symbols: list[str] = []
    imports: list[str] = []
    idents: Counter[str] = Counter()

    _walk_python(tree.root_node, symbols, imports, idents)
    return symbols, imports, idents


def _walk_python(
    node,  # type: ignore[type-arg]
    symbols: list[str],
    imports: list[str],
    idents: Counter[str],
    depth: int = 0,
) -> None:
    """Recursively walk a Python AST node, collecting symbols and imports."""
    ntype = node.type

    if ntype == "function_definition":
        # child[1] is the identifier (name)
        for child in node.children:
            if child.type == "identifier" and child.text:
                name = child.text.decode("utf-8", errors="replace")
                if not name.startswith("_") or name.startswith("__"):
                    symbols.append(name)
                idents[name] += 1
                break
        return  # don't descend into function bodies for imports

    elif ntype == "class_definition":
        for child in node.children:
            if child.type == "identifier" and child.text:
                name = child.text.decode("utf-8", errors="replace")
                symbols.append(name)
                idents[name] += 1
                break

    elif ntype == "import_statement":
        # import a.b.c  → dotted_name children
        for child in node.children:
            if child.type == "dotted_name" and child.text:
                imports.append(child.text.decode("utf-8", errors="replace"))
            elif child.type == "aliased_import":
                for subchild in child.children:
                    if subchild.type == "dotted_name" and subchild.text:
                        imports.append(subchild.text.decode("utf-8", errors="replace"))

    elif ntype == "import_from_statement":
        # from a.b import c → first dotted_name is the module
        for child in node.children:
            if child.type == "dotted_name" and child.text:
                imports.append(child.text.decode("utf-8", errors="replace"))
                break

    elif ntype == "identifier" and node.text:
        name = node.text.decode("utf-8", errors="replace")
        if len(name) > 2 and name.isidentifier():
            idents[name] += 1

    for child in node.children:
        _walk_python(child, symbols, imports, idents, depth + 1)


def _parse_javascript(src: bytes) -> tuple[list[str], list[str], Counter[str]]:
    """Extract (symbols, imports, identifier_counter) from JS/TS source."""
    try:
        import tree_sitter_javascript
        from tree_sitter import Language, Parser
        JS_LANG = Language(tree_sitter_javascript.language())
        parser = Parser(JS_LANG)
    except Exception:
        return [], [], Counter()

    tree = parser.parse(src)
    symbols: list[str] = []
    imports: list[str] = []
    idents: Counter[str] = Counter()

    _walk_javascript(tree.root_node, symbols, imports, idents)
    return symbols, imports, idents


def _walk_javascript(
    node,  # type: ignore[type-arg]
    symbols: list[str],
    imports: list[str],
    idents: Counter[str],
    depth: int = 0,
) -> None:
    """Recursively walk a JS AST node."""
    ntype = node.type

    if ntype == "function_declaration":
        for child in node.children:
            if child.type == "identifier" and child.text:
                name = child.text.decode("utf-8", errors="replace")
                symbols.append(name)
                idents[name] += 1
                break

    elif ntype == "class_declaration":
        for child in node.children:
            if child.type == "identifier" and child.text:
                name = child.text.decode("utf-8", errors="replace")
                symbols.append(name)
                idents[name] += 1
                break

    elif ntype == "lexical_declaration":
        # const foo = () => ... or const foo = function ...
        for child in node.children:
            if child.type == "variable_declarator":
                for subchild in child.children:
                    if subchild.type == "identifier" and subchild.text:
                        name = subchild.text.decode("utf-8", errors="replace")
                        # Only if followed by arrow_function or function
                        has_fn = any(
                            c.type in ("arrow_function", "function")
                            for c in child.children
                        )
                        if has_fn:
                            symbols.append(name)
                        idents[name] += 1
                        break

    elif ntype == "import_statement":
        # from "module" or from 'module'
        for child in node.children:
            if child.type == "string" and child.text:
                raw = child.text.decode("utf-8", errors="replace").strip("'\"`")
                if not raw.startswith("."):
                    imports.append(raw)
                break

    elif ntype == "identifier" and node.text:
        name = node.text.decode("utf-8", errors="replace")
        if len(name) > 2 and name.isidentifier():
            idents[name] += 1

    for child in node.children:
        _walk_javascript(child, symbols, imports, idents, depth + 1)


# ── utility helpers ───────────────────────────────────────────────────────────

def _get_repo_commit(root: Path) -> str:
    """Return HEAD SHA or a content hash if git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        sha = result.stdout.strip()
        if sha and len(sha) >= 7:
            return sha
    except Exception:
        pass
    # Fallback: hash the listing of the top-level directory
    try:
        listing = sorted(str(p) for p in root.iterdir())
        return "nongit-" + hashlib.sha1("\n".join(listing).encode()).hexdigest()[:12]
    except Exception:
        return "unknown"


def _load_gitignore(root: Path) -> list[str]:
    """Return a list of gitignore glob patterns from .gitignore, if present."""
    patterns: list[str] = []
    gi = root / ".gitignore"
    if gi.exists():
        try:
            for line in gi.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
        except OSError:
            pass
    return patterns


def _is_ignored(path: Path, root: Path, patterns: list[str]) -> bool:
    """Simple gitignore pattern check (prefix/suffix matching, not full git semantics)."""
    rel = str(path.relative_to(root)).replace("\\", "/")
    name = path.name
    for pat in patterns:
        pat = pat.lstrip("/")
        # Directory pattern (trailing slash)
        if pat.endswith("/"):
            if rel.startswith(pat.rstrip("/")) or ("/" + pat.rstrip("/") + "/") in ("/" + rel + "/"):
                return True
        # Wildcard suffix (e.g. *.pyc)
        elif pat.startswith("*"):
            if name.endswith(pat[1:]):
                return True
        # Exact name match
        elif pat == name or rel == pat or rel.startswith(pat + "/"):
            return True
    return False


def _walk_repo(root: Path, gitignore: list[str]) -> Iterator[Path]:
    """Yield all non-ignored source files under root."""
    skip_dirs = _SKIP_DIRS | {".secrets.baseline"}
    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        # Prune directories in-place
        dirnames[:] = [
            d for d in sorted(dirnames)
            if d not in skip_dirs
            and not d.endswith(".egg-info")
            and not _is_ignored(dp / d, root, gitignore)
        ]
        for fname in sorted(filenames):
            fp = dp / fname
            if not _is_ignored(fp, root, gitignore):
                yield fp


def _path_to_module(rel: Path) -> str:
    """Convert a relative path to a dotted module name."""
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else str(rel)


def _normalize_import(imp: str, src_module: str, root: Path) -> str | None:
    """Normalize an import string to a module name for edge building.

    Returns None for stdlib/external that can't be resolved.
    """
    # Relative imports would have "." prefix — skip for now
    if imp.startswith("."):
        return None
    # Check if it's an internal module (first component matches a top-level dir or file)
    first = imp.split(".")[0]
    if (root / first).exists() or (root / f"{first}.py").exists():
        return imp
    return None


def _extract_domain_terms(root: Path, idents: Counter[str], top_n: int = 20) -> list[str]:
    """Extract candidate domain terms from identifiers and README headings."""
    terms: Counter[str] = Counter()

    # Identifiers with count > 1, length > 3, not Python keywords
    _PY_KEYWORDS = {
        "def", "class", "return", "import", "from", "self", "True", "False",
        "None", "and", "or", "not", "if", "else", "elif", "for", "while",
        "with", "try", "except", "finally", "raise", "pass", "break",
        "continue", "lambda", "yield", "async", "await", "global", "nonlocal",
        "assert", "del", "in", "is", "print", "type", "str", "int", "float",
        "bool", "list", "dict", "set", "tuple", "len", "range", "open",
        "super", "object", "init", "main", "test", "args", "kwargs", "path",
        "name", "data", "value", "result", "output", "input", "error", "key",
        "msg", "log", "info", "debug", "config", "options", "params", "run",
        "get", "set", "has", "add", "new", "old", "tmp", "var", "val",
    }
    for ident, count in idents.most_common(200):
        if (
            len(ident) >= 4
            and count >= 2
            and ident.lower() not in _PY_KEYWORDS
            and not ident.startswith("_")
            and re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", ident)
        ):
            terms[ident] += count

    # README headings
    for readme_name in ("README.md", "README.rst", "README.txt", "README"):
        readme = root / readme_name
        if readme.exists():
            try:
                text = readme.read_text(encoding="utf-8", errors="replace")
                for line in text.splitlines():
                    # Markdown headings
                    m = re.match(r"^#{1,4}\s+(.+)$", line.strip())
                    if m:
                        for word in re.findall(r"[A-Za-z][a-zA-Z0-9]+", m.group(1)):
                            if len(word) >= 4 and word.lower() not in _PY_KEYWORDS:
                                terms[word] += 5  # weight headings higher
                    # RST headings (underline pattern)
                    elif re.match(r"^[=\-~`]{4,}$", line.strip()):
                        pass  # the line before would be the heading text
            except OSError:
                pass
        if terms:
            break

    return [term for term, _ in terms.most_common(top_n)]


def _detect_frameworks(root: Path) -> list[str]:
    """Heuristically detect frameworks from dependency files."""
    found: list[str] = []
    seen: set[str] = set()

    def _check(text: str) -> None:
        lower = text.lower()
        for dep, label in _FRAMEWORK_DEPS.items():
            if dep in lower and label not in seen:
                found.append(label)
                seen.add(label)

    # pyproject.toml
    if (root / "pyproject.toml").exists():
        try:
            _check((root / "pyproject.toml").read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass

    # requirements.txt / requirements*.txt
    for req in root.glob("requirements*.txt"):
        try:
            _check(req.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass

    # package.json
    if (root / "package.json").exists():
        try:
            _check((root / "package.json").read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass

    return found
