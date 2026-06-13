"""Tests for the Gemini eval adapter (registration, lookup, validation).

Scope: adds a second eval agent (gemini) alongside claude_code without
touching runner/scorer/reports/DB/dashboard/Docker. These tests cover only
the adapter contract surface and adapter-driven config validation.
"""
from __future__ import annotations

import pytest

from primer.config import Settings
from primer.errors import ConfigError
from primer.eval.adapters import get_adapter
from primer.eval.adapters.gemini import GeminiAdapter
from primer.eval.agent_adapter import AgentAdapter


class TestRegistration:
    """gemini must be registered without disturbing claude_code."""

    def test_both_agents_present(self):
        import primer.eval.adapters as adapters_mod

        assert "claude_code" in adapters_mod._REGISTRY
        assert "gemini" in adapters_mod._REGISTRY

    def test_lookup_returns_gemini_instance(self):
        adapter = get_adapter("gemini")
        assert isinstance(adapter, GeminiAdapter)
        assert isinstance(adapter, AgentAdapter)

    def test_lookup_is_case_insensitive(self):
        assert isinstance(get_adapter("GEMINI"), GeminiAdapter)

    def test_claude_code_lookup_unchanged(self):
        """Adding gemini must not break the existing claude_code lookup."""
        from primer.eval.adapters.claude_code import ClaudeCodeAdapter

        adapter = get_adapter("claude_code")
        assert isinstance(adapter, ClaudeCodeAdapter)
        assert adapter.adapter_name == "claude_code"
        assert adapter.required_env_key() == "ANTHROPIC_API_KEY"
        assert adapter.context_filename() == "CLAUDE.md"

    def test_unknown_agent_still_rejected(self):
        with pytest.raises(ValueError):
            get_adapter("no_such_agent")


class TestContract:
    """The adapter must satisfy the AgentAdapter contract exactly."""

    def setup_method(self):
        self.adapter = GeminiAdapter()

    def test_adapter_name(self):
        assert self.adapter.adapter_name == "gemini"

    def test_required_env_key(self):
        assert self.adapter.required_env_key() == "GEMINI_API_KEY"

    def test_api_host(self):
        assert self.adapter.api_host() == "generativelanguage.googleapis.com"

    def test_context_filename(self):
        assert self.adapter.context_filename() == "CLAUDE.md"

    def test_build_invocation_is_noninteractive(self):
        from primer.eval.models import Task, TaskMutation

        task = Task(
            id="t1",
            task_type="stub_function",
            prompt="do the thing",
            verify_cmd="pytest",
            mutation=TaskMutation(kind="stub"),
        )
        argv = self.adapter.build_invocation(task)
        assert argv[0] == "gemini"
        assert "do the thing" in argv
        # Non-interactive single-shot prompt flag must be present.
        assert "--prompt" in argv

    def test_parse_telemetry_never_sets_pass_fail(self):
        """AgentTelemetry carries no pass/fail field (AD-4); parsing is safe."""
        tel = self.adapter.parse_telemetry('{"stats": {"usage": '
                                           '{"input_tokens": 10, "output_tokens": 5}}}')
        assert tel.tokens == 15
        assert tel.cost_confidence == "estimated"
        assert tel.agent_error is False

    def test_parse_telemetry_handles_garbage(self):
        tel = self.adapter.parse_telemetry("not json at all")
        assert tel.tokens == 0
        assert tel.agent_error is True


class TestValidation:
    """validate_runtime() must require GEMINI_API_KEY when PRIMER_AGENT=gemini."""

    def test_gemini_agent_accepted_with_key(self, clean_env, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "ollama")  # provider needs no key
        monkeypatch.setenv("PRIMER_AGENT", "gemini")
        monkeypatch.setenv("GEMINI_API_KEY", "gm-test-key")
        Settings().validate_runtime()  # should not raise

    def test_gemini_agent_requires_gemini_key(self, clean_env, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("PRIMER_AGENT", "gemini")
        # GEMINI_API_KEY intentionally not set
        with pytest.raises(ConfigError) as exc_info:
            Settings().validate_runtime()
        assert "GEMINI_API_KEY" in str(exc_info.value)

    def test_missing_gemini_key_error_hides_value(self, clean_env, monkeypatch):
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("PRIMER_AGENT", "gemini")
        with pytest.raises(ConfigError) as exc_info:
            Settings().validate_runtime()
        assert "gm-" not in str(exc_info.value)

    def test_claude_code_validation_unchanged(self, clean_env, monkeypatch):
        """Selecting claude_code must still require ANTHROPIC_API_KEY, not gemini's."""
        monkeypatch.setenv("PRIMER_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("PRIMER_AGENT", "claude_code")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        Settings().validate_runtime()  # should not raise
