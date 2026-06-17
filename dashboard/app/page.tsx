import { readFile } from "node:fs/promises";
import path from "node:path";
import { EmptyState } from "@/components/EmptyState";
import { RepositoryOverview } from "@/components/RepositoryOverview";
import type { RepositoryData } from "@/lib/types";

export default async function Home() {
  let data: RepositoryData | null = null;

  try {
    const filePath = path.join(process.cwd(), "public", "repository.json");
    const raw = await readFile(filePath, "utf-8");
    const parsed = JSON.parse(raw) as RepositoryData;
    if (parsed && typeof parsed === "object" && "schema_version" in parsed) {
      data = parsed;
    }
  } catch {
    // file absent or invalid — fall through to EmptyState
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      {data ? <RepositoryOverview data={data} /> : <EmptyState />}
    </div>
  );
}
