"use client";

import { useRouter } from "next/navigation";
import { formatDate, shortenCommit, verdictColor } from "@/lib/format";
import type { EvaluationSummary } from "@/lib/types";

interface Props {
  evaluations: EvaluationSummary[];
  a: number | null;
  b: number | null;
}

export function EvaluationPicker({ evaluations, a, b }: Props) {
  const router = useRouter();

  function handleChange(which: "a" | "b", value: string) {
    const params = new URLSearchParams();
    const nextA = which === "a" ? value : (a !== null ? String(a) : "");
    const nextB = which === "b" ? value : (b !== null ? String(b) : "");
    if (nextA) params.set("a", nextA);
    if (nextB) params.set("b", nextB);
    const qs = params.toString();
    router.push(qs ? `?${qs}` : "?");
  }

  if (evaluations.length === 0) {
    return (
      <div className="text-zinc-500 text-xs font-mono py-4">
        No evaluations available. Run{" "}
        <code className="font-mono bg-zinc-100 px-1.5 py-0.5 rounded text-zinc-700">
          primer eval .
        </code>{" "}
        and export data first.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="text-zinc-500 text-xs font-mono uppercase tracking-widest">
        Select evaluations to compare
      </div>
      <div className="grid grid-cols-2 gap-6">
        <PickerSelect
          label="Baseline A"
          evaluations={evaluations}
          value={a}
          onChange={(v) => handleChange("a", v)}
        />
        <PickerSelect
          label="New B"
          evaluations={evaluations}
          value={b}
          onChange={(v) => handleChange("b", v)}
        />
      </div>
      {(a !== null || b !== null) && (
        <p className="text-xs font-mono text-zinc-400">
          {a === null || b === null
            ? "Select both evaluations to view the comparison."
            : null}
        </p>
      )}
    </div>
  );
}

function PickerSelect({
  label,
  evaluations,
  value,
  onChange,
}: {
  label: string;
  evaluations: EvaluationSummary[];
  value: number | null;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs font-mono text-zinc-500 uppercase tracking-widest">
        {label}
      </label>
      <select
        className="border border-zinc-200 rounded px-3 py-2 text-xs font-mono text-zinc-700 bg-white focus:outline-none focus:ring-2 focus:ring-zinc-300 cursor-pointer"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">— pick evaluation —</option>
        {evaluations.map((ev) => (
          <option key={ev.id} value={ev.id}>
            #{ev.id} · {shortenCommit(ev.repo_commit)} ·{" "}
            {formatDate(ev.created_at)} · {ev.verdict}
          </option>
        ))}
      </select>
      {value !== null && (
        <span className={`text-xs font-mono ${verdictColor(evaluations.find((e) => e.id === value)?.verdict ?? "within-noise")}`}>
          {evaluations.find((e) => e.id === value)?.verdict ?? ""}
        </span>
      )}
    </div>
  );
}
