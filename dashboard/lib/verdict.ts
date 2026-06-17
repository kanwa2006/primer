import type { VerdictLabel, FlipState } from "./types";

// Shared noise threshold formula — must stay in sync with export.py:273
export function noiseThreshold(stddev: number, nTasks: number): number {
  return Math.max(1 / nTasks, stddev);
}

// Verdict display maps (locked by spec §13.5)
export const VERDICT_WORD: Record<VerdictLabel, string> = {
  positive: "Helped",
  negative: "Hurt",
  "within-noise": "No measurable effect",
  refused: "Not comparable",
};

export const VERDICT_GLYPH: Record<VerdictLabel, string> = {
  positive: "▲",
  negative: "▼",
  "within-noise": "≈",
  refused: "⊘",
};

// Lucide icon names — imported where used
export const VERDICT_LUCIDE: Record<VerdictLabel, string> = {
  positive: "TrendingUp",
  negative: "TrendingDown",
  "within-noise": "Minus",
  refused: "Ban",
};

// CSS classes for verdict pill styling
export function verdictPillClass(v: VerdictLabel): string {
  switch (v) {
    case "positive":
      return "bg-[var(--verdict-positive-bg)] text-[var(--verdict-positive-fg)] border border-[var(--verdict-positive-border)] rounded-full";
    case "negative":
      return "bg-[var(--verdict-negative-bg)] text-[var(--verdict-negative-fg)] border border-[var(--verdict-negative-border)] rounded-full";
    case "within-noise":
      return "bg-transparent text-[var(--verdict-noise-fg)] border border-[var(--verdict-noise-border)] rounded-full";
    case "refused":
      return "bg-transparent text-[var(--verdict-refused-fg)] border border-[var(--verdict-refused-border)] rounded-full line-through";
  }
}

export function verdictTextClass(v: VerdictLabel): string {
  switch (v) {
    case "positive":     return "text-[var(--verdict-positive-fg)]";
    case "negative":     return "text-[var(--verdict-negative-fg)]";
    case "within-noise": return "text-[var(--verdict-noise-fg)]";
    case "refused":      return "text-[var(--verdict-refused-fg)]";
  }
}

// Flip state display maps (locked by spec §13.5)
export const FLIP_LABELS: Record<FlipState, string> = {
  FAIL_TO_PASS: "Fixed by the file",
  PASS_TO_FAIL: "Broken by the file",
  PASS_TO_PASS: "Passed with and without",
  FAIL_TO_FAIL: "Failed with and without",
};

export const FLIP_ORDER: Record<FlipState, number> = {
  FAIL_TO_PASS: 0,
  PASS_TO_FAIL: 1,
  PASS_TO_PASS: 2,
  FAIL_TO_FAIL: 3,
};

// Agent adapter display map — keyed on real values from data
export const AGENT_DISPLAY: Record<string, string> = {
  claude_code: "Claude Code",
  gemini: "Gemini (experimental)",
};

export function formatAgent(adapter: string): string {
  return AGENT_DISPLAY[adapter] ?? adapter.replace(/_/g, " ");
}
