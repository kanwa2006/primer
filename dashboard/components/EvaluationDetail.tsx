"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { WarningBanner } from "@/components/WarningBanner";
import { VerdictHero } from "@/components/VerdictHero";
import { TrustArchitecture } from "@/components/TrustArchitecture";
import { MetricsGrid } from "@/components/MetricsGrid";
import { TaskFlipTable } from "@/components/TaskFlipTable";
import type { DashboardData } from "@/lib/types";

interface Props {
  data: DashboardData;
  prevId: number | null;
}

export function EvaluationDetail({ data, prevId }: Props) {
  return (
    <div className="flex flex-col gap-8">
      <h1 className="sr-only">
        {data.repo.name} — Evaluation #{data.id}
      </h1>
      <div className="flex items-center justify-between">
        <Link
          href="/"
          className="text-xs font-mono text-zinc-500 hover:text-zinc-700 transition-colors duration-150"
        >
          ← All evaluations
        </Link>
        {prevId !== null && (
          <Link
            href={`/compare/?a=${prevId}&b=${data.id}`}
            className="text-xs font-mono text-zinc-500 hover:text-zinc-700 transition-colors duration-150"
          >
            Compare with previous evaluation →
          </Link>
        )}
      </div>

      <motion.div
        className="flex flex-col gap-12"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
      >
        {/* Warnings — critical integrity flags first */}
        <WarningBanner
          providerMismatch={data.provider_mismatch_warning}
          isolationMismatch={data.isolation_mismatch_warning}
          flakyTask={data.flaky_task_warning}
        />

        {/* Primary verdict — the answer */}
        <VerdictHero data={data} />

        {/* Metrics grid */}
        <MetricsGrid data={data} />

        {/* Methods credential — measurement identity, integrity & provenance (collapsible) */}
        <TrustArchitecture data={data} />

        {/* Per-task flip table */}
        <TaskFlipTable tasks={data.per_task} />
      </motion.div>
    </div>
  );
}
