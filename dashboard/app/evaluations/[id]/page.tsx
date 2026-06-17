import { readFile } from "node:fs/promises";
import path from "node:path";
import { EvaluationDetail } from "@/components/EvaluationDetail";
import { EmptyState } from "@/components/EmptyState";
import type { DashboardData, RepositoryData } from "@/lib/types";

// Prevents serving unmatched dynamic segments in static export mode.
export const dynamicParams = false;

export async function generateStaticParams(): Promise<{ id: string }[]> {
  try {
    const raw = await readFile(
      path.join(process.cwd(), "public", "repository.json"),
      "utf-8"
    );
    const data: RepositoryData = JSON.parse(raw);
    return data.evaluations.map((e) => ({ id: String(e.id) }));
  } catch {
    // SQLite auto-increment starts at 1, so "0" is never a real evaluation id.
    // This placeholder satisfies Next.js export's requirement that every dynamic
    // route has at least one static path; the page renders EmptyState for it.
    return [{ id: "0" }];
  }
}

export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  // Placeholder path generated when no repository data exists at build time.
  if (id === "0") {
    return (
      <div className="max-w-5xl mx-auto px-6 py-10">
        <EmptyState />
      </div>
    );
  }

  try {
    const raw = await readFile(
      path.join(process.cwd(), "public", "evaluations", `${id}.json`),
      "utf-8"
    );
    const data: DashboardData = JSON.parse(raw);

    let prevId: number | null = null;
    try {
      const repoRaw = await readFile(
        path.join(process.cwd(), "public", "repository.json"),
        "utf-8"
      );
      const repo: RepositoryData = JSON.parse(repoRaw);
      const idx = repo.evaluations.findIndex((e) => String(e.id) === id);
      if (idx !== -1 && idx + 1 < repo.evaluations.length) {
        prevId = repo.evaluations[idx + 1].id;
      }
    } catch {
      // prevId stays null
    }

    return (
      <div className="max-w-5xl mx-auto px-6 py-10">
        <EvaluationDetail data={data} prevId={prevId} />
      </div>
    );
  } catch {
    return (
      <div className="max-w-5xl mx-auto px-6 py-10">
        <EmptyState />
      </div>
    );
  }
}
