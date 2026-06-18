"""LLM provider ABC and shared data models.

This is the ONLY module in PRIMER where vendor SDK imports are permitted.
log_safe() MUST be used before any log write that touches LLM output or keys.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal


# Patterns for secrets that must never appear in logs
_REDACT_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9\-_]+"),   # Anthropic keys
    re.compile(r"sk-[A-Za-z0-9\-_]+"),        # OpenAI-style keys
    re.compile(r"AIza[A-Za-z0-9\-_]+"),       # Google/Gemini keys
]


@dataclass
class TokenUsage:
    """Token accounting for one LLM call.

    Two cache fields are included for completeness; the generated file is typically
    below the minimum token threshold for prompt caching.
    cost_usd is NEVER rendered without consulting cost_confidence.
    """
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cost_usd: float = 0.0
    cost_confidence: Literal["exact", "estimated", "free"] = "estimated"


@dataclass
class LLMResponse:
    """Structured response from a single LLM call."""
    content: str
    usage: TokenUsage
    model: str
    provider: str


class LLMProvider(ABC):
    """Abstract base for all LLM providers.

    Concrete implementations live in this package (primer/llm/) ONLY.
    All other PRIMER modules obtain a provider via get_provider(config).
    """

    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[dict],
        model: str,
    ) -> LLMResponse:
        """Send a completion request and return a structured response.

        Args:
            system: System prompt text.
            messages: List of {"role": "user"|"assistant", "content": str} dicts.
            model: Model identifier string.

        Returns:
            LLMResponse with content, usage, model, and provider fields populated.
        """

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Return a cost estimate in USD for the given token counts."""

    @property
    @abstractmethod
    def supports_caching(self) -> bool:
        """True if this provider supports prompt caching."""

    @staticmethod
    def log_safe(text: str) -> str:
        """Redact known secret patterns before any log write.

        Replaces sk-…, sk-ant-…, AIza… patterns with '[REDACTED]'.
        Must be called before writing any LLM output, raw log, or error message
        that may contain key material.
        """
        result = text
        for pattern in _REDACT_PATTERNS:
            result = pattern.sub("[REDACTED]", result)
        return result
