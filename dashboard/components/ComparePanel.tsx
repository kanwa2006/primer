"use client";

import { computeComparison } from "@/lib/compare";
import { formatPct, formatDelta, formatCost } from "@/lib/format";
import { noiseThreshold } from "@/lib/verdict";
import { VerdictBadge } from "@/components/VerdictBadge";
import { InstrumentCard } from "@/components/InstrumentCard";
import { TaskFlipTable } from "@/components/TaskFlipTable";
import { TriangleAlert } from "lucide-react";
import type { DashboardData } from "@/lib/types";

interface Props {
  a: DashboardData;
  b: DashboardData;
}

export function ComparePanel({ a, b }: Props) {
  const result = computeComparison(a, b);
  const ntA = noiseThreshold(a.success_stddev, a.n_tasks);
  const ntB = noiseThreshold(b.success_stddev, b.n_tasks);

  return (
    <div className="flex flex-col gap-10">
      {/* Eval headlines */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <EvalHeadline label="Baseline A" data={a} />
        <EvalHeadline label="New B"      data={b} />
      </div>

      {/* Isolation mismatch warning */}
      {result.isolation_mismatch && (
        <div
          role="alert"
          className="flex items-start gap-2.5 px-4 py-3 rounded-md border border-[var(--warning-border)] bg-[var(--warning-bg)]"
        >
          <TriangleAlert size={14} strokeWidth={1.5} className="text-[var(--warning-fg)] mt-0.5 shrink-0" aria-hidden />
          <p className="text-[var(--warning-fg)] t-body">
            Isolation mismatch: base image, network mode, or egress enforcement differ. Results may not be directly comparable.
          </p>
        </div>
      )}

      {/* Cross-eval delta panel */}
      <InstrumentCard lift={false} glow className="p-6 reveal-on-scroll">
        <div className="t-eyebrow mb-4">Cross-evaluation delta</div>
        {result.refused ? (
          <div className="flex flex-col gap-2">
            <VerdictBadge verdict="refused" />
            <p className="t-body text-[var(--text-secondary)] max-w-[60ch]">
              PRIMER won't compare these runs: they used different models, so any
              difference couldn't be attributed to the context file. Refusing to guess is the point.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <div className="flex items-baseline gap-3">
              <span className="t-data text-3xl font-semibold text-[var(--text-primary)]">
                {formatDelta(result.cross_report_delta)}
              </span>
              <span className="t-data text-xs text-[var(--text-tertiary)]">B − A success delta</span>
            </div>
            <p className="t-body text-[var(--text-tertiary)] max-w-[70ch]">
              Interpret against each evaluation's noise envelope — A ±{(ntA * 100).toFixed(1)} pp, B ±{(ntB * 100).toFixed(1)} pp.
              A cross-evaluation delta smaller than these bands is not a reliable difference.
            </p>
          </div>
        )}
      </InstrumentCard>

      {/* Confidence qualifiers */}
      {!result.refused && (ntA !== ntB || a.cost_confidence !== b.cost_confidence) && (
        <div className="flex flex-col gap-1.5">
          {ntA !== ntB && (
            <p className="t-body text-[var(--text-secondary)] max-w-[70ch]">
              {ntA > ntB ? "Baseline A" : "New B"} is noisier — its noise envelope is wider, so treat its delta with more caution.
            </p>
          )}
          {a.cost_confidence !== b.cost_confidence && (
            <p className="t-body text-[var(--warning-fg)] max-w-[70ch]">
              ⚠ Cost confidence differs (A: {a.cost_confidence}, B: {b.cost_confidence}) — cost figures are not directly comparable.
            </p>
          )}
        </div>
      )}

      {/* Provenance diff table */}
      <div className="reveal-on-scroll">
        <div className="t-eyebrow mb-3">Provenance diff</div>
        <div className="overflow-x-auto border border-[var(--border-hairline)] rounded-card shadow-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border-hairline)] bg-[var(--surface-raised)]">
                {["Field", "Baseline A", "New B"].map((h) => (
                  <th key={h} className="py-2 px-4 text-left t-eyebrow">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.fields.map((row) => (
                <tr
                  key={row.label}
                  className={`border-b border-[var(--border-hairline)] last:border-0 ${row.differ ? "bg-[var(--warning-bg)]" : ""}`}
                >
                  <td className="py-2 px-4 text-xs font-mono text-[var(--text-tertiary)]">{row.label}</td>
                  <td className={`py-2 px-4 text-xs font-mono ${row.differ ? "text-[var(--warning-fg)] font-semibold" : "text-[var(--text-secondary)]"}`}>
                    {row.a || <span className="text-[var(--text-tertiary)]">—</span>}
                  </td>
                  <td className={`py-2 px-4 text-xs font-mono ${row.differ ? "text-[var(--warning-fg)] font-semibold" : "text-[var(--text-secondary)]"}`}>
                    {row.b || <span className="text-[var(--text-tertiary)]">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Per-task comparison */}
      {(a.per_task.length > 0 || b.per_task.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 reveal-on-scroll">
          <div>
            <div className="t-eyebrow mb-3">Baseline A — per-task</div>
            <TaskFlipTable tasks={a.per_task} />
          </div>
          <div>
            <div className="t-eyebrow mb-3">New B — per-task</div>
            <TaskFlipTable tasks={b.per_task} />
          </div>
        </div>
      )}
    </div>
  );
}

function EvalHeadline({ label, data }: { label: string; data: DashboardData }) {
  const nt = noiseThreshold(data.success_stddev, data.n_tasks);
  const deltaStr = data.success_delta !== null
    ? (data.success_delta > 0 ? `+${(data.success_delta * 100).toFixed(1)}` : `${(data.success_delta * 100).toFixed(1)}`) + " pp"
    : "N/A";

  return (
    <InstrumentCard className="p-5 flex flex-col gap-3">
      <div className="t-eyebrow">{label}</div>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="t-data text-2xl font-semibold text-[var(--text-primary)]">
          {formatPct(data.success_rate_with)}
        </span>
        <span className="t-data text-xs text-[var(--text-tertiary)]">with</span>
        <span className="t-data text-xs text-[var(--text-tertiary)]">
          ({deltaStr} ±{(nt * 100).toFixed(1)} pp)
        </span>
      </div>
      <div className="t-data text-xs text-[var(--text-tertiary)]">
        {formatPct(data.success_rate_without)} without
      </div>
      <VerdictBadge verdict={data.verdict} size="sm" />
      <div className="t-data text-xs text-[var(--text-tertiary)]">
        {data.model} · {data.provider}
      </div>
      <div className="t-data text-xs text-[var(--text-tertiary)]">
        cost {formatCost(data.cost_with, data.cost_confidence)}
      </div>
    </InstrumentCard>
  );
}
