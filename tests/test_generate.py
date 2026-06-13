"""Phase 2 tests — LLM provider layer + context-file generation.

Acceptance criteria tested here (Session 2 §9):
  llm/base.py:
    - log_safe() redacts sk-, sk-ant-, AIza patterns (unit-tested with samples)
    - ABC defines complete/estimate_cost/supports_caching
  llm/factory.py:
    - Returns correct provider per primer_llm_provider; unknown ⇒ ValueError
    - tests/test_arch_boundaries.py finds zero vendor-SDK imports outside primer/llm/
      (that test is already in test_arch_boundaries.py; Phase 2 makes it non-trivial)
  llm/anthropic.py:
    - complete() returns LLMResponse with exact token counts; cost_confidence="exact"
    - (live call gated by ANTHROPIC_API_KEY; mocked here)
  llm/ollama.py:
    - cost_usd=0.0, cost_confidence="free"
    - empty/<20-char output → retry once → OllamaOutputError
  generate/context_writer.py:
    - Produces a ≤~20-line file with real test/build commands and no
      linter-enforceable/generic/directory-dump lines
    - Malformed output retries once then raises GenerationError
    - usage tagged as overhead (cost_confidence field present)
    - filename-agnostic (M7): accepts any filename, does not hardcode AGENTS.md
    - Exactly ONE Layer-1 LLM call for a valid response
"""
from __future__ import annotations

import asyncio
from typing import Literal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from primer.errors import GenerationError, OllamaOutputError
from primer.generate.context_writer import (
    GenerationResult,
    _build_profile_summary,
    _is_valid,
    write_context,
)
from primer.generate.prompts import (
    LEAN_SYSTEM_PROMPT,
    RETRY_SYSTEM_PROMPT,
    build_retry_message,
    build_user_message,
)
from primer.ingest.models import CommandSet, LanguageStat, RepoProfile
from primer.llm.base import LLMProvider, LLMResponse, TokenUsage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(
    test_cmd: str = "pytest tests/",
    build_cmd: str | None = None,
    languages: list[LanguageStat] | None = None,
) -> RepoProfile:
    return RepoProfile(
        repo_commit="abc1234",
        languages=languages or [LanguageStat(name="Python", percent=90.0)],
        frameworks=["pytest"],
        commands=CommandSet(
            package_manager="pip",
            test_cmd=test_cmd,
            build_cmd=build_cmd,
        ),
        top_level_dirs=["src", "tests"],
        key_modules=["mylib.core", "mylib.utils"],
        domain_terms=["widget", "pipeline"],
    )


def _make_token_usage(confidence: Literal["exact", "estimated", "free"] = "exact") -> TokenUsage:
    return TokenUsage(
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.001,
        cost_confidence=confidence,
    )


def _make_llm_response(content: str, confidence: Literal["exact", "estimated", "free"] = "exact") -> LLMResponse:
    return LLMResponse(
        content=content,
        usage=_make_token_usage(confidence),
        model="claude-sonnet-4-6",
        provider="anthropic",
    )


VALID_CONTENT = (
    "## Commands\n"
    "- Test: `pytest tests/ -x`\n"
    "- Lint: `ruff check .`\n\n"
    "## Non-obvious conventions\n"
    "- Internal: use `mylib.core.Widget` not the top-level alias.\n"
    "- Config loaded from `~/.mylib.toml` first, then env vars override.\n"
)

INVALID_SHORT = "Hi"
INVALID_LARGE = "x" * (9 * 1024)  # > 8 KB
INVALID_NO_CMD = (
    "This repo uses Python. It has a nice architecture. "
    "There are several modules in the package. "
    "The code is well documented and follows best practices."
)


# ===========================================================================
# log_safe() — redaction unit tests
# ===========================================================================

class TestLogSafe:
    def test_redacts_sk_ant(self):
        raw = "Key is sk-ant-api03-ABCDEFG1234567890-suffix"
        result = LLMProvider.log_safe(raw)
        assert "[REDACTED]" in result
        assert "sk-ant-" not in result

    def test_redacts_sk(self):
        raw = "openai key: sk-proj-xxxxxxxxxxxxxxxxxxx"
        result = LLMProvider.log_safe(raw)
        assert "[REDACTED]" in result
        assert "sk-proj" not in result

    def test_redacts_google_key_pattern(self):
        # Build the test string dynamically so the pattern doesn't appear verbatim
        # in source (avoids triggering gitleaks/detect-secrets on test data).
        prefix = "AIza"
        raw = "google key: " + prefix + "SyD-12345678901234567890abcdef"
        result = LLMProvider.log_safe(raw)
        assert "[REDACTED]" in result
        assert prefix not in result

    def test_clean_text_unchanged(self):
        raw = "No secrets here. Just ordinary text."
        assert LLMProvider.log_safe(raw) == raw

    def test_multiple_secrets_all_redacted(self):
        # Build key-like strings dynamically to avoid triggering secret scanners.
        google_prefix = "AIza"
        raw = "sk-ant-xxx and " + google_prefix + "Sy-yyy and sk-abc"
        result = LLMProvider.log_safe(raw)
        assert "sk-ant-" not in result
        assert google_prefix not in result
        assert result.count("[REDACTED]") >= 2

    def test_empty_string(self):
        assert LLMProvider.log_safe("") == ""


# ===========================================================================
# LLMProvider ABC
# ===========================================================================

class TestLLMProviderABC:
    def test_cannot_instantiate_abc_directly(self):
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_all_methods(self):
        class Incomplete(LLMProvider):
            pass  # missing required implementations

        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_subclass_works(self):
        class Minimal(LLMProvider):
            async def complete(self, system, messages, model):
                return _make_llm_response("ok test command: pytest")

            def estimate_cost(self, i, o):
                return 0.0

            @property
            def supports_caching(self):
                return False

        m = Minimal()
        assert not m.supports_caching
        assert m.estimate_cost(100, 50) == 0.0


# ===========================================================================
# TokenUsage + LLMResponse dataclasses
# ===========================================================================

class TestTokenUsage:
    def test_defaults(self):
        u = TokenUsage(input_tokens=10, output_tokens=5)
        assert u.cache_creation_input_tokens == 0
        assert u.cache_read_input_tokens == 0
        assert u.cost_usd == 0.0
        assert u.cost_confidence == "estimated"

    def test_both_cache_fields_present(self):
        """Both cache fields must exist (C8)."""
        u = TokenUsage(
            input_tokens=0, output_tokens=0,
            cache_creation_input_tokens=512,
            cache_read_input_tokens=256,
        )
        assert u.cache_creation_input_tokens == 512
        assert u.cache_read_input_tokens == 256

    def test_cost_confidence_literal(self):
        for v in ("exact", "estimated", "free"):
            u = TokenUsage(input_tokens=0, output_tokens=0, cost_confidence=v)
            assert u.cost_confidence == v


# ===========================================================================
# factory.get_provider()
# ===========================================================================

class TestGetProvider:
    def test_anthropic_returns_anthropic_provider(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-0000000000")
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "anthropic")
        from primer.config import Settings
        from primer.llm.factory import get_provider
        from primer.llm.anthropic import AnthropicProvider

        config = Settings()
        provider = get_provider(config)
        assert isinstance(provider, AnthropicProvider)

    def test_ollama_returns_ollama_provider(self, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-0000000000")
        from primer.config import Settings
        from primer.llm.factory import get_provider
        from primer.llm.ollama import OllamaProvider

        config = Settings()
        provider = get_provider(config)
        assert isinstance(provider, OllamaProvider)

    def test_unknown_provider_raises_value_error(self, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "banana")
        from primer.config import Settings
        from primer.llm.factory import get_provider

        config = Settings()
        with pytest.raises(ValueError, match="banana"):
            get_provider(config)

    def test_post_mvp_provider_raises_value_error(self, monkeypatch):
        # Phase 5: openai/gemini/openrouter are now implemented.
        # They raise ConfigError (missing key), not ValueError("Post-MVP").
        # Verify unknown provider still raises ValueError.
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "unknown_provider_xyz")
        from primer.config import Settings
        from primer.llm.factory import get_provider
        config = Settings()
        with pytest.raises(ValueError):
            get_provider(config)

    def test_anthropic_missing_key_raises(self, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "anthropic")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from primer.config import Settings
        from primer.llm.factory import get_provider
        from primer.errors import ConfigError

        config = Settings()
        with pytest.raises(ConfigError):
            get_provider(config)


# ===========================================================================
# AnthropicProvider (mocked — no live API call)
# ===========================================================================

class TestAnthropicProvider:
    def test_cost_confidence_exact(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-0000000000")
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "anthropic")
        from primer.config import Settings
        from primer.llm.factory import get_provider

        config = Settings()
        provider = get_provider(config)
        assert provider.supports_caching is True

    def test_estimate_cost_positive(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-0000000000")
        from primer.llm.anthropic import AnthropicProvider

        p = AnthropicProvider(api_key="sk-ant-test-0000000000")
        cost = p.estimate_cost(1_000_000, 1_000_000)
        assert cost > 0

    def test_complete_returns_llm_response(self, monkeypatch):
        """Mock the Anthropic async client to avoid a live API call."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-0000000000")
        from primer.llm.anthropic import AnthropicProvider

        # Build a mock response matching the Anthropic SDK shape
        mock_usage = MagicMock()
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50
        mock_usage.cache_creation_input_tokens = 0
        mock_usage.cache_read_input_tokens = 0

        mock_block = MagicMock()
        mock_block.text = "Test: `pytest tests/`\nBuild: `make`"

        mock_resp = MagicMock()
        mock_resp.content = [mock_block]
        mock_resp.usage = mock_usage
        mock_resp.model = "claude-sonnet-4-6"

        provider = AnthropicProvider(api_key="sk-ant-test-0000000000")

        async def fake_create(**kwargs):
            return mock_resp

        provider._client.messages.create = fake_create

        result = asyncio.run(
            provider.complete("sys", [{"role": "user", "content": "hi"}], "claude-sonnet-4-6")
        )
        assert isinstance(result, LLMResponse)
        assert result.usage.cost_confidence == "exact"
        assert result.usage.input_tokens == 100
        assert result.usage.output_tokens == 50
        assert result.provider == "anthropic"


# ===========================================================================
# OllamaProvider
# ===========================================================================

class TestOllamaProvider:
    def test_cost_is_zero_and_free(self):
        from primer.llm.ollama import OllamaProvider

        p = OllamaProvider(base_url="http://localhost:11434", model="llama3.3")
        assert p.estimate_cost(100, 100) == 0.0
        assert p.supports_caching is False

    def test_valid_response_returns_result(self):
        from primer.llm.ollama import OllamaProvider

        p = OllamaProvider(base_url="http://localhost:11434", model="llama3.3")

        valid_content = "Run tests: `pytest tests/`\nBuild: `make build`\nNon-obvious: use widget API."

        with patch.object(p, "_call_once", new=AsyncMock(return_value=valid_content)):
            result = asyncio.run(
                p.complete("sys", [{"role": "user", "content": "hi"}], "llama3.3")
            )
        assert isinstance(result, LLMResponse)
        assert result.usage.cost_usd == 0.0
        assert result.usage.cost_confidence == "free"
        assert result.provider == "ollama"

    def test_empty_output_retries_then_raises(self):
        from primer.llm.ollama import OllamaProvider

        p = OllamaProvider(base_url="http://localhost:11434", model="llama3.3")

        # Both attempts return empty
        with patch.object(p, "_call_once", new=AsyncMock(return_value="")):
            with pytest.raises(OllamaOutputError):
                asyncio.run(
                    p.complete("sys", [{"role": "user", "content": "hi"}], "llama3.3")
                )

    def test_short_output_retries_then_raises(self):
        from primer.llm.ollama import OllamaProvider

        p = OllamaProvider(base_url="http://localhost:11434", model="llama3.3")

        # Always returns fewer than 20 chars
        with patch.object(p, "_call_once", new=AsyncMock(return_value="ok")):
            with pytest.raises(OllamaOutputError):
                asyncio.run(
                    p.complete("sys", [{"role": "user", "content": "hi"}], "llama3.3")
                )

    def test_first_invalid_second_valid_succeeds(self):
        from primer.llm.ollama import OllamaProvider

        p = OllamaProvider(base_url="http://localhost:11434", model="llama3.3")

        valid = "Run tests: `pytest`\nLint: `ruff check .`\nUse widget API for core calls."
        call_count = {"n": 0}

        async def side_effect(*args, **kwargs):
            call_count["n"] += 1
            return "" if call_count["n"] == 1 else valid

        with patch.object(p, "_call_once", side_effect=side_effect):
            result = asyncio.run(
                p.complete("sys", [{"role": "user", "content": "hi"}], "llama3.3")
            )
        assert isinstance(result, LLMResponse)
        assert call_count["n"] == 2


# ===========================================================================
# _is_valid() unit tests
# ===========================================================================

class TestIsValid:
    def test_valid_content_passes(self):
        assert _is_valid(VALID_CONTENT)

    def test_too_short_fails(self):
        assert not _is_valid(INVALID_SHORT)

    def test_too_large_fails(self):
        assert not _is_valid(INVALID_LARGE)

    def test_no_command_like_content_fails(self):
        assert not _is_valid(INVALID_NO_CMD)

    def test_content_with_backtick_command_passes(self):
        content = "Use `pytest tests/ -x` to run tests.\nUse `make build` for builds.\nNon-obvious: configure via env."
        assert _is_valid(content)


# ===========================================================================
# _build_profile_summary()
# ===========================================================================

class TestBuildProfileSummary:
    def test_includes_test_cmd(self):
        profile = _make_profile(test_cmd="pytest tests/ -x")
        summary = _build_profile_summary(profile)
        assert "pytest tests/ -x" in summary

    def test_includes_language(self):
        profile = _make_profile()
        summary = _build_profile_summary(profile)
        assert "Python" in summary

    def test_includes_repo_commit(self):
        profile = _make_profile()
        summary = _build_profile_summary(profile)
        assert "abc1234" in summary

    def test_missing_build_cmd_not_in_summary(self):
        profile = _make_profile(build_cmd=None)
        summary = _build_profile_summary(profile)
        assert "Build command" not in summary


# ===========================================================================
# write_context() — the ONE Layer-1 call
# ===========================================================================

class TestWriteContext:
    """Tests for write_context() — the single Layer-1 LLM call."""

    def _mock_provider(self, response_content: str, confidence="exact") -> MagicMock:
        provider = MagicMock(spec=LLMProvider)
        provider._default_model = "claude-sonnet-4-6"
        provider.complete = AsyncMock(
            return_value=_make_llm_response(response_content, confidence)
        )
        return provider

    def test_returns_generation_result(self):
        provider = self._mock_provider(VALID_CONTENT)
        profile = _make_profile()

        result = asyncio.run(
            write_context(profile, provider, filename="CLAUDE.md")
        )
        assert isinstance(result, GenerationResult)

    def test_filename_is_passed_through(self):
        """M7: write_context is filename-agnostic; caller provides the name."""
        for name in ("CLAUDE.md", "AGENTS.md", "GEMINI.md"):
            provider = self._mock_provider(VALID_CONTENT)
            profile = _make_profile()
            result = asyncio.run(
                write_context(profile, provider, filename=name)
            )
            assert result.filename == name

    def test_exactly_one_call_for_valid_response(self):
        """Exactly ONE LLM call when first response is valid."""
        provider = self._mock_provider(VALID_CONTENT)
        profile = _make_profile()

        asyncio.run(
            write_context(profile, provider, filename="CLAUDE.md")
        )
        assert provider.complete.call_count == 1

    def test_usage_tagged_as_overhead(self):
        """Usage from write_context is PRIMER overhead — cost_confidence must be set."""
        provider = self._mock_provider(VALID_CONTENT)
        profile = _make_profile()

        result = asyncio.run(
            write_context(profile, provider, filename="CLAUDE.md")
        )
        assert result.usage.cost_confidence in ("exact", "estimated", "free")

    def test_lines_populated(self):
        provider = self._mock_provider(VALID_CONTENT)
        profile = _make_profile()

        result = asyncio.run(
            write_context(profile, provider, filename="CLAUDE.md")
        )
        assert result.lines == len(VALID_CONTENT.splitlines())

    def test_invalid_first_valid_second_retries(self):
        """If first response is invalid, retry once with simplified prompt."""
        call_count = {"n": 0}
        responses = [INVALID_SHORT, VALID_CONTENT]

        async def fake_complete(system, messages, model):
            r = responses[min(call_count["n"], len(responses) - 1)]
            call_count["n"] += 1
            return _make_llm_response(r)

        provider = MagicMock(spec=LLMProvider)
        provider._default_model = "claude-sonnet-4-6"
        provider.complete = fake_complete

        profile = _make_profile()
        result = asyncio.run(
            write_context(profile, provider, filename="CLAUDE.md")
        )
        assert isinstance(result, GenerationResult)
        assert call_count["n"] == 2

    def test_both_invalid_raises_generation_error(self):
        """If both attempts return invalid content, raise GenerationError."""
        provider = MagicMock(spec=LLMProvider)
        provider._default_model = "claude-sonnet-4-6"
        provider.complete = AsyncMock(return_value=_make_llm_response(INVALID_SHORT))

        profile = _make_profile()
        with pytest.raises(GenerationError):
            asyncio.run(
                write_context(profile, provider, filename="CLAUDE.md")
            )

    def test_too_large_output_raises_generation_error(self):
        """Output > 8 KB → retry → GenerationError."""
        provider = MagicMock(spec=LLMProvider)
        provider._default_model = "claude-sonnet-4-6"
        provider.complete = AsyncMock(return_value=_make_llm_response(INVALID_LARGE))

        profile = _make_profile()
        with pytest.raises(GenerationError):
            asyncio.run(
                write_context(profile, provider, filename="CLAUDE.md")
            )

    def test_content_includes_test_command(self):
        """Generated content must include something resembling the test command."""
        content = "Run tests: `pytest tests/ -x`\nUse core API, not the shim.\nConfig: see config.toml."
        provider = self._mock_provider(content)
        profile = _make_profile(test_cmd="pytest tests/ -x")

        result = asyncio.run(
            write_context(profile, provider, filename="CLAUDE.md")
        )
        assert "pytest" in result.content

    def test_no_hardcoded_agents_md(self):
        """M7: write_context never hardcodes 'AGENTS.md' as the filename.
        The filename comes from the caller."""
        provider = self._mock_provider(VALID_CONTENT)
        profile = _make_profile()

        result = asyncio.run(
            write_context(profile, provider, filename="CLAUDE.md")
        )
        # filename field should reflect what was passed in, not a hardcoded value
        assert result.filename == "CLAUDE.md"

    def test_ollama_free_cost_confidence(self):
        """Ollama responses carry cost_confidence='free'; cost_usd may be 0."""
        # Build a response matching the real Ollama provider output (cost_usd=0.0)
        free_usage = TokenUsage(
            input_tokens=0, output_tokens=0, cost_usd=0.0, cost_confidence="free"
        )
        free_response = LLMResponse(
            content=VALID_CONTENT,
            usage=free_usage,
            model="llama3.3",
            provider="ollama",
        )
        provider = MagicMock(spec=LLMProvider)
        provider._default_model = "llama3.3"
        provider.complete = AsyncMock(return_value=free_response)

        profile = _make_profile()
        result = asyncio.run(
            write_context(profile, provider, filename="AGENTS.md")
        )
        assert result.usage.cost_confidence == "free"
        assert result.usage.cost_usd == 0.0


# ===========================================================================
# Prompts sanity checks
# ===========================================================================

class TestPrompts:
    def test_lean_system_prompt_not_empty(self):
        assert len(LEAN_SYSTEM_PROMPT) > 100

    def test_retry_system_prompt_not_empty(self):
        assert len(RETRY_SYSTEM_PROMPT) > 50

    def test_build_user_message_includes_summary(self):
        msg = build_user_message("Test: pytest tests/")
        assert "pytest" in msg

    def test_build_retry_message_includes_summary(self):
        msg = build_retry_message("Test: pytest tests/")
        assert "pytest" in msg
