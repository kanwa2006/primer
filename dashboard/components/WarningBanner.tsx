"use client";

import { motion, AnimatePresence } from "motion/react";

interface WarningBannerProps {
  providerMismatch: string | null;
  isolationMismatch: string | null;
  flakyTask: string | null;
}

function SingleWarning({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-3 px-4 py-3 rounded border border-amber-500/20 bg-amber-500/5">
      <svg
        width="16"
        height="16"
        viewBox="0 0 16 16"
        fill="none"
        aria-hidden="true"
        className="text-amber-600 mt-0.5 shrink-0"
      >
        <path
          d="M8 2L14.5 13H1.5L8 2Z"
          stroke="currentColor"
          strokeWidth="1.2"
          strokeLinejoin="round"
        />
        <line x1="8" y1="7" x2="8" y2="10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
        <circle cx="8" cy="11.5" r="0.6" fill="currentColor" />
      </svg>
      <p className="text-amber-700 text-xs leading-relaxed font-mono">{message}</p>
    </div>
  );
}

export function WarningBanner({
  providerMismatch,
  isolationMismatch,
  flakyTask,
}: WarningBannerProps) {
  const warnings = [providerMismatch, isolationMismatch, flakyTask].filter(Boolean) as string[];

  return (
    <AnimatePresence>
      {warnings.length > 0 && (
        <motion.div
          className="flex flex-col gap-2"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          role="alert"
          aria-live="polite"
        >
          {warnings.map((w, i) => (
            <SingleWarning key={i} message={w} />
          ))}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
