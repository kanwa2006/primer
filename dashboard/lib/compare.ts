// Mirror of primer/report/render.py render_compare — keep in lockstep.

import type { DashboardData, ComparisonResult, DiffRow } from "./types";

export function computeComparison(
  a: DashboardData,
  b: DashboardData,
): ComparisonResult {
  const provider_mismatch =
    a.provider !== b.provider || a.model !== b.model;
  const isolation_mismatch =
    a.network_mode !== b.network_mode ||
    a.egress_enforced !== b.egress_enforced ||
    a.base_image !== b.base_image;
  const refused = provider_mismatch;
  const cross_report_delta =
    provider_mismatch || a.success_delta == null || b.success_delta == null
      ? null
      : b.success_delta - a.success_delta;

  const fields: DiffRow[] = [
    {
      label: "Repo commit",
      a: a.repo_commit,
      b: b.repo_commit,
      differ: a.repo_commit !== b.repo_commit,
    },
    {
      label: "Evaluated at",
      a: a.created_at,
      b: b.created_at,
      differ: a.created_at !== b.created_at,
    },
    {
      label: "Provider",
      a: a.provider,
      b: b.provider,
      differ: a.provider !== b.provider,
    },
    {
      label: "Model",
      a: a.model,
      b: b.model,
      differ: a.model !== b.model,
    },
    {
      label: "Agent",
      a: a.agent_adapter,
      b: b.agent_adapter,
      differ: a.agent_adapter !== b.agent_adapter,
    },
    {
      label: "Base image",
      a: a.base_image,
      b: b.base_image,
      differ: a.base_image !== b.base_image,
    },
    {
      label: "Network mode",
      a: a.network_mode,
      b: b.network_mode,
      differ: a.network_mode !== b.network_mode,
    },
    {
      label: "Egress enforced",
      a: String(a.egress_enforced),
      b: String(b.egress_enforced),
      differ: a.egress_enforced !== b.egress_enforced,
    },
    {
      label: "Tasks",
      a: String(a.n_tasks),
      b: String(b.n_tasks),
      differ: a.n_tasks !== b.n_tasks,
    },
    {
      label: "Runs/config",
      a: String(a.runs_per_config),
      b: String(b.runs_per_config),
      differ: a.runs_per_config !== b.runs_per_config,
    },
  ];

  return { provider_mismatch, isolation_mismatch, refused, cross_report_delta, fields };
}
