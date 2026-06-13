"""Data models for Phase 3 eval (Spec A, Session 2 §4.6).

Two token streams that MUST NEVER be mixed:
  - PRIMER overhead: tokens spent generating the context file (Layer-1)
  - Eval cost:       tokens spent by the in-container agent (Layer-2, captured here)

RunResult.base_image stores a resolved sha256 digest (M5), never a bare tag.
AgentTelemetry carries NO pass/fail field (AD-4): pass/fail comes from verify_cmd exit code only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class TaskMutation:
    """How runner.py reproduces the deterministic failing start state."""
    kind: Literal["revert", "stub"]
    target_commit: str | None = None   # revert: the source-only commit to revert
    target_file: str | None = None     # stub: file containing the function
    target_symbol: str | None = None   # stub: function to replace with raise NotImplementedError


@dataclass
class Task:
    """A single eval task with a deterministic failing start state."""
    id: str                              # e.g. "revert_<sha>_<test>" or "stub_<file>_<fn>"
    task_type: Literal["revert_reimplement", "stub_function"]
    prompt: str                          # instruction given to the eval agent
    verify_cmd: str                      # repo's own test runner; exit code is the sole verdict
    mutation: TaskMutation               # how to reproduce the failing start state
    source_ref: str | None = None        # commit SHA or "path/to/file.py::func_name"
    validated: bool = False              # True only after preflight passes


@dataclass
class AgentTelemetry:
    """Parsed output from the in-container agent. NO pass/fail (AD-4).

    Pass/fail is determined solely by verify_cmd exit code in runner.py.
    """
    tokens: int
    iterations: int
    duration_s: float
    cost_usd: float
    cost_confidence: Literal["exact", "estimated", "free"]
    agent_error: bool                    # True if agent reported an error (does NOT affect passed)
    raw_log: str                         # REDACTED by runner before this field is populated


@dataclass
class RunResult:
    """Result of one container run of one task arm (with_context True/False).

    Spec A (Session 1 Final Revision) — authoritative.
    base_image stores a sha256 digest (M5), e.g. "python:3.11-slim@sha256:abc123..."
    egress_enforced=True ONLY when a deny-by-default proxy was active (Spec B honesty gate).
    """
    # --- identity / outcome ---
    task_id: str
    passed: bool
    timeout: bool
    flaky: bool
    with_context: bool

    # --- eval-agent cost stream (in-container; feeds before/after delta) ---
    agent_adapter: str
    agent_tokens: int
    iterations: int
    duration_s: float
    cost_usd: float
    cost_confidence: Literal["exact", "estimated", "free"]

    # --- PRIMER-brain provenance (who generated the context file under test) ---
    provider: str
    model: str

    # --- isolation + reproducibility audit trail ---
    base_image: str              # resolved sha256 digest (M5)
    repo_commit: str             # repo SHA the eval ran against
    network_mode: str            # "proxy-egress" | "open-bridge" | "offline"
    egress_allowed_host: str | None
    egress_enforced: bool        # True ONLY if deny-by-default proxy was active
    caps_dropped: bool
    container_id: str
    agent_log_path: str          # path to REDACTED agent log on disk
    run_timestamp: str           # ISO-8601 UTC

    # --- harness-validity fingerprint gate (BLK-2 / M4) ---
    # True: WITH arm; marker found; harness valid.
    # False: WITH arm; marker absent; scorer aborts (HarnessValidityError).
    # None: WITHOUT arm (not applicable), or adapter does not participate.
    harness_fingerprint_valid: bool | None = None


@dataclass
class TaskScore:
    """Aggregated score for one task across repeated runs."""
    task_id: str
    task_type: str
    pass_rate_without: float
    pass_rate_with: float
    delta: float | None          # None if comparison refused (Q9d / AD-5)
    runs: int
    flaky_any: bool


@dataclass
class ScoreReport:
    """Full scored result for a primer eval run.

    success_delta may be None (refused on provider/model mismatch — Q9d).
    primer_overhead_usd is NEVER added to cost_with/cost_without (two-stream rule).
    """
    repo_commit: str
    created_at: str              # ISO-8601 UTC
    n_tasks: int
    runs_per_config: int

    # --- outcome ---
    success_rate_without: float
    success_rate_with: float
    success_delta: float | None  # None → refused on mismatch
    success_stddev: float
    success_min: float
    success_max: float

    # --- eval cost stream only ---
    cost_without: float
    cost_with: float
    cost_delta_pct: float | None
    cost_confidence: str         # worst-of constituent runs

    # --- per-task breakdown ---
    per_task: list[TaskScore] = field(default_factory=list)

    # --- provenance / isolation ---
    provider: str = ""
    model: str = ""
    agent_adapter: str = ""
    base_image: str = ""
    network_mode: str = ""
    egress_enforced: bool = False

    # --- honesty warnings (None = clean) ---
    provider_mismatch_warning: str | None = None
    isolation_mismatch_warning: str | None = None
    flaky_task_warning: str | None = None

    # --- PRIMER overhead (NEVER summed into cost_with/without) ---
    primer_overhead_usd: float = 0.0
    primer_overhead_confidence: str = "estimated"
