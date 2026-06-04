"use client";

import { motion } from "motion/react";
import { verdictWord, verdictIcon } from "@/lib/format";
import type { DashboardData, VerdictLabel } from "@/lib/types";

// ─── Display maps (all logic local per B.3 spec) ─────────────────────────────

function formatHeroDelta(delta: number | null): string {
  if (delta === null) return "N/A";
  const pp = (delta * 100).toFixed(1);
  if (delta > 0) return `+${pp} pp`;
  return `${pp} pp`;
}

function interpretationCopy(verdict: VerdictLabel, delta: number | null): string {
  switch (verdict) {
    case "positive":
      return "Context file improved agent success rate beyond measurement noise.";
    case "negative":
      return "Context file reduced agent success rate beyond measurement noise.";
    case "within-noise": {
      const ppNote =
        delta !== null
          ? `(${delta > 0 ? "+" : ""}${(delta * 100).toFixed(1)} pp) `
          : "";
      return (
        `We ran the measurement. The delta ${ppNote}is real but can't yet be ` +
        `distinguished from natural variance at this task count. ` +
        `You're protected from acting on noise.`
      );
    }
    case "refused":
      return "Provider or model mismatch across compared runs — delta refused. Check the warnings above.";
  }
}

// ─── Per-verdict class helpers ────────────────────────────────────────────────

function leftBorderClass(v: VerdictLabel): string {
  if (v === "positive") return "border-l-positive";
  if (v === "negative") return "border-l-negative";
  return "border-l-zinc-300";
}

function cardBgClass(v: VerdictLabel): string {
  if (v === "positive") return "bg-positive/10";
  if (v === "negative") return "bg-negative/10";
  return "bg-zinc-50";
}

function headingTextClass(v: VerdictLabel): string {
  if (v === "positive") return "text-emerald-700";
  if (v === "negative") return "text-red-700";
  return "text-zinc-500";
}

function deltaTextClass(v: VerdictLabel): string {
  if (v === "positive") return "text-emerald-700";
  if (v === "negative") return "text-red-700";
  if (v === "within-noise") return "text-zinc-700";
  return "text-zinc-500";
}

// ─── Confidence Ruler ────────────────────────────────────────────────────────

interface ConfidenceRulerProps {
  delta: number;          // proportion — e.g. 0.18 means 18 pp
  noiseThreshold: number; // proportion — e.g. 0.20 means 20 pp
  verdict: VerdictLabel;
}

function ConfidenceRuler({ delta, noiseThreshold, verdict }: ConfidenceRulerProps) {
  const absDelta = Math.abs(delta);

  // Range in proportion space — always shows noise zone comfortably; delta never clips
  const range = Math.max(noiseThreshold * 2.8, absDelta * 1.5, 0.20);

  // Proportion value → 0–100% position on the bar, clamped away from edges
  const toPct = (x: number) =>
    Math.min(97, Math.max(3, ((x + range) / (2 * range)) * 100));

  const noiseL  = toPct(-noiseThreshold);
  const noiseR  = toPct(noiseThreshold);
  const zeroPct = toPct(0);
  const dotPct  = toPct(delta);

  const threshPp  = (noiseThreshold * 100).toFixed(1);
  const absDeltaPp = (absDelta * 100).toFixed(1);
  const sign = delta > 0 ? "+" : delta < 0 ? "−" : "";

  const dotBgClass =
    verdict === "positive" ? "bg-positive" :
    verdict === "negative" ? "bg-negative" :
    "bg-zinc-500";

  const caption =
    verdict === "within-noise"
      ? `Delta ${sign}${absDeltaPp} pp falls inside the noise envelope (±${threshPp} pp)`
      : `Delta ${sign}${absDeltaPp} pp  ·  noise envelope ±${threshPp} pp`;

  return (
    <div
      className="flex flex-col gap-2 pt-1"
      role="img"
      aria-label={caption}
    >
      {/* Track */}
      <div className="relative h-7 flex items-center" aria-hidden="true">
        {/* Base track */}
        <div className="w-full h-1.5 rounded-full bg-zinc-200 relative overflow-hidden">
          {/* Noise band — draws in from centre (same timing regardless of verdict) */}
          <motion.div
            className="absolute inset-y-0 bg-zinc-300/80"
            style={{ left: `${noiseL}%` }}
            initial={{ width: "0%" }}
            animate={{ width: `${noiseR - noiseL}%` }}
            transition={{ duration: 0.32, delay: 0.12, ease: [0.16, 1, 0.3, 1] }}
          />
        </div>

        {/* Zero tick */}
        <div
          className="absolute h-4 w-px bg-zinc-400/60"
          style={{ left: `${zeroPct}%` }}
        />

        {/* Delta marker — outer div positions, inner motion.div animates */}
        <div
          className="absolute"
          style={{ left: `${dotPct}%`, transform: "translateX(-50%)" }}
        >
          <motion.div
            className={`w-3 h-3 rounded-full ${dotBgClass} ring-2 ring-white shadow-sm`}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.32, delay: 0.30, ease: [0.16, 1, 0.3, 1] }}
          />
        </div>
      </div>

      {/* Axis labels */}
      <div className="relative h-4 select-none" aria-hidden="true">
        <span
          className="absolute text-[10px] font-mono text-zinc-400 -translate-x-1/2"
          style={{ left: `${Math.max(7, noiseL)}%` }}
        >
          −{threshPp}pp
        </span>
        <span
          className="absolute text-[10px] font-mono text-zinc-400 -translate-x-1/2"
          style={{ left: `${zeroPct}%` }}
        >
          0
        </span>
        <span
          className="absolute text-[10px] font-mono text-zinc-400 -translate-x-1/2"
          style={{ left: `${Math.min(93, noiseR)}%` }}
        >
          +{threshPp}pp
        </span>
      </div>

      {/* Caption */}
      <p className="text-[11px] font-mono text-zinc-400 leading-snug">
        {caption}
      </p>
    </div>
  );
}

// ─── VerdictHero ─────────────────────────────────────────────────────────────

interface VerdictHeroProps {
  data: DashboardData;
}

export function VerdictHero({ data }: VerdictHeroProps) {
  const { verdict, success_delta, n_tasks, success_stddev, runs_per_config } = data;
  const noiseThreshold = Math.max(1 / n_tasks, success_stddev);
  const showRuler = verdict !== "refused" && success_delta !== null;
  const v = verdict as VerdictLabel;

  return (
    <motion.div
      className={`relative flex flex-col gap-5 rounded-lg border border-zinc-200 border-l-4 px-6 sm:px-8 py-8 sm:py-10 ${leftBorderClass(v)} ${cardBgClass(v)}`}
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      role="region"
      aria-label={`Verdict: ${verdictWord(v)}`}
    >
      {/* Verdict word + icon (word-first, never color-alone) + delta — staggered reveal */}
      <div className="flex flex-col gap-2">
        {/* Word + icon: first in at delay 0 — identical timing regardless of verdict */}
        <motion.span
          className={`flex items-center gap-2 text-lg sm:text-xl font-semibold tracking-tight ${headingTextClass(v)}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, delay: 0.04, ease: [0.16, 1, 0.3, 1] }}
        >
          <span aria-hidden="true">{verdictIcon(v)}</span>
          {verdictWord(v)}
        </motion.span>

        {/* Delta number: enters just after the word */}
        <motion.span
          className={`text-6xl sm:text-7xl md:text-8xl font-mono font-semibold tracking-tight leading-none whitespace-nowrap ${deltaTextClass(v)}`}
          aria-label={`Success delta: ${formatHeroDelta(success_delta)} percentage points`}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.32, delay: 0.10, ease: [0.16, 1, 0.3, 1] }}
        >
          {formatHeroDelta(success_delta)}
        </motion.span>
        <span className="text-xs font-mono text-zinc-500">pp = percentage points</span>
      </div>

      {/* Interpretation */}
      <p className="text-sm text-zinc-600 leading-relaxed max-w-[62ch]">
        {interpretationCopy(v, success_delta)}
      </p>

      {/* Confidence ruler */}
      {showRuler && (
        <ConfidenceRuler
          delta={success_delta!}
          noiseThreshold={noiseThreshold}
          verdict={v}
        />
      )}

      {/* Measurement confidence footer */}
      <p className="text-[11px] font-mono text-zinc-400">
        {verdict !== "refused"
          ? `n=${n_tasks} tasks · ${runs_per_config} runs/config · σ=±${(success_stddev * 100).toFixed(3)} pp`
          : `n=${n_tasks} tasks · ${runs_per_config} runs/config`}
      </p>
    </motion.div>
  );
}
