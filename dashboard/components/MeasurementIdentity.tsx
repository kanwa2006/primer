"use client";

import { motion } from "motion/react";
import { shortenCommit, formatDate } from "@/lib/format";
import type { DashboardData } from "@/lib/types";

const AGENT_DISPLAY: Record<string, string> = {
  claude_code: "Claude Code",
  codex: "Codex",
  gemini_code: "Gemini Code",
  openrouter: "OpenRouter",
};

function formatAgent(adapter: string): string {
  return AGENT_DISPLAY[adapter] ?? adapter.replace(/_/g, " ");
}

function Chip({ label, value }: { label: string; value: string }) {
  return (
    <div className="inline-flex items-center gap-2 border border-zinc-200 rounded-md px-3 py-1.5 bg-white">
      <span className="text-zinc-400 text-[10px] font-mono uppercase tracking-widest leading-none">
        {label}
      </span>
      <span className="text-zinc-700 text-xs font-mono font-medium leading-none">
        {value}
      </span>
    </div>
  );
}

interface Props {
  data: DashboardData;
}

export function MeasurementIdentity({ data }: Props) {
  const { agent_adapter, n_tasks, runs_per_config, repo_commit, created_at } = data;

  return (
    <motion.div
      className="flex flex-col gap-5"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
    >
      {/* Primary statement */}
      <p className="text-zinc-900 text-lg font-medium leading-snug max-w-[52ch]">
        Measured the effect of a repository context file on AI agent task
        success.
      </p>

      {/* Comparison block */}
      <div
        className="border border-zinc-200 rounded-lg bg-zinc-50/60"
        role="region"
        aria-label="Measurement comparison: without vs with context file"
      >
        {/* Desktop: side-by-side grid */}
        <div className="hidden sm:grid sm:grid-cols-[1fr_56px_1fr]">
          {/* WITHOUT arm */}
          <div className="flex flex-col gap-1.5 px-5 py-4">
            <span className="text-zinc-800 text-sm font-mono font-semibold tracking-tight">
              WITHOUT context file
            </span>
            <span className="text-zinc-500 text-xs leading-relaxed">
              No context file present in /work
            </span>
          </div>

          {/* VS divider — vertical */}
          <div className="flex flex-col items-center justify-center gap-1.5 py-4 border-x border-zinc-200">
            <div className="w-px flex-1 bg-zinc-200" />
            <span className="text-zinc-400 text-[10px] font-mono uppercase tracking-widest px-1">
              vs
            </span>
            <div className="w-px flex-1 bg-zinc-200" />
          </div>

          {/* WITH arm */}
          <div className="flex flex-col gap-1.5 px-5 py-4">
            <span className="text-zinc-800 text-sm font-mono font-semibold tracking-tight">
              WITH context file
            </span>
            <span className="text-zinc-500 text-xs leading-relaxed">
              Context file present in /work
            </span>
          </div>
        </div>

        {/* Mobile: stacked */}
        <div className="sm:hidden flex flex-col">
          <div className="flex flex-col gap-1.5 px-4 py-3.5">
            <span className="text-zinc-800 text-sm font-mono font-semibold tracking-tight">
              WITHOUT context file
            </span>
            <span className="text-zinc-500 text-xs leading-relaxed">
              No context file present in /work
            </span>
          </div>

          {/* VS divider — horizontal */}
          <div className="flex items-center gap-3 px-4 py-2 border-y border-zinc-200 bg-zinc-100/50">
            <div className="flex-1 h-px bg-zinc-200" />
            <span className="text-zinc-400 text-[10px] font-mono uppercase tracking-widest">
              vs
            </span>
            <div className="flex-1 h-px bg-zinc-200" />
          </div>

          <div className="flex flex-col gap-1.5 px-4 py-3.5">
            <span className="text-zinc-800 text-sm font-mono font-semibold tracking-tight">
              WITH context file
            </span>
            <span className="text-zinc-500 text-xs leading-relaxed">
              Context file present in /work
            </span>
          </div>
        </div>
      </div>

      {/* Identity chips */}
      <div className="flex flex-wrap gap-2">
        <Chip label="Agent" value={formatAgent(agent_adapter)} />
        <Chip
          label="Tasks"
          value={`${n_tasks} · ${runs_per_config} runs/config`}
        />
      </div>

      {/* Secondary provenance row */}
      <p className="text-zinc-400 text-xs font-mono">
        commit {shortenCommit(repo_commit)} · evaluated {formatDate(created_at)}
      </p>
    </motion.div>
  );
}
