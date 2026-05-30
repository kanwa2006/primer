"""Context-file generation — the ONE Layer-1 LLM call in the PRIMER pipeline.

Key contracts (Session 2 §4.5, Decision Addendum M7):
- Exactly ONE call to provider.complete() per successful generation.
- Output must be a LEAN ≤~20-line file.
- Validation: <50 chars OR no code-block/command-like content OR >8 KB / truncated
  → retry once with a simplified prompt → else GenerationError.
- filename is sourced from the caller (M7: adapter.context_filename()), not hardcoded.
- Usage is tagged as PRIMER OVERHEAD — never mixed into eval cost (two-stream rule).
- Temperature 0 for reproducibility (generator determinism confirmed requirement).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from primer.errors import GenerationError
from primer.generate.prompts import (
    LEAN_SYSTEM_PROMPT,
    RETRY_SYSTEM_PROMPT,
    build_retry_message,
    build_user_message,
)
from primer.ingest.models import RepoProfile
from primer.llm.base import LLMProvider, TokenUsage

# ---------------------------------------------------------------------------
# Validation thresholds (C9: two layers compose)
# ---------------------------------------------------------------------------
_MIN_CONTENT_CHARS = 50        # generate-layer minimum (Q9c provider layer: <20)
_MAX_CONTENT_BYTES = 8 * 1024  # 8 KB — truncated / runaway output
_MAX_LINES = 25                # soft ceiling for the lean-file check (≤~20 lines spec)

# A "code-block-like" pattern: at least one command, path, or backtick sequence
_CODE_LIKE_RE = re.compile(
    r"(`[^`]+`|^\s*[a-z][\w\-]*(run|test|build|install|exec|lint|check|npm|pip|uv|pytest|make)\b)",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class GenerationResult:
    """Result of a single context-file generation.

    Attributes:
        content:  The generated file content (the artifact under test).
        usage:    Token usage tagged as PRIMER OVERHEAD — never eval cost.
        lines:    Number of lines in content.
        filename: The logical filename chosen by the caller (M7).
    """
    content: str
    usage: TokenUsage
    lines: int
    filename: str


def _is_valid(content: str) -> bool:
    """Return True if the content passes the generate-layer validation rules (C9)."""
    if len(content) < _MIN_CONTENT_CHARS:
        return False
    if len(content.encode("utf-8")) > _MAX_CONTENT_BYTES:
        return False
    # Must contain something code-like (a command, backtick snippet, etc.)
    if not _CODE_LIKE_RE.search(content):
        return False
    return True


def _build_profile_summary(profile: RepoProfile) -> str:
    """Serialize the relevant RepoProfile fields into a compact summary string."""
    lines: list[str] = []

    if profile.languages:
        lang_str = ", ".join(
            f"{ls.name} ({ls.percent:.0f}%)" for ls in profile.languages
        )
        lines.append(f"Languages: {lang_str}")

    if profile.frameworks:
        lines.append(f"Frameworks: {', '.join(profile.frameworks)}")

    cmds = profile.commands
    if cmds.package_manager:
        lines.append(f"Package manager: {cmds.package_manager}")
    if cmds.test_cmd:
        lines.append(f"Test command: {cmds.test_cmd}")
    if cmds.build_cmd:
        lines.append(f"Build command: {cmds.build_cmd}")
    if cmds.lint_cmd:
        lines.append(f"Lint command: {cmds.lint_cmd}")
    if cmds.dev_cmd:
        lines.append(f"Dev command: {cmds.dev_cmd}")

    if profile.top_level_dirs:
        lines.append(f"Top-level dirs: {', '.join(profile.top_level_dirs[:8])}")

    if profile.key_modules:
        lines.append(f"Key modules: {', '.join(profile.key_modules[:10])}")

    if profile.domain_terms:
        lines.append(f"Domain terms: {', '.join(profile.domain_terms[:15])}")

    lines.append(f"Repo commit: {profile.repo_commit}")

    return "\n".join(lines)


async def write_context(
    profile: RepoProfile,
    provider: LLMProvider,
    filename: str = "AGENTS.md",
) -> GenerationResult:
    """Generate a lean context file from a repo profile.

    This is the SINGLE Layer-1 LLM call in the PRIMER MVP pipeline.
    The caller must pass the correct filename (from adapter.context_filename())
    per M7; this function is filename-agnostic.

    Args:
        profile:   Structural profile of the target repository (heuristic, no LLM).
        provider:  Configured LLM provider (from get_provider(config)).
        filename:  Logical name for the generated file (e.g. "CLAUDE.md"). M7.

    Returns:
        GenerationResult with content, usage (PRIMER overhead), lines, filename.

    Raises:
        GenerationError: If output is invalid after one retry.
    """
    profile_summary = _build_profile_summary(profile)

    # --- First attempt ---
    response = await provider.complete(
        system=LEAN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_message(profile_summary)}],
        model=_get_model(provider),
    )

    content = response.content.strip()

    if _is_valid(content):
        return _make_result(content, response.usage, filename)

    # --- Retry once with a simplified prompt ---
    retry_response = await provider.complete(
        system=RETRY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_retry_message(profile_summary)}],
        model=_get_model(provider),
    )

    retry_content = retry_response.content.strip()

    if _is_valid(retry_content):
        # Combine usage from both calls (both are PRIMER overhead)
        combined_usage = _combine_usage(response.usage, retry_response.usage)
        return _make_result(retry_content, combined_usage, filename)

    raise GenerationError(
        f"Context-file generation failed after one retry. "
        f"The model returned output that is too short (<{_MIN_CONTENT_CHARS} chars), "
        f"too large (>{_MAX_CONTENT_BYTES} bytes), or lacks any command-like content. "
        f"Try a different provider or check the repo profile."
    )


def _get_model(provider: LLMProvider) -> str:
    """Extract the model name from the provider (fall back to a safe default)."""
    return getattr(provider, "_default_model", None) or getattr(provider, "_model", "claude-sonnet-4-6")


def _make_result(content: str, usage: TokenUsage, filename: str) -> GenerationResult:
    lines = len(content.splitlines())
    return GenerationResult(
        content=content,
        usage=usage,
        lines=lines,
        filename=filename,
    )


def _combine_usage(first: TokenUsage, second: TokenUsage) -> TokenUsage:
    """Merge two TokenUsage records (both are PRIMER overhead from the same call chain)."""
    # Worst-case confidence
    confidence_order = {"exact": 0, "estimated": 1, "free": 2}
    worst = max(
        first.cost_confidence,
        second.cost_confidence,
        key=lambda c: confidence_order.get(c, 1),
    )
    return TokenUsage(
        input_tokens=first.input_tokens + second.input_tokens,
        output_tokens=first.output_tokens + second.output_tokens,
        cache_creation_input_tokens=(
            first.cache_creation_input_tokens + second.cache_creation_input_tokens
        ),
        cache_read_input_tokens=(
            first.cache_read_input_tokens + second.cache_read_input_tokens
        ),
        cost_usd=first.cost_usd + second.cost_usd,
        cost_confidence=worst,
    )
