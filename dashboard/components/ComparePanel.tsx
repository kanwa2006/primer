"use client";

import { computeComparison } from "@/lib/compare";
import { formatPct, formatDelta, formatCost, verdictColor, verdictWord, verdictIcon } from "@/lib/format";
import { TaskFlipTable } from "@/components/TaskFlipTable";
import type { DashboardData } from "@/lib/types";

// Noise threshold = max(1/n_tasks, success_stddev) — mirrors the engine verdict rule.
function noiseThreshold(d: DashboardData): number {
  return Math.max(1 / d.n_tasks, d.success_stddev);
}

interface Props {
  a: DashboardData;
  b: DashboardData;
}

export function ComparePanel({ a, b }: Props) {
  const result = computeComparison(a, b);

  return (
    <div className="flex flex-col gap-10">
      <div className="grid grid-cols-2 gap-6">
        <EvalHeadline label="Baseline A" data={a} />
        <EvalHeadline label="New B" data={b} />
      </div>

      {result.isolation_mismatch && (
        <div className="flex items-start gap-3 px-4 py-3 rounded border border-amber-500/20 bg-amber-500/5" role="alert">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" className="text-amber-600 mt-0.5 shrink-0">
            <path d="M8 2L14.5 13H1.5L8 2Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
            <line x1="8" y1="7" x2="8" y2="10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
            <circle cx="8" cy="11.5" r="0.6" fill="currentColor" />
          </svg>
          <p className="text-amber-700 text-xs leading-relaxed font-mono">
            Isolation mismatch: base image, network mode, or egress enforcement differ. Results may not be directly comparable.
          </p>
        </div>
      )}

      <div className="border border-zinc-200 rounded-lg p-6">
        <div className="text-zinc-500 text-xs font-mono uppercase tracking-widest mb-4">
          Cross-evaluation delta
        </div>
        {result.refused ? (
          <div className="flex flex-col gap-2">
            <span className="text-xs font-mono text-refused uppercase tracking-wider">Refused</span>
            <p className="text-xs text-zinc-500 font-mono leading-relaxed">
              Provider or model differ between evaluations. Showing a cross-evaluation delta would
              produce a fabricated number. Delta is withheld per honesty invariants.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <div className="flex items-baseline gap-3">
              <span className="text-2xl font-mono font-semibold text-zinc-900">
                {formatDelta(result.cross_report_delta)}
              </span>
              <span className="text-xs font-mono text-zinc-500">B − A success delta</span>
            </div>
            <p className="text-xs font-mono text-zinc-400 leading-relaxed max-w-[70ch]">
              Interpret against each evaluation&apos;s noise envelope — A ± {(noiseThreshold(a) * 100).toFixed(1)} pp, B ± {(noiseThreshold(b) * 100).toFixed(1)} pp. A cross-evaluation delta smaller than these bands is not a reliable difference.
            </p>
          </div>
        )}
      </div>

      {!result.refused &&
        (noiseThreshold(a) !== noiseThreshold(b) ||
          a.cost_confidence !== b.cost_confidence) && (
          <div className="flex flex-col gap-1.5">
            {noiseThreshold(a) !== noiseThreshold(b) && (
              <p className="text-xs font-mono text-zinc-500 leading-relaxed max-w-[70ch]">
                {noiseThreshold(a) > noiseThreshold(b) ? "Baseline A" : "New B"} is
                noisier — its noise envelope is wider, so treat its delta with more
                caution.
              </p>
            )}
            {a.cost_confidence !== b.cost_confidence && (
              <p className="text-xs font-mono text-amber-700 leading-relaxed max-w-[70ch]">
                ⚠ Cost confidence differs (A: {a.cost_confidence}, B:{" "}
                {b.cost_confidence}) — cost figures are not directly comparable.
              </p>
            )}
          </div>
        )}

      <div>
        <div className="text-zinc-500 text-xs font-mono uppercase tracking-widest mb-3">
          Provenance diff
        </div>
        <div className="overflow-x-auto border border-zinc-200 rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 bg-zinc-50">
                <th className="py-2 px-4 text-left text-xs font-mono text-zinc-500 uppercase tracking-widest w-36">
                  Field
                </th>
                <th className="py-2 px-4 text-left text-xs font-mono text-zinc-500 uppercase tracking-widest">
                  Baseline A
                </th>
                <th className="py-2 px-4 text-left text-xs font-mono text-zinc-500 uppercase tracking-widest">
                  New B
                </th>
              </tr>
            </thead>
            <tbody>
              {result.fields.map((row) => (
                <tr
                  key={row.label}
                  className={`border-b border-zinc-100 last:border-0 ${row.differ ? "bg-amber-50" : ""}`}
                >
                  <td className="py-2 px-4 text-xs font-mono text-zinc-400">{row.label}</td>
                  <td className={`py-2 px-4 text-xs font-mono ${row.differ ? "text-amber-700 font-semibold" : "text-zinc-700"}`}>
                    {row.a || <span className="text-zinc-400">—</span>}
                  </td>
                  <td className={`py-2 px-4 text-xs font-mono ${row.differ ? "text-amber-700 font-semibold" : "text-zinc-700"}`}>
                    {row.b || <span className="text-zinc-400">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {(a.per_task.length > 0 || b.per_task.length > 0) && (
        <div className="grid grid-cols-2 gap-6">
          <div>
            <div className="text-zinc-500 text-xs font-mono uppercase tracking-widest mb-3">
              Baseline A — per-task
            </div>
            <TaskFlipTable tasks={a.per_task} />
          </div>
          <div>
            <div className="text-zinc-500 text-xs font-mono uppercase tracking-widest mb-3">
              New B — per-task
            </div>
            <TaskFlipTable tasks={b.per_task} />
          </div>
        </div>
      )}
    </div>
  );
}

function EvalHeadline({ label, data }: { label: string; data: DashboardData }) {
  return (
    <div className="border border-zinc-200 rounded-lg p-5 flex flex-col gap-3">
      <div className="text-zinc-400 text-xs font-mono uppercase tracking-widest">{label}</div>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="text-lg font-mono font-semibold text-zinc-900">
          {formatPct(data.success_rate_with)}
        </span>
        <span className="text-xs text-zinc-500 font-mono">with</span>
        <span className="text-xs text-zinc-500 font-mono">
          ({formatDelta(data.success_delta)} ± {(noiseThreshold(data) * 100).toFixed(1)} pp)
        </span>
      </div>
      <div className="text-xs text-zinc-500 font-mono">
        {formatPct(data.success_rate_without)} without
      </div>
      <div>
        <span className={`text-xs font-mono font-semibold ${verdictColor(data.verdict)}`}>
          <span aria-hidden="true">{verdictIcon(data.verdict)}</span> {verdictWord(data.verdict)}
        </span>
      </div>
      <div className="text-xs font-mono text-zinc-400">
        {data.model} · {data.provider}
      </div>
      <div className="text-xs font-mono text-zinc-500">
        cost {formatCost(data.cost_with, data.cost_confidence)}
      </div>
    </div>
  );
}
