"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { BASE_PATH } from "@/lib/basePath";
import { ComparePanel } from "@/components/ComparePanel";
import { EvaluationPicker } from "@/components/EvaluationPicker";
import type { DashboardData, RepositoryData, EvaluationSummary } from "@/lib/types";

// useSearchParams() caller — MUST be inside <Suspense> (Next 15 static export requirement)
function CompareContent() {
  const params = useSearchParams();
  const rawA = params.get("a");
  const rawB = params.get("b");
  const idA = rawA !== null && rawA !== "" ? parseInt(rawA, 10) : null;
  const idB = rawB !== null && rawB !== "" ? parseInt(rawB, 10) : null;
  const bothValid =
    idA !== null && !isNaN(idA) && idB !== null && !isNaN(idB);

  if (bothValid) {
    return <EvalCompareFetch idA={idA!} idB={idB!} />;
  }
  return <EvalPickerFetch idA={idA} idB={idB} />;
}

function EvalCompareFetch({ idA, idB }: { idA: number; idB: number }) {
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "ok"; a: DashboardData; b: DashboardData }
    | { status: "error"; message: string }
  >({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [resA, resB] = await Promise.all([
          fetch(`${BASE_PATH}/evaluations/${idA}.json`),
          fetch(`${BASE_PATH}/evaluations/${idB}.json`),
        ]);
        if (!resA.ok)
          throw new Error(`Evaluation #${idA} not found (HTTP ${resA.status})`);
        if (!resB.ok)
          throw new Error(`Evaluation #${idB} not found (HTTP ${resB.status})`);
        const [a, b]: [DashboardData, DashboardData] = await Promise.all([
          resA.json(),
          resB.json(),
        ]);
        if (!cancelled) setState({ status: "ok", a, b });
      } catch (e) {
        if (!cancelled) setState({ status: "error", message: (e as Error).message });
      }
    }
    load();
    return () => { cancelled = true; };
  }, [idA, idB]);

  if (state.status === "loading") return <Spinner />;

  if (state.status === "error") {
    return (
      <div className="flex flex-col gap-6">
        <div
          className="flex items-start gap-3 px-4 py-3 rounded border border-red-300/30 bg-red-500/5"
          role="alert"
        >
          <p className="text-red-400 text-xs leading-relaxed font-mono">{state.message}</p>
        </div>
        <EvalPickerFetch idA={null} idB={null} />
      </div>
    );
  }

  return <ComparePanel a={state.a} b={state.b} />;
}

function EvalPickerFetch({
  idA,
  idB,
}: {
  idA: number | null;
  idB: number | null;
}) {
  const [evals, setEvals] = useState<EvaluationSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${BASE_PATH}/repository.json`);
        if (!res.ok)
          throw new Error(`repository.json not found (HTTP ${res.status})`);
        const data: RepositoryData = await res.json();
        if (!cancelled) setEvals(data.evaluations);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  if (error) {
    return (
      <div className="text-xs font-mono text-red-400 py-4" role="alert">
        Failed to load evaluations: {error}
      </div>
    );
  }

  if (evals === null) return <Spinner />;

  return <EvaluationPicker evaluations={evals} a={idA} b={idB} />;
}

function Spinner() {
  return (
    <div className="text-zinc-500 text-xs font-mono py-8 text-center animate-pulse">
      Loading…
    </div>
  );
}

export default function ComparePage() {
  return (
    <main className="max-w-5xl mx-auto px-6 py-10">
      <div className="flex flex-col gap-8">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold tracking-tight text-zinc-900">
            Compare evaluations
          </h1>
          <p className="text-xs font-mono text-zinc-500">
            Side-by-side provenance diff and cross-evaluation delta.
          </p>
        </div>
        <Suspense
          fallback={
            <div className="text-zinc-500 text-xs font-mono py-8 text-center animate-pulse">
              Loading…
            </div>
          }
        >
          <CompareContent />
        </Suspense>
      </div>
    </main>
  );
}
