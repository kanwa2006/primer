"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { motion, useMotionValue, useSpring, useReducedMotion } from "motion/react";
import { cn } from "@/lib/cn";

interface InstrumentCardProps {
  children: ReactNode;
  className?: string;
  /** Lift + scale on hover (pointer devices). Default true. */
  lift?: boolean;
  /** Track the pointer with a spring-lagged local glow ("mole under sand"). Default true. */
  glow?: boolean;
  /** Reveal once on scroll-in. Default false (used for above-the-fold cards). */
  reveal?: boolean;
  role?: string;
  "aria-label"?: string;
}

// Machined instrument surface: layered elevation + 1px edge-light, an optional
// pointer-tracked local glow, and a spring hover lift. Compositor-only.
//
// Cursor Surface V2 — the glow position is spring-smoothed, so the lit region
// LAGS and trails the pointer in its direction of travel, then settles and
// fades. The surface reacts; the cursor does not. Disabled on touch + reduced
// motion (the ::before is also removed in CSS under reduced motion).
export function InstrumentCard({
  children,
  className,
  lift = true,
  glow = true,
  reveal = false,
  role,
  "aria-label": ariaLabel,
}: InstrumentCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();

  // Raw pointer position (in %) → springs → CSS vars on the element.
  const x = useMotionValue(50);
  const y = useMotionValue(0);
  // Softer, heavier spring — the lit region trails and settles physically (V3).
  const sx = useSpring(x, { stiffness: 110, damping: 24, mass: 0.65 });
  const sy = useSpring(y, { stiffness: 110, damping: 24, mass: 0.65 });

  useEffect(() => {
    if (!glow || reduce) return;
    const el = ref.current;
    if (!el) return;
    const ux = sx.on("change", (v) => el.style.setProperty("--gx", `${v}%`));
    const uy = sy.on("change", (v) => el.style.setProperty("--gy", `${v}%`));
    return () => { ux(); uy(); };
  }, [glow, reduce, sx, sy]);

  const handleMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!glow || reduce || e.pointerType !== "mouse") return;
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    x.set(((e.clientX - r.left) / r.width) * 100);
    y.set(((e.clientY - r.top) / r.height) * 100);
  };

  return (
    <motion.div
      ref={ref}
      onPointerMove={handleMove}
      whileHover={lift && !reduce ? { y: -4, scale: 1.006 } : undefined}
      transition={{ type: "spring", stiffness: 320, damping: 26 }}
      role={role}
      aria-label={ariaLabel}
      className={cn(
        "instrument-surface rounded-card border border-[var(--border-hairline)]",
        "bg-[var(--surface-elevated)] shadow-card",
        "transition-[border-color,box-shadow] duration-300",
        lift && "hover:border-[var(--border-strong)] hover:shadow-card-hover",
        reveal && "reveal-on-scroll",
        className
      )}
    >
      {children}
    </motion.div>
  );
}
