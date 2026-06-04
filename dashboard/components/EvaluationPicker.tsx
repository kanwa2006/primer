"use client";

import { useRouter } from "next/navigation";
import { formatDate, shortenCommit, verdictColor, verdictWord, verdictIcon } from "@/lib/format";
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

  const selectedA = a !== null ? evaluations.find((e) => e.id === a) ?? null : null;
  const selectedB = b !== null ? evaluations.find((e) => e.id === b) ?? null : null;

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
          incompatibleWith={selectedB}
          onChange={(v) => handleChange("a", v)}
        />
        <PickerSelect
          label="New B"
          evaluations={evaluations}
          value={b}
          incompatibleWith={selectedA}
          onChange={(v) => handleChange("b", v)}
        />
      </div>
      {(a !== null || b !== null) && (
        <p className="text-xs font-mono text-zinc-500">
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
  incompatibleWith,
  onChange,
}: {
  label: string;
  evaluations: EvaluationSummary[];
  value: number | null;
  incompatibleWith: EvaluationSummary | null;
  onChange: (v: string) => void;
}) {
  const selectId = label.toLowerCase().replace(/\s+/g, "-");
  const isIncompatible = (ev: EvaluationSummary) =>
    incompatibleWith != null &&
    ev.id !== incompatibleWith.id &&
    (ev.provider !== incompatibleWith.provider || ev.model !== incompatibleWith.model);
  const anyDisabled = evaluations.some(isIncompatible);
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={selectId} className="text-xs font-mono text-zinc-500 uppercase tracking-widest">
        {label}
      </label>
      <select
        id={selectId}
        className="border border-zinc-200 rounded px-3 py-2 text-xs font-mono text-zinc-700 bg-white focus:outline-none focus:ring-2 focus:ring-zinc-300 cursor-pointer"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">— pick evaluation —</option>
        {evaluations.map((ev) => {
          const disabled = isIncompatible(ev);
          return (
            <option key={ev.id} value={ev.id} disabled={disabled}>
              #{ev.id} · {shortenCommit(ev.repo_commit)} ·{" "}
              {formatDate(ev.created_at)} · {verdictIcon(ev.verdict)} {verdictWord(ev.verdict)}
              {disabled ? " — not comparable (different provider/model)" : ""}
            </option>
          );
        })}
      </select>
      {anyDisabled && (
        <p className="text-[11px] font-mono text-zinc-500 leading-relaxed">
          Disabled evaluations use a different provider or model than the other selection.
          PRIMER refuses cross-model comparisons, so they cannot be compared here.
        </p>
      )}
      {value !== null && (
        <span className={`text-xs font-mono ${verdictColor(evaluations.find((e) => e.id === value)?.verdict ?? "within-noise")}`}>
          {(() => {
            const ev = evaluations.find((e) => e.id === value);
            return ev ? `${verdictIcon(ev.verdict)} ${verdictWord(ev.verdict)}` : "";
          })()}
        </span>
      )}
    </div>
  );
}
