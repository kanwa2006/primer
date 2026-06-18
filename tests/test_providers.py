"""Tests for the multi-provider LLM matrix.

Covers:
- OpenAIProvider: complete(), cost_confidence="estimated", estimate_cost, factory wiring
- GeminiProvider: complete(), cost_confidence="exact", estimate_cost, factory wiring
- OpenRouterProvider: complete(), cost_confidence="estimated", estimate_cost, factory wiring
- factory.get_provider(): wires all three providers from config; raises ConfigError on missing keys
- Arch boundary: vendor SDK imports live only in primer/llm/ (existing boundary test covers this)
- Q9b: correct cost_confidence per provider
- Q9d: provider/model uniformity (existing scorer tests cover mismatch; checked here at unit level)
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run a coroutine in the test event loop."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# OpenAIProvider
# ---------------------------------------------------------------------------

class TestOpenAIProvider:
    """Unit tests for primer.llm.openai.OpenAIProvider."""

    def _make_fake_response(self, content="hello", prompt_tokens=10, completion_tokens=5):
        usage = MagicMock()
        usage.prompt_tokens = prompt_tokens
        usage.completion_tokens = completion_tokens

        message = MagicMock()
        message.content = content

        choice = MagicMock()
        choice.message = message

        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = usage
        resp.model = "gpt-4o"
        return resp

    def _make_provider(self, model="gpt-4o"):
        """Return OpenAIProvider with AsyncOpenAI client construction mocked."""
        with patch("primer.llm.openai._openai.AsyncOpenAI"):
            from primer.llm.openai import OpenAIProvider
            p = OpenAIProvider(api_key="sk-test-000000000000000000000000", model=model)
        return p

    def test_complete_returns_llm_response(self):
        provider = self._make_provider()
        fake_resp = self._make_fake_response("world", prompt_tokens=20, completion_tokens=8)
        provider._client.chat.completions.create = AsyncMock(return_value=fake_resp)

        result = _run(
            provider.complete("sys", [{"role": "user", "content": "hi"}], "gpt-4o")
        )

        assert result.content == "world"
        assert result.provider == "openai"
        assert result.model == "gpt-4o"
        assert result.usage.input_tokens == 20
        assert result.usage.output_tokens == 8

    def test_cost_confidence_is_estimated(self):
        """Q9b: OpenAI cost_confidence must be 'estimated'."""
        provider = self._make_provider()
        fake_resp = self._make_fake_response()
        provider._client.chat.completions.create = AsyncMock(return_value=fake_resp)

        result = _run(
            provider.complete("sys", [{"role": "user", "content": "hi"}], "gpt-4o")
        )

        assert result.usage.cost_confidence == "estimated"

    def test_estimate_cost_gpt4o(self):
        from primer.llm.openai import OpenAIProvider
        with patch("primer.llm.openai._openai.AsyncOpenAI"):
            provider = OpenAIProvider(api_key="sk-test-000000000000000000000000", model="gpt-4o")
        cost = provider.estimate_cost(1_000_000, 1_000_000)
        # gpt-4o: $2.50/M input + $10.00/M output = $12.50
        assert abs(cost - 12.50) < 0.01

    def test_estimate_cost_gpt4o_mini(self):
        from primer.llm.openai import OpenAIProvider
        with patch("primer.llm.openai._openai.AsyncOpenAI"):
            provider = OpenAIProvider(api_key="sk-test-000000000000000000000000", model="gpt-4o-mini")
        cost = provider.estimate_cost(1_000_000, 1_000_000)
        # $0.15/M + $0.60/M = $0.75
        assert abs(cost - 0.75) < 0.01

    def test_supports_caching_false(self):
        provider = self._make_provider()
        assert provider.supports_caching is False

    def test_complete_no_usage_returns_zero_tokens(self):
        provider = self._make_provider()

        resp = MagicMock()
        resp.choices = []
        resp.usage = None
        resp.model = "gpt-4o"
        provider._client.chat.completions.create = AsyncMock(return_value=resp)

        result = _run(
            provider.complete("sys", [{"role": "user", "content": "hi"}], "gpt-4o")
        )

        assert result.usage.input_tokens == 0
        assert result.usage.output_tokens == 0
        assert result.content == ""


# ---------------------------------------------------------------------------
# GeminiProvider
# ---------------------------------------------------------------------------

class TestGeminiProvider:
    """Unit tests for primer.llm.gemini.GeminiProvider (google-genai SDK)."""

    def _make_fake_response(self, text="hello", prompt_tokens=15, candidate_tokens=7):
        part = MagicMock()
        part.text = text

        content = MagicMock()
        content.parts = [part]

        candidate = MagicMock()
        candidate.content = content

        meta = MagicMock()
        meta.prompt_token_count = prompt_tokens
        meta.candidates_token_count = candidate_tokens

        resp = MagicMock()
        resp.candidates = [candidate]
        resp.usage_metadata = meta
        return resp

    def _make_provider_with_mock(self, model="gemini-1.5-flash"):
        """Return (provider, mock_aio_models) where generate_content is pre-wired."""
        with patch("google.genai.Client") as MockClient:
            provider_obj = None
            from primer.llm.gemini import GeminiProvider
            provider_obj = GeminiProvider(api_key="AIzaTest000000", model=model)
        # provider_obj._client is a MagicMock; wire aio.models.generate_content
        return provider_obj

    def test_complete_returns_llm_response(self):
        from primer.llm.gemini import GeminiProvider

        with patch("google.genai.Client"):
            provider = GeminiProvider(api_key="AIzaTest000000", model="gemini-1.5-flash")

        fake_resp = self._make_fake_response("gemini answer", 15, 7)
        provider._client.aio.models.generate_content = AsyncMock(return_value=fake_resp)

        result = _run(
            provider.complete(
                "sys", [{"role": "user", "content": "q"}], "gemini-1.5-flash"
            )
        )

        assert result.content == "gemini answer"
        assert result.provider == "gemini"
        assert result.usage.input_tokens == 15
        assert result.usage.output_tokens == 7

    def test_cost_confidence_is_exact(self):
        """Q9b: Gemini cost_confidence must be 'exact'."""
        from primer.llm.gemini import GeminiProvider

        with patch("google.genai.Client"):
            provider = GeminiProvider(api_key="AIzaTest000000", model="gemini-1.5-flash")

        fake_resp = self._make_fake_response()
        provider._client.aio.models.generate_content = AsyncMock(return_value=fake_resp)

        result = _run(
            provider.complete(
                "sys", [{"role": "user", "content": "q"}], "gemini-1.5-flash"
            )
        )

        assert result.usage.cost_confidence == "exact"

    def test_estimate_cost_gemini_flash(self):
        from primer.llm.gemini import GeminiProvider

        with patch("google.genai.Client"):
            provider = GeminiProvider(api_key="AIzaTest000000", model="gemini-1.5-flash")

        cost = provider.estimate_cost(1_000_000, 1_000_000)
        # $0.075/M + $0.30/M = $0.375
        assert abs(cost - 0.375) < 0.001

    def test_estimate_cost_gemini_pro(self):
        from primer.llm.gemini import GeminiProvider

        with patch("google.genai.Client"):
            provider = GeminiProvider(api_key="AIzaTest000000", model="gemini-1.5-pro")

        cost = provider.estimate_cost(1_000_000, 1_000_000)
        # $1.25/M + $5.00/M = $6.25
        assert abs(cost - 6.25) < 0.01

    def test_supports_caching_false(self):
        from primer.llm.gemini import GeminiProvider

        with patch("google.genai.Client"):
            provider = GeminiProvider(api_key="AIzaTest000000")
        assert provider.supports_caching is False

    def test_complete_no_candidates_returns_empty(self):
        from primer.llm.gemini import GeminiProvider

        with patch("google.genai.Client"):
            provider = GeminiProvider(api_key="AIzaTest000000", model="gemini-1.5-flash")

        resp = MagicMock()
        resp.candidates = []
        resp.usage_metadata = None
        provider._client.aio.models.generate_content = AsyncMock(return_value=resp)

        result = _run(
            provider.complete("sys", [{"role": "user", "content": "q"}], "gemini-1.5-flash")
        )

        assert result.content == ""
        assert result.usage.input_tokens == 0
        assert result.usage.output_tokens == 0


# ---------------------------------------------------------------------------
# OpenRouterProvider
# ---------------------------------------------------------------------------

class TestOpenRouterProvider:
    """Unit tests for primer.llm.openrouter.OpenRouterProvider."""

    def _fake_requests_post(self, content="or answer", prompt_tokens=12, completion_tokens=6):
        data = {
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
            "model": "anthropic/claude-3-haiku",
        }
        resp = MagicMock()
        resp.json.return_value = data
        resp.raise_for_status = MagicMock()
        return resp

    def test_complete_returns_llm_response(self):
        from primer.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(api_key="or-test-00000000")
        fake_resp = self._fake_requests_post("openrouter result", 12, 6)

        with patch("primer.llm.openrouter.requests.post", return_value=fake_resp):
            result = _run(
                provider.complete(
                    "sys", [{"role": "user", "content": "hi"}], "anthropic/claude-3-haiku"
                )
            )

        assert result.content == "openrouter result"
        assert result.provider == "openrouter"
        assert result.usage.input_tokens == 12
        assert result.usage.output_tokens == 6

    def test_cost_confidence_is_estimated(self):
        """Q9b: OpenRouter cost_confidence must be 'estimated'."""
        from primer.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(api_key="or-test-00000000")
        fake_resp = self._fake_requests_post()

        with patch("primer.llm.openrouter.requests.post", return_value=fake_resp):
            result = _run(
                provider.complete(
                    "sys", [{"role": "user", "content": "hi"}], "anthropic/claude-3-haiku"
                )
            )

        assert result.usage.cost_confidence == "estimated"

    def test_estimate_cost_known_model(self):
        from primer.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            api_key="or-test-00000000",  # pragma: allowlist secret
            model="anthropic/claude-3-5-sonnet",
        )
        cost = provider.estimate_cost(1_000_000, 1_000_000)
        # $3.00/M + $15.00/M = $18.00
        assert abs(cost - 18.00) < 0.01

    def test_estimate_cost_unknown_model_uses_default(self):
        from primer.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            api_key="or-test-00000000",  # pragma: allowlist secret
            model="some/unknown-future-model",
        )
        cost = provider.estimate_cost(1_000_000, 1_000_000)
        # Default: $1.00/M + $3.00/M = $4.00
        assert abs(cost - 4.00) < 0.01

    def test_supports_caching_false(self):
        from primer.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(api_key="or-test-00000000")
        assert provider.supports_caching is False

    def test_request_error_raises_runtime_error(self):
        import requests as req_lib
        from primer.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(api_key="or-test-00000000")

        with patch("primer.llm.openrouter.requests.post", side_effect=req_lib.RequestException("conn failed")):
            with pytest.raises(RuntimeError, match="OpenRouter request failed"):
                _run(
                    provider.complete(
                        "sys", [{"role": "user", "content": "hi"}], "model"
                    )
                )

    def test_key_not_logged_in_error_message(self):
        """Security: API key must not appear in RuntimeError message (log_safe)."""
        import requests as req_lib
        from primer.llm.openrouter import OpenRouterProvider

        secret_key = "or-sk-ant-super-secret-key-12345"  # pragma: allowlist secret
        provider = OpenRouterProvider(api_key=secret_key)

        with patch(
            "primer.llm.openrouter.requests.post",
            side_effect=req_lib.RequestException(f"failed with key {secret_key}"),
        ):
            with pytest.raises(RuntimeError) as exc_info:
                _run(
                    provider.complete("sys", [{"role": "user", "content": "hi"}], "model")
                )

        assert secret_key not in str(exc_info.value)


# ---------------------------------------------------------------------------
# Factory wiring — additional providers
# ---------------------------------------------------------------------------

class TestFactoryAdditionalProviders:
    """factory.get_provider() instantiates additional providers from config."""

    def test_openai_provider_wired(self, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-000000000000000000000000")

        from primer.config import Settings
        from primer.llm.factory import get_provider
        from primer.llm.openai import OpenAIProvider

        with patch("primer.llm.openai._openai.AsyncOpenAI"):
            config = Settings()
            provider = get_provider(config)

        assert isinstance(provider, OpenAIProvider)

    def test_gemini_provider_wired(self, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "gemini")
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaTest000000000000000000000000000")

        from primer.config import Settings
        from primer.llm.factory import get_provider
        from primer.llm.gemini import GeminiProvider

        with patch("google.genai.Client"):
            config = Settings()
            provider = get_provider(config)

        assert isinstance(provider, GeminiProvider)

    def test_openrouter_provider_wired(self, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-000000000000000000000000")

        from primer.config import Settings
        from primer.llm.factory import get_provider
        from primer.llm.openrouter import OpenRouterProvider

        config = Settings()
        provider = get_provider(config)

        assert isinstance(provider, OpenRouterProvider)

    def test_openai_missing_key_raises_config_error(self, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "openai")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        from primer.config import Settings
        from primer.llm.factory import get_provider
        from primer.errors import ConfigError

        config = Settings()
        with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
            get_provider(config)

    def test_gemini_missing_key_raises_config_error(self, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "gemini")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        from primer.config import Settings
        from primer.llm.factory import get_provider
        from primer.errors import ConfigError

        monkeypatch.setattr(Settings, "model_config", {**Settings.model_config, "env_file": None})

        config = Settings()
        with pytest.raises(ConfigError, match="GEMINI_API_KEY"):
            get_provider(config)

    def test_openrouter_missing_key_raises_config_error(self, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "openrouter")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        from primer.config import Settings
        from primer.llm.factory import get_provider
        from primer.errors import ConfigError

        config = Settings()
        with pytest.raises(ConfigError, match="OPENROUTER_API_KEY"):
            get_provider(config)

    def test_unknown_provider_raises_value_error(self, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "bogus_provider_xyz")

        from primer.config import Settings
        from primer.llm.factory import get_provider

        config = Settings()
        with pytest.raises(ValueError, match="bogus_provider_xyz"):
            get_provider(config)


# ---------------------------------------------------------------------------
# Q9b compliance table — assert all providers return correct cost_confidence
# ---------------------------------------------------------------------------

class TestQ9bCostConfidence:
    """Verify cost_confidence is exactly right for every provider (Q9b)."""

    EXPECTED = {
        "anthropic": "exact",
        "gemini":    "exact",
        "openai":    "estimated",
        "openrouter": "estimated",
        "ollama":    "free",
    }

    def test_anthropic_exact(self):
        from primer.llm.anthropic import AnthropicProvider

        with patch("primer.llm.anthropic._anthropic.AsyncAnthropic"):
            provider = AnthropicProvider(api_key="sk-ant-test-0000000000")

        usage = MagicMock()
        usage.input_tokens = 5
        usage.output_tokens = 3
        usage.cache_creation_input_tokens = 0
        usage.cache_read_input_tokens = 0

        part = MagicMock()
        part.text = "ok"

        fake_msg = MagicMock()
        fake_msg.content = [part]
        fake_msg.usage = usage
        fake_msg.model = "claude-sonnet-4-6"

        provider._client.messages.create = AsyncMock(return_value=fake_msg)

        result = _run(
            provider.complete("sys", [{"role": "user", "content": "hi"}], "claude-sonnet-4-6")
        )
        assert result.usage.cost_confidence == "exact"

    def test_gemini_exact(self):
        from primer.llm.gemini import GeminiProvider

        with patch("google.genai.Client"):
            provider = GeminiProvider(api_key="AIzaTest000000")

        part = MagicMock(); part.text = "ok"
        content = MagicMock(); content.parts = [part]
        candidate = MagicMock(); candidate.content = content
        meta = MagicMock(); meta.prompt_token_count = 5; meta.candidates_token_count = 3
        resp = MagicMock(); resp.candidates = [candidate]; resp.usage_metadata = meta

        provider._client.aio.models.generate_content = AsyncMock(return_value=resp)
        result = _run(
            provider.complete("sys", [{"role": "user", "content": "q"}], "gemini-1.5-flash")
        )

        assert result.usage.cost_confidence == "exact"

    def test_openai_estimated(self):
        from primer.llm.openai import OpenAIProvider

        with patch("primer.llm.openai._openai.AsyncOpenAI"):
            provider = OpenAIProvider(api_key="sk-test-000000000000000000000000")

        usage = MagicMock(); usage.prompt_tokens = 5; usage.completion_tokens = 3
        msg = MagicMock(); msg.content = "ok"
        choice = MagicMock(); choice.message = msg
        resp = MagicMock(); resp.choices = [choice]; resp.usage = usage; resp.model = "gpt-4o"

        provider._client.chat.completions.create = AsyncMock(return_value=resp)
        result = _run(
            provider.complete("sys", [{"role": "user", "content": "hi"}], "gpt-4o")
        )

        assert result.usage.cost_confidence == "estimated"

    def test_openrouter_estimated(self):
        from primer.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(api_key="or-test-00000000")
        data = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            "model": "model",
        }
        resp = MagicMock(); resp.json.return_value = data; resp.raise_for_status = MagicMock()

        with patch("primer.llm.openrouter.requests.post", return_value=resp):
            result = _run(
                provider.complete("sys", [{"role": "user", "content": "hi"}], "model")
            )

        assert result.usage.cost_confidence == "estimated"

    def test_ollama_free(self):
        from primer.llm.ollama import OllamaProvider
        import requests as req_lib

        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3")
        data = {"message": {"role": "assistant", "content": "x" * 25}}
        resp = MagicMock(); resp.json.return_value = data; resp.raise_for_status = MagicMock()

        with patch("primer.llm.ollama.requests.post", return_value=resp):
            result = _run(
                provider.complete("sys", [{"role": "user", "content": "hi"}], "llama3")
            )

        assert result.usage.cost_confidence == "free"
        assert result.usage.cost_usd == 0.0
