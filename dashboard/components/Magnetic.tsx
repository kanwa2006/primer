"use client";

import { useRef, type ReactNode } from "react";
import {
  motion,
  useMotionValue,
  useSpring,
  useReducedMotion,
} from "motion/react";

interface MagneticProps {
  children: ReactNode;
  className?: string;
  /** Max pull toward the cursor, px. Spec: 2–4px. Default 3. */
  strength?: number;
  as?: "div" | "span";
}

// Magnetic interaction — the element drifts 2–4px toward the cursor and springs
// back on exit. Premium, never playful. Reserve for primary/navigational
// affordances. Disabled under reduced motion and on touch (no pointer events).
export function Magnetic({
  children,
  className,
  strength = 3,
  as = "span",
}: MagneticProps) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 280, damping: 18, mass: 0.4 });
  const sy = useSpring(y, { stiffness: 280, damping: 18, mass: 0.4 });

  const onMove = (e: React.PointerEvent) => {
    if (reduce || e.pointerType !== "mouse") return;
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const dx = (e.clientX - (r.left + r.width / 2)) / (r.width / 2);
    const dy = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
    x.set(Math.max(-1, Math.min(1, dx)) * strength);
    y.set(Math.max(-1, Math.min(1, dy)) * strength);
  };
  const onLeave = () => {
    x.set(0);
    y.set(0);
  };

  const MotionTag = as === "div" ? motion.div : motion.span;

  return (
    <MotionTag
      ref={ref as never}
      data-magnetic=""
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      style={{ x: sx, y: sy, display: "inline-flex" }}
      whileHover={reduce ? undefined : { scale: 1.015 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      className={className}
    >
      {children}
    </MotionTag>
  );
}
