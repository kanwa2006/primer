"use client";

import Link from "next/link";
import {
  formatDate,
  formatDelta,
  shortenCommit,
  verdictColor,
} from "@/lib/format";
import type { EvaluationSummary } from "@/lib/types";

export function EvaluationLedger({
  evaluations,
}: {
  evaluations: EvaluationSummary[];
}) {
  if (evaluations.length === 0) return null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left border-b border-zinc-200">
            <th className="pb-2 pr-6 text-xs font-mono uppercase tracking-widest text-zinc-400 font-medium">
              Commit
            </th>
            <th className="pb-2 pr-6 text-xs font-mono uppercase tracking-widest text-zinc-400 font-medium">
              Date
            </th>
            <th className="pb-2 pr-6 text-xs font-mono uppercase tracking-widest text-zinc-400 font-medium">
              Verdict
            </th>
            <th className="pb-2 pr-6 text-xs font-mono uppercase tracking-widest text-zinc-400 font-medium">
              Delta
            </th>
            <th className="pb-2 text-xs font-mono uppercase tracking-widest text-zinc-400 font-medium">
              Egress
            </th>
          </tr>
        </thead>
        <tbody>
          {evaluations.map((ev) => {
            const withinNoise = ev.verdict === "within-noise";
            const noiseEnvelope = `± ${(ev.noise_threshold * 100).toFixed(1)} pp`;
            return (
              <tr
                key={ev.id}
                className="border-b border-zinc-100 hover:bg-zinc-50 transition-colors"
              >
                <td className="py-3 pr-6">
                  <Link
                    href={`/evaluations/${ev.id}/`}
                    className="font-mono text-xs text-zinc-700 hover:text-zinc-900 underline-offset-2 hover:underline"
                  >
                    {shortenCommit(ev.repo_commit)}
                  </Link>
                </td>
                <td className="py-3 pr-6 text-xs text-zinc-500">
                  {formatDate(ev.created_at)}
                </td>
                <td className="py-3 pr-6">
                  <span className={`text-xs font-medium ${verdictColor(ev.verdict)}`}>
                    {ev.verdict}
                  </span>
                </td>
                <td className="py-3 pr-6">
                  <span className="text-xs text-zinc-700">
                    {formatDelta(ev.success_delta)}
                  </span>
                  <span className="text-xs text-zinc-400 ml-1.5">{noiseEnvelope}</span>
                  {withinNoise && (
                    <span className="ml-2 text-xs font-mono text-zinc-400">
                      within noise
                    </span>
                  )}
                </td>
                <td className="py-3">
                  {ev.egress_enforced ? (
                    <span className="text-xs font-mono text-positive">enforced</span>
                  ) : (
                    <span className="text-xs font-mono text-zinc-400">open</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
