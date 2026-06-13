"""PRIMER runtime configuration (single source of truth).

All PRIMER_* and *_API_KEY variables are read from environment / .env.
Never hardcode values outside this module.
"""
from __future__ import annotations

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

from primer.errors import ConfigError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Layer-1 provider (PRIMER's brain) ────────────────────────────────────
    primer_llm_provider: str = "anthropic"
    primer_default_model: str = "claude-sonnet-4-6"

    # API keys stored as SecretStr so they never appear in repr/str/logs
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None

    # Ollama (local; $0 generation)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.3"

    # ── Layer-2 agent (eval agent inside Docker) ─────────────────────────────
    primer_agent: str = "claude_code"
    primer_agent_api_host: str = "api.anthropic.com"

    # ── Eval knobs ───────────────────────────────────────────────────────────
    primer_task_count: int = 5
    primer_min_tasks: int = 3
    primer_eval_runs: int = 3
    primer_eval_timeout_s: int = 600          # M1: was 300, raised to 600
    primer_commit_scan_depth: int = 200
    primer_eval_mem_limit: str = "2g"

    # ── Infra ────────────────────────────────────────────────────────────────
    docker_base_image: str = "python:3.11-slim"   # readable tag; resolved to digest at eval (M5)
    proxy_image: str = "primer-egress-proxy:latest"
    database_url: str = "sqlite:///primer.db"

    # ── Derived properties ───────────────────────────────────────────────────
    @property
    def docker_client_timeout_s(self) -> int:
        """Docker HTTP read timeout: must exceed eval timeout (Spec D)."""
        return self.primer_eval_timeout_s + 30

    def validate_generation_runtime(self) -> None:
        """Raise ConfigError if the selected LLM provider key is missing.

        Validates ONLY the generation provider (Layer-1 brain) — used by
        `primer init`, which never touches the eval agent. Does not validate
        `primer_agent`. Never logs or includes key values in error messages.
        """
        provider = self.primer_llm_provider.lower()
        provider_key_map: dict[str, SecretStr | None] = {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "gemini": self.gemini_api_key,
            "openrouter": self.openrouter_api_key,
            "ollama": None,  # no key required
        }

        if provider not in provider_key_map:
            raise ConfigError(
                f"Unknown LLM provider: {provider!r}. "
                f"Supported: {sorted(provider_key_map)}"
            )

        if provider != "ollama":
            key = provider_key_map[provider]
            if key is None:
                env_var = f"{provider.upper()}_API_KEY"
                raise ConfigError(
                    f"Provider {provider!r} requires {env_var} to be set. "
                    f"Add it to .env (see .env.example)."
                )

    def validate_runtime(self) -> None:
        """Raise ConfigError if the selected provider or agent key is missing.

        Never logs or includes key values in error messages.
        """
        provider = self.primer_llm_provider.lower()
        provider_key_map: dict[str, SecretStr | None] = {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "gemini": self.gemini_api_key,
            "openrouter": self.openrouter_api_key,
            "ollama": None,  # no key required
        }

        if provider not in provider_key_map:
            raise ConfigError(
                f"Unknown LLM provider: {provider!r}. "
                f"Supported: {sorted(provider_key_map)}"
            )

        if provider != "ollama":
            key = provider_key_map[provider]
            if key is None:
                env_var = f"{provider.upper()}_API_KEY"
                raise ConfigError(
                    f"Provider {provider!r} requires {env_var} to be set. "
                    f"Add it to .env (see .env.example)."
                )

        # Resolve the eval agent's required key from its adapter (Phase 3:
        # replaces the static map). Each adapter declares its own requirement
        # via required_env_key(); a None return means the agent needs no key
        # (e.g. a local/offline agent). PRIMER is therefore not Anthropic-only —
        # selecting a different agent re-points validation automatically.
        from primer.eval.adapters import get_adapter

        agent = self.primer_agent.lower()
        try:
            adapter = get_adapter(agent)
        except ValueError as exc:
            # Registry already produces a key-free "Unknown agent adapter" message.
            raise ConfigError(str(exc)) from exc

        required_env = adapter.required_env_key()
        if required_env:
            agent_key: SecretStr | None = getattr(self, required_env.lower(), None)
            if agent_key is None:
                raise ConfigError(
                    f"Agent {agent!r} requires {required_env} to be set. "
                    f"Add it to .env (see .env.example)."
                )
