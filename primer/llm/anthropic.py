"""Anthropic provider — the default Layer-1 PRIMER brain.

cost_confidence = "exact" (Anthropic returns exact token counts).
Vendor SDK import is permitted here (security rule 2).
"""
from __future__ import annotations

import anthropic as _anthropic

from primer.llm.base import LLMProvider, LLMResponse, TokenUsage

# Pricing per million tokens (as of claude-sonnet-4-6; update if model changes).
# Input: $3.00/M, Output: $15.00/M.
_SONNET_INPUT_PER_M = 3.00
_SONNET_OUTPUT_PER_M = 15.00


def _price_per_m(model: str) -> tuple[float, float]:
    """Return (input_per_M, output_per_M) USD for the given model."""
    m = model.lower()
    if "opus" in m:
        return 15.00, 75.00
    if "haiku" in m:
        return 0.80, 4.00
    # Default: Sonnet pricing
    return _SONNET_INPUT_PER_M, _SONNET_OUTPUT_PER_M


class AnthropicProvider(LLMProvider):
    """Calls the Anthropic Messages API.

    Initialized from the api_key SecretStr; never stores the raw key in logs.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self._client = _anthropic.AsyncAnthropic(api_key=api_key)
        self._default_model = model
        self._provider_name = "anthropic"

    async def complete(
        self,
        system: str,
        messages: list[dict],
        model: str,
    ) -> LLMResponse:
        """Call the Anthropic Messages API at temperature=0.

        Returns an LLMResponse with cost_confidence="exact".
        """
        response = await self._client.messages.create(
            model=model,
            max_tokens=1024,
            temperature=0,
            system=system,
            messages=messages,
        )

        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        usage = response.usage
        input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0)
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0)
        cache_read = getattr(usage, "cache_read_input_tokens", 0)

        cost = self.estimate_cost(input_tokens, output_tokens)

        token_usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=cache_creation,
            cache_read_input_tokens=cache_read,
            cost_usd=cost,
            cost_confidence="exact",
        )

        return LLMResponse(
            content=content,
            usage=token_usage,
            model=response.model,
            provider=self._provider_name,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Exact cost in USD based on public Anthropic token pricing."""
        inp_per_m, out_per_m = _price_per_m(self._default_model)
        return (input_tokens / 1_000_000) * inp_per_m + (output_tokens / 1_000_000) * out_per_m

    @property
    def supports_caching(self) -> bool:
        """Anthropic supports prompt caching (dormant in MVP — file is < 1,024 tokens)."""
        return True
