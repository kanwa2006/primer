"use client";

import { EmptyState } from "@/components/EmptyState";
import { EvaluationLedger } from "@/components/EvaluationLedger";
import { HeroBand } from "@/components/HeroBand";
import { InstrumentStatusBar } from "@/components/InstrumentStatusBar";
import { PipelineChips } from "@/components/PipelineChips";
import { formatDate } from "@/lib/format";
import { shortenCommit } from "@/lib/format";
import type { RepositoryData } from "@/lib/types";

export function RepositoryOverview({ data }: { data: RepositoryData }) {
  if (data.evaluation_count === 0) return <EmptyState />;

  const latestEval = data.evaluations[0] ?? null;

  // History-as-stability read + condition-change flags (§7.1)
  const evals = data.evaluations;
  const n = evals.length;
  const sameProviderModel =
    new Set(evals.map((e) => `${e.provider}/${e.model}`)).size === 1;
  const sameIsolation =
    new Set(evals.map((e) => String(e.egress_enforced))).size === 1;
  const allWithinNoise = n > 0 && evals.every((e) => e.verdict === "within-noise");
  const conditionFlags: string[] = [];
  if (n >= 2 && !sameProviderModel)
    conditionFlags.push(
      "Provider or model changed across history — verdicts are not directly comparable."
    );
  if (n >= 2 && !sameIsolation)
    conditionFlags.push(
      "Egress-enforcement setting changed across history — isolation was not held constant."
    );
  const stabilityRead = allWithinNoise
    ? `Within noise across ${n} evaluation${n === 1 ? "" : "s"}${sameProviderModel ? ` under ${evals[0].model}` : ""} — no measurable effect detected so far.`
    : sameProviderModel
    ? `${n} evaluation${n === 1 ? "" : "s"} under ${evals[0].model}.`
    : `${n} evaluations across changing conditions.`;

  return (
    <div className="flex flex-col gap-10">
      {/* Hero band — first impression + verdict */}
      <HeroBand data={data} />

      {/* Instrument Status Bar — persistent rigor surface */}
      {latestEval && (
        <InstrumentStatusBar
          egressEnforced={latestEval.egress_enforced}
          nTasks={latestEval.n_tasks}
          runsPerConfig={latestEval.runs_per_config}
          successStddev={latestEval.success_stddev}
          agentAdapter={latestEval.agent_adapter}
          model={latestEval.model}
        />
      )}

      {/* Pipeline chip row */}
      <div className="reveal-on-scroll">
        <p className="t-eyebrow mb-3">Measurement pipeline</p>
        <PipelineChips />
      </div>

      {/* History-as-stability read */}
      {n >= 1 && (
        <div className="flex flex-col gap-1.5 reveal-on-scroll">
          {n === 1 ? (
            <p className="t-body text-[var(--text-secondary)] max-w-[60ch]">
              This is the first evaluation for this repo. History appears once you run PRIMER again.
            </p>
          ) : (
            <p className="t-lead max-w-[60ch]">{stabilityRead}</p>
          )}
          {conditionFlags.map((f) => (
            <p key={f} className="t-body text-[var(--warning-fg)]">⚠ {f}</p>
          ))}
        </div>
      )}

      {/* Stale export caption */}
      {latestEval && (
        <p className="t-caption -mt-6">
          Showing last export — commit{" "}
          <span className="t-data" title={latestEval.repo_commit}>{shortenCommit(latestEval.repo_commit)}</span>
          , {formatDate(latestEval.created_at)}. Re-run PRIMER and re-export to update.
        </p>
      )}

      {/* Evaluation ledger */}
      <div className="reveal-on-scroll">
        <h2 className="t-eyebrow mb-4">Evaluations</h2>
        <EvaluationLedger evaluations={data.evaluations} />
      </div>
    </div>
  );
}
