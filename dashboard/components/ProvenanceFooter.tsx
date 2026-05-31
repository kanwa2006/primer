"use client";

import { motion } from "motion/react";
import { formatCost, shortenCommit, formatDate } from "@/lib/format";
import type { DashboardData } from "@/lib/types";

interface ProvenanceFooterProps {
  data: DashboardData;
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-zinc-600 text-xs font-mono uppercase tracking-widest">
        {label}
      </span>
      <span className="text-zinc-400 text-xs font-mono break-all">{value}</span>
    </div>
  );
}

export function ProvenanceFooter({ data }: ProvenanceFooterProps) {
  const {
    provider,
    model,
    agent_adapter,
    base_image,
    network_mode,
    egress_enforced,
    repo_commit,
    created_at,
    primer_overhead_usd,
    primer_overhead_confidence,
  } = data;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="text-zinc-600 text-xs font-mono uppercase tracking-widest mb-3">
        Provenance
      </div>

      <div className="border border-zinc-800 rounded-lg p-4 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        <Field label="Provider" value={provider} />
        <Field label="Model" value={model} />
        <Field label="Agent" value={agent_adapter} />
        <Field label="Network" value={`${network_mode} ${egress_enforced ? "(enforced)" : "(open)"}`} />
        <Field
          label="Base image"
          value={base_image.length > 40 ? base_image.slice(0, 40) + "…" : base_image}
        />
        <Field label="Commit" value={shortenCommit(repo_commit)} />
        <Field label="Evaluated" value={formatDate(created_at)} />
        <Field
          label="PRIMER overhead"
          value={formatCost(primer_overhead_usd, primer_overhead_confidence)}
        />
      </div>

      <p className="text-zinc-700 text-xs font-mono mt-3">
        PRIMER overhead is the cost of generating the context file (Layer-1 provider).
        It is never included in the eval cost delta above.
      </p>
    </motion.div>
  );
}
