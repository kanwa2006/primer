"""Adapter registry: name → AgentAdapter instance."""
from __future__ import annotations

from primer.eval.adapters.claude_code import ClaudeCodeAdapter

_REGISTRY: dict[str, type] = {
    "claude_code": ClaudeCodeAdapter,
}


def get_adapter(name: str):
    """Return an AgentAdapter instance for the given name.

    Raises ValueError for unknown adapter names.
    """
    cls = _REGISTRY.get(name.lower())
    if cls is None:
        known = sorted(_REGISTRY)
        raise ValueError(
            f"Unknown agent adapter: {name!r}. Known adapters: {known}"
        )
    return cls()
