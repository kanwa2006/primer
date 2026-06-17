"use client";

import { TrendingUp, TrendingDown, Minus, Ban } from "lucide-react";
import type { VerdictLabel } from "@/lib/types";
import { VERDICT_WORD } from "@/lib/verdict";
import { cn } from "@/lib/cn";

const ICONS: Record<VerdictLabel, React.ComponentType<{ size?: number; strokeWidth?: number; "aria-hidden"?: boolean }>> = {
  positive:      TrendingUp,
  negative:      TrendingDown,
  "within-noise": Minus,
  refused:       Ban,
};

interface VerdictBadgeProps {
  verdict: VerdictLabel;
  size?: "sm" | "md";
  className?: string;
}

export function VerdictBadge({ verdict, size = "md", className }: VerdictBadgeProps) {
  const Icon = ICONS[verdict];

  const pillClass = {
    positive:       "bg-[var(--verdict-positive-bg)] text-[var(--verdict-positive-fg)] border border-[var(--verdict-positive-border)]",
    negative:       "bg-[var(--verdict-negative-bg)] text-[var(--verdict-negative-fg)] border border-[var(--verdict-negative-border)]",
    "within-noise": "bg-transparent text-[var(--verdict-noise-fg)] border border-[var(--verdict-noise-border)]",
    refused:        "bg-transparent text-[var(--verdict-refused-fg)] border border-[var(--verdict-refused-border)]",
  }[verdict];

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full font-medium whitespace-nowrap tracking-tight",
        size === "sm" ? "px-2.5 py-0.5 text-[11px]" : "px-3 py-1 text-xs",
        pillClass,
        className
      )}
    >
      <Icon size={size === "sm" ? 10 : 12} strokeWidth={1.5} aria-hidden />
      {VERDICT_WORD[verdict]}
    </span>
  );
}
