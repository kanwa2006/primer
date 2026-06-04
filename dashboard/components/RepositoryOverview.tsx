"use client";

import { EmptyState } from "@/components/EmptyState";
import { EvaluationLedger } from "@/components/EvaluationLedger";
import { formatDelta, formatDate, shortenCommit, verdictColor, verdictWord, verdictIcon } from "@/lib/format";
import type { RepositoryData } from "@/lib/types";

export function RepositoryOverview({ data }: { data: RepositoryData }) {
  if (data.evaluation_count === 0) return <EmptyState />;

  const latestEval = data.evaluations[0] ?? null;

  return (
    <div className="flex flex-col gap-10">
      {/* Repository identity */}
      <div>
        <div className="flex items-baseline gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
            {data.repo.name}
          </h1>
          {data.repo.url && (
            <a
              href={data.repo.url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`View ${data.repo.name} on external site`}
              className="text-sm text-zinc-500 hover:text-zinc-700 transition-colors"
            >
              ↗
            </a>
          )}
        </div>

        <div className="mt-1 text-xs font-mono text-zinc-400">
          {shortenCommit(data.repo.latest_commit)}
        </div>

        {data.latest_verdict && latestEval && (
          <>
            <div className="mt-2 text-sm flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <span className="text-zinc-500">Latest result:</span>
              <span className={`font-medium ${verdictColor(data.latest_verdict)}`}>
                <span aria-hidden="true">{verdictIcon(data.latest_verdict)}</span> {verdictWord(data.latest_verdict)}
              </span>
              {latestEval.success_delta !== null && (
                <>
                  <span className="text-zinc-700 font-mono text-sm">
                    {formatDelta(latestEval.success_delta)}
                  </span>
                  <span className="text-zinc-400 font-mono text-xs">
                    ± {(latestEval.noise_threshold * 100).toFixed(1)} pp noise threshold
                  </span>
                </>
              )}
            </div>
            <p className="mt-1 text-xs font-mono text-zinc-400 leading-relaxed max-w-[60ch]">
              Showing the last export — commit {shortenCommit(latestEval.repo_commit)}, {formatDate(latestEval.created_at)}. Re-run PRIMER and re-export to update.
            </p>
          </>
        )}
      </div>

      {/* Evaluation ledger */}
      <div>
        <h2 className="text-xs font-mono uppercase tracking-widest text-zinc-400 mb-4">
          Evaluations
        </h2>
        {data.evaluation_count === 1 && (
          <p className="text-xs font-mono text-zinc-400 mb-3 max-w-[60ch] leading-relaxed">
            This is the first evaluation for this repo. History appears once you run PRIMER again.
          </p>
        )}
        <EvaluationLedger evaluations={data.evaluations} />
      </div>
    </div>
  );
}
