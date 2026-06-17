"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { formatDate } from "@/lib/format";
import { noiseThreshold, VERDICT_WORD } from "@/lib/verdict";
import { VerdictBadge } from "@/components/VerdictBadge";
import { InstrumentCard } from "@/components/InstrumentCard";
import type { RepositoryData, EvaluationSummary, VerdictLabel } from "@/lib/types";

// ─── DeltaStepChart ──────────────────────────────────────────────────────────
// Step chart (not smoothed) with error bars and dashed zero baseline.
// Text-alternative summary generated from data.

interface DeltaStepChartProps {
  evals: EvaluationSummary[];
}

function DeltaStepChart({ evals }: DeltaStepChartProps) {
  const reduce = useReducedMotion();
  const [hover, setHover] = useState<number | null>(null);

  // Sorted oldest-first for charting
  const points = [...evals].reverse();
  const n = points.length;

  if (n === 0) return null;

  // Chart dimensions
  const W = 800;
  const H = 260;
  const PL = 56, PR = 20, PT = 20, PB = 40;
  const chartW = W - PL - PR;
  const chartH = H - PT - PB;

  // Value range — include zero always
  const allDeltas = points.map((p) => p.success_delta ?? 0);
  const allNT = points.map((p) => noiseThreshold(p.success_stddev, p.n_tasks));
  const rawMin = Math.min(0, ...allDeltas.map((d, i) => d - allNT[i]));
  const rawMax = Math.max(0, ...allDeltas.map((d, i) => d + allNT[i]));
  const pad = Math.max((rawMax - rawMin) * 0.15, 0.05);
  const yMin = rawMin - pad;
  const yMax = rawMax + pad;
  const yRange = yMax - yMin;

  const toX = (i: number) => PL + (n === 1 ? chartW / 2 : (i / (n - 1)) * chartW);
  const toY = (v: number) => PT + chartH - ((v - yMin) / yRange) * chartH;

  // Zero line Y
  const zeroY = toY(0);

  // Step path (horizontal segments between adjacent points)
  let stepPath = "";
  for (let i = 0; i < n; i++) {
    const x = toX(i);
    const y = toY(points[i].success_delta ?? 0);
    if (i === 0) {
      stepPath += `M ${x},${y}`;
    } else {
      const prevX = toX(i - 1);
      stepPath += ` H ${x} V ${y}`;
    }
  }

  // Y-axis labels
  const yTicks = [-0.4, -0.2, 0, 0.2, 0.4].filter((t) => t >= yMin && t <= yMax);

  // Verdict colors
  const verdictStroke: Record<VerdictLabel, string> = {
    positive:       "var(--verdict-positive-fg)",
    negative:       "var(--verdict-negative-fg)",
    "within-noise": "var(--text-tertiary)",
    refused:        "var(--text-tertiary)",
  };

  // Text-alternative summary
  const latest = evals[0];
  const textSummary = `${n} evaluation${n === 1 ? "" : "s"} shown. Latest: ${VERDICT_WORD[latest.verdict]}, delta ${
    latest.success_delta !== null ? ((latest.success_delta * 100).toFixed(1) + " pp") : "N/A"
  }, noise ±${(noiseThreshold(latest.success_stddev, latest.n_tasks) * 100).toFixed(1)} pp.`;

  const band = chartW / Math.max(n, 1);
  const hp = hover !== null ? points[hover] : null;
  const hpNt = hp ? noiseThreshold(hp.success_stddev, hp.n_tasks) : 0;

  return (
    <InstrumentCard lift={false} glow className="p-4 sm:p-5">
      <div className="relative" role="img" aria-label={textSummary}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full select-none"
          aria-hidden="true"
          style={{ maxHeight: 300 }}
        >
          {/* Y-axis gridlines */}
          {yTicks.map((t) => (
            <line key={t} x1={PL} y1={toY(t)} x2={W - PR} y2={toY(t)} stroke="var(--border-hairline)" strokeWidth="1" shapeRendering="crispEdges" />
          ))}

          {/* Zero baseline — dashed */}
          <line x1={PL} y1={zeroY} x2={W - PR} y2={zeroY} stroke="var(--text-tertiary)" strokeWidth="1" strokeDasharray="4 4" shapeRendering="crispEdges" />

          {/* Crosshair on hover */}
          {hover !== null && (
            <line x1={toX(hover)} y1={PT} x2={toX(hover)} y2={H - PB} stroke="var(--accent-signal)" strokeWidth="1" strokeDasharray="3 3" opacity="0.7" />
          )}

          {/* Step path — draws in (flat data draws flat); reduced motion renders complete */}
          <motion.path
            d={stepPath}
            fill="none"
            stroke="var(--accent-signal)"
            strokeWidth="1.5"
            strokeLinejoin="round"
            initial={reduce ? { pathLength: 1, opacity: 1 } : { pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: reduce ? 0 : 0.7, ease: [0.16, 1, 0.3, 1] }}
          />

          {/* Error bars + dots — points fade in progressively, focus on hover */}
          {points.map((p, i) => {
            const x = toX(i);
            const y = toY(p.success_delta ?? 0);
            const nt = noiseThreshold(p.success_stddev, p.n_tasks);
            const yLo = toY((p.success_delta ?? 0) - nt);
            const yHi = toY((p.success_delta ?? 0) + nt);
            const stroke = verdictStroke[p.verdict];
            const focused = hover === i;
            const dim = hover !== null && !focused;

            return (
              <motion.g
                key={p.id}
                initial={reduce ? { opacity: 1 } : { opacity: 0 }}
                animate={{ opacity: dim ? 0.4 : 1 }}
                transition={{ duration: reduce ? 0 : 0.3, delay: reduce ? 0 : 0.5 + i * 0.06 }}
              >
                <line x1={x} y1={yHi} x2={x} y2={yLo} stroke="var(--text-tertiary)" strokeWidth="1" strokeDasharray="2 2" />
                <line x1={x - 4} y1={yHi} x2={x + 4} y2={yHi} stroke="var(--text-tertiary)" strokeWidth="1" />
                <line x1={x - 4} y1={yLo} x2={x + 4} y2={yLo} stroke="var(--text-tertiary)" strokeWidth="1" />
                <circle cx={x} cy={y} r={focused ? 6 : 4} fill={focused ? stroke : "var(--surface-base)"} stroke={stroke} strokeWidth="2" style={{ transition: "r .15s" }} />
              </motion.g>
            );
          })}

          {/* Y axis labels */}
          {yTicks.map((t) => (
            <text key={t} x={PL - 6} y={toY(t) + 4} textAnchor="end" fontSize="9" fontFamily="var(--font-geist-mono)" fill="var(--text-tertiary)">
              {t > 0 ? `+${(t * 100).toFixed(0)}` : (t * 100).toFixed(0)}
            </text>
          ))}

          {/* X axis labels */}
          {points.map((p, i) => (
            <text key={p.id} x={toX(i)} y={H - 6} textAnchor="middle" fontSize="9" fontFamily="var(--font-geist-mono)" fill={hover === i ? "var(--text-secondary)" : "var(--text-tertiary)"}>
              #{p.id}
            </text>
          ))}

          <text x={PL - 6} y={PT - 6} textAnchor="end" fontSize="9" fontFamily="var(--font-geist-mono)" fill="var(--text-tertiary)">pp</text>

          {/* Invisible hit areas */}
          {points.map((p, i) => (
            <rect
              key={`hit-${p.id}`}
              x={toX(i) - band / 2}
              y={PT}
              width={band}
              height={chartH}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              style={{ cursor: "crosshair" }}
            />
          ))}
        </svg>

        {/* Premium tooltip — real numbers, including ugly ones */}
        {hp && (
          <div
            className="pointer-events-none absolute z-10 rounded-md border border-[var(--border-strong)] bg-[var(--surface-raised)]/95 backdrop-blur-md shadow-card-hover px-3 py-2 -translate-x-1/2 -translate-y-[115%]"
            style={{ left: `${(toX(hover!) / W) * 100}%`, top: `${(toY(hp.success_delta ?? 0) / H) * 100}%` }}
          >
            <div className="flex items-center gap-2 mb-1">
              <VerdictBadge verdict={hp.verdict} size="sm" />
              <span className="t-data text-[10px] text-[var(--text-tertiary)]">#{hp.id}</span>
            </div>
            <div className="t-data text-xs text-[var(--text-primary)] whitespace-nowrap">
              {hp.success_delta !== null
                ? `${hp.success_delta > 0 ? "+" : ""}${(hp.success_delta * 100).toFixed(1)} pp`
                : "N/A"}
              <span className="text-[var(--text-tertiary)]"> ± {(hpNt * 100).toFixed(1)} pp</span>
            </div>
            <div className="t-caption mt-0.5 whitespace-nowrap">{formatDate(hp.created_at)}</div>
          </div>
        )}
      </div>

      {/* Text alt */}
      <p className="t-caption mt-3">
        {textSummary} No interpolation — each point is a discrete evaluation.
      </p>
    </InstrumentCard>
  );
}

// ─── VerdictDistribution ─────────────────────────────────────────────────────

function VerdictDistribution({ evals }: { evals: EvaluationSummary[] }) {
  const counts: Record<VerdictLabel, number> = {
    positive: 0, negative: 0, "within-noise": 0, refused: 0,
  };
  for (const e of evals) counts[e.verdict]++;

  const total = evals.length;
  const entries = (Object.entries(counts) as [VerdictLabel, number][]).filter(([, n]) => n > 0);

  return (
    <div className="reveal-on-scroll">
      <h2 className="t-eyebrow mb-3">
        Verdict distribution ({total} evaluation{total === 1 ? "" : "s"})
      </h2>
      <div className="flex flex-col gap-2">
        {entries.map(([verdict, count]) => (
          <div key={verdict} className="flex items-center gap-3">
            <VerdictBadge verdict={verdict} size="sm" />
            <div className="flex-1 h-2 bg-[var(--surface-raised)] rounded-full overflow-hidden">
              <motion.div
                className={{
                  positive:       "h-full origin-left bg-[var(--verdict-positive-fg)]",
                  negative:       "h-full origin-left bg-[var(--verdict-negative-fg)]",
                  "within-noise": "h-full origin-left bg-[var(--text-tertiary)]",
                  refused:        "h-full origin-left bg-[var(--border-strong)]",
                }[verdict]}
                style={{ width: `${(count / total) * 100}%` }}
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              />
            </div>
            <span className="t-data text-xs text-[var(--text-tertiary)] w-8 text-right">{count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── ConditionsPanel ──────────────────────────────────────────────────────────

function ConditionsPanel({ evals }: { evals: EvaluationSummary[] }) {
  const providerModels = [...new Set(evals.map((e) => `${e.provider}/${e.model}`))];
  const egresses = [...new Set(evals.map((e) => e.egress_enforced ? "enforced" : "open"))];
  const changed = providerModels.length > 1 || egresses.length > 1;

  return (
    <InstrumentCard lift={false} glow className="px-5 py-4 reveal-on-scroll">
      <h2 className="t-eyebrow mb-3">Measurement conditions</h2>
      <div className="flex flex-col gap-1.5">
        <p className="t-data text-xs text-[var(--text-secondary)]">
          Provider/model: {providerModels.join(", ")}
        </p>
        <p className="t-data text-xs text-[var(--text-secondary)]">
          Egress: {egresses.join(", ")}
        </p>
        {changed && (
          <p className="t-data text-xs text-[var(--warning-fg)] mt-1">
            ⚠ Conditions changed across history — verdicts may not be directly comparable.
          </p>
        )}
      </div>
    </InstrumentCard>
  );
}

// ─── TrendsView ──────────────────────────────────────────────────────────────

export function TrendsView({ data }: { data: RepositoryData }) {
  const evals = data.evaluations; // newest-first from export
  const latest  = evals[0];
  const previous = evals[1] ?? null;

  const smallSample = evals.length < 3;

  return (
    <div className="flex flex-col gap-10">
      {/* Step chart */}
      <DeltaStepChart evals={evals} />

      {/* Small-sample note */}
      {smallSample && (
        <p className="t-lead">History builds as you run more evaluations.</p>
      )}

      {/* Latest-vs-previous delta */}
      {previous && (
        <div className="border border-[var(--border-hairline)] rounded-card bg-[var(--surface-elevated)] shadow-card px-5 py-4 reveal-on-scroll">
          <h2 className="t-eyebrow mb-3">Latest vs previous</h2>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <p className="t-eyebrow mb-1.5">Previous #{previous.id}</p>
              <VerdictBadge verdict={previous.verdict} size="sm" />
              <p className="t-data text-xs text-[var(--text-secondary)] mt-1.5">
                {previous.success_delta !== null
                  ? `${previous.success_delta > 0 ? "+" : ""}${(previous.success_delta * 100).toFixed(1)} pp`
                  : "N/A"}
                {" "}±{(noiseThreshold(previous.success_stddev, previous.n_tasks) * 100).toFixed(1)} pp
              </p>
            </div>
            <div>
              <p className="t-eyebrow mb-1.5">Latest #{latest.id}</p>
              <VerdictBadge verdict={latest.verdict} size="sm" />
              <p className="t-data text-xs text-[var(--text-secondary)] mt-1.5">
                {latest.success_delta !== null
                  ? `${latest.success_delta > 0 ? "+" : ""}${(latest.success_delta * 100).toFixed(1)} pp`
                  : "N/A"}
                {" "}±{(noiseThreshold(latest.success_stddev, latest.n_tasks) * 100).toFixed(1)} pp
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Verdict distribution */}
      <VerdictDistribution evals={evals} />

      {/* Conditions panel */}
      <ConditionsPanel evals={evals} />
    </div>
  );
}
