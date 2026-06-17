"use client";

import { motion } from "motion/react";
import { formatPct, formatCost, formatCostDelta } from "@/lib/format";
import type { DashboardData } from "@/lib/types";

interface MetricCellProps {
  label: string;
  value: string;
  sub?: string;
  index: number;
}

function MetricCell({ label, value, sub, index }: MetricCellProps) {
  return (
    <motion.div
      className="flex flex-col gap-1 py-4 px-4"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05, ease: [0.16, 1, 0.3, 1] }}
    >
      <span className="t-eyebrow">{label}</span>
      <span className="t-data text-[var(--text-primary)] text-2xl font-semibold tracking-tight">
        {value}
      </span>
      {sub && <span className="t-caption">{sub}</span>}
    </motion.div>
  );
}

interface MetricsGridProps {
  data: DashboardData;
}

export function MetricsGrid({ data }: MetricsGridProps) {
  const {
    success_rate_without, success_rate_with,
    success_stddev, success_min, success_max,
    cost_without, cost_with, cost_delta_pct, cost_confidence,
    n_tasks, runs_per_config,
    primer_overhead_usd, primer_overhead_confidence,
  } = data;

  const costSubLabel =
    cost_confidence === "estimated" ? "estimated — provider cost approximate"
    : cost_confidence === "free"    ? "local run — no provider cost"
    : undefined;

  return (
    <div className="reveal-on-scroll">
      <h2 className="t-eyebrow mb-3">Metrics</h2>

      <div className="rounded-card border border-[var(--border-hairline)] bg-[var(--surface-elevated)] shadow-card overflow-hidden">
      {/* Success rates */}
      <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-[var(--border-hairline)]">
        <MetricCell label="Without" value={formatPct(success_rate_without)} sub="success rate" index={0} />
        <MetricCell label="With"    value={formatPct(success_rate_with)}    sub="success rate" index={1} />
        <MetricCell
          label="Variance"
          value={`±${(success_stddev * 100).toFixed(1)} pp`}
          sub={`min ${formatPct(success_min)} / max ${formatPct(success_max)}`}
          index={2}
        />
        <MetricCell label="Tasks" value={String(n_tasks)} sub={`${runs_per_config} runs/config`} index={3} />
      </div>

      {/* Cost row (eval stream only) */}
      <div className="border-t border-[var(--border-hairline)] grid grid-cols-2 md:grid-cols-3 divide-x divide-[var(--border-hairline)]">
        <MetricCell label="Cost without" value={formatCost(cost_without, cost_confidence)} index={4} />
        <MetricCell label="Cost with"    value={formatCost(cost_with, cost_confidence)}    index={5} />
        <MetricCell
          label="Cost delta"
          value={formatCostDelta(cost_delta_pct)}
          sub={costSubLabel}
          index={6}
        />
      </div>

      {/* PRIMER overhead — always its own line */}
      <div className="border-t border-[var(--border-hairline)] px-4 py-3 flex items-center justify-between gap-4">
        <div className="flex flex-col gap-0.5">
          <span className="t-eyebrow">PRIMER overhead</span>
          <span className="t-data text-[var(--text-secondary)] text-sm">
            {formatCost(primer_overhead_usd, primer_overhead_confidence)}
          </span>
        </div>
        <p className="t-caption text-right max-w-[32ch]">
          Generation cost (Layer-1 provider). Never included in eval cost delta.
        </p>
      </div>
      </div>
    </div>
  );
}
