import type { CostConfidence } from "./types";

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

export function shortenCommit(sha: string): string {
  return sha.slice(0, 8);
}

const MONTHS = [
  "Jan","Feb","Mar","Apr","May","Jun",
  "Jul","Aug","Sep","Oct","Nov","Dec",
];

// Deterministic UTC — renders identical bytes on server (build TZ) and client.
// Fixes React hydration mismatch #418 caused by toLocaleString TZ divergence.
export function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    const day = d.getUTCDate();
    const mon = MONTHS[d.getUTCMonth()];
    const yr  = d.getUTCFullYear();
    return `${day} ${mon} ${yr}`;
  } catch {
    return iso;
  }
}

export function formatDateTime(iso: string): string {
  try {
    const d = new Date(iso);
    const day = d.getUTCDate();
    const mon = MONTHS[d.getUTCMonth()];
    const yr  = d.getUTCFullYear();
    const hh  = String(d.getUTCHours()).padStart(2, "0");
    const mm  = String(d.getUTCMinutes()).padStart(2, "0");
    return `${day} ${mon} ${yr}, ${hh}:${mm} UTC`;
  } catch {
    return iso;
  }
}
