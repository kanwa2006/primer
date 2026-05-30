"""AgentAdapter ABC (AD-3, AD-4).

Thin adapters supply:
  - required_env_key()   → the single env var injected in-container
  - api_host()           → egress allowlist target for the proxy
  - context_filename()   → file the agent reads from CWD (CLAUDE.md for ClaudeCode)
  - build_invocation()   → in-container argv (identical both arms — AD-4)
  - parse_telemetry()    → tokens/cost/agent_error — NO pass/fail (AD-4)

All Docker/network/timeout/cleanup logic is in runner.py (fat runner — AD-3).
Adapters MUST NOT import docker, open sockets, or decide pass/fail.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from primer.eval.models import AgentTelemetry, Task


class AgentAdapter(ABC):
    """Abstract base for all eval agent adapters.

    Contract (AD-3, AD-4):
    - Adapters are THIN: no docker import, no sockets, no pass/fail decision.
    - build_invocation() returns identical argv for both arms.
    - parse_telemetry() extracts cost/token info; never sets passed.
    - context_filename() is the file runner writes (WITH) or omits (WITHOUT).
    """

    @property
    @abstractmethod
    def adapter_name(self) -> str:
        """Short name identifying this adapter (e.g. 'claude_code')."""

    @abstractmethod
    def required_env_key(self) -> str:
        """The single environment variable injected into the eval container.

        Only this one key is passed via --env. PRIMER's other keys are never
        injected (Q10 / Spec B step 5).
        """

    @abstractmethod
    def api_host(self) -> str:
        """Hostname the egress proxy allowlists (e.g. 'api.anthropic.com').

        This makes the proxy allowlist per-adapter — swapping to a different
        agent re-points the proxy automatically (AD-3).
        """

    @abstractmethod
    def context_filename(self) -> str:
        """Filename the agent reads from CWD (e.g. 'CLAUDE.md').

        runner.py writes this file (with_context=True) or guarantees it
        does not exist (with_context=False). Flags are identical both arms;
        only the file presence differs (M4, Spec B step 8).
        """

    @abstractmethod
    def build_invocation(self, task: "Task") -> list[str]:
        """Return the in-container command-line argv to run the agent headlessly.

        Contract:
        - Non-interactive; must not prompt for user input.
        - IDENTICAL for with_context=True and with_context=False arms (AD-4).
        - Writes nothing outside /work (the mounted temp dir).
        - Raises AgentNotFoundError if the CLI is absent from the image.
        """

    @abstractmethod
    def parse_telemetry(self, raw_log: str) -> "AgentTelemetry":
        """Parse tokens, cost, duration, and error state from the agent's log output.

        Contract (AD-4):
        - MUST NOT set or infer pass/fail. That is determined by verify_cmd exit code.
        - raw_log has already been redacted by runner.py before this call.
        - Returns AgentTelemetry with sensible defaults if parsing fails.
        """
