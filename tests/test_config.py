"""Tests for primer/config.py — Phase 0 acceptance criteria."""
from __future__ import annotations

import pytest

from primer.config import Settings
from primer.errors import ConfigError
from primer.eval.agent_adapter import AgentAdapter


class TestDefaults:
    def test_llm_provider_default(self, clean_env):
        s = Settings()
        assert s.primer_llm_provider == "anthropic"

    def test_default_model(self, clean_env):
        s = Settings()
        assert s.primer_default_model == "claude-sonnet-4-6"

    def test_eval_timeout_default(self, clean_env):
        """M1: timeout must be 600."""
        s = Settings()
        assert s.primer_eval_timeout_s == 600

    def test_docker_base_image_default(self, clean_env):
        s = Settings()
        assert s.docker_base_image == "python:3.11-slim"

    def test_min_tasks_default(self, clean_env):
        s = Settings()
        assert s.primer_min_tasks == 3

    def test_eval_runs_default(self, clean_env):
        s = Settings()
        assert s.primer_eval_runs == 3

    def test_task_count_default(self, clean_env):
        s = Settings()
        assert s.primer_task_count == 5

    def test_commit_scan_depth_default(self, clean_env):
        s = Settings()
        assert s.primer_commit_scan_depth == 200

    def test_mem_limit_default(self, clean_env):
        s = Settings()
        assert s.primer_eval_mem_limit == "2g"

    def test_ollama_base_url_default(self, clean_env):
        s = Settings()
        assert s.ollama_base_url == "http://localhost:11434"

    def test_ollama_model_default(self, clean_env):
        s = Settings()
        assert s.ollama_model == "llama3.3"

    def test_agent_default(self, clean_env):
        s = Settings()
        assert s.primer_agent == "claude_code"

    def test_agent_api_host_default(self, clean_env):
        s = Settings()
        assert s.primer_agent_api_host == "api.anthropic.com"

    def test_proxy_image_default(self, clean_env):
        s = Settings()
        assert s.proxy_image == "primer-egress-proxy:latest"

    def test_database_url_default(self, clean_env):
        s = Settings()
        assert s.database_url == "sqlite:///primer.db"


class TestDockerClientTimeout:
    """Spec D: docker_client_timeout_s == eval_timeout_s + 30."""

    def test_default_is_630(self, clean_env):
        s = Settings()
        assert s.docker_client_timeout_s == 630

    @pytest.mark.parametrize("timeout,expected", [
        (300, 330),
        (600, 630),
        (120, 150),
        (0, 30),
    ])
    def test_parametrized(self, monkeypatch, timeout, expected):
        monkeypatch.setenv("PRIMER_EVAL_TIMEOUT_S", str(timeout))
        s = Settings()
        assert s.docker_client_timeout_s == expected


class TestValidateRuntime:
    """validate_runtime() must raise ConfigError on missing provider or agent key."""

    def test_passes_with_all_keys(self, env_with_keys):
        s = Settings()
        s.validate_runtime()  # should not raise

    def test_raises_on_missing_provider_key(self, clean_env, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("PRIMER_AGENT", "claude_code")
        # ANTHROPIC_API_KEY intentionally not set
        s = Settings()
        with pytest.raises(ConfigError) as exc_info:
            s.validate_runtime()
        msg = str(exc_info.value)
        assert "ANTHROPIC_API_KEY" in msg
        # Must NOT contain a real key value (there isn't one, but guard the pattern)
        assert "sk-" not in msg

    def test_raises_on_missing_agent_key(self, clean_env, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "ollama")  # ollama needs no provider key
        monkeypatch.setenv("PRIMER_AGENT", "claude_code")
        # ANTHROPIC_API_KEY not set — should still fail for the agent
        s = Settings()
        with pytest.raises(ConfigError) as exc_info:
            s.validate_runtime()
        assert "ANTHROPIC_API_KEY" in str(exc_info.value)

    def test_raises_on_unknown_provider(self, clean_env, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "badprovider")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("PRIMER_AGENT", "claude_code")
        s = Settings()
        with pytest.raises(ConfigError):
            s.validate_runtime()

    def test_raises_on_unknown_agent(self, clean_env, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("PRIMER_AGENT", "bad_agent")
        s = Settings()
        with pytest.raises(ConfigError):
            s.validate_runtime()

    def test_ollama_provider_no_key_required(self, clean_env, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("PRIMER_AGENT", "claude_code")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        s = Settings()
        s.validate_runtime()  # ollama doesn't need its own key


class _FakeAdapter(AgentAdapter):
    """Minimal test-double adapter: declares an env key (or None) for validation.

    Only required_env_key() matters here; the other members satisfy the ABC.
    Production gemini/openai/ollama eval adapters are POST-MVP (spec M8), so we
    prove provider-agnostic validation with test doubles rather than shipping them.
    """

    def __init__(self, name: str, env_key: str | None):
        self._name = name
        self._env_key = env_key

    @property
    def adapter_name(self) -> str:
        return self._name

    def required_env_key(self) -> str | None:
        return self._env_key

    def api_host(self) -> str:
        return "example.invalid"

    def context_filename(self) -> str:
        return "AGENTS.md"

    def build_invocation(self, task):  # pragma: no cover - never called in validation
        raise NotImplementedError

    def parse_telemetry(self, raw_log):  # pragma: no cover - never called in validation
        raise NotImplementedError


def _register_fake(monkeypatch, name: str, env_key: str | None) -> None:
    """Register a fake adapter class in the live registry for the test's duration."""
    import primer.eval.adapters as adapters_mod

    def _factory(_n=name, _k=env_key):
        return _FakeAdapter(_n, _k)

    patched = dict(adapters_mod._REGISTRY)
    patched[name] = _factory
    monkeypatch.setattr(adapters_mod, "_REGISTRY", patched)


class TestAdapterDrivenValidation:
    """validate_runtime() resolves the agent's required key from its adapter,
    not from a hardcoded Anthropic map — PRIMER works with any configured agent.
    """

    def test_claude_adapter_requires_anthropic_key(self, clean_env, monkeypatch):
        """The real claude_code adapter declares ANTHROPIC_API_KEY."""
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "ollama")  # provider needs no key
        monkeypatch.setenv("PRIMER_AGENT", "claude_code")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        Settings().validate_runtime()  # should not raise

    def test_gemini_adapter_requires_gemini_key(self, clean_env, monkeypatch):
        _register_fake(monkeypatch, "gemini", "GEMINI_API_KEY")
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("PRIMER_AGENT", "gemini")
        # GEMINI_API_KEY missing → must fail naming that exact var
        with pytest.raises(ConfigError) as exc_info:
            Settings().validate_runtime()
        assert "GEMINI_API_KEY" in str(exc_info.value)

        monkeypatch.setenv("GEMINI_API_KEY", "gm-test-key")
        Settings().validate_runtime()  # now passes

    def test_openai_adapter_requires_openai_key(self, clean_env, monkeypatch):
        _register_fake(monkeypatch, "codex", "OPENAI_API_KEY")
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("PRIMER_AGENT", "codex")
        with pytest.raises(ConfigError) as exc_info:
            Settings().validate_runtime()
        assert "OPENAI_API_KEY" in str(exc_info.value)

        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        Settings().validate_runtime()  # now passes

    def test_keyless_adapter_requires_no_key(self, clean_env, monkeypatch):
        """An adapter declaring no key (e.g. a local/offline agent) needs nothing."""
        _register_fake(monkeypatch, "local_agent", None)
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("PRIMER_AGENT", "local_agent")
        # No agent key set anywhere — must still pass.
        Settings().validate_runtime()

    def test_unknown_adapter_rejected(self, clean_env, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("PRIMER_AGENT", "no_such_agent")
        with pytest.raises(ConfigError) as exc_info:
            Settings().validate_runtime()
        assert "no_such_agent" in str(exc_info.value)


class TestValidateGenerationRuntime:
    """validate_generation_runtime() validates ONLY the LLM provider, never the agent."""

    def test_passes_with_provider_key_only(self, clean_env, monkeypatch):
        """init must work with a provider key even when the agent key is absent."""
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "gemini")
        monkeypatch.setenv("GEMINI_API_KEY", "gm-test-key")
        # ANTHROPIC_API_KEY (the agent key) intentionally not set
        s = Settings()
        s.validate_generation_runtime()  # should not raise

    def test_does_not_validate_agent(self, clean_env, monkeypatch):
        """Even an unknown agent must not cause generation validation to fail."""
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "ollama")  # no provider key needed
        monkeypatch.setenv("PRIMER_AGENT", "bad_agent")
        s = Settings()
        s.validate_generation_runtime()  # should not raise

    def test_raises_on_missing_provider_key(self, clean_env, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "gemini")
        # GEMINI_API_KEY intentionally not set
        s = Settings()
        with pytest.raises(ConfigError) as exc_info:
            s.validate_generation_runtime()
        assert "GEMINI_API_KEY" in str(exc_info.value)

    def test_raises_on_unknown_provider(self, clean_env, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "badprovider")
        s = Settings()
        with pytest.raises(ConfigError):
            s.validate_generation_runtime()

    def test_ollama_no_key_required(self, clean_env, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "ollama")
        s = Settings()
        s.validate_generation_runtime()  # no key required


class TestSecretRedaction:
    """API key values must never appear in repr, str, or ConfigError messages (SecretStr)."""

    def test_repr_does_not_expose_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-supersecret-value-12345")
        s = Settings()
        rep = repr(s)
        assert "sk-ant-supersecret-value-12345" not in rep

    def test_str_does_not_expose_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-supersecret-value-12345")
        s = Settings()
        assert "sk-ant-supersecret-value-12345" not in str(s)

    def test_config_error_does_not_expose_key(self, clean_env, monkeypatch):
        """Even if a key happens to be present, errors must not echo it."""
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-supersecret-openai-key")
        monkeypatch.setenv("PRIMER_AGENT", "bad_agent")
        s = Settings()
        with pytest.raises(ConfigError) as exc_info:
            s.validate_runtime()
        assert "sk-supersecret-openai-key" not in str(exc_info.value)
