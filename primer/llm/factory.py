"""LLM provider factory — the ONLY constructor of provider objects used outside primer/llm/.

Security rule 2: all LLM calls go through get_provider(config).
No vendor SDK imports here; those live in the provider modules.
"""
from __future__ import annotations

from primer.config import Settings
from primer.llm.base import LLMProvider


def get_provider(config: Settings) -> LLMProvider:
    """Instantiate and return the configured LLM provider.

    Args:
        config: Loaded Settings instance.

    Returns:
        A concrete LLMProvider for the configured primer_llm_provider.

    Raises:
        ValueError: If the provider name is unknown.
        ConfigError: Propagated if the API key is missing (raised by the provider).
    """
    provider = config.primer_llm_provider.lower()

    if provider == "anthropic":
        from primer.llm.anthropic import AnthropicProvider
        if config.anthropic_api_key is None:
            from primer.errors import ConfigError
            raise ConfigError(
                "Provider 'anthropic' requires ANTHROPIC_API_KEY to be set."
            )
        return AnthropicProvider(
            api_key=config.anthropic_api_key.get_secret_value(),
            model=config.primer_default_model,
        )

    if provider == "ollama":
        from primer.llm.ollama import OllamaProvider
        return OllamaProvider(
            base_url=config.ollama_base_url,
            model=config.ollama_model,
        )

    # POST-MVP providers
    if provider in ("openai", "gemini", "openrouter"):
        raise ValueError(
            f"Provider {provider!r} is Post-MVP and not yet implemented. "
            "Use 'anthropic' or 'ollama'."
        )

    raise ValueError(
        f"Unknown LLM provider: {provider!r}. "
        "Supported providers: anthropic, ollama (openai/gemini/openrouter are Post-MVP)."
    )
