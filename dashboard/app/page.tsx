"use client";

import { useEffect, useState, useReducer } from "react";
import { motion } from "motion/react";
import { EmptyState } from "@/components/EmptyState";
import { MeasurementIdentity } from "@/components/MeasurementIdentity";
import { TrustArchitecture } from "@/components/TrustArchitecture";
import { VerdictHero } from "@/components/VerdictHero";
import { MetricsGrid } from "@/components/MetricsGrid";
import { TaskFlipTable } from "@/components/TaskFlipTable";
import { WarningBanner } from "@/components/WarningBanner";
import { ProvenanceFooter } from "@/components/ProvenanceFooter";
import type { DashboardData } from "@/lib/types";

type State =
  | { status: "loading" }
  | { status: "empty" }
  | { status: "error"; message: string }
  | { status: "ok"; data: DashboardData };

export default function Home() {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/data.json`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json: DashboardData) => {
        if (!json || typeof json !== "object" || !("schema_version" in json)) {
          setState({ status: "empty" });
          return;
        }
        setState({ status: "ok", data: json });
      })
      .catch(() => setState({ status: "empty" }));
  }, []);

  return (
    <div className="min-h-[100dvh] bg-white">
      <main className="max-w-5xl mx-auto px-6 py-10">
        {state.status === "loading" && (
          <div className="flex items-center justify-center min-h-[60vh]">
            <div className="text-zinc-400 text-xs font-mono animate-pulse">
              Loading…
            </div>
          </div>
        )}

        {(state.status === "empty" || state.status === "error") && (
          <EmptyState />
        )}

        {state.status === "ok" && (
          <motion.div
            className="flex flex-col gap-12"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
          >
            {/* Warnings — critical integrity flags first */}
            <WarningBanner
              providerMismatch={state.data.provider_mismatch_warning}
              isolationMismatch={state.data.isolation_mismatch_warning}
              flakyTask={state.data.flaky_task_warning}
            />

            {/* Primary verdict — the answer */}
            <VerdictHero data={state.data} />

            {/* Measurement identity — what was measured, by whom, how */}
            <MeasurementIdentity data={state.data} />

            {/* Trust architecture — why the result is credible */}
            <TrustArchitecture data={state.data} />

            {/* Metrics grid */}
            <MetricsGrid data={state.data} />

            {/* Per-task flip table */}
            <TaskFlipTable tasks={state.data.per_task} />

            {/* Provenance */}
            <ProvenanceFooter data={state.data} />
          </motion.div>
        )}
      </main>

    </div>
  );
}
