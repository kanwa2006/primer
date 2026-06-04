"use client";

import { motion } from "motion/react";

export function EmptyState() {
  return (
    <motion.div
      className="flex flex-col items-center justify-center min-h-[60vh] text-center px-6"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="w-12 h-12 rounded-full border border-zinc-300 flex items-center justify-center mb-6">
        <svg
          width="20"
          height="20"
          viewBox="0 0 20 20"
          fill="none"
          aria-hidden="true"
          className="text-zinc-500"
        >
          <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5" />
          <line x1="10" y1="6" x2="10" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          <circle cx="10" cy="13.5" r="0.75" fill="currentColor" />
        </svg>
      </div>

      <h2 className="text-zinc-900 text-xl font-semibold tracking-tight mb-2">
        No evaluations yet
      </h2>
      <p className="text-zinc-500 text-sm max-w-[44ch] leading-relaxed mb-6">
        Run{" "}
        <code className="font-mono text-zinc-700 bg-zinc-100 px-1.5 py-0.5 rounded text-xs">
          primer eval .
        </code>{" "}
        then{" "}
        <code className="font-mono text-zinc-700 bg-zinc-100 px-1.5 py-0.5 rounded text-xs">
          primer export --site-output dashboard/public
        </code>{" "}
        to measure whether your context file helps.
      </p>

      <div className="text-xs font-mono text-zinc-500 tracking-widest uppercase">
        PRIMER — a measurement harness
      </div>
    </motion.div>
  );
}
