"use client";

import type { ReactNode } from "react";
import { motion } from "motion/react";
import { shortenCommit, formatPct } from "@/lib/format";
import type { DashboardData, VerdictLabel } from "@/lib/types";

// ─── Shared micro-primitives ──────────────────────────────────────────────────

function MonoValue({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={`text-sm font-mono font-medium leading-snug ${className}`}>
      {children}
    </span>
  );
}

function MetaLabel({ children }: { children: ReactNode }) {
  return (
    <span className="text-[9px] font-mono text-zinc-400 uppercase tracking-widest leading-none">
      {children}
    </span>
  );
}

// ─── Pillar value compositions ────────────────────────────────────────────────

function IsolationValue({
  networkMode,
  egressEnforced,
}: {
  networkMode: string;
  egressEnforced: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <span
          aria-hidden="true"
          className={`w-1.5 h-1.5 rounded-full shrink-0 mt-px ${
            egressEnforced ? "bg-emerald-500" : "bg-amber-400"
          }`}
        />
        <MonoValue className="text-zinc-900">{networkMode}</MonoValue>
      </div>
      <MonoValue
        className={`text-xs ${
          egressEnforced ? "text-zinc-500" : "text-amber-500"
        }`}
      >
        {egressEnforced ? "egress enforced" : "egress not enforced"}
      </MonoValue>
    </div>
  );
}

function OneVariableValue() {
  return (
    <div className="flex flex-col gap-1.5">
      <MonoValue className="text-zinc-900">Context file only</MonoValue>
      <MonoValue className="text-xs text-zinc-400">
        Everything else identical
      </MonoValue>
    </div>
  );
}

function PairedValue({
  nTasks,
  runsPerConfig,
}: {
  nTasks: number;
  runsPerConfig: number;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <MonoValue className="text-zinc-900">
        {nTasks} tasks x {runsPerConfig} runs/config
      </MonoValue>
      <MonoValue className="text-xs text-zinc-500">
        {nTasks * runsPerConfig * 2} total runs
      </MonoValue>
    </div>
  );
}

function ReproducibleValue({
  commit,
  baseImage,
}: {
  commit: string;
  baseImage: string;
}) {
  const displayImage = baseImage.startsWith("sha256:")
    ? "sha256:" + baseImage.slice(7, 19) + "..."
    : baseImage.length > 24
    ? baseImage.slice(0, 24) + "..."
    : baseImage;

  return (
    <div className="flex flex-col gap-3">
      {/* Evaluated Commit row */}
      <div className="flex flex-col gap-0.5">
        <MetaLabel>Evaluated Commit</MetaLabel>
        <MonoValue className="text-zinc-900">{shortenCommit(commit)}</MonoValue>
      </div>

      {/* Row separator */}
      <div className="w-full h-px bg-zinc-200" aria-hidden="true" />

      {/* Base Image row */}
      <div className="flex flex-col gap-0.5">
        <MetaLabel>Base Image</MetaLabel>
        <MonoValue className="text-zinc-900 break-all">{displayImage}</MonoValue>
      </div>
    </div>
  );
}

function VarianceValue({
  stddev,
  min,
  max,
}: {
  stddev: number;
  min: number;
  max: number;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <MonoValue className="text-zinc-900">
        σ = ±{(stddev * 100).toFixed(1)} pp
      </MonoValue>
      <MonoValue className="text-xs text-zinc-500">
        range {formatPct(min)} to {formatPct(max)}
      </MonoValue>
    </div>
  );
}

const VERDICT_DISPLAY: Record<VerdictLabel, string> = {
  positive: "Positive",
  negative: "Negative",
  "within-noise": "Within-noise",
  refused: "Refused",
};

const VERDICT_ORDER: VerdictLabel[] = [
  "positive",
  "negative",
  "within-noise",
  "refused",
];

function HonestOutcomesValue({
  activeVerdict,
}: {
  activeVerdict: VerdictLabel;
}) {
  return (
    <div
      className="flex flex-col gap-1"
      aria-label={`Current verdict: ${activeVerdict}`}
    >
      {VERDICT_ORDER.map((v) => (
        <div key={v} className="flex items-baseline gap-2">
          <MonoValue
            className={v === activeVerdict ? "text-zinc-900" : "text-zinc-400"}
          >
            {VERDICT_DISPLAY[v]}
          </MonoValue>
          {v === activeVerdict && (
            <span
              className="text-[9px] font-mono text-zinc-400 uppercase tracking-wider"
              aria-hidden="true"
            >
              this report
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── TrustPillar ──────────────────────────────────────────────────────────────

interface TrustPillarProps {
  label: string;
  value: ReactNode;
  explanation: string;
  index: number;
}

function TrustPillar({ label, value, explanation, index }: TrustPillarProps) {
  return (
    <motion.div
      className="flex flex-col gap-3 px-5 py-5"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.28,
        delay: 0.1 + index * 0.055,
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-400 leading-none">
        {label}
      </span>
      <div>{value}</div>
      <p className="text-xs text-zinc-500 leading-relaxed">{explanation}</p>
    </motion.div>
  );
}

// ─── TrustArchitecture ────────────────────────────────────────────────────────

interface TrustArchitectureProps {
  data: DashboardData;
}

export function TrustArchitecture({ data }: TrustArchitectureProps) {
  const {
    network_mode,
    egress_enforced,
    n_tasks,
    runs_per_config,
    repo_commit,
    base_image,
    success_stddev,
    success_min,
    success_max,
    verdict,
  } = data;

  const pillars: Omit<TrustPillarProps, "index">[] = [
    {
      label: "Isolated Execution",
      value: (
        <IsolationValue
          networkMode={network_mode}
          egressEnforced={egress_enforced}
        />
      ),
      explanation:
        "Each run starts in a fresh container. Egress is restricted to the agent's required API host only - no other outbound access.",
    },
    {
      label: "One Variable",
      value: <OneVariableValue />,
      explanation:
        "Both arms run with identical flags, the same agent, and the same task. The only difference is whether the context file is present in /work.",
    },
    {
      label: "Paired Before / After",
      value: <PairedValue nTasks={n_tasks} runsPerConfig={runs_per_config} />,
      explanation: `${runs_per_config} runs per arm detect flaky tests before they contaminate the delta. Runs are sequential - no resource contention noise.`,
    },
    {
      label: "Reproducible",
      value: (
        <ReproducibleValue commit={repo_commit} baseImage={base_image} />
      ),
      explanation:
        "Fixed commit and immutable base image digest. This exact evaluation can be reproduced by anyone with the same repo commit.",
    },
    {
      label: "Variance Reported",
      value: (
        <VarianceValue
          stddev={success_stddev}
          min={success_min}
          max={success_max}
        />
      ),
      explanation:
        "Spread across runs is always surfaced. When the delta falls inside the noise envelope, PRIMER labels it explicitly rather than reporting a false signal.",
    },
    {
      label: "Honest Outcomes",
      value: <HonestOutcomesValue activeVerdict={verdict} />,
      explanation:
        "A ~0 or negative delta is a valid, shippable result. PRIMER is designed to measure - not to prove that context files help.",
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="text-zinc-500 text-xs font-mono uppercase tracking-widest mb-3">
        How this was measured
      </div>

      <div
        className="border border-zinc-200 rounded-lg overflow-hidden"
        role="region"
        aria-label="Measurement integrity"
      >
        {/* Row 1: Isolated Execution / One Variable / Paired Before After */}
        <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-zinc-200">
          {pillars.slice(0, 3).map((p, i) => (
            <TrustPillar key={p.label} {...p} index={i} />
          ))}
        </div>

        {/* Row 2: Reproducible / Variance Reported / Honest Outcomes */}
        <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-zinc-200 border-t border-zinc-200">
          {pillars.slice(3, 6).map((p, i) => (
            <TrustPillar key={p.label} {...p} index={i + 3} />
          ))}
        </div>
      </div>
    </motion.div>
  );
}
