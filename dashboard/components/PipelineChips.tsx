// Pipeline chip row — static SVG/flex connector L→R per §7.1.
// Illustrates the PRIMER measurement pipeline; purely informational.

const STEPS = [
  "Ingest",
  "Generate CLAUDE.md",
  "Derive tasks",
  "Build pinned image",
  "Run ×N (with/without)",
  "Score",
  "Export",
] as const;

export function PipelineChips() {
  return (
    <div
      className="w-full overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden [mask-image:linear-gradient(to_right,#000_94%,transparent)] lg:[mask-image:none]"
      aria-label="PRIMER pipeline"
    >
      <div className="flex items-center gap-0 min-w-max py-1">
        {STEPS.map((step, i) => (
          <span key={step} className="flex items-center gap-0">
            <span className="px-2.5 py-1 rounded-md border border-[var(--border-hairline)] bg-[var(--surface-raised)] text-[11px] font-medium tracking-tight text-[var(--text-secondary)] whitespace-nowrap">
              {step}
            </span>
            {i < STEPS.length - 1 && (
              <svg
                width="20"
                height="8"
                viewBox="0 0 20 8"
                fill="none"
                className="shrink-0"
                aria-hidden="true"
              >
                <line
                  x1="0" y1="4" x2="14" y2="4"
                  stroke="var(--border-strong)"
                  strokeWidth="1"
                  shapeRendering="crispEdges"
                />
                <polyline
                  points="11,1 15,4 11,7"
                  fill="none"
                  stroke="var(--border-strong)"
                  strokeWidth="1"
                  shapeRendering="crispEdges"
                />
              </svg>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}
