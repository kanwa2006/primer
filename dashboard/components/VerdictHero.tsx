"use client";

import { motion } from "motion/react";
import { formatDelta, verdictColor, verdictBg } from "@/lib/format";
import type { DashboardData } from "@/lib/types";

const VERDICT_LABEL: Record<string, string> = {
  "positive":     "POSITIVE",
  "negative":     "NEGATIVE",
  "within-noise": "WITHIN NOISE",
  "refused":      "REFUSED",
};

const VERDICT_DESCRIPTION: Record<string, string> = {
  "positive":     "Context file improved agent success rate beyond measurement noise.",
  "negative":     "Context file reduced agent success rate beyond measurement noise.",
  "within-noise": "Delta is within measurement noise — not distinguishable from zero.",
  "refused":      "Provider or model mismatch across compared runs — delta refused.",
};

interface VerdictHeroProps {
  data: DashboardData;
}

export function VerdictHero({ data }: VerdictHeroProps) {
  const { verdict, success_delta, n_tasks, success_stddev } = data;
  const noiseThreshold = Math.max(1 / n_tasks, success_stddev);
  const deltaStr = formatDelta(success_delta);

  return (
    <motion.div
      className="flex flex-col items-start gap-4"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
    >
      {/* Delta number — the hero */}
      <div className="flex items-baseline gap-4 flex-wrap">
        <span
          className={`text-6xl md:text-7xl font-mono font-semibold tracking-tight leading-none ${verdictColor(verdict)}`}
          aria-label={`Success delta: ${deltaStr}`}
        >
          {deltaStr}
        </span>

        {/* Verdict badge */}
        <span
          className={`inline-flex items-center px-2.5 py-1 rounded border text-xs font-mono tracking-widest uppercase ${verdictBg(verdict)} ${verdictColor(verdict)}`}
        >
          {VERDICT_LABEL[verdict] ?? verdict}
        </span>
      </div>

      {/* Description */}
      <p className="text-zinc-600 text-sm max-w-[60ch] leading-relaxed">
        {VERDICT_DESCRIPTION[verdict] ?? ""}
      </p>

      {/* Noise threshold note */}
      {verdict !== "refused" && (
        <p className="text-zinc-500 text-xs font-mono">
          noise threshold = max(1/{n_tasks}, σ={success_stddev.toFixed(3)}) ={" "}
          {noiseThreshold.toFixed(3)}
        </p>
      )}
    </motion.div>
  );
}
