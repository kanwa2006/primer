"""PRIMER eval package — the measurement harness.

Modules:
  models        — Task, RunResult, AgentTelemetry, ScoreReport, TaskScore
  tasks         — derive_tasks() (deterministic, no LLM)
  preflight     — validate_task() (3× good-pass / broken-fail)
  images        — build_eval_image() (per-repo deps layer)
  network       — EgressNetwork context manager (egress proxy)
  agent_adapter — AgentAdapter ABC
  adapters/     — ClaudeCodeAdapter (default), GeminiAdapter (experimental)
  runner        — run_task() fat runner (all isolation logic here)
  scorer        — score() aggregation, variance, refuse-on-mismatch
"""
