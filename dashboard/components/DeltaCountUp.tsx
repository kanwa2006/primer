"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";
import { cn } from "@/lib/cn";

interface DeltaCountUpProps {
  delta: number | null;
  className?: string;
}

// Counts up from 0 to |delta| pp over ~900ms. If delta is exactly 0 (or null),
// skips the count-up and fades in the final value — per spec §15.3.
export function DeltaCountUp({ delta, className }: DeltaCountUpProps) {
  const reduce = useReducedMotion();
  const pp = delta !== null ? delta * 100 : null;
  const isExactZero = pp === 0;
  const [display, setDisplay] = useState<string>(isExactZero || pp === null ? formatPp(pp) : "0.0 pp");
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    // Honor prefers-reduced-motion: snap to the final value, no count-up (spec §15.4).
    if (pp === null || isExactZero || reduce) {
      setDisplay(formatPp(pp));
      return;
    }

    const duration = 900;
    const start = performance.now();
    const target = Math.abs(pp);
    const sign = pp > 0 ? "+" : "−";

    function tick(now: number) {
      const elapsed = now - start;
      const t = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
      const current = target * eased;
      setDisplay(`${sign}${current.toFixed(1)} pp`);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        setDisplay(formatPp(pp));
      }
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [pp, isExactZero, reduce]);

  return (
    <span
      className={cn("font-mono tabular-nums", className)}
      aria-label={`Success delta: ${formatPp(pp)}`}
    >
      {display}
    </span>
  );
}

function formatPp(pp: number | null): string {
  if (pp === null) return "N/A";
  if (pp > 0) return `+${pp.toFixed(1)} pp`;
  if (pp < 0) return `−${Math.abs(pp).toFixed(1)} pp`;
  return "0.0 pp";
}
