"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { ChevronLeft } from "lucide-react";
import { WarningBanner } from "@/components/WarningBanner";
import { VerdictHero } from "@/components/VerdictHero";
import { InstrumentStatusBar } from "@/components/InstrumentStatusBar";
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

      {/* Breadcrumb + compare link */}
      <div className="flex items-center justify-between">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors duration-150"
        >
          <ChevronLeft size={14} strokeWidth={1.75} aria-hidden />
          All evaluations
        </Link>
        {prevId !== null && (
          <Link
            href={`/compare/?a=${prevId}&b=${data.id}`}
            className="text-[13px] font-medium text-[var(--text-tertiary)] hover:text-[var(--accent-signal)] transition-colors duration-150"
          >
            Compare with previous →
          </Link>
        )}
      </div>

      <motion.div
        className="flex flex-col gap-10"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
      >
        {/* 1. Warning banners — critical integrity flags first */}
        <WarningBanner
          providerMismatch={data.provider_mismatch_warning}
          isolationMismatch={data.isolation_mismatch_warning}
          flakyTask={data.flaky_task_warning}
        />

        {/* 2. Verdict hero — the answer */}
        <VerdictHero data={data} />

        {/* 3. Instrument Status Bar */}
        <InstrumentStatusBar
          egressEnforced={data.egress_enforced}
          networkMode={data.network_mode}
          baseImage={data.base_image}
          nTasks={data.n_tasks}
          runsPerConfig={data.runs_per_config}
          successStddev={data.success_stddev}
          agentAdapter={data.agent_adapter}
          model={data.model}
        />

        {/* 4. Metrics grid */}
        <MetricsGrid data={data} />

        {/* 5. Methods panel (collapsible) */}
        <TrustArchitecture data={data} />

        {/* 6. Per-task flip table */}
        <TaskFlipTable tasks={data.per_task} />
      </motion.div>
    </div>
  );
}
