"use client";

import { Shield, ShieldOff } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatAgent } from "@/lib/verdict";

interface InstrumentStatusBarProps {
  egressEnforced: boolean;
  nTasks: number;
  runsPerConfig: number;
  successStddev: number;
  agentAdapter: string;
  model: string;
  // Optional — available from DashboardData but not EvaluationSummary
  networkMode?: string;
  baseImage?: string;
  className?: string;
}

// Persistent hairline strip surfacing buried rigor — §8.
// Reads state from data; never asserts enforcement.
// networkMode and baseImage are optional: only shown when full eval data available.
export function InstrumentStatusBar({
  egressEnforced,
  nTasks,
  runsPerConfig,
  successStddev,
  agentAdapter,
  model,
  networkMode,
  baseImage,
  className,
}: InstrumentStatusBarProps) {
  const EgressIcon = egressEnforced ? Shield : ShieldOff;
  const egressLabel = egressEnforced ? "egress enforced" : "egress open";
  const egressColor = egressEnforced ? "text-[var(--verdict-positive-fg)]" : "text-[var(--warning-fg)]";

  // Truncate sha256 digest for display; full in title
  const shortImage = baseImage
    ? baseImage.includes("@sha256:")
      ? `…@sha256:${baseImage.split("@sha256:")[1].slice(0, 8)}`
      : baseImage.length > 30
      ? `${baseImage.slice(0, 30)}…`
      : baseImage
    : null;

  const Dot = () => (
    <span className="text-[var(--border-strong)] select-none" aria-hidden>·</span>
  );

  return (
    <div
      className={cn(
        "w-full border border-[var(--border-hairline)] rounded-md bg-[var(--surface-elevated)] shadow-card px-4 py-2.5",
        className
      )}
      aria-label="Instrument status"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 t-data text-[11px] text-[var(--text-secondary)]">
        {/* Network mode + egress */}
        <span className="flex items-center gap-1.5">
          <EgressIcon size={12} strokeWidth={1.5} className={egressColor} aria-hidden />
          {networkMode && (
            <span className="text-[var(--text-tertiary)]">{networkMode}</span>
          )}
          <span className={cn("font-medium", egressColor)}>{egressLabel}</span>
        </span>

        {/* Base image digest (full eval only) */}
        {shortImage && (
          <>
            <Dot />
            <span
              title={baseImage}
              className="cursor-help underline decoration-dotted decoration-[var(--text-tertiary)] underline-offset-2"
            >
              sha256 {shortImage}
            </span>
          </>
        )}

        <Dot />
        <span>n={nTasks}×{runsPerConfig}</span>

        <Dot />
        <span>σ ±{(successStddev * 100).toFixed(1)} pp</span>

        <Dot />
        <span className="text-[var(--text-tertiary)]">
          {formatAgent(agentAdapter)}/{model}
        </span>
      </div>
    </div>
  );
}
