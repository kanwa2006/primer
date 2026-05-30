"""Gemini provider — Layer-1 PRIMER brain for Google Gemini models.

cost_confidence = "exact" per Q9b (Gemini returns exact token counts and
PRIMER uses Google's published per-token rate card).

Uses the current google-genai SDK (google.genai.Client).
Vendor SDK import (google.genai) is permitted here per security rule 2.
"""
from __future__ import annotations

import google.genai as genai
import google.genai.types as genai_types

from primer.llm.base import LLMProvider, LLMResponse, TokenUsage

# ---------------------------------------------------------------------------
# Model pricing (USD per 1M tokens).  Source: https://ai.google.dev/pricing
# (checked 2026-05; <=128K context window pricing)
# ---------------------------------------------------------------------------
_PRICING: dict[str, tuple[float, float]] = {
    # (input_per_M, output_per_M)
    "gemini-2.0-flash":         (0.10,  0.40),
    "gemini-2.0-flash-lite":    (0.075, 0.30),
    "gemini-1.5-flash":         (0.075, 0.30),
    "gemini-1.5-flash-8b":      (0.0375, 0.15),
    "gemini-1.5-pro":           (1.25,  5.00),
    "gemini-1.0-pro":           (0.50,  1.50),
}

_DEFAULT_INPUT_PER_M  = 0.075   # fallback: gemini-1.5-flash pricing
_DEFAULT_OUTPUT_PER_M = 0.30


def _price_per_m(model: str) -> tuple[float, float]:
    """Return (input_per_M, output_per_M) for the given model string."""
    m = model.lower()
    for key, prices in _PRICING.items():
        if key in m:
            return prices
    return _DEFAULT_INPUT_PER_M, _DEFAULT_OUTPUT_PER_M


class GeminiProvider(LLMProvider):
    """Calls the Google Gemini API via the google-genai SDK (google.genai.Client).

    cost_confidence = "exact": Gemini returns prompt_token_count and
    candidates_token_count directly; PRIMER applies the published rate card.
    """

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._default_model = model
        self._provider_name = "gemini"

    async def complete(
        self,
        system: str,
        messages: list[dict],
        model: str,
    ) -> LLMResponse:
        """Call Gemini via client.aio.models.generate_content at temperature=0.

        Returns LLMResponse with cost_confidence="exact".
        """
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            max_output_tokens=1024,
        )

        # Build contents list from messages
        contents: list[genai_types.Content] = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                genai_types.Content(
                    role=role,
                    parts=[genai_types.Part(text=msg["content"])],
                )
            )

        response: genai_types.GenerateContentResponse = (
            await self._client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        )

        # Extract text content
        content = ""
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.text:
                        content += part.text

        # Extract token usage from usage_metadata
        meta = response.usage_metadata
        input_tokens  = (meta.prompt_token_count     or 0) if meta else 0
        output_tokens = (meta.candidates_token_count or 0) if meta else 0

        cost = self.estimate_cost(input_tokens, output_tokens)

        token_usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            cost_confidence="exact",
        )

        return LLMResponse(
            content=content,
            usage=token_usage,
            model=model,
            provider=self._provider_name,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Exact cost in USD based on Google's published token rate card."""
        inp_per_m, out_per_m = _price_per_m(self._default_model)
        return (
            (input_tokens  / 1_000_000) * inp_per_m
            + (output_tokens / 1_000_000) * out_per_m
        )

    @property
    def supports_caching(self) -> bool:
        """Gemini supports context caching (dormant in MVP)."""
        return False
