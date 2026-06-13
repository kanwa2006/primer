"""GeminiAdapter — eval agent adapter for the Gemini CLI (headless).

Follows the same AgentAdapter contract as ClaudeCodeAdapter (AD-3, AD-4):
  - Thin: no docker import, no sockets, no pass/fail decision.
  - build_invocation() returns identical argv for both with/without arms (AD-4).
  - parse_telemetry() extracts tokens/cost/error; never sets passed (AD-4).

Invocation: gemini --prompt "<prompt>" --output-format json --yolo
  - Non-interactive (--prompt runs once and exits); --yolo auto-approves actions.
  - Launched with cwd=/work so Gemini reads its context file from there natively.
  - Identical flags for both with_context and without_context arms (AD-4).

Telemetry parsing:
  - Reads token usage from stats/usageMetadata when present.
  - Gemini CLI does not report an exact billed USD cost, so cost_confidence is
    "estimated" and cost_usd defaults to 0.0 (honest: we do not fabricate cost).
  - Reads an error flag when present; otherwise infers error on unparseable logs.
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from primer.eval.agent_adapter import AgentAdapter
from primer.eval.models import AgentTelemetry

if TYPE_CHECKING:
    from primer.eval.models import Task

log = logging.getLogger(__name__)


class GeminiAdapter(AgentAdapter):
    """Adapter for the Gemini CLI (headless)."""

    @property
    def adapter_name(self) -> str:
        return "gemini"

    def required_env_key(self) -> str:
        return "GEMINI_API_KEY"

    def api_host(self) -> str:
        return "generativelanguage.googleapis.com"

    def context_filename(self) -> str:
        return "CLAUDE.md"

    def build_invocation(self, task: "Task") -> list[str]:
        """Return the headless Gemini CLI invocation argv.

        Flags identical both arms (AD-4). The prompt is passed via --prompt,
        which runs a single non-interactive turn and exits. --yolo auto-approves
        tool actions so the agent never blocks on a confirmation prompt.
        """
        return [
            "gemini",
            "--prompt", task.prompt,
            "--output-format", "json",
            "--yolo",
        ]

    def parse_telemetry(self, raw_log: str) -> AgentTelemetry:
        """Parse Gemini CLI JSON output for token telemetry.

        Does NOT infer pass/fail (AD-4). If parsing fails, returns safe defaults.
        raw_log has already been redacted by runner.py.
        """
        tokens = 0
        iterations = 0
        duration_s = 0.0
        cost_usd = 0.0
        agent_error = False

        json_obj = _extract_last_json(raw_log)
        if json_obj is not None:
            try:
                stats = json_obj.get("stats", {}) or {}

                # Token usage may live under stats/usage or a top-level
                # usageMetadata block depending on CLI version. Try both.
                usage = (
                    stats.get("usage")
                    or json_obj.get("usageMetadata")
                    or json_obj.get("usage")
                    or {}
                )
                tokens = _sum_tokens(usage)

                iterations = int(
                    stats.get("turns", 0)
                    or json_obj.get("num_turns", 0)
                    or 0
                )

                duration_ms = (
                    stats.get("duration_ms")
                    or json_obj.get("duration_ms")
                    or 0
                )
                duration_s = float(duration_ms) / 1000.0

                agent_error = bool(
                    json_obj.get("is_error", False)
                    or json_obj.get("error") is not None
                )

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
            cost_confidence="estimated",  # Gemini CLI does not report billed USD
            agent_error=agent_error,
            raw_log=raw_log,              # already redacted by runner
        )


def _sum_tokens(usage: dict) -> int:
    """Sum input + output tokens across the field names Gemini may use."""
    if not isinstance(usage, dict):
        return 0
    input_tokens = (
        usage.get("input_tokens")
        or usage.get("promptTokenCount")
        or 0
    )
    output_tokens = (
        usage.get("output_tokens")
        or usage.get("candidatesTokenCount")
        or 0
    )
    try:
        return int(input_tokens) + int(output_tokens)
    except (TypeError, ValueError):
        return 0


def _extract_last_json(text: str) -> dict | None:
    """Try to extract the last complete JSON object from text."""
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

    # If no single-line JSON, try parsing the entire text as one object.
    if not candidates:
        try:
            obj = json.loads(text.strip())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    return candidates[0] if candidates else None
