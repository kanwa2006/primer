"""AgentAdapter ABC.

Thin adapters supply:
  - required_env_key()   → the single env var injected in-container
  - api_host()           → egress allowlist target for the proxy
  - context_filename()   → file the agent reads from CWD (CLAUDE.md for ClaudeCode)
  - build_invocation()   → in-container argv (identical both arms)
  - parse_telemetry()    → tokens/cost/agent_error — NO pass/fail

All Docker/network/timeout/cleanup logic is in runner.py (fat runner).
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
    def required_env_key(self) -> str | None:
        """The single environment variable injected into the eval container.

        Only this one key is passed via --env. PRIMER's other keys are never
        injected (Q10 / Spec B step 5). Return None for an agent that needs no
        key (e.g. a local/offline agent); config validation then skips the
        agent-key check for that adapter.
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

    def image_layers(self) -> list[str]:
        """Return Dockerfile instruction strings required to install this agent's CLI.

        Each string is appended as a Dockerfile instruction line to the eval image
        Dockerfile during the build phase (AD-2). Lines are typically RUN or ENV
        instructions. The build phase runs with host networking so external package
        repositories are reachable; the eval run step does not.

        The default returns no layers — adapters whose CLI is already present in the
        base image need not override this method. Adapters that must provision a CLI
        (e.g. ClaudeCodeAdapter) return the required installation instructions here.
        """
        return []

    def fingerprint_instruction(self) -> str | None:
        """Return the instruction text to append to the context file for the WITH arm.

        The runner appends the returned string (on its own line) to context_content
        before writing context_file_path. Returns None if the adapter does not
        participate in the fingerprint gate (BLK-2 / M4).

        The ClaudeCodeAdapter override returns the full directive text. Adapters that
        do not override this method are exempt from the harness-validity gate.
        """
        return None

    def check_fingerprint(self, raw_log: str, with_context: bool) -> bool | None:
        """Check whether the agent acknowledged the fingerprint instruction (M4 gate).

        Args:
            raw_log: the already-redacted agent log string from LLMProvider.log_safe().
            with_context: True for the WITH arm; False for the WITHOUT arm.

        Returns:
            True  — WITH arm; marker found; harness valid for this run.
            False — WITH arm; marker absent; harness failure; scorer must abort.
            None  — WITHOUT arm (gate not applicable), OR adapter does not participate.

        Must not raise. The default implementation always returns None.
        """
        return None
