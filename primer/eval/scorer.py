"""Scorer — aggregation, variance, and refuse-on-mismatch (AD-5, M3).

score() runs all tasks × {without, with} × runs_per_config SEQUENTIALLY (Q1).
For each run, context_content is threaded to run_task, which writes (WITH) or
omits (WITHOUT) the context file directly in the cloned work_dir. The source
repository is NEVER mutated (BLK-5).

Honesty rules:
  - success_delta = None on provider/model mismatch (Q9d, AD-5)
  - isolation_mismatch_warning when network_mode/egress_enforced/base_image not uniform
  - "egress-restricted" claim only if ALL runs have egress_enforced=True
  - cost_confidence = worst-of constituent runs
  - primer_overhead_usd carried separately, NEVER summed into cost_with/without (two-stream rule)
  - variance (stddev/min/max) always reported, never collapsed (M3)
"""
from __future__ import annotations

import datetime
import logging
import math
import shutil
import tempfile
import time
from typing import TYPE_CHECKING

from primer.errors import HarnessValidityError
from primer.eval.models import RunResult, ScoreReport, TaskScore
from primer.eval.runner import run_task

if TYPE_CHECKING:
    from primer.config import Settings
    from primer.eval.agent_adapter import AgentAdapter
    from primer.eval.models import Task
    from primer.ingest.models import RepoProfile

log = logging.getLogger(__name__)

# Q2: flaky retry — if verify_cmd fails first run, retry once after this delay
_FLAKY_RETRY_DELAY_S = 5.0

# Cost confidence ranking (worst = lowest rank)
_CONFIDENCE_RANK = {"exact": 2, "estimated": 1, "free": 0}


def score(
    profile: "RepoProfile",
    repo_path: str,
    tasks: list["Task"],
    config: "Settings",
    adapter: "AgentAdapter",
    image_tag: str,
    context_content: str = "",
    provider: str = "",
    model: str = "",
    primer_overhead_usd: float = 0.0,
    primer_overhead_confidence: str = "estimated",
    runs_per_config: int = 3,
    collect_runs: list[RunResult] | None = None,
) -> ScoreReport:
    """Run all tasks × {without, with} × runs_per_config and aggregate results.

    Sequential execution (Q1). Returns a ScoreReport with signed delta,
    variance, and all honesty warnings populated.

    context_content: the text of the generated context file (CLAUDE.md).
    provider/model: the Layer-1 provider that generated the file (PRIMER overhead).
    collect_runs: if a list is supplied, each RunResult is appended to it as it
        is produced, giving the caller access to run-level data for persistence.
        Callers that only need the ScoreReport may omit this parameter.
    """
    all_runs: list[RunResult] = []
    per_task_runs: dict[str, list[RunResult]] = {t.id: [] for t in tasks}

    for task in tasks:
        for with_ctx in (False, True):  # WITHOUT first, then WITH
            for run_idx in range(runs_per_config):
                log.info(
                    "scoring task=%s with_context=%s run=%d/%d",
                    task.id, with_ctx, run_idx + 1, runs_per_config,
                )

                # The runner writes the context file directly into the cloned
                # work_dir; the source repo is NEVER touched (BLK-5). The scorer
                # only threads the content through.
                run_result = _run_with_retry(
                    task=task,
                    repo_path=repo_path,
                    with_context=with_ctx,
                    profile=profile,
                    config=config,
                    adapter=adapter,
                    image_tag=image_tag,
                    context_content=context_content,
                )

                # BLK-2: abort if the WITH arm did not acknowledge the context file
                # (M4 harness-validity gate). False = marker absent = harness broken.
                # None = adapter does not participate; never an abort condition.
                if with_ctx and run_result.harness_fingerprint_valid is False:
                    raise HarnessValidityError(
                        f"WITH arm of task {task.id!r} (run {run_idx + 1}/{runs_per_config}) "
                        f"did not acknowledge the context file — harness integrity failure. "
                        f"No delta will be reported. "
                        f"Verify the fingerprint instruction text "
                        f"(see 16_BLK2_SPECIFICATION.md §4)."
                    )

                # Fill in provider/model provenance (PRIMER brain, not agent)
                run_result.provider = provider
                run_result.model = model

                all_runs.append(run_result)
                per_task_runs[task.id].append(run_result)
                if collect_runs is not None:
                    collect_runs.append(run_result)

    # ----- Aggregate ---------------------------------------------------------
    return _aggregate(
        tasks=tasks,
        all_runs=all_runs,
        per_task_runs=per_task_runs,
        runs_per_config=runs_per_config,
        provider=provider,
        model=model,
        adapter=adapter,
        profile=profile,
        primer_overhead_usd=primer_overhead_usd,
        primer_overhead_confidence=primer_overhead_confidence,
    )


def _run_with_retry(
    task: "Task",
    repo_path: str,
    with_context: bool,
    profile,
    config: "Settings",
    adapter: "AgentAdapter",
    image_tag: str,
    context_content: str = "",
) -> RunResult:
    """Q2 flaky policy: if verify_cmd fails first run, retry once after 5s.

    fail-twice → passed=False, flaky=False
    fail-then-pass → passed=True, flaky=True + warning
    """
    result = run_task(
        task=task,
        repo_path=repo_path,
        with_context=with_context,
        profile=profile,
        config=config,
        adapter=adapter,
        image_tag=image_tag,
        context_content=context_content,
    )

    if not result.passed and not result.timeout:
        log.debug("Q2 retry: task %s failed first run, retrying after %ds", task.id, _FLAKY_RETRY_DELAY_S)
        time.sleep(_FLAKY_RETRY_DELAY_S)
        retry_result = run_task(
            task=task,
            repo_path=repo_path,
            with_context=with_context,
            profile=profile,
            config=config,
            adapter=adapter,
            image_tag=image_tag,
            context_content=context_content,
        )
        if retry_result.passed:
            # Fail-then-pass → flaky=True, passed=True
            retry_result.flaky = True
            log.warning("Q2: task %s is FLAKY (fail-then-pass)", task.id)
            return retry_result
        else:
            # Fail-twice → passed=False, flaky=False
            return retry_result

    return result


def _aggregate(
    tasks: list["Task"],
    all_runs: list[RunResult],
    per_task_runs: dict[str, list[RunResult]],
    runs_per_config: int,
    provider: str,
    model: str,
    adapter: "AgentAdapter",
    profile,
    primer_overhead_usd: float,
    primer_overhead_confidence: str,
) -> ScoreReport:
    """Aggregate all runs into a ScoreReport with all honesty checks."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Per-task scores
    per_task: list[TaskScore] = []
    for task in tasks:
        runs = per_task_runs.get(task.id, [])
        without_runs = [r for r in runs if not r.with_context]
        with_runs = [r for r in runs if r.with_context]

        pr_without = _pass_rate(without_runs)
        pr_with = _pass_rate(with_runs)
        flaky_any = any(r.flaky for r in runs)

        # Check provider/model consistency for this task
        providers = {r.provider for r in runs}
        models = {r.model for r in runs}
        task_delta: float | None = None
        if len(providers) <= 1 and len(models) <= 1:
            task_delta = pr_with - pr_without

        per_task.append(TaskScore(
            task_id=task.id,
            task_type=task.task_type,
            pass_rate_without=pr_without,
            pass_rate_with=pr_with,
            delta=task_delta,
            runs=len(runs),
            flaky_any=flaky_any,
        ))

    # Overall success rates
    without_runs = [r for r in all_runs if not r.with_context]
    with_runs = [r for r in all_runs if r.with_context]

    success_rate_without = _pass_rate(without_runs)
    success_rate_with = _pass_rate(with_runs)

    # Variance across all runs (M3 — never collapsed)
    all_pass_values = [1.0 if r.passed else 0.0 for r in all_runs]
    stddev = _stddev(all_pass_values)
    success_min = min(all_pass_values) if all_pass_values else 0.0
    success_max = max(all_pass_values) if all_pass_values else 0.0

    # Cost streams (eval only — PRIMER overhead kept separate)
    cost_without = sum(r.cost_usd for r in without_runs)
    cost_with = sum(r.cost_usd for r in with_runs)
    cost_delta_pct: float | None = None
    if cost_without > 0:
        cost_delta_pct = (cost_with - cost_without) / cost_without * 100.0

    # Worst-of cost confidence
    all_confidences = [r.cost_confidence for r in all_runs]
    cost_confidence = _worst_confidence(all_confidences) if all_confidences else "estimated"

    # ----- Honesty checks ---------------------------------------------------

    # Q9d / AD-5: refuse delta on provider/model mismatch
    providers = {r.provider for r in all_runs}
    models = {r.model for r in all_runs}
    provider_mismatch_warning: str | None = None
    success_delta: float | None = success_rate_with - success_rate_without

    if len(providers) > 1 or len(models) > 1:
        success_delta = None
        cost_delta_pct = None
        provider_mismatch_warning = (
            f"Provider/model mismatch across compared runs — delta refused. "
            f"Providers: {sorted(providers)}, Models: {sorted(models)}."
        )
        log.warning("provider/model mismatch: delta set to None")

    # Isolation consistency check
    network_modes = {r.network_mode for r in all_runs}
    egress_flags = {r.egress_enforced for r in all_runs}
    base_images = {r.base_image for r in all_runs}
    isolation_mismatch_warning: str | None = None

    if len(network_modes) > 1 or len(egress_flags) > 1 or len(base_images) > 1:
        isolation_mismatch_warning = (
            f"Isolation settings not uniform across runs. "
            f"network_mode={network_modes}, egress_enforced={egress_flags}, "
            f"base_image count={len(base_images)}."
        )
        log.warning("isolation mismatch detected")

    # egress_enforced is True in report ONLY if ALL runs were enforced
    egress_enforced = all(r.egress_enforced for r in all_runs) if all_runs else False

    # Dominant values (first run's values, or most common)
    dominant_network_mode = _most_common([r.network_mode for r in all_runs]) or "unknown"
    dominant_base_image = _most_common([r.base_image for r in all_runs]) or ""

    # Flaky warning
    flaky_task_ids = [t.task_id for t in per_task if t.flaky_any]
    flaky_task_warning: str | None = None
    if flaky_task_ids:
        flaky_task_warning = f"Flaky tasks detected: {flaky_task_ids}. Results annotated."

    return ScoreReport(
        repo_commit=profile.repo_commit,
        created_at=now,
        n_tasks=len(tasks),
        runs_per_config=runs_per_config,
        success_rate_without=success_rate_without,
        success_rate_with=success_rate_with,
        success_delta=success_delta,
        success_stddev=stddev,
        success_min=success_min,
        success_max=success_max,
        cost_without=cost_without,
        cost_with=cost_with,
        cost_delta_pct=cost_delta_pct,
        cost_confidence=cost_confidence,
        per_task=per_task,
        provider=provider,
        model=model,
        agent_adapter=adapter.adapter_name,
        base_image=dominant_base_image,
        network_mode=dominant_network_mode,
        egress_enforced=egress_enforced,
        provider_mismatch_warning=provider_mismatch_warning,
        isolation_mismatch_warning=isolation_mismatch_warning,
        flaky_task_warning=flaky_task_warning,
        primer_overhead_usd=primer_overhead_usd,
        primer_overhead_confidence=primer_overhead_confidence,
    )


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def _pass_rate(runs: list[RunResult]) -> float:
    if not runs:
        return 0.0
    return sum(1 for r in runs if r.passed) / len(runs)


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _worst_confidence(confs: list[str]) -> str:
    ranked = sorted(confs, key=lambda c: _CONFIDENCE_RANK.get(c, 0))
    return ranked[0] if ranked else "estimated"


def _most_common(values: list[str]) -> str | None:
    if not values:
        return None
    return max(set(values), key=values.count)
