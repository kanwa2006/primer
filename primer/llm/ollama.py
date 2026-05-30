"""Ollama provider — local $0 generation brain.

Calls the local Ollama REST API via requests (no vendor SDK needed).
cost_confidence = "free"; cost_usd = 0.0.
Output validation per Q9c: empty / non-UTF-8 / <20 chars → retry once → OllamaOutputError.
"""
from __future__ import annotations

import json

import requests

from primer.errors import OllamaOutputError
from primer.llm.base import LLMProvider, LLMResponse, TokenUsage

_MIN_OUTPUT_CHARS = 20


class OllamaProvider(LLMProvider):
    """Calls a local Ollama model via the /api/chat endpoint.

    The base_url and model are configured in Settings (ollama_base_url, ollama_model).
    No API key required; cost is always $0.
    """

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._provider_name = "ollama"

    async def complete(
        self,
        system: str,
        messages: list[dict],
        model: str,
    ) -> LLMResponse:
        """POST to the local Ollama /api/chat endpoint.

        Retries once if output is invalid per Q9c.
        Raises OllamaOutputError after the second failure.
        """
        content = await self._call_once(system, messages, model)
        if not self._valid(content):
            # Retry once with a simplified prompt (Q9c)
            simplified = [{"role": "user", "content": messages[-1]["content"] + "\n\nBe concise."}]
            content = await self._call_once(system, simplified, model)
            if not self._valid(content):
                raise OllamaOutputError(
                    f"Ollama model {model!r} returned invalid output after retry "
                    f"(empty, non-UTF-8, or fewer than {_MIN_OUTPUT_CHARS} characters). "
                    "Check that the model is running: `ollama serve`."
                )

        # Ollama does not return per-token cost; usage is unknown
        token_usage = TokenUsage(
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            cost_confidence="free",
        )
        return LLMResponse(
            content=content,
            usage=token_usage,
            model=model,
            provider=self._provider_name,
        )

    async def _call_once(self, system: str, messages: list[dict], model: str) -> str:
        """Make a single /api/chat request and return the content string."""
        payload = {
            "model": model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        try:
            resp = requests.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            # Ollama response shape: {"message": {"role": "assistant", "content": "..."}}
            content = data.get("message", {}).get("content", "")
            if not isinstance(content, str):
                return ""
            return content
        except (requests.RequestException, json.JSONDecodeError, UnicodeDecodeError):
            return ""

    @staticmethod
    def _valid(content: str) -> bool:
        """Return True if content passes Q9c validation."""
        if not content:
            return False
        try:
            content.encode("utf-8")
        except UnicodeEncodeError:
            return False
        return len(content) >= _MIN_OUTPUT_CHARS

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Always $0 for local Ollama."""
        return 0.0

    @property
    def supports_caching(self) -> bool:
        """Ollama does not support prompt caching."""
        return False
