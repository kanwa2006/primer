# PRIMER V3 — Implementation Architecture

**File:** `PRIMER_V3_IMPLEMENTATION_ARCHITECTURE.md`
**Inputs:** Product Experience Specification (Spec); Readiness Audit; Readiness Roadmap; Cleanup Execution Specification.
**Authority:** Spec > Roadmap > Audit. CLAUDE.md and the V2 §0.1 freeze govern conduct; all `primer/**` change remains approval-gated. This document defines structure only — no code, no prompts, no task breakdowns.

---

## 0. Architectural Premise — Frozen Core / Mutable Shell

The single governing fact: **PRIMER's measurement engine, its data contracts, its routes, and its scoring math are a frozen core; V3 is a presentation-layer architecture composed above the export boundary.** The data is already honest (Spec §2); V3 re-weights, re-labels, wraps, adds, and — at one gated seam — recolors. It never reaches below the field output of the export boundary.

**The stack, top to bottom:**

```
Voice / copy system            ─┐
Motion-primitive layer (wrap)   │  MUTABLE SHELL  (V3 presentation architecture)
Honesty-surfacing components    │  — built/finished by the implementation phases
Verdict + label display system  │
Palette / token foundation     ─┘
────────── export boundary (field output is FROZEN) ──────────
scores.json · repository.json · evaluations/<id>.json   ← contracts (FROZEN shape)
primer/report/export.py builders · render.py · cli.py    ← FROZEN behavior; only
                                                            color string + refusal
                                                            predicate are gated-mutable
primer/eval · store · generate · ingest · llm · Docker   ← FROZEN CORE
```

Everything the implementation phases do lives above the boundary, except **Phase A**, which touches only presentation attributes (badge color, CLI color, refusal predicate, dead-path retirement) below it under approval.

---

## 1. Disposition Map

Five dispositions, sharply defined:
- **Frozen** — forbidden to change (behavior, fields, schema, routes, scoring, isolation).
- **Survives** — carried into V3 with role and internals intact (at most cleanup-level color/copy already applied).
- **Replaced** — retired; a different element assumes its role.
- **Wrapped** — kept intact; a new layer is composed around it to add V3 behavior.
- **Rebuilt** — role retained; internals re-implemented.

### 1.1 Frozen

| Element | Why frozen |
|---|---|
| `primer/eval/**`, `primer/store/**`, `primer/generate/**`, `primer/ingest/**`, `primer/llm/**`, Docker/network/egress isolation | Spec §19; V2 §0.1 — the measurement apparatus |
| Verdict / flip / noise math (`_compute_verdict`, `_compute_flip_state`, `noise_threshold = max(1/n_tasks, stddev)`) | Scoring logic — Spec §19 |
| Contract field schemas + names (`scores.json`, `repository.json`, `evaluations/<id>.json`) | No new fields/formats/schema — Spec §19 |
| Routes `/`, `/evaluations/[id]`, `/compare` | No new routes — Spec §19 |
| Static-export mechanics (`output: export`, `generateStaticParams`, `dynamicParams=false`) | Delivery model is fixed |

### 1.2 Survives

| Element | Note |
|---|---|
| The honest data contracts | The premise of V3; nothing to fix |
| Route server components (`app/page.tsx`, `app/evaluations/[id]/page.tsx`) | Read frozen contracts; unchanged |
| `dashboard/lib/types.ts`, `dashboard/lib/basePath.ts` | `types.ts` mirrors the frozen schema |
| `ConfidenceRuler` (delta + noise marker), VerdictHero within-noise calm treatment | Already §13-honest; becomes substrate for Phase-C motion |
| `WarningBanner` amber-for-warnings semantic | Semantic correct (contrast fixed in cleanup) |
| `MeasurementIdentity` (with/without basis) | §11-compliant |
| `lib/format.ts` cost-confidence qualifiers (`formatCost`) | §11/§16-compliant |
| Site-export field builders (`build_repository_json`, `build_evaluation_json`, `build_dashboard_json`) | Field output frozen; survives as shared builder |

### 1.3 Replaced

| Element | Successor | Track |
|---|---|---|
| `TrustArchitecture` + `ProvenanceFooter` (triplicated provenance) | One consolidated Methods credential | Cleanup C3 (done) |
| Raw-enum verdict rendering | Human word + non-color icon display mapping | Cleanup C1/C2 (done) |
| Q5 within-noise/refused color rule (tokens) | §13 neutral/muted palette | Cleanup C1 (done) |
| Q5 color rule in badge `build_scores_json` and CLI `render.py` | §13 neutral/muted mapping | **Phase A (gated)** |
| Provider/model-only refusal predicate | Provider/model/**isolation** refusal | **Phase A (gated)** |
| `data.json` path (`write_dashboard_json` + `--data-output`) | Site-export path | **Phase A (gated)** |
| Obsolete `primer-dashboard` / `primer-motion` skills | V3 Spec as sole authority | Cleanup C0 (done) |

### 1.4 Wrapped

| Element | Wrapping layer |
|---|---|
| Existing component render trees | Centralized motion-primitive layer — valence-neutral reveal/stagger/expand, `@supports` + reduced-motion guarded, compositor-only (Phase C) |
| All route content | Layout-level persistent framing line (cleanup C2; architecturally a layout wrapper) |
| `lib/compare.ts` eligibility predicate (lockstep with engine `render_compare`) | Pin/tray interaction + disabled-with-explanation refusal UI; predicate stays the source of truth (Phase B) |

### 1.5 Rebuilt

| Element | Role kept; internals re-implemented as |
|---|---|
| `EvaluationLedger` (raw table) | Stability-read-in-words + condition-change flags, table demoted to L4 (§10) — Phase B |
| `ComparePanel` + `EvaluationPicker` (two-`<select>` URL flow) | Pin/tray model with dual variance-band framing, asymmetric cost-confidence labeling, "noisier/wider-range" surfacing (§12/§8) — Phase B; **logic wrapped (1.4), UI rebuilt** |
| Per-task flip presentation | Human-label table (cleanup) **plus** an honest flip-state stacked bar (§13) — Phase B |

---

## 2. Implementation Phases (after cleanup C0–C4)

Cleanup established the honest static foundation (palette, verdict words/icons, framing, variance-beside-delta, empty states, Methods consolidation). The phases below build the remaining V3 experience on top and align the gated engine. Each phase is described architecturally; sequencing follows the Spec §20 additive rule (no phase undoes an earlier one).

### Phase A — Engine & Contract Honesty Alignment *(approval-gated prerequisite)*
- **Objective:** once V3 authority is recorded and V2 §0.1 amended (presentation-only), make badge, CLI, and dashboard tell one honest story.
- **Architectural scope:** realizes the Replaced color rules (badge, CLI), the Replaced refusal predicate (adds isolation), and the Replaced `data.json` retirement. No field, schema, scoring, or route change.
- **Dependencies:** the governance approval gate. Disjoint from dashboard files except the `lib/compare.ts` mirror, which moves in lockstep with `render_compare`.
- **Parallelization:** runs parallel with Phases B and C once the gate opens (`primer/**` files are disjoint from the dashboard shell).
- **Frozen boundary respected:** only color strings, the refusal predicate, and the dead export path move; verdict math and contract shapes are untouched.
- **Exit state:** badge and CLI no longer render within-noise/refused as caution-yellow; cross-isolation deltas are refused engine-side; a single export path remains.

### Phase B — Experience Depth Completion
- **Objective:** finish the §20-Phase-2 surfaces cleanup left partial so every reader-facing surface carries full honesty depth.
- **Architectural scope:** Rebuild of repository history (stability read + condition-change flags), Rebuild of the comparison experience (pin/tray) Wrapping the eligibility predicate, Rebuild of per-task evidence (+ stacked bar). Entirely above the frozen contracts; reads existing fields only.
- **Dependencies:** cleanup C1–C3 (honest verdict/color/label/variance foundation). The comparison rebuild's full correctness depends on Phase A's isolation refusal; sequence the engine predicate before or alongside the comparison UI, otherwise the dashboard mirror is the declared interim source of truth.
- **Parallelization:** the history, comparison, and per-task tracks are mutually independent (disjoint components); parallel with Phase A.
- **Frozen boundary respected:** routes and contracts unchanged.
- **Exit state:** repository reads as stability-in-words with condition-change flags; comparison is a pin/tray with dual bands and disabled-with-explanation; flip evidence pairs a human-label table with an honest stacked bar.

### Phase C — Premium Motion & Interaction Layer *(wrapped)*
- **Objective:** add §20-Phase-3 premium feel as a centralized motion layer wrapping the settled structure, identical across verdict valences.
- **Architectural scope:** introduces the Wrapped motion-primitive layer (verdict reveal + variance-band draw-in, focus expand, scroll-driven per-task stagger, comparison pin/unpin and page view-transitions) and the microinteraction/tooltip/focus-motion language. Compositor-only, `@supports` + reduced-motion guarded; with no JS or under reduced-motion it degrades exactly to the Phase-B experience.
- **Dependencies:** Phase B (structure must be settled — motion never alters structure).
- **Parallelization:** after B; independent of Phase A.
- **Frozen boundary respected:** no data/route change; no valence-differential motion (2b.5); no Rejection-Register pattern.
- **Exit state:** motion is valence-neutral and reduced-motion-safe; the static fallback equals Phase B.

### Phase D — Voice Finalization & Release Gate
- **Objective:** finalize the §16 voice across all states and pass the §17 Premium SaaS Quality Checklist, resolving every "UNKNOWN/verify" item against the real render.
- **Architectural scope:** a cross-cutting copy/voice convergence (no new components); §17 becomes the acceptance gate; the §18 principles and the 2b register are the audit lens.
- **Dependencies:** A–C (all surfaces present in final form).
- **Parallelization:** convergent and final; not parallel.
- **Exit state:** every §17 item is PASS, every §18 principle testably holds, no 2b pattern present on any surface.

---

## 3. Cross-Phase Invariants

These hold at every phase boundary and are the architecture's acceptance lens:

- **The frozen core is inviolable** — engine, schema, fields, routes, scoring, isolation (Spec §19). Only Phase A touches below the boundary, and only presentation attributes, under approval.
- **The eight Spec §18 principles are architectural invariants** — result-is-the-product; uncertainty-rides-with-the-number; provenance-is-the-credential; the Recruiter Test; refusal-is-a-feature; no Rejection-Register pattern; motion identical across valences; repository-is-the-anchor.
- **Must-not-regress set** (carried from the Cleanup Spec) — `primer_overhead_usd` separation, VerdictHero within-noise calm treatment, ConfidenceRuler, WarningBanner amber semantic, reduced-motion guard, provider/model refusal, cost-confidence qualifiers, honest contracts/routes.
- **Additivity** — each phase composes onto the prior; no phase rewrites a settled layer (Spec §20).
- **Single source of truth for eligibility** — the comparison refusal predicate has exactly one authority (`render_compare`, mirrored by `lib/compare.ts`); the UI wraps it, never reimplements it.
- **Degradation floor** — the no-JS / reduced-motion rendering of the shell never falls below the Phase-B honest static experience.
