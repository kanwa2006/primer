"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { ChevronDown, Shield, ShieldOff } from "lucide-react";
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "@/components/ui/collapsible";
import { formatCost, formatPct, shortenCommit, formatDateTime } from "@/lib/format";
import { formatAgent } from "@/lib/verdict";
import { cn } from "@/lib/cn";
import type { DashboardData } from "@/lib/types";

function Field({
  label,
  value,
  valueTitle,
  className,
}: {
  label: string;
  value: string;
  valueTitle?: string;
  className?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[var(--text-tertiary)] text-[10px] font-mono uppercase tracking-widest leading-none">
        {label}
      </span>
      <span
        className={cn("text-xs font-mono break-all text-[var(--text-secondary)]", className)}
        title={valueTitle}
      >
        {value}
      </span>
    </div>
  );
}

// MethodsPanel (renamed from TrustArchitecture) — shadcn Collapsible per §M3.
export function TrustArchitecture({ data }: { data: DashboardData }) {
  const [open, setOpen] = useState(false);
  const {
    provider, model, agent_adapter,
    network_mode, egress_enforced,
    base_image, repo_commit, created_at,
    n_tasks, runs_per_config,
    success_stddev, success_min, success_max,
    primer_overhead_usd, primer_overhead_confidence,
  } = data;

  const displayImage =
    base_image.length > 44 ? `${base_image.slice(0, 44)}…` : base_image;
  const EgressIcon = egress_enforced ? Shield : ShieldOff;
  const egressColor = egress_enforced ? "text-[var(--verdict-positive-fg)]" : "text-[var(--warning-fg)]";

  const summary = `${formatAgent(agent_adapter)} · ${provider}/${model} · ${n_tasks} tasks × ${runs_per_config} runs/config · egress ${
    egress_enforced ? "enforced" : "open"
  }`;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
    >
      <Collapsible open={open} onOpenChange={setOpen}>
        <div className="border border-[var(--border-hairline)] rounded-card bg-[var(--surface-elevated)]">
          <CollapsibleTrigger asChild>
            <button className="w-full px-5 py-4 flex items-center justify-between gap-4 hover:bg-[var(--surface-raised)] transition-colors rounded-card text-left">
              <span className="flex flex-col gap-1 min-w-0">
                <span className="text-[var(--text-tertiary)] text-[10px] font-mono uppercase tracking-widest">
                  Methods — how this was measured
                </span>
                <span className="text-[var(--text-secondary)] text-xs font-mono truncate">
                  {summary}
                </span>
              </span>
              <ChevronDown
                size={14}
                strokeWidth={1.5}
                className={cn(
                  "text-[var(--text-tertiary)] shrink-0 transition-transform duration-200",
                  open && "rotate-180"
                )}
                aria-hidden
              />
            </button>
          </CollapsibleTrigger>

          <CollapsibleContent>
            <div className="border-t border-[var(--border-hairline)] px-5 py-5 flex flex-col gap-6">
              <p className="text-[var(--text-secondary)] text-sm leading-relaxed max-w-[60ch]">
                Measured the effect of a repository context file on AI agent task
                success. Both arms ran the same agent, the same flags, and the same
                tasks — the only difference was whether the context file was present
                in <code className="font-mono text-xs text-[var(--text-primary)]">/work</code>.
              </p>

              {/* Isolation line */}
              <div className="flex flex-col gap-0.5">
                <span className="text-[var(--text-tertiary)] text-[10px] font-mono uppercase tracking-widest leading-none">
                  Isolation
                </span>
                <span className="flex items-center gap-2 text-xs font-mono text-[var(--text-secondary)]">
                  <EgressIcon size={12} strokeWidth={1.5} className={egressColor} aria-hidden />
                  {network_mode}
                  <span className={cn("font-medium", egressColor)}>
                    {egress_enforced ? "egress enforced" : "egress open"}
                  </span>
                </span>
              </div>

              {/* Provenance grid */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-4 gap-y-5">
                <Field label="Provider" value={provider} />
                <Field label="Model"    value={model} />
                <Field label="Agent"    value={formatAgent(agent_adapter)} />
                <Field label="Tasks"    value={`${n_tasks} × ${runs_per_config} runs/config`} />
                <Field
                  label="Variance"
                  value={`σ ±${(success_stddev * 100).toFixed(1)} pp · ${formatPct(success_min)}–${formatPct(success_max)}`}
                />
                <Field label="Commit"     value={shortenCommit(repo_commit)} valueTitle={repo_commit} />
                <Field label="Base image" value={displayImage}               valueTitle={base_image} />
                <Field label="Evaluated"  value={formatDateTime(created_at)} />
              </div>

              {/* PRIMER overhead — separate line, never summed into eval cost */}
              <div className="border-t border-[var(--border-hairline)] pt-4 flex flex-col gap-1">
                <Field
                  label="PRIMER overhead"
                  value={formatCost(primer_overhead_usd, primer_overhead_confidence)}
                />
                <p className="text-[var(--text-tertiary)] text-xs font-mono mt-1 max-w-[60ch] leading-relaxed">
                  The cost of generating the context file (Layer-1 provider). Never
                  included in the eval cost delta above.
                </p>
              </div>
            </div>
          </CollapsibleContent>
        </div>
      </Collapsible>
    </motion.div>
  );
}
