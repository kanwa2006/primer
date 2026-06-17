"use client";

import { motion } from "motion/react";
import { GraticuleBg } from "@/components/GraticuleBg";
import { InstrumentCard } from "@/components/InstrumentCard";
import { VerdictBadge } from "@/components/VerdictBadge";
import { DeltaCountUp } from "@/components/DeltaCountUp";
import { noiseThreshold } from "@/lib/verdict";
import type { RepositoryData } from "@/lib/types";

interface HeroBandProps {
  data: RepositoryData;
}

const ease = [0.16, 1, 0.3, 1] as const;

export function HeroBand({ data }: HeroBandProps) {
  const latest = data.evaluations[0] ?? null;
  const verdict = data.latest_verdict;

  return (
    <InstrumentCard
      lift={false}
      glow
      className="rounded-hero overflow-hidden px-6 sm:px-10 py-12 sm:py-16 backdrop-blur-2xl bg-[var(--surface-elevated)]/72 shadow-hero"
    >
      <GraticuleBg />

      <div className="relative z-10 flex flex-col gap-7 max-w-3xl">
        {/* Eyebrow — sans, not mono */}
        <motion.p
          className="t-eyebrow"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease }}
        >
          CLAUDE.md Evaluation
        </motion.p>

        {/* Thesis — the dominant element on the page */}
        <motion.h1
          className="t-display text-[var(--text-primary)]"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.05, ease }}
        >
          Does your{" "}
          <span className="t-data text-[var(--accent-signal)]">CLAUDE.md</span>{" "}
          actually help your coding agent?
        </motion.h1>

        {/* Sub — lead */}
        <motion.p
          className="t-lead max-w-[54ch]"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1, ease }}
        >
          A controlled before-and-after measurement in pinned Docker containers —
          same agent, same tasks, honest noise-envelope reporting.
        </motion.p>

        {/* Live verdict strip — proof, secondary to the thesis */}
        {verdict && latest && (
          <motion.div
            className="flex flex-wrap items-center gap-x-4 gap-y-3 pt-3 mt-1 border-t border-[var(--border-hairline)]"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.42, delay: 0.16, ease }}
          >
            <VerdictBadge verdict={verdict} size="md" />
            <span className="t-data text-3xl sm:text-4xl font-semibold tracking-tight text-[var(--text-primary)]">
              <DeltaCountUp delta={latest.success_delta} />
            </span>
            <span className="t-data text-xs text-[var(--text-tertiary)]">
              ± {(noiseThreshold(latest.success_stddev, latest.n_tasks) * 100).toFixed(1)} pp
              {" · "}n={latest.n_tasks}×{latest.runs_per_config}
              {" · "}isolated Docker
            </span>
          </motion.div>
        )}
      </div>
    </InstrumentCard>
  );
}
