"""PRIMER eval package — the measurement moat.

Phase 3 modules:
  models      — Task, RunResult, AgentTelemetry, ScoreReport, TaskScore
  tasks       — derive_tasks() (Spec C, no LLM, deterministic)
  preflight   — validate_task() (3× good-pass / broken-fail)
  images      — build_eval_image() (AD-2, per-repo deps layer)
  network     — EgressNetwork context manager (Spec B proxy-egress)
  agent_adapter — AgentAdapter ABC (AD-3, AD-4)
  adapters/   — ClaudeCodeAdapter (MVP default)
  runner      — run_task() fat runner (Specs B+D, all isolation here)
  scorer      — score() aggregation, variance, refuse-on-mismatch (AD-5)
"""
