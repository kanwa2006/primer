import { readFile } from "node:fs/promises";
import path from "node:path";
import { EmptyState } from "@/components/EmptyState";
import { TrendsView } from "@/components/TrendsView";
import type { RepositoryData } from "@/lib/types";

export default async function TrendsPage() {
  let data: RepositoryData | null = null;

  try {
    const filePath = path.join(process.cwd(), "public", "repository.json");
    const raw = await readFile(filePath, "utf-8");
    const parsed = JSON.parse(raw) as RepositoryData;
    if (parsed && typeof parsed === "object" && "schema_version" in parsed) {
      data = parsed;
    }
  } catch {
    // fall through
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <div className="mb-8">
        <p className="t-eyebrow mb-2.5">Longitudinal view</p>
        <h1 className="t-h1 text-[var(--text-primary)]">Trends</h1>
        <p className="t-lead mt-3 max-w-[52ch]">
          Success-rate delta over time. Each point is one evaluation; error bars show the noise envelope.
        </p>
      </div>
      {data && data.evaluation_count > 0 ? (
        <TrendsView data={data} />
      ) : (
        <EmptyState />
      )}
    </div>
  );
}
