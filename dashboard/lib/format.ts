import type { CostConfidence, VerdictLabel } from "./types";

export function formatPct(value: number, signed = false): string {
  const pct = (value * 100).toFixed(1);
  if (signed && value > 0) return `+${pct}%`;
  return `${pct}%`;
}

export function formatDelta(delta: number | null): string {
  if (delta === null) return "N/A";
  const pp = (delta * 100).toFixed(1);
  if (delta > 0) return `+${pp} pp`;
  return `${pp} pp`;
}

export function formatCost(usd: number, confidence: CostConfidence): string {
  if (confidence === "free") return "local (no cost)";
  const prefix = confidence === "estimated" ? "≈ " : "";
  return `${prefix}$${usd.toFixed(4)}`;
}

export function formatCostDelta(pct: number | null): string {
  if (pct === null) return "N/A";
  const val = pct.toFixed(1);
  if (pct > 0) return `+${val}%`;
  return `${val}%`;
}

export function verdictColor(verdict: VerdictLabel): string {
  switch (verdict) {
    case "positive":     return "text-emerald-700";
    case "negative":     return "text-red-700";
    case "within-noise": return "text-within-noise";
    case "refused":      return "text-refused";
  }
}

export function verdictBg(verdict: VerdictLabel): string {
  switch (verdict) {
    case "positive":     return "bg-positive/10 border-positive/30";
    case "negative":     return "bg-negative/10 border-negative/30";
    case "within-noise": return "bg-within-noise/10 border-within-noise/30";
    case "refused":      return "bg-refused/10 border-refused/30";
  }
}

// Word-first verdict label (§5/§16) — never shown by color alone.
export function verdictWord(verdict: VerdictLabel): string {
  switch (verdict) {
    case "positive":     return "Helped";
    case "negative":     return "Hurt";
    case "within-noise": return "No measurable effect";
    case "refused":      return "Not comparable";
  }
}

// Non-color shape cue paired with the word (§13).
export function verdictIcon(verdict: VerdictLabel): string {
  switch (verdict) {
    case "positive":     return "▲";
    case "negative":     return "▼";
    case "within-noise": return "≈";
    case "refused":      return "⊘";
  }
}

// Human flip-state labels (§16).
export function flipLabel(state: string): string {
  switch (state) {
    case "FAIL_TO_PASS": return "Fixed by the file";
    case "PASS_TO_FAIL": return "Broken by the file";
    case "PASS_TO_PASS": return "Passed with and without";
    case "FAIL_TO_FAIL": return "Failed with and without";
    default:             return state;
  }
}

export function flipStateColor(state: string): string {
  switch (state) {
    case "FAIL_TO_PASS": return "text-positive";
    case "PASS_TO_FAIL": return "text-negative";
    case "PASS_TO_PASS": return "text-zinc-400";
    case "FAIL_TO_FAIL": return "text-zinc-600";
    default:             return "text-zinc-500";
  }
}

export function flipStateBadge(state: string): string {
  switch (state) {
    case "FAIL_TO_PASS": return "bg-positive/10 text-emerald-700 border-positive/30";
    case "PASS_TO_FAIL": return "bg-negative/10 text-red-700 border-negative/30";
    case "PASS_TO_PASS": return "bg-zinc-100 text-zinc-600 border-zinc-200";
    case "FAIL_TO_FAIL": return "bg-zinc-100 text-zinc-600 border-zinc-200";
    default:             return "bg-zinc-100 text-zinc-600 border-zinc-200";
  }
}

export function shortenCommit(sha: string): string {
  return sha.slice(0, 8);
}

export function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}
