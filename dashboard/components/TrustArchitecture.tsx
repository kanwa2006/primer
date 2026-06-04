"use client";

import { motion } from "motion/react";
import { formatCost, formatPct, shortenCommit, formatDate } from "@/lib/format";
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

function Field({
  label,
  value,
  className = "text-zinc-700",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-zinc-500 text-[10px] font-mono uppercase tracking-widest leading-none">
        {label}
      </span>
      <span className={`text-xs font-mono break-all ${className}`}>{value}</span>
    </div>
  );
}

// Consolidated "Methods" credential — measurement identity, integrity, and
// provenance in one collapsible artifact (Provenance-is-the-credential, §3/§10).
// Collapsed it shows a one-line summary (never a mystery box); expanded it lets
// a developer confirm isolation / egress_enforced / provenance in one interaction.
export function TrustArchitecture({ data }: { data: DashboardData }) {
  const {
    provider,
    model,
    agent_adapter,
    network_mode,
    egress_enforced,
    base_image,
    repo_commit,
    created_at,
    n_tasks,
    runs_per_config,
    success_stddev,
    success_min,
    success_max,
    primer_overhead_usd,
    primer_overhead_confidence,
  } = data;

  const displayImage =
    base_image.length > 40 ? base_image.slice(0, 40) + "…" : base_image;

  const summary = `${formatAgent(agent_adapter)} · ${provider}/${model} · ${n_tasks} tasks × ${runs_per_config} runs/config · egress ${
    egress_enforced ? "enforced" : "not enforced"
  }`;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
    >
      <details className="group border border-zinc-200 rounded-lg bg-white">
        <summary className="cursor-pointer list-none px-5 py-4 flex items-center justify-between gap-4 hover:bg-zinc-50 transition-colors rounded-lg">
          <span className="flex flex-col gap-1 min-w-0">
            <span className="text-zinc-500 text-xs font-mono uppercase tracking-widest">
              Methods — how this was measured
            </span>
            <span className="text-zinc-700 text-xs font-mono truncate">
              {summary}
            </span>
          </span>
          <span
            aria-hidden="true"
            className="text-zinc-400 text-xs font-mono shrink-0 transition-transform group-open:rotate-180"
          >
            ▾
          </span>
        </summary>

        <div className="border-t border-zinc-200 px-5 py-5 flex flex-col gap-6">
          <p className="text-zinc-700 text-sm leading-relaxed max-w-[60ch]">
            Measured the effect of a repository context file on AI agent task
            success. Both arms ran the same agent, the same flags, and the same
            tasks — the only difference was whether the context file was present
            in <span className="font-mono text-xs">/work</span>.
          </p>

          {/* Isolation + egress (highlighted) */}
          <div className="flex flex-col gap-0.5">
            <span className="text-zinc-500 text-[10px] font-mono uppercase tracking-widest leading-none">
              Isolation
            </span>
            <span className="flex flex-wrap items-center gap-2 text-xs font-mono text-zinc-700">
              <span
                aria-hidden="true"
                className={`w-1.5 h-1.5 rounded-full ${
                  egress_enforced ? "bg-emerald-600" : "bg-amber-600"
                }`}
              />
              {network_mode}
              <span
                className={`font-medium ${
                  egress_enforced ? "text-emerald-700" : "text-amber-700"
                }`}
              >
                {egress_enforced ? "egress enforced" : "egress not enforced"}
              </span>
            </span>
          </div>

          {/* Provenance + measurement fields */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-4 gap-y-5">
            <Field label="Provider" value={provider} />
            <Field label="Model" value={model} />
            <Field label="Agent" value={formatAgent(agent_adapter)} />
            <Field
              label="Tasks"
              value={`${n_tasks} × ${runs_per_config} runs/config`}
            />
            <Field
              label="Variance"
              value={`σ ±${(success_stddev * 100).toFixed(1)} pp · ${formatPct(
                success_min
              )}–${formatPct(success_max)}`}
            />
            <Field label="Evaluated commit" value={shortenCommit(repo_commit)} />
            <Field label="Base image" value={displayImage} />
            <Field label="Evaluated" value={formatDate(created_at)} />
          </div>

          {/* PRIMER overhead — a SEPARATE line, never summed into the eval cost delta */}
          <div className="border-t border-zinc-200 pt-4 flex flex-col gap-1">
            <div className="flex flex-col gap-0.5">
              <span className="text-zinc-500 text-[10px] font-mono uppercase tracking-widest leading-none">
                PRIMER overhead
              </span>
              <span className="text-xs font-mono text-zinc-700">
                {formatCost(primer_overhead_usd, primer_overhead_confidence)}
              </span>
            </div>
            <p className="text-zinc-500 text-xs font-mono mt-1 max-w-[60ch] leading-relaxed">
              The cost of generating the context file (Layer-1 provider). Never
              included in the eval cost delta above.
            </p>
          </div>
        </div>
      </details>
    </motion.div>
  );
}
