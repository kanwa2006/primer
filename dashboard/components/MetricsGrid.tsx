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
      className="flex flex-col gap-1 py-4 px-0"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.3,
        delay: index * 0.05,
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      <span className="text-zinc-500 text-xs uppercase tracking-widest font-mono">
        {label}
      </span>
      <span className="text-zinc-900 text-2xl font-mono font-semibold tracking-tight">
        {value}
      </span>
      {sub && (
        <span className="text-zinc-500 text-xs font-mono">{sub}</span>
      )}
    </motion.div>
  );
}

interface MetricsGridProps {
  data: DashboardData;
}

export function MetricsGrid({ data }: MetricsGridProps) {
  const {
    success_rate_without,
    success_rate_with,
    success_stddev,
    success_min,
    success_max,
    cost_without,
    cost_with,
    cost_delta_pct,
    cost_confidence,
    n_tasks,
    runs_per_config,
  } = data;

  return (
    <div>
      {/* Section header */}
      <div className="text-zinc-500 text-xs font-mono uppercase tracking-widest mb-3">
        Metrics
      </div>

      {/* Success rates */}
      <div className="border-t border-zinc-200 grid grid-cols-2 md:grid-cols-4 divide-x divide-zinc-200">
        <MetricCell
          label="Without"
          value={formatPct(success_rate_without)}
          sub="success rate"
          index={0}
        />
        <MetricCell
          label="With"
          value={formatPct(success_rate_with)}
          sub="success rate"
          index={1}
        />
        <MetricCell
          label="Variance"
          value={`±${(success_stddev * 100).toFixed(1)} pp`}
          sub={`min ${formatPct(success_min)} / max ${formatPct(success_max)}`}
          index={2}
        />
        <MetricCell
          label="Tasks"
          value={String(n_tasks)}
          sub={`${runs_per_config} runs/config`}
          index={3}
        />
      </div>

      {/* Cost row */}
      <div className="border-t border-zinc-200 grid grid-cols-2 md:grid-cols-3 divide-x divide-zinc-200">
        <MetricCell
          label="Cost without"
          value={formatCost(cost_without, cost_confidence)}
          index={4}
        />
        <MetricCell
          label="Cost with"
          value={formatCost(cost_with, cost_confidence)}
          index={5}
        />
        <MetricCell
          label="Cost delta"
          value={formatCostDelta(cost_delta_pct)}
          sub={
            cost_confidence === "estimated"
              ? "estimated — provider cost approximate"
              : cost_confidence === "free"
              ? "local run — no provider cost"
              : undefined
          }
          index={6}
        />
      </div>
    </div>
  );
}
