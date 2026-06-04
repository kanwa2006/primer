"use client";

import { motion, AnimatePresence } from "motion/react";
import { flipStateBadge, flipLabel, formatPct, formatDelta } from "@/lib/format";
import type { TaskData } from "@/lib/types";

// Interesting-first: the two genuine flips lead, unaffected tasks follow (§11).
const FLIP_ORDER: Record<string, number> = {
  FAIL_TO_PASS: 0,
  PASS_TO_FAIL: 1,
  PASS_TO_PASS: 2,
  FAIL_TO_FAIL: 3,
};

interface TaskRowProps {
  task: TaskData;
  index: number;
}

function TaskRow({ task, index }: TaskRowProps) {
  return (
    <motion.tr
      key={task.task_id}
      className="border-b border-zinc-200 last:border-0"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.2,
        delay: index * 0.04,
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      <td className="py-3 pr-6">
        <div className="flex flex-col gap-0.5">
          <span className="font-mono text-xs text-zinc-700 break-all">
            {task.task_id}
          </span>
          <span className="text-zinc-500 text-xs font-mono">{task.task_type}</span>
        </div>
      </td>

      <td className="py-3 pr-6">
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-mono ${flipStateBadge(task.flip_state)}`}
        >
          {flipLabel(task.flip_state)}
        </span>
      </td>

      <td className="py-3 pr-6 font-mono text-xs text-zinc-600">
        {formatPct(task.pass_rate_without)} / {formatPct(task.pass_rate_with)}
      </td>

      <td className="py-3 pr-6 font-mono text-xs text-zinc-600">
        {formatDelta(task.delta)}
      </td>

      <td className="py-3 text-xs font-mono text-zinc-500">
        {task.flaky_any && (
          <span className="text-amber-700">flaky</span>
        )}
      </td>
    </motion.tr>
  );
}

interface TaskFlipTableProps {
  tasks: TaskData[];
}

export function TaskFlipTable({ tasks }: TaskFlipTableProps) {
  if (tasks.length === 0) {
    return (
      <div className="text-zinc-500 text-xs font-mono py-4">
        No per-task data.
      </div>
    );
  }

  const orderedTasks = [...tasks].sort(
    (a, b) => (FLIP_ORDER[a.flip_state] ?? 9) - (FLIP_ORDER[b.flip_state] ?? 9)
  );

  return (
    <div>
      <div className="text-zinc-500 text-xs font-mono uppercase tracking-widest mb-3">
        Per-task flips
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[600px] text-sm" role="table">
          <thead>
            <tr className="border-b border-zinc-200">
              <th className="pb-2 text-left text-xs font-mono text-zinc-500 uppercase tracking-widest pr-6">
                Task
              </th>
              <th className="pb-2 text-left text-xs font-mono text-zinc-500 uppercase tracking-widest pr-6">
                Flip
              </th>
              <th className="pb-2 text-left text-xs font-mono text-zinc-500 uppercase tracking-widest pr-6">
                Without / With
              </th>
              <th className="pb-2 text-left text-xs font-mono text-zinc-500 uppercase tracking-widest pr-6">
                Delta
              </th>
              <th className="pb-2 text-left text-xs font-mono text-zinc-500 uppercase tracking-widest" />
            </tr>
          </thead>
          <tbody>
            <AnimatePresence initial={false}>
              {orderedTasks.map((task, i) => (
                <TaskRow key={task.task_id} task={task} index={i} />
              ))}
            </AnimatePresence>
          </tbody>
        </table>
      </div>
    </div>
  );
}
