"""OpenRouter provider — Layer-1 PRIMER brain via the OpenRouter API.

OpenRouter is an OpenAI-compatible endpoint aggregating many models.
cost_confidence = "estimated" per Q9b: token counts are returned but PRIMER's
rate card is an approximation (OpenRouter charges vary by model and routing).

No vendor SDK needed — uses requests against the OpenAI-compatible endpoint.
"""
from __future__ import annotations

import json

import requests

from primer.llm.base import LLMProvider, LLMResponse, TokenUsage

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ---------------------------------------------------------------------------
# Approximate pricing (USD per 1M tokens) for common OpenRouter-hosted models.
# OpenRouter marks up slightly; these are approximations.  cost_confidence
# is therefore "estimated" regardless of model.
# ---------------------------------------------------------------------------
_PRICING: dict[str, tuple[float, float]] = {
    "claude-3-5-sonnet":     (3.00,  15.00),
    "claude-3-haiku":        (0.25,   1.25),
    "gpt-4o":                (2.50,  10.00),
    "gpt-4o-mini":           (0.15,   0.60),
    "llama-3.3-70b":         (0.12,   0.30),
    "mistral-7b":            (0.06,   0.06),
    "deepseek-r1":           (0.55,   2.19),
}

_DEFAULT_INPUT_PER_M  = 1.00
_DEFAULT_OUTPUT_PER_M = 3.00


def _price_per_m(model: str) -> tuple[float, float]:
    """Return (input_per_M, output_per_M) for the given model string."""
    m = model.lower()
    for key, prices in _PRICING.items():
        if key in m:
            return prices
    return _DEFAULT_INPUT_PER_M, _DEFAULT_OUTPUT_PER_M


class OpenRouterProvider(LLMProvider):
    """Calls the OpenRouter API using the OpenAI-compatible /chat/completions endpoint.

    Uses requests (no vendor SDK) since OpenRouter exposes a standard REST API.
    cost_confidence = "estimated".
    """

    def __init__(
        self,
        api_key: str,
        model: str = "anthropic/claude-3-haiku",
        base_url: str = _OPENROUTER_BASE_URL,
    ) -> None:
        self._api_key = api_key
        self._default_model = model
        self._base_url = base_url.rstrip("/")
        self._provider_name = "openrouter"

    async def complete(
        self,
        system: str,
        messages: list[dict],
        model: str,
    ) -> LLMResponse:
        """POST to OpenRouter's /chat/completions endpoint.

        Returns LLMResponse with cost_confidence="estimated".
        """
        full_messages = [{"role": "system", "content": system}, *messages]

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/kanwa2006/primer",
            "X-Title": "PRIMER",
        }
        payload = {
            "model": model,
            "messages": full_messages,
            "temperature": 0,
        }

        # OpenRouter is a REST API — use requests synchronously inside async
        # (acceptable for MVP: this is the generation call, not the hot path)
        try:
            resp = requests.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"OpenRouter request failed: {LLMProvider.log_safe(str(exc))}"
            ) from exc

        content = ""
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "") or ""

        usage_data = data.get("usage", {})
        input_tokens  = usage_data.get("prompt_tokens",     0)
        output_tokens = usage_data.get("completion_tokens", 0)

        cost = self.estimate_cost(input_tokens, output_tokens)

        token_usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            cost_confidence="estimated",
        )

        responded_model = data.get("model", model)
        return LLMResponse(
            content=content,
            usage=token_usage,
            model=responded_model,
            provider=self._provider_name,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimated cost in USD using PRIMER's approximate OpenRouter rate card."""
        inp_per_m, out_per_m = _price_per_m(self._default_model)
        return (
            (input_tokens  / 1_000_000) * inp_per_m
            + (output_tokens / 1_000_000) * out_per_m
        )

    @property
    def supports_caching(self) -> bool:
        """OpenRouter does not expose a unified caching API."""
        return False
