"""OpenAI provider — Layer-1 PRIMER brain for OpenAI-hosted models.

cost_confidence = "estimated" (token counts are exact from the API, but cost
depends on the model's rate card which PRIMER hard-codes and may lag updates).
Per Q9b: openai = "estimated→exact"; PRIMER ships as "estimated" to be honest.

Vendor SDK import (openai) is permitted here per security rule 2.
"""
from __future__ import annotations

import openai as _openai

from primer.llm.base import LLMProvider, LLMResponse, TokenUsage

# ---------------------------------------------------------------------------
# Model pricing (USD per 1M tokens).  Update when OpenAI changes rates.
# Source: https://openai.com/pricing  (checked 2026-05)
# ---------------------------------------------------------------------------
_PRICING: dict[str, tuple[float, float]] = {
    # (input_per_M, output_per_M)
    "gpt-4o":              (2.50,  10.00),
    "gpt-4o-mini":         (0.15,   0.60),
    "gpt-4-turbo":        (10.00,  30.00),
    "gpt-4":              (30.00,  60.00),
    "gpt-3.5-turbo":       (0.50,   1.50),
    "o1":                 (15.00,  60.00),
    "o1-mini":             (3.00,  12.00),
    "o3-mini":             (1.10,   4.40),
}

_DEFAULT_INPUT_PER_M  = 2.50   # fallback: gpt-4o pricing
_DEFAULT_OUTPUT_PER_M = 10.00


def _price_per_m(model: str) -> tuple[float, float]:
    """Return (input_per_M, output_per_M) for the given model string.

    Matches longest key first to avoid "gpt-4o" shadowing "gpt-4o-mini".
    """
    m = model.lower()
    for key in sorted(_PRICING, key=len, reverse=True):
        if key in m:
            return _PRICING[key]
    return _DEFAULT_INPUT_PER_M, _DEFAULT_OUTPUT_PER_M


class OpenAIProvider(LLMProvider):
    """Calls the OpenAI Chat Completions API via the official openai SDK.

    cost_confidence is "estimated" because PRIMER hard-codes the rate card.
    Token counts themselves are exact (returned by the API).
    """

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self._client = _openai.AsyncOpenAI(api_key=api_key)
        self._default_model = model
        self._provider_name = "openai"

    async def complete(
        self,
        system: str,
        messages: list[dict],
        model: str,
    ) -> LLMResponse:
        """Call the OpenAI Chat Completions API at temperature=0.

        Returns LLMResponse with cost_confidence="estimated".
        Token counts come directly from response.usage.
        """
        full_messages = [{"role": "system", "content": system}, *messages]

        response = await self._client.chat.completions.create(
            model=model,
            messages=full_messages,  # type: ignore[arg-type]
            temperature=0,
        )

        content = ""
        if response.choices:
            msg = response.choices[0].message
            if msg.content:
                content = msg.content

        usage = response.usage
        input_tokens  = usage.prompt_tokens     if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        cost = self.estimate_cost(input_tokens, output_tokens)

        token_usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            cost_confidence="estimated",
        )

        return LLMResponse(
            content=content,
            usage=token_usage,
            model=response.model,
            provider=self._provider_name,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimated cost in USD based on PRIMER's hard-coded rate card."""
        inp_per_m, out_per_m = _price_per_m(self._default_model)
        return (
            (input_tokens  / 1_000_000) * inp_per_m
            + (output_tokens / 1_000_000) * out_per_m
        )

    @property
    def supports_caching(self) -> bool:
        """OpenAI supports prompt caching for eligible models (dormant in MVP)."""
        return False
