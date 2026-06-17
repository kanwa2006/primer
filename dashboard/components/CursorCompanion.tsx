"use client";

import { useEffect, useState } from "react";
import {
  motion,
  useMotionValue,
  useSpring,
  useReducedMotion,
} from "motion/react";

// Premium cursor companion — a near-invisible lagged follower that increases
// the *perception* of smoothness without becoming a visual feature.
// Pointer-fine only; removed under reduced motion and on touch.
// Also doubles as the ambient controller: pauses the aurora when the tab hides.
export function CursorCompanion() {
  const reduce = useReducedMotion();
  const [fine, setFine] = useState(false);
  const [active, setActive] = useState(false);

  const x = useMotionValue(-100);
  const y = useMotionValue(-100);
  // Lagged interpolation — the "delayed follow".
  const sx = useSpring(x, { stiffness: 220, damping: 26, mass: 0.6 });
  const sy = useSpring(y, { stiffness: 220, damping: 26, mass: 0.6 });
  const scale = useSpring(1, { stiffness: 300, damping: 22 });

  // Pause ambient drift when the tab is hidden (perf + battery).
  useEffect(() => {
    const onVis = () =>
      document.body.setAttribute(
        "data-tab-hidden",
        document.hidden ? "true" : "false"
      );
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  useEffect(() => {
    if (reduce) return;
    const mq = window.matchMedia("(hover: hover) and (pointer: fine)");
    setFine(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setFine(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [reduce]);

  useEffect(() => {
    if (!fine || reduce) return;
    const move = (e: PointerEvent) => {
      x.set(e.clientX);
      y.set(e.clientY);
      if (!active) setActive(true);
      // Subtle emphasis over interactive targets.
      const el = e.target as HTMLElement | null;
      const interactive = !!el?.closest(
        'a, button, [role="button"], input, select, summary, [data-magnetic]'
      );
      scale.set(interactive ? 1.9 : 1);
    };
    const leave = () => setActive(false);
    window.addEventListener("pointermove", move, { passive: true });
    window.addEventListener("pointerleave", leave);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerleave", leave);
    };
  }, [fine, reduce, active, scale, x, y]);

  if (reduce || !fine) return null;

  return (
    <motion.div
      aria-hidden="true"
      className="cursor-companion fixed top-0 left-0 z-[60] pointer-events-none rounded-full"
      style={{
        x: sx,
        y: sy,
        scale,
        width: 10,
        height: 10,
        marginLeft: -5,
        marginTop: -5,
        background: "var(--accent-signal)",
        opacity: active ? 0.32 : 0,
        mixBlendMode: "screen",
        transition: "opacity 0.3s ease",
      }}
    />
  );
}
