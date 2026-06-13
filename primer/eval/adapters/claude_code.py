"""ClaudeCodeAdapter — MVP default eval agent adapter.

Invocation: claude -p "<prompt>" --output-format json --permission-mode bypassPermissions
  - No --bare (M4): file presence/absence is controlled solely by the filesystem.
  - Launched with cwd=/work so Claude Code reads CLAUDE.md from there natively.
  - Identical flags for both with_context and without_context arms (AD-4).

Telemetry parsing:
  - Reads total_cost_usd (fallback: cost_usd) → cost_confidence="exact"
  - Reads usage.input_tokens + usage.output_tokens for token count
  - Reads num_turns for iterations
  - Reads is_error for agent_error

Committed context-file handling (C3):
  - If the repo already has a committed CLAUDE.md, evaluation continues normally.
  - WITHOUT arm: the committed file is removed from the clone before the container runs.
  - WITH arm: the committed file is overwritten with the PRIMER-generated content.
  - runner.run_task() emits a warning when a committed file is detected in the clone.
"""
from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from primer.errors import AgentNotFoundError
from primer.eval.agent_adapter import AgentAdapter
from primer.eval.models import AgentTelemetry

if TYPE_CHECKING:
    from primer.eval.models import Task

log = logging.getLogger(__name__)

# ⚠️ [EMPIRICAL VERIFICATION REQUIRED] — see 16_BLK2_SPECIFICATION.md §4.4
# FINGERPRINT_INSTRUCTION is a provisional candidate. It must be verified against a
# live Claude Code run before the gate is considered operative. Replace this text with
# the confirmed wording after completing the verification procedure.
FINGERPRINT_INSTRUCTION = (
    'PRIMER_FINGERPRINT_V1: Before starting the task, output '
    '"primer_fingerprint_v1_acknowledged" as the first line of your response.'
)
FINGERPRINT_MARKER = "primer_fingerprint_v1_acknowledged"


class ClaudeCodeAdapter(AgentAdapter):
    """Adapter for the Claude Code CLI (headless)."""

    @property
    def adapter_name(self) -> str:
        return "claude_code"

    def required_env_key(self) -> str:
        return "ANTHROPIC_API_KEY"

    def api_host(self) -> str:
        return "api.anthropic.com"

    def context_filename(self) -> str:
        # M7: ClaudeCodeAdapter uses CLAUDE.md (what Claude Code reads from CWD)
        return "CLAUDE.md"

    def build_invocation(self, task: "Task") -> list[str]:
        """Return the headless Claude Code invocation argv.

        No --bare (M4). Flags identical both arms (AD-4).
        The prompt is passed via -p / --print flag.

        Permission configuration (runtime compatibility fix):
          --permission-mode dontAsk   makes the session fully non-interactive:
                                      tools not in the allowedTools list are
                                      silently denied rather than prompting,
                                      preventing container hangs.
          --allowedTools Bash,Edit,MultiEdit,Write,Read
                                      pre-authorises the exact tool set needed
                                      for eval tasks (file reads, edits, writes,
                                      bash for self-verification). Equivalent to
                                      bypassPermissions for these tools; root-
                                      compatible (bypassPermissions is blocked
                                      under root in Claude Code 2.1.x+).
        """
        return [
            "claude",
            "--print",
            task.prompt,
            "--output-format", "json",
            "--permission-mode", "dontAsk",
            "--allowedTools", "Bash,Edit,MultiEdit,Write,Read",
        ]

    def image_layers(self) -> list[str]:
        """Dockerfile instructions to provision the Claude Code CLI in the eval image.

        Uses Anthropic's official signed apt repository (Node-free path).
        The apt package installs a standalone native binary to /usr/bin/claude,
        which is on the default PATH for the container's sh -c invocation.

        Installation approach (from External Verification / BLK-1):
          - Targets the 'stable' channel (~1 week behind latest) for reproducibility.
          - Does NOT use npm: python:3.11-slim has a documented apt/npm defect.
          - Does NOT use the native curl installer: it targets ~/.local/bin which
            is not on the default PATH for a non-login container shell.
          - Disables DISABLE_AUTOUPDATER: eval containers run on an internal-only
            network; an update check would be blocked by the egress proxy and
            would add latency or noise to the eval run.

        Prerequisites (curl, ca-certificates, gnupg) are not present in
        python:3.11-slim and must be installed before the apt key can be added.
        Source: https://code.claude.com/docs/en/setup
        """
        return [
            # Install prerequisites absent from python:3.11-slim (Debian Bookworm slim)
            (
                "RUN apt-get update "
                "&& apt-get install -y --no-install-recommends curl ca-certificates gnupg "
                "&& rm -rf /var/lib/apt/lists/*"
            ),
            # Add Anthropic's signed apt repo (stable channel) and install claude-code
            (
                "RUN install -d -m 0755 /etc/apt/keyrings "
                "&& curl -fsSL https://downloads.claude.ai/keys/claude-code.asc "
                "-o /etc/apt/keyrings/claude-code.asc "
                '&& echo "deb [signed-by=/etc/apt/keyrings/claude-code.asc] '
                'https://downloads.claude.ai/claude-code/apt/stable stable main" '
                "> /etc/apt/sources.list.d/claude-code.list "
                "&& apt-get update "
                "&& apt-get install -y --no-install-recommends claude-code "
                "&& apt-get clean "
                "&& rm -rf /var/lib/apt/lists/*"
            ),
            # Disable background auto-updater: eval containers use an internal-only
            # network where update checks are blocked by the egress proxy.
            "ENV DISABLE_AUTOUPDATER=1",
        ]

    def fingerprint_instruction(self) -> str | None:
        """Return the M4 fingerprint directive to append to CLAUDE.md in the WITH arm.

        ⚠️ [EMPIRICAL VERIFICATION REQUIRED] — the text is provisional.
        See 16_BLK2_SPECIFICATION.md §4 and §4.4 for verification procedure.
        """
        return FINGERPRINT_INSTRUCTION

    def check_fingerprint(self, raw_log: str, with_context: bool) -> bool | None:
        """Search raw_log for FINGERPRINT_MARKER (M4 Probe A / Probe C gate).

        WITH arm: returns True if marker found, False otherwise.
        WITHOUT arm: returns None (gate not applicable for this arm).
        Must not raise.
        """
        if not with_context:
            return None
        try:
            return FINGERPRINT_MARKER in raw_log
        except Exception:
            return None

    def parse_telemetry(self, raw_log: str) -> AgentTelemetry:
        """Parse Claude Code JSON output for token/cost telemetry.

        Does NOT infer pass/fail (AD-4). If parsing fails, returns safe defaults.
        raw_log has already been redacted by runner.py.
        """
        tokens = 0
        iterations = 0
        duration_s = 0.0
        cost_usd = 0.0
        agent_error = False

        # Claude Code may emit multiple JSON objects (stream-json) or one (json).
        # We look for the last complete JSON object in the log.
        json_obj = _extract_last_json(raw_log)
        if json_obj is not None:
            try:
                # Cost: total_cost_usd preferred, fallback to cost_usd
                cost_usd = float(
                    json_obj.get("total_cost_usd")
                    or json_obj.get("cost_usd")
                    or 0.0
                )

                # Token usage
                usage = json_obj.get("usage", {}) or {}
                tokens = int(
                    usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                )

                # Iterations / turns
                iterations = int(json_obj.get("num_turns", 0) or 0)

                # Duration
                duration_ms = json_obj.get("duration_ms", 0) or 0
                duration_s = float(duration_ms) / 1000.0

                # Error flag
                agent_error = bool(json_obj.get("is_error", False))

            except (TypeError, ValueError, KeyError) as exc:
                log.debug("telemetry parse error: %s", exc)
                agent_error = True
        else:
            log.debug("no JSON found in agent log — using zero telemetry")
            agent_error = True

        return AgentTelemetry(
            tokens=tokens,
            iterations=iterations,
            duration_s=duration_s,
            cost_usd=cost_usd,
            cost_confidence="exact",  # Anthropic billing is exact (Q9b)
            agent_error=agent_error,
            raw_log=raw_log,          # already redacted by runner
        )


def _extract_last_json(text: str) -> dict | None:
    """Try to extract the last complete JSON object from text."""
    # Find all {...} blocks (non-greedy won't work; use rfind for last brace)
    # Look for lines that parse as JSON objects
    candidates = []
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    candidates.append(obj)
                    break
            except json.JSONDecodeError:
                pass

    # If no single-line JSON, try parsing entire text
    if not candidates:
        try:
            obj = json.loads(text.strip())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    return candidates[0] if candidates else None
