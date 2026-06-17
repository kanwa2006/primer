"use client";

import Link from "next/link";
import { GitCommit, ArrowRight } from "lucide-react";
import { formatDate, shortenCommit } from "@/lib/format";
import { VerdictBadge } from "@/components/VerdictBadge";
import type { EvaluationSummary } from "@/lib/types";

function deltaStr(delta: number | null): string {
  if (delta === null) return "N/A";
  return delta > 0 ? `+${(delta * 100).toFixed(1)} pp` : `${(delta * 100).toFixed(1)} pp`;
}

export function EvaluationLedger({
  evaluations,
}: {
  evaluations: EvaluationSummary[];
}) {
  if (evaluations.length === 0) return null;

  return (
    <>
      {/* Mobile — card reflow (no horizontal scroll, no crushed cells) */}
      <ul className="md:hidden flex flex-col gap-3">
        {evaluations.map((ev) => (
          <li key={ev.id}>
            <Link
              href={`/evaluations/${ev.id}/`}
              className="block rounded-card border border-[var(--border-hairline)] bg-[var(--surface-elevated)] p-4 shadow-card transition-colors active:bg-[var(--surface-raised)]"
              title={ev.repo_commit}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="inline-flex items-center gap-1.5 t-data text-xs text-[var(--text-secondary)]">
                  <GitCommit size={12} strokeWidth={1.5} aria-hidden />
                  {shortenCommit(ev.repo_commit)}
                </span>
                <span className="t-caption">{formatDate(ev.created_at)}</span>
              </div>
              <div className="mt-3 flex items-center justify-between gap-3">
                <VerdictBadge verdict={ev.verdict} size="sm" />
                <span className="t-data text-xs text-[var(--text-secondary)]">
                  {deltaStr(ev.success_delta)}
                  <span className="text-[var(--text-tertiary)] ml-1.5">
                    ± {(ev.noise_threshold * 100).toFixed(1)} pp
                  </span>
                </span>
              </div>
              <div className="mt-3 flex items-center justify-between gap-3 border-t border-[var(--border-hairline)] pt-2.5">
                <span className={ev.egress_enforced ? "t-data text-[11px] text-[var(--verdict-positive-fg)]" : "t-data text-[11px] text-[var(--warning-fg)]"}>
                  egress {ev.egress_enforced ? "enforced" : "open"}
                </span>
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--accent-signal)]">
                  View <ArrowRight size={12} strokeWidth={1.75} aria-hidden />
                </span>
              </div>
            </Link>
          </li>
        ))}
      </ul>

      {/* Desktop — full ledger table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm" aria-label="Evaluation history">
          <thead>
            <tr className="text-left border-b border-[var(--border-hairline)]">
              {["Commit", "Date", "Verdict", "Delta ± noise", "Egress", "Compare"].map((h, i) => (
                <th
                  key={h}
                  scope="col"
                  className="pb-2.5 pr-4 t-eyebrow font-medium last:pr-0"
                >
                  {i === 5 ? <span className="sr-only">{h}</span> : h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {evaluations.map((ev, i) => {
              const olderSibling = evaluations[i + 1] ?? null;
              return (
                <tr
                  key={ev.id}
                  className="border-b border-[var(--border-hairline)] hover:bg-[var(--surface-raised)] transition-colors duration-100"
                >
                  <td className="py-3 pr-4">
                    <Link
                      href={`/evaluations/${ev.id}/`}
                      className="inline-flex items-center gap-1.5 t-data text-xs text-[var(--text-secondary)] hover:text-[var(--accent-signal)] transition-colors underline-offset-2 hover:underline"
                      title={ev.repo_commit}
                    >
                      <GitCommit size={12} strokeWidth={1.5} aria-hidden />
                      {shortenCommit(ev.repo_commit)}
                    </Link>
                  </td>
                  <td className="py-3 pr-4 t-caption">{formatDate(ev.created_at)}</td>
                  <td className="py-3 pr-4">
                    <VerdictBadge verdict={ev.verdict} size="sm" />
                  </td>
                  <td className="py-3 pr-4 t-data text-xs text-[var(--text-secondary)]">
                    {deltaStr(ev.success_delta)}
                    <span className="text-[var(--text-tertiary)] ml-1.5">
                      ± {(ev.noise_threshold * 100).toFixed(1)} pp
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    <span className={ev.egress_enforced ? "t-data text-xs text-[var(--verdict-positive-fg)]" : "t-data text-xs text-[var(--warning-fg)]"}>
                      {ev.egress_enforced ? "enforced" : "open"}
                    </span>
                  </td>
                  <td className="py-3">
                    {olderSibling && (
                      <Link
                        href={`/compare/?a=${olderSibling.id}&b=${ev.id}`}
                        className="t-data text-xs text-[var(--text-tertiary)] hover:text-[var(--accent-signal)] transition-colors"
                      >
                        compare →
                      </Link>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
