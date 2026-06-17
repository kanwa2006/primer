"use client";

import { useRouter } from "next/navigation";
import { formatDate, shortenCommit } from "@/lib/format";
import { VERDICT_WORD, VERDICT_GLYPH } from "@/lib/verdict";
import { VerdictBadge } from "@/components/VerdictBadge";
import {
  Select, SelectContent, SelectItem, SelectLabel, SelectTrigger, SelectValue, SelectGroup, SelectSeparator,
} from "@/components/ui/select";
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
      <div className="text-[var(--text-tertiary)] text-xs font-mono py-4">
        No evaluations available. Run{" "}
        <code className="font-mono bg-[var(--surface-raised)] px-1.5 py-0.5 rounded text-[var(--text-secondary)]">
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
      <p className="text-[var(--text-tertiary)] text-xs font-mono">
        Select two evaluations to compare. PRIMER refuses cross-model comparisons.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
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
      {(a !== null || b !== null) && (a === null || b === null) && (
        <p className="text-xs font-mono text-[var(--text-tertiary)]">
          Select both evaluations to view the comparison.
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
  const isIncompatible = (ev: EvaluationSummary) =>
    incompatibleWith != null &&
    ev.id !== incompatibleWith.id &&
    (ev.provider !== incompatibleWith.provider || ev.model !== incompatibleWith.model);

  const anyDisabled = evaluations.some(isIncompatible);
  const selectedEval = value !== null ? evaluations.find((e) => e.id === value) : null;

  return (
    <div className="flex flex-col gap-2">
      <label className="text-[10px] font-mono text-[var(--text-tertiary)] uppercase tracking-widest">
        {label}
      </label>
      <Select
        value={value !== null ? String(value) : ""}
        onValueChange={onChange}
      >
        <SelectTrigger>
          <SelectValue placeholder="— pick evaluation —" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectLabel>Evaluations</SelectLabel>
            {evaluations.map((ev) => {
              const disabled = isIncompatible(ev);
              return (
                <SelectItem
                  key={ev.id}
                  value={String(ev.id)}
                  disabled={disabled}
                >
                  #{ev.id} · {shortenCommit(ev.repo_commit)} · {formatDate(ev.created_at)} · {VERDICT_GLYPH[ev.verdict]} {VERDICT_WORD[ev.verdict]}
                  {disabled ? " (incompatible)" : ""}
                </SelectItem>
              );
            })}
          </SelectGroup>
        </SelectContent>
      </Select>

      {anyDisabled && (
        <p className="text-[11px] font-mono text-[var(--text-tertiary)] leading-relaxed">
          Greyed evaluations use a different provider or model — PRIMER refuses cross-model comparisons.
        </p>
      )}
      {selectedEval && (
        <VerdictBadge verdict={selectedEval.verdict} size="sm" />
      )}
    </div>
  );
}
