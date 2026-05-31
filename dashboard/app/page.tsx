"use client";

import { useEffect, useState, useReducer } from "react";
import { motion } from "motion/react";
import { EmptyState } from "@/components/EmptyState";
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
    fetch("/data.json")
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
    <div className="min-h-[100dvh] bg-zinc-950">
      {/* Nav bar */}
      <header className="border-b border-zinc-800 sticky top-0 z-10 bg-zinc-950/95 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm font-semibold text-zinc-100 tracking-tight">
              PRIMER
            </span>
            <span className="text-zinc-700 text-xs font-mono">scorecard</span>
          </div>

          {state.status === "ok" && (
            <span className="text-zinc-600 text-xs font-mono hidden sm:block">
              {state.data.repo_commit.slice(0, 8)}
            </span>
          )}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10">
        {state.status === "loading" && (
          <div className="flex items-center justify-center min-h-[60vh]">
            <div className="text-zinc-600 text-xs font-mono animate-pulse">
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
            {/* Warnings — always first if present */}
            <WarningBanner
              providerMismatch={state.data.provider_mismatch_warning}
              isolationMismatch={state.data.isolation_mismatch_warning}
              flakyTask={state.data.flaky_task_warning}
            />

            {/* Primary verdict */}
            <VerdictHero data={state.data} />

            {/* Metrics grid */}
            <MetricsGrid data={state.data} />

            {/* Per-task flip table */}
            <TaskFlipTable tasks={state.data.per_task} />

            {/* Provenance */}
            <ProvenanceFooter data={state.data} />
          </motion.div>
        )}
      </main>

      <footer className="border-t border-zinc-900 mt-16">
        <div className="max-w-5xl mx-auto px-6 py-6 flex items-center justify-between">
          <span className="text-zinc-700 text-xs font-mono">
            PRIMER — Every context-file tool generates. PRIMER measures.
          </span>
          <a
            href="https://github.com/kanwa2006/primer"
            target="_blank"
            rel="noopener noreferrer"
            className="text-zinc-700 hover:text-zinc-500 text-xs font-mono transition-colors duration-150"
            aria-label="PRIMER on GitHub"
          >
            GitHub
          </a>
        </div>
      </footer>
    </div>
  );
}
