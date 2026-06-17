// Graticule texture backdrop — inline SVG tick pattern per §14.5.
// shape-rendering:crispEdges, low-contrast. Purely decorative.
export function GraticuleBg({ className = "" }: { className?: string }) {
  return (
    <div
      className={`absolute inset-0 graticule-bg pointer-events-none select-none ${className}`}
      aria-hidden="true"
    />
  );
}
