// Types mirror the dashboard.json schema produced by primer/report/export.py
// Field names must match exactly (primer-dashboard skill).

export type VerdictLabel = "positive" | "negative" | "within-noise" | "refused";
export type FlipState =
  | "PASS_TO_PASS"
  | "PASS_TO_FAIL"
  | "FAIL_TO_PASS"
  | "FAIL_TO_FAIL";
export type CostConfidence = "exact" | "estimated" | "free";

export interface TaskData {
  task_id: string;
  task_type: string;
  pass_rate_without: number;
  pass_rate_with: number;
  delta: number | null;
  flip_state: FlipState;
  runs: number;
  flaky_any: boolean;
}

export interface DashboardData {
  // schema
  schema_version: number;

  // report identity
  repo_commit: string;
  created_at: string;

  // M3 computed verdict
  verdict: VerdictLabel;

  // core metrics
  n_tasks: number;
  runs_per_config: number;
  success_rate_without: number;
  success_rate_with: number;
  success_delta: number | null;
  success_stddev: number;
  success_min: number;
  success_max: number;

  // cost (eval stream only — primer_overhead is separate)
  cost_without: number;
  cost_with: number;
  cost_delta_pct: number | null;
  cost_confidence: CostConfidence;

  // provenance / isolation
  provider: string;
  model: string;
  agent_adapter: string;
  base_image: string;
  network_mode: string;
  egress_enforced: boolean;

  // honesty warnings (null = clean)
  provider_mismatch_warning: string | null;
  isolation_mismatch_warning: string | null;
  flaky_task_warning: string | null;

  // PRIMER overhead — separate from eval cost
  primer_overhead_usd: number;
  primer_overhead_confidence: CostConfidence;

  // per-task breakdown
  per_task: TaskData[];
}
