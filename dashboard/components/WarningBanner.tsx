"use client";

import { motion, AnimatePresence } from "motion/react";
import { TriangleAlert } from "lucide-react";

interface WarningBannerProps {
  providerMismatch: string | null;
  isolationMismatch: string | null;
  flakyTask: string | null;
}

interface WarningEntry {
  key: string;
  label: string;
  message: string;
}

function SingleWarning({ label, message }: { label: string; message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2.5 px-4 py-3 rounded-md border border-[var(--warning-border)] bg-[var(--warning-bg)]"
    >
      <TriangleAlert
        size={14}
        strokeWidth={1.5}
        className="text-[var(--warning-fg)] mt-0.5 shrink-0"
        aria-hidden
      />
      <div>
        <p className="text-[10px] font-mono uppercase tracking-widest text-[var(--warning-fg)] font-semibold mb-0.5">
          {label}
        </p>
        <p className="text-[var(--warning-fg)] text-xs leading-relaxed font-mono">{message}</p>
      </div>
    </div>
  );
}

export function WarningBanner({
  providerMismatch,
  isolationMismatch,
  flakyTask,
}: WarningBannerProps) {
  const warnings: WarningEntry[] = [
    { key: "provider",  label: "Provider mismatch",    message: providerMismatch  ?? "" },
    { key: "isolation", label: "Isolation mismatch",   message: isolationMismatch ?? "" },
    { key: "flaky",     label: "Flaky tasks detected", message: flakyTask         ?? "" },
  ].filter((w) => w.message !== "");

  if (warnings.length === 0) return null;

  return (
    <AnimatePresence initial>
      <motion.div
        className="flex flex-col gap-2"
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
        aria-live="polite"
      >
        {warnings.map((w) => (
          <SingleWarning key={w.key} label={w.label} message={w.message} />
        ))}
      </motion.div>
    </AnimatePresence>
  );
}
