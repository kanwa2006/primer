"use client";

import { useEffect, useState } from "react";
import { Copy, Check } from "lucide-react";
import { BASE_PATH } from "@/lib/basePath";
import { InstrumentCard } from "@/components/InstrumentCard";

// Export page — badge preview + raw JSON viewer with copy buttons (§7.7)

interface ScoresData {
  schemaVersion: number;
  label: string;
  message: string;
  color: string;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback ignored
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1.5 text-[10px] font-mono text-[var(--text-tertiary)] hover:text-[var(--text-primary)] border border-[var(--border-hairline)] rounded px-2 py-1 transition-colors"
      aria-label={copied ? "Copied!" : "Copy to clipboard"}
    >
      {copied ? (
        <><Check size={11} strokeWidth={2} /> Copied</>
      ) : (
        <><Copy size={11} strokeWidth={1.5} /> Copy</>
      )}
    </button>
  );
}

function JsonViewer({ url, label }: { url: string; label: string }) {
  const [data, setData] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(url)
      .then((r) => r.json())
      .then((d) => setData(d))
      .catch(() => setError("Failed to load " + url));
  }, [url]);

  const pretty = data ? JSON.stringify(data, null, 2) : null;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-4">
        <h3 className="t-eyebrow">{label}</h3>
        <div className="flex items-center gap-2">
          <span className="t-data text-[10px] text-[var(--text-tertiary)]">{url}</span>
          {pretty && <CopyButton text={pretty} />}
        </div>
      </div>
      <div className="border border-[var(--border-hairline)] rounded-md bg-[var(--surface-raised)] p-4 overflow-x-auto max-h-96">
        {error ? (
          <p className="text-xs font-mono text-[var(--warning-fg)]">{error}</p>
        ) : pretty ? (
          <pre className="text-[11px] font-mono text-[var(--text-secondary)] leading-relaxed whitespace-pre">{pretty}</pre>
        ) : (
          <p className="text-xs font-mono text-[var(--text-tertiary)]">Loading…</p>
        )}
      </div>
    </div>
  );
}

export default function ExportPage() {
  const [scores, setScores] = useState<ScoresData | null>(null);

  useEffect(() => {
    fetch(`${BASE_PATH}/scores.json`)
      .then((r) => r.json())
      .then((d) => setScores(d as ScoresData))
      .catch(() => {});
  }, []);

  const badgeUrl = `https://img.shields.io/endpoint?url=<your-site>/primer/scores.json`;
  const badgeMd = `![PRIMER](${badgeUrl})`;

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <div className="mb-10">
        <p className="t-eyebrow mb-2.5">Artifacts</p>
        <h1 className="t-h1 text-[var(--text-primary)]">Export</h1>
        <p className="t-lead mt-3 max-w-[52ch]">
          Live badge, badge markdown snippet, and raw JSON exports for reproducibility.
        </p>
      </div>

      <div className="flex flex-col gap-10">

        {/* Badge preview */}
        <section className="reveal-on-scroll">
          <h2 className="t-eyebrow mb-3">Shields.io badge</h2>
          <InstrumentCard lift={false} glow className="p-5 flex flex-col gap-4">
            {scores ? (
              <div className="flex items-center gap-4">
                {/* Live badge data preview */}
                <span
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-medium text-white"
                  style={{ backgroundColor: scores.color === "64748b" ? "#64748b" : scores.color === "green" ? "#22c55e" : scores.color === "red" ? "#ef4444" : "#71717a" }}
                >
                  {scores.label} | {scores.message}
                </span>
                <span className="t-data text-xs text-[var(--text-tertiary)]">Live from scores.json</span>
              </div>
            ) : (
              <p className="t-data text-xs text-[var(--text-tertiary)]">Loading badge data…</p>
            )}

            <div className="flex flex-col gap-1.5">
              <label className="t-eyebrow">Badge markdown</label>
              <div className="flex items-center gap-2">
                <code className="text-[11px] font-mono text-[var(--text-secondary)] bg-[var(--surface-raised)] px-3 py-1.5 rounded border border-[var(--border-hairline)] flex-1 overflow-x-auto">
                  {badgeMd}
                </code>
                <CopyButton text={badgeMd} />
              </div>
            </div>
          </InstrumentCard>
        </section>

        {/* Raw JSON viewers */}
        <section className="flex flex-col gap-6 reveal-on-scroll">
          <h2 className="t-eyebrow">Raw exports</h2>
          <JsonViewer url={`${BASE_PATH}/scores.json`}      label="scores.json" />
          <JsonViewer url={`${BASE_PATH}/repository.json`}  label="repository.json" />
        </section>

        {/* Reproducibility note */}
        <InstrumentCard lift={false} glow className="px-5 py-4 reveal-on-scroll">
          <h2 className="t-eyebrow mb-2">Reproducibility</h2>
          <p className="t-body text-[var(--text-secondary)]">
            Every evaluation export includes the base image sha256 digest, agent adapter, provider/model, task count, runs per config, egress mode, and exact repo commit. These fields are sufficient to reproduce the measurement environment.
          </p>
        </InstrumentCard>

      </div>
    </div>
  );
}
