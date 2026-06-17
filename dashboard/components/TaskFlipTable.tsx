"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown } from "lucide-react";
import { formatPct, formatDelta } from "@/lib/format";
import { FLIP_LABELS, FLIP_ORDER } from "@/lib/verdict";
import { cn } from "@/lib/cn";
import type { TaskData, FlipState } from "@/lib/types";

// Interesting-first order (§7.3)
const BAR_SEGMENTS = [
  { key: "FAIL_TO_PASS" as FlipState, label: "Fixed by the file",       color: "bg-[var(--verdict-positive-fg)]" },
  { key: "PASS_TO_FAIL" as FlipState, label: "Broken by the file",      color: "bg-[var(--verdict-negative-fg)]" },
  { key: "PASS_TO_PASS" as FlipState, label: "Passed with and without", color: "bg-[var(--text-tertiary)]" },
  { key: "FAIL_TO_FAIL" as FlipState, label: "Failed with and without", color: "bg-[var(--surface-raised)]" },
] as const;

const TASK_TYPE_EXPLANATION: Record<string, string> = {
  stub_function:       "A function stub is provided; the agent must implement it so the pytest suite passes.",
  revert_reimplement:  "A working implementation is reverted to an older commit; the agent must re-implement it so tests pass.",
};

function flipBadgeClass(state: FlipState): string {
  switch (state) {
    case "FAIL_TO_PASS": return "bg-[var(--verdict-positive-bg)] text-[var(--verdict-positive-fg)] border border-[var(--verdict-positive-border)]";
    case "PASS_TO_FAIL": return "bg-[var(--verdict-negative-bg)] text-[var(--verdict-negative-fg)] border border-[var(--verdict-negative-border)]";
    default:             return "bg-[var(--surface-raised)] text-[var(--text-tertiary)] border border-[var(--border-hairline)]";
  }
}

function FlipStackedBar({ counts, total }: { counts: Record<string, number>; total: number }) {
  if (total === 0) return null;
  const summary = BAR_SEGMENTS.filter((s) => (counts[s.key] ?? 0) > 0)
    .map((s) => `${counts[s.key]} ${s.label.toLowerCase()}`)
    .join(", ");

  return (
    <div className="mb-4 flex flex-col gap-2">
      <motion.div
        className="flex h-2 w-full overflow-hidden rounded-full bg-[var(--surface-raised)] origin-left"
        role="img"
        aria-label={`Flip distribution across ${total} task${total === 1 ? "" : "s"}: ${summary}`}
        initial={{ scaleX: 0, opacity: 0 }}
        animate={{ scaleX: 1, opacity: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        {/* Widths are static (no layout thrash); the whole bar draws in via scaleX. */}
        {BAR_SEGMENTS.map((s) =>
          (counts[s.key] ?? 0) > 0 ? (
            <div
              key={s.key}
              className={s.color}
              style={{ width: `${((counts[s.key] ?? 0) / total) * 100}%` }}
            />
          ) : null
        )}
      </motion.div>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {BAR_SEGMENTS.map((s) => (
          <span key={s.key} className="inline-flex items-center gap-1.5 text-[11px] font-mono text-[var(--text-tertiary)]">
            <span aria-hidden className={`w-2 h-2 rounded-sm ${s.color}`} />
            {s.label}{" "}
            <span className="text-[var(--text-secondary)] font-medium">{counts[s.key] ?? 0}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function TaskRow({ task, index }: { task: TaskData; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const typeExplanation = TASK_TYPE_EXPLANATION[task.task_type] ?? null;

  return (
    <>
      <motion.tr
        className={cn(
          "border-b border-[var(--border-hairline)] last:border-0 cursor-pointer hover:bg-[var(--surface-raised)] transition-colors",
          expanded && "bg-[var(--surface-raised)]"
        )}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2, delay: index * 0.04, ease: [0.16, 1, 0.3, 1] }}
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <td className="py-3 pr-4">
          <div className="flex flex-col gap-0.5">
            <span className="font-mono text-xs text-[var(--text-secondary)] break-all">
              {task.task_id}
            </span>
            <span className="text-[var(--text-tertiary)] text-[10px] font-mono">{task.task_type}</span>
          </div>
        </td>
        <td className="py-3 pr-4">
          <span className={cn(
            "inline-flex items-center px-2 py-0.5 rounded text-xs font-mono",
            flipBadgeClass(task.flip_state)
          )}>
            {FLIP_LABELS[task.flip_state]}
          </span>
        </td>
        <td className="py-3 pr-4 font-mono text-xs text-[var(--text-secondary)] tabular-nums">
          {formatPct(task.pass_rate_without)} / {formatPct(task.pass_rate_with)}
        </td>
        <td className="py-3 pr-4 font-mono text-xs text-[var(--text-secondary)] tabular-nums">
          {formatDelta(task.delta)}
        </td>
        <td className="py-3 text-xs font-mono">
          {task.flaky_any && (
            <span className="text-[var(--warning-fg)]">flaky</span>
          )}
        </td>
        <td className="py-3 pl-2 w-6">
          <ChevronDown
            size={12}
            strokeWidth={1.5}
            className={cn(
              "text-[var(--text-tertiary)] transition-transform duration-200",
              expanded && "rotate-180"
            )}
            aria-hidden
          />
        </td>
      </motion.tr>

      {/* Expandable detail row */}
      <AnimatePresence>
        {expanded && (
          <motion.tr
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
          >
            <td colSpan={6} className="pb-4 px-4 bg-[var(--surface-raised)]">
              <div className="pt-3 flex flex-col gap-2 border-t border-[var(--border-hairline)]">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                  <div>
                    <p className="text-[var(--text-tertiary)] text-[10px] uppercase tracking-widest mb-0.5">Runs</p>
                    <p className="text-[var(--text-secondary)]">{task.runs}</p>
                  </div>
                  <div>
                    <p className="text-[var(--text-tertiary)] text-[10px] uppercase tracking-widest mb-0.5">Task type</p>
                    <p className="text-[var(--text-secondary)]">{task.task_type}</p>
                  </div>
                  <div>
                    <p className="text-[var(--text-tertiary)] text-[10px] uppercase tracking-widest mb-0.5">Flaky</p>
                    <p className={task.flaky_any ? "text-[var(--warning-fg)]" : "text-[var(--text-tertiary)]"}>
                      {task.flaky_any ? "Yes — results may be unreliable" : "No"}
                    </p>
                  </div>
                </div>
                {typeExplanation && (
                  <p className="text-[var(--text-tertiary)] text-[11px] font-mono leading-relaxed max-w-[60ch]">
                    {typeExplanation}
                  </p>
                )}
              </div>
            </td>
          </motion.tr>
        )}
      </AnimatePresence>
    </>
  );
}

interface TaskFlipTableProps {
  tasks: TaskData[];
}

export function TaskFlipTable({ tasks }: TaskFlipTableProps) {
  if (tasks.length === 0) {
    return (
      <div className="text-[var(--text-tertiary)] text-xs font-mono py-4">
        No per-task data.
      </div>
    );
  }

  const orderedTasks = [...tasks].sort(
    (a, b) => (FLIP_ORDER[a.flip_state] ?? 9) - (FLIP_ORDER[b.flip_state] ?? 9)
  );

  const counts: Record<string, number> = {
    FAIL_TO_PASS: 0, PASS_TO_FAIL: 0, PASS_TO_PASS: 0, FAIL_TO_FAIL: 0,
  };
  for (const t of tasks) counts[t.flip_state] = (counts[t.flip_state] ?? 0) + 1;

  return (
    <div className="reveal-on-scroll">
      <h2 className="t-eyebrow mb-3">Per-task flips</h2>

      <FlipStackedBar counts={counts} total={tasks.length} />

      {/* Mobile — card reflow */}
      <ul className="md:hidden flex flex-col gap-2.5">
        {orderedTasks.map((task) => (
          <li
            key={task.task_id}
            className="rounded-card border border-[var(--border-hairline)] bg-[var(--surface-elevated)] shadow-card p-3.5"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex flex-col gap-0.5 min-w-0">
                <span className="t-data text-xs text-[var(--text-secondary)] break-all">{task.task_id}</span>
                <span className="t-data text-[10px] text-[var(--text-tertiary)]">{task.task_type}</span>
              </div>
              <span className={cn("inline-flex shrink-0 items-center px-2 py-0.5 rounded text-[11px] font-medium whitespace-nowrap", flipBadgeClass(task.flip_state))}>
                {FLIP_LABELS[task.flip_state]}
              </span>
            </div>
            <div className="mt-2.5 flex items-center justify-between gap-3 border-t border-[var(--border-hairline)] pt-2.5 t-data text-xs">
              <span className="text-[var(--text-tertiary)]">
                {formatPct(task.pass_rate_without)} / {formatPct(task.pass_rate_with)}
                {task.flaky_any && <span className="text-[var(--warning-fg)] ml-2">flaky</span>}
              </span>
              <span className="text-[var(--text-secondary)]">{formatDelta(task.delta)}</span>
            </div>
          </li>
        ))}
      </ul>

      <p className="t-caption mb-3 mt-3 hidden md:block">Click a row to expand task details.</p>

      <div className="hidden md:block overflow-x-auto">
        <table className="w-full min-w-[600px] text-sm" role="table">
          <thead>
            <tr className="border-b border-[var(--border-hairline)]">
              {[
                { l: "Task" }, { l: "Flip" }, { l: "Without / With" }, { l: "Delta" },
                { l: "Flaky", sr: true }, { l: "Details", sr: true },
              ].map((h, i) => (
                <th
                  key={i}
                  scope="col"
                  className="pb-2 text-left text-[10px] font-mono text-[var(--text-tertiary)] uppercase tracking-widest pr-4 last:pr-0"
                >
                  {h.sr ? <span className="sr-only">{h.l}</span> : h.l}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {orderedTasks.map((task, i) => (
              <TaskRow key={task.task_id} task={task} index={i} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
