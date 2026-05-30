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

Eligibility guard:
  - If the repo already has a committed CLAUDE.md, eval is out of MVP scope.
  - That is the developer-file experiment; PRIMER only measures its own generated file.
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

# The unique instruction planted in the context file for the M4 harness-validity gate.
# If the WITH arm does not produce this fingerprint, the harness is broken.
FINGERPRINT_INSTRUCTION = "PRIMER_FINGERPRINT_V1"
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
        """
        return [
            "claude",
            "--print",
            task.prompt,
            "--output-format", "json",
            "--permission-mode", "bypassPermissions",
        ]

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
