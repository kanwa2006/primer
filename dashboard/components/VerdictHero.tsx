"use client";

import { motion } from "motion/react";
import { TrendingUp, TrendingDown, Minus, Ban } from "lucide-react";
import { DeltaCountUp } from "@/components/DeltaCountUp";
import { InstrumentCard } from "@/components/InstrumentCard";
import { noiseThreshold, verdictTextClass, VERDICT_WORD } from "@/lib/verdict";
import type { DashboardData, VerdictLabel } from "@/lib/types";

// ─── Interpretation copy (spec §13.4) ────────────────────────────────────────

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
      return "PRIMER won't compute a delta here: the two runs used different models, so any difference couldn't be attributed to the context file. This is by design — check the warnings above.";
  }
}

const ICONS = {
  positive:       TrendingUp,
  negative:       TrendingDown,
  "within-noise": Minus,
  refused:        Ban,
} as const;

// ─── Confidence Ruler — the signature instrument (caliper) ───────────────────

interface ConfidenceRulerProps {
  delta: number;
  noiseThresholdProp: number;
  verdict: VerdictLabel;
}

function ConfidenceRuler({ delta, noiseThresholdProp, verdict }: ConfidenceRulerProps) {
  const absDelta = Math.abs(delta);
  const range = Math.max(noiseThresholdProp * 2.8, absDelta * 1.5, 0.2);
  const toPct = (x: number) =>
    Math.min(98, Math.max(2, ((x + range) / (2 * range)) * 100));

  const noiseL  = toPct(-noiseThresholdProp);
  const noiseR  = toPct(noiseThresholdProp);
  const zeroPct = toPct(0);
  const dotPct  = toPct(delta);
  const threshPp   = (noiseThresholdProp * 100).toFixed(1);
  const absDeltaPp = (absDelta * 100).toFixed(1);
  const sign = delta > 0 ? "+" : delta < 0 ? "−" : "";

  const dotColor =
    verdict === "positive" ? "var(--verdict-positive-fg)" :
    verdict === "negative" ? "var(--verdict-negative-fg)" :
    "var(--verdict-noise-fg)";

  const caption =
    verdict === "within-noise"
      ? `Delta ${sign}${absDeltaPp} pp falls inside the noise envelope (±${threshPp} pp)`
      : `Delta ${sign}${absDeltaPp} pp  ·  noise envelope ±${threshPp} pp`;

  // Engraved tick array — minor ticks across the scale, majors at 0 and ±threshold.
  const N = 32;
  const ticks = Array.from({ length: N + 1 }, (_, i) => {
    const pct = (i / N) * 100;
    // distance (in pct) to a labelled major position
    const nearMajor =
      Math.abs(pct - zeroPct) < 0.8 ||
      Math.abs(pct - noiseL) < 0.8 ||
      Math.abs(pct - noiseR) < 0.8;
    return { pct, nearMajor };
  });

  return (
    <figure className="flex flex-col gap-2.5 m-0" role="img" aria-label={caption}>
      {/* Machined caliper panel — recessed track, engraved scale */}
      <div
        className="relative rounded-md border border-[var(--border-hairline)] bg-[var(--surface-base)] px-4 pt-5 pb-4"
        style={{ boxShadow: "var(--ruler-recess)" }}
        aria-hidden="true"
      >
        <div className="relative h-12">
          {/* Engraved ticks — theme-tuned tokens keep depth in both modes */}
          {ticks.map(({ pct, nearMajor }, i) => (
            <span
              key={i}
              className="absolute top-0 w-px"
              style={{
                left: `${pct}%`,
                height: nearMajor ? 16 : 9,
                background: nearMajor ? "var(--ruler-tick-major)" : "var(--ruler-tick)",
              }}
            />
          ))}

          {/* Active measurement zone — the noise envelope, expands from zero */}
          <motion.div
            className="absolute top-0 h-4 rounded-[3px]"
            style={{
              left: `${noiseL}%`,
              width: `${noiseR - noiseL}%`,
              transformOrigin: "center",
              background:
                "linear-gradient(180deg, var(--accent-glow), transparent), var(--surface-raised)",
              borderLeft: "1px solid var(--accent-signal)",
              borderRight: "1px solid var(--accent-signal)",
              opacity: 0.9,
            }}
            initial={{ scaleX: 0, opacity: 0 }}
            animate={{ scaleX: 1, opacity: 0.9 }}
            transition={{ duration: 0.5, delay: 0.12, ease: [0.32, 0.72, 0, 1] }}
          />

          {/* Zero datum line */}
          <div
            className="absolute top-[-2px] w-px h-[22px] bg-[var(--text-secondary)]"
            style={{ left: `${zeroPct}%`, opacity: 0.6 }}
          />

          {/* Caliper indicator blade — seats at the reading with a slight overshoot */}
          <motion.div
            className="absolute top-[-4px]"
            style={{ left: `${dotPct}%`, transform: "translateX(-50%)" }}
            initial={{ opacity: 0, scaleY: 0.3, y: -2 }}
            animate={{ opacity: 1, scaleY: 1, y: 0 }}
            transition={{
              duration: 0.42,
              delay: 0.34,
              ease: [0.32, 0.72, 0, 1],
            }}
          >
            <div
              className="w-px h-[26px] mx-auto"
              style={{ background: dotColor, boxShadow: `0 0 6px ${dotColor}` }}
            />
            <motion.div
              className="w-3 h-3 rounded-full mx-auto -mt-[7px] ring-2 ring-[var(--surface-base)]"
              style={{ background: dotColor, boxShadow: `0 0 10px ${dotColor}55` }}
              initial={{ scale: 0 }}
              animate={{ scale: [0, 1.18, 1] }}
              transition={{ duration: 0.3, delay: 0.46, ease: [0.32, 0.72, 0, 1] }}
            />
          </motion.div>
        </div>
      </div>

      {/* Scale labels */}
      <div className="relative h-4 select-none" aria-hidden="true">
        <span className="absolute t-data text-[10px] text-[var(--text-tertiary)] -translate-x-1/2"
          style={{ left: `${Math.max(6, noiseL)}%` }}>−{threshPp}</span>
        <span className="absolute t-data text-[10px] text-[var(--text-secondary)] -translate-x-1/2"
          style={{ left: `${zeroPct}%` }}>0</span>
        <span className="absolute t-data text-[10px] text-[var(--text-tertiary)] -translate-x-1/2"
          style={{ left: `${Math.min(94, noiseR)}%` }}>+{threshPp}</span>
      </div>

      <figcaption className="t-data text-[11px] text-[var(--text-tertiary)] leading-snug">
        {caption}
      </figcaption>
    </figure>
  );
}

// ─── VerdictHero ─────────────────────────────────────────────────────────────

interface VerdictHeroProps {
  data: DashboardData;
}

export function VerdictHero({ data }: VerdictHeroProps) {
  const { verdict, success_delta, n_tasks, success_stddev, runs_per_config } = data;
  const nt = noiseThreshold(success_stddev, n_tasks);
  const showRuler = verdict !== "refused" && success_delta !== null;
  const v = verdict as VerdictLabel;
  const Icon = ICONS[v];

  return (
    <InstrumentCard
      lift={false}
      glow
      role="region"
      aria-label={`Verdict: ${VERDICT_WORD[v]}`}
      className="flex flex-col gap-6 px-6 sm:px-8 py-8 sm:py-10 backdrop-blur-xl bg-[var(--surface-elevated)]/75 shadow-hero"
    >
      <div className="flex flex-col gap-3">
        {/* Verdict word + icon */}
        <motion.span
          className={`flex items-center gap-2 t-h3 ${verdictTextClass(v)}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, delay: 0.04, ease: [0.16, 1, 0.3, 1] }}
        >
          <Icon size={20} strokeWidth={1.75} aria-hidden />
          {VERDICT_WORD[v]}
        </motion.span>

        {/* Delta — the instrument readout */}
        <motion.div
          className="t-data text-6xl sm:text-7xl md:text-8xl font-semibold tracking-tight leading-none"
          aria-label={`Success delta: ${success_delta !== null ? (success_delta * 100).toFixed(1) : "N/A"} percentage points`}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.32, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
        >
          <DeltaCountUp delta={success_delta} className={verdictTextClass(v)} />
        </motion.div>
        <span className="t-caption">pp = percentage points</span>
      </div>

      {/* Interpretation */}
      <p className="t-body text-[var(--text-secondary)] max-w-[62ch]">
        {interpretationCopy(v, success_delta)}
      </p>

      {/* Confidence Ruler — the optical center */}
      {showRuler && (
        <ConfidenceRuler delta={success_delta!} noiseThresholdProp={nt} verdict={v} />
      )}

      {/* Measurement footer */}
      <p className="t-data text-[11px] text-[var(--text-tertiary)]">
        {verdict !== "refused"
          ? `n=${n_tasks} tasks · ${runs_per_config} runs/config · σ ±${(success_stddev * 100).toFixed(3)} pp`
          : `n=${n_tasks} tasks · ${runs_per_config} runs/config`}
      </p>
    </InstrumentCard>
  );
}
