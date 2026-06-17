// Aurora atmosphere — fixed, GPU-composited radial mesh tied to the semantic
// palette. Pure CSS (see .aurora-field in globals.css); ~0.5KB, static-safe.
// Sits behind all content; never interactive.
export function AuroraBg() {
  return <div className="aurora-field" aria-hidden="true" />;
}
