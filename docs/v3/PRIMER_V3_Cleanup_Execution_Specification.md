# PRIMER V3 — Cleanup Execution Specification

**File:** `PRIMER_V3_CLEANUP_EXECUTION_SPEC.md`
**Inputs:** V3 Product Experience Specification (Spec); V3 Implementation Readiness Audit (Audit); V3 Implementation Readiness Roadmap (Roadmap).

---

## 0. Authority, Scope & Global Constraints

**Authority order:** Spec > Roadmap > Audit. CLAUDE.md governs execution conduct. The V2 `PRIMER_V2_ARCHITECTURE_IMPLEMENTATION_SPEC.md` §0.1 "Frozen surfaces" rule still binds all engine/CLI code until its amendment is approved — therefore **every change to `primer/**` is excluded from C0–C4 and routed to the approval-gated set.**

**Scope:** Cleanup only. Executable phases are **C0–C4**. Approval-gated items (Roadmap Phase 1 governance + all engine/CLI touches) are the excluded "Phase 5" and appear only in the callout. No implementation phases beyond C0–C4.

**Global constraints (binding on every phase):** No code. No implementation prompts. No UI redesign. No architecture redesign. No new product ideas. C0–C4 touch **dashboard files and untracked cruft only**; routes, schema, fields, scoring, and export formats are untouched. Exact hex tokens, final copy strings, and component internals are implementation-time decisions and are deliberately **not** specified here (specifying them would constitute redesign); acceptance criteria are outcome-based and reference Spec sections.

**Phase map (reconciliation):**

| Cleanup phase | Roadmap origin | Nature |
|---|---|---|
| C0 | Roadmap Phase 0 | Delete-now (zero-risk) |
| C1 | Roadmap Phase 2 — color subset | Refactor-now (dashboard) |
| C2 | Roadmap Phase 2 — verdict/label/framing subset | Refactor-now (dashboard) |
| C3 | Roadmap Phase 3 + provenance consolidation | Refactor-now (dashboard) |
| C4 | Roadmap Phase 4 | Audit + conditional Refactor-now (dashboard) |
| Excluded ("Phase 5") | Roadmap Phase 1 governance + all `primer/**` touches | Approval-gated |

**Residual-seam note:** Roadmap Phase 2's badge/CLI recolor is moved to the excluded set (frozen `primer/**`). Consequently, after C0–C4 the **dashboard** is V3-honest but the **badge `scores.json` and CLI report remain yellow**, and cross-isolation comparison still computes, until the approval-gated work lands. C0–C4 do not, by themselves, make the badge honest.

**Canonical completion-report format (referenced by every phase):** Phase ID · paths deleted · paths modified · each acceptance item (met / not met) · each validation gate (pass / fail) · rollback invoked (yes/no — refactor phases only) · commit hash · unresolved blockers.

---

## C0 — Zero-Risk Deletions & Hygiene

**Objective:** Remove untracked duplicate/cruft artifacts and the two obsolete anti-V3 skills so no executor is misdirected and the tree is clean before any refactor begins.

**Files/directories affected:**

| Path | Change type | Note |
|---|---|---|
| `.agents_backup/` (incl. `skills/primer-dashboard/`, `skills/primer-motion/`) | Delete | Duplicate of `.agents/` + obsolete skills (Audit §4, §6 #1–3) |
| `package.json`, `package-lock.json`, `node_modules/` (repo root) | Delete | `.gitignore`-acknowledged "prep packages"; nothing imports them (Audit §4, §6 #4) |
| `dashboard/tsconfig.tsbuildinfo` | Delete | Build cache, regenerated (Audit §6 #6) |
| `skills-audit.txt` | Delete | Generated dump (Audit §6 #7) |
| `.gitignore` | Refactor (hygiene) | Add `dashboard/*.tsbuildinfo` and `skills-audit.txt` so they do not reappear |

**Dependencies:** None.
**Parallelization:** Runs parallel with all other phases and with the approval-gated track.
**Acceptance criteria:** All four artifacts absent from the working tree; no engine or dashboard source references any deleted path; the obsolete `primer-dashboard`/`primer-motion` skills no longer resolve anywhere.
**Validation criteria:** build passes + tests pass + static export succeeds.
**Rollback criteria:** Not applicable (Delete-now items; no Refactor-now items in this phase). The `.gitignore` edit is reversible by revert if it over-matches.
**Completion report:** Canonical format; confirm the five paths and CI-green status.

---

## C1 — Color-Honesty Recolor (dashboard)

**Objective:** Move within-noise and refused off caution-yellow and resolve dark-token/contrast debt, establishing the honest palette foundation that C2–C3 build on without change (Spec §13, §20).

**Files/directories affected (all Refactor-now):** `dashboard/tailwind.config.ts`, `dashboard/lib/format.ts` (`verdictColor`, `verdictBg`, `flipStateBadge`), `dashboard/components/WarningBanner.tsx`, `dashboard/components/ComparePanel.tsx`, `dashboard/app/globals.css`.

**Dependencies:** C0 complete (clean tree). Independent of the approval-gated badge/CLI recolor.
**Parallelization:** Parallel with C0 and the approved engine track (disjoint files); **must precede C2/C3** (shares `lib/format.ts`).
**Acceptance criteria:**
- No dashboard surface renders within-noise or refused in amber/yellow; within-noise = calm non-warning neutral, refused = muted/desaturated (§13).
- Amber appears only on the three warning flags (§13).
- The Tailwind token that shadowed the default `neutral` scale is renamed; no unintended color shifts elsewhere.
- Verdict, warning, and flip-state colors meet WCAG AA on the light surface; flip-state pills no longer use dark-surface tokens (§13, §17).
- VerdictHero's existing within-noise calm-zinc treatment is preserved (must-not-regress).

**Validation criteria:** build passes + visual regression check + accessibility check.
**Rollback criteria:** If AA contrast or the visual baseline regresses and cannot be remediated in-phase, revert this phase's commits; dashboard-only, no data/route/schema touched, so revert fully restores the prior palette.
**Completion report:** Canonical format; report contrast results per verdict/warning/flip token.

---

## C2 — Verdict Legibility, Framing & Labels (dashboard)

**Objective:** Replace raw enums with human, never-color-alone verdict and flip labels, add the persistent framing line, and remove "scorecard" framing (Spec §4, §5, §11, §13, §16).

**Files/directories affected (all Refactor-now):** `dashboard/components/VerdictHero.tsx`, `dashboard/lib/format.ts` (verdict word/icon mapping), `dashboard/components/RepositoryOverview.tsx`, `dashboard/components/EvaluationLedger.tsx`, `dashboard/components/ComparePanel.tsx` (`EvalHeadline`), `dashboard/components/EvaluationPicker.tsx`, `dashboard/components/SiteHeader.tsx`, `dashboard/app/layout.tsx`, `dashboard/components/TaskFlipTable.tsx`.

**Dependencies:** C1 complete (verdict word/icon uses the C1 color helpers; shared `lib/format.ts`).
**Parallelization:** Sequential after C1. Within the phase, the header/framing files and the per-surface enum replacements may be split across workers.
**Acceptance criteria:**
- Every verdict shown to a reader is a human word + non-color icon (Helped ▲ / No measurable effect ≈ / Hurt ▼ / Not comparable ⊘) per §5/§13; no raw verdict enum string appears in the reading layer on RepositoryOverview, EvaluationLedger, ComparePanel, or EvaluationPicker (§16).
- A persistent framing line is present on every page (§4/§5/§14); "scorecard" is removed from header and document metadata (§10/§16).
- Per-task flips render in human language, ordered interesting-first (FAIL_TO_PASS, PASS_TO_FAIL first), with task type (§11).
- "pp" is expanded to "percentage points" on first use (§5).
- Copy stays within §16 voice; no strings beyond the Spec's prescribed labels are invented.

**Validation criteria:** build passes + visual regression check + accessibility check.
**Rollback criteria:** If labels/framing regress comprehension or break the build/baseline, revert this phase's commits; restores prior headings and enum rendering. Dashboard-only.
**Completion report:** Canonical format; list each surface confirmed enum-free and the framing line's presence per route.

---

## C3 — Honesty-Surfacing Depth & Provenance Consolidation (dashboard)

**Objective:** Make uncertainty ride with every delta, complete the empty-state suite, retire the dead `data.json` copy reference, and consolidate provenance into one Methods credential (Spec §3, §9, §10, §11, §12; Audit §4, §6 #8).

**Files/directories affected (all Refactor-now):** `dashboard/components/RepositoryOverview.tsx`, `dashboard/components/ComparePanel.tsx`, `dashboard/components/EmptyState.tsx`, `dashboard/components/TrustArchitecture.tsx`, `dashboard/components/ProvenanceFooter.tsx`, `dashboard/components/EvaluationDetail.tsx`.

**Dependencies:** C1 and C2 complete (depth builds on the settled verdict/color/label system; shared files).
**Parallelization:** Sequential after C2. The empty-state work and the provenance consolidation may be split across workers (disjoint components).
**Acceptance criteria:**
- Repository L1 shows the latest verdict with its variance band + `noise_threshold` adjacent, plus a freshness anchor (`repo_commit` + `created_at`) (§3/§10/§14; Principle 2).
- No comparison surface displays any delta (per-eval or cross-eval) without its variance band (§12; Principle 2).
- Empty/edge states cover the §9 set reachable in a static export (no-evaluations, staleness/freshness, refused-as-integrity, not-evaluated, first-evaluation); the dead `--data-output … data.json` reference is replaced with current `--site-output dashboard/public` guidance.
- Provenance is one Methods credential (collapse-capable) with `egress_enforced` highlighted; `primer_overhead_usd` stays a separate line, never summed (§11; 2b.12 — must-not-regress); the redundant provenance component is removed only after its unique fields are merged.

**Validation criteria:** build passes + static export succeeds + visual regression check + accessibility check.
**Rollback criteria:** If the merge drops the separated-overhead line, the `egress_enforced` highlight, or a variance band, revert this phase's commits; restores both prior provenance components and the prior repo/compare/empty surfaces. Dashboard-only.
**Completion report:** Canonical format; confirm overhead-line preservation and "no delta without a band" across all surfaces.

---

## C4 — Motion Debt Audit & Neutralization (dashboard)

**Objective:** Confirm existing motion complies with §7 (compositor-only, valence-neutral, reduced-motion-guarded) and remove any existing effect that violates it. No new motion is designed — verdict-reveal and scroll-driven work are Spec §20 Phase 3 implementation and are out of cleanup scope.

**Files/directories affected:** all `dashboard/components/*.tsx` importing `motion/react`; `dashboard/app/globals.css` (reduced-motion guard verification). Changes are Refactor-now **only if** a violation is found; otherwise verification-only.

**Dependencies:** C1–C3 complete (structure settled, per §20 additive rule).
**Parallelization:** Runs last; verification can proceed in parallel with the approved engine track.
**Acceptance criteria:**
- A complete inventory of existing `motion/react` usages exists, each confirmed: animates `transform`/`opacity` only; identical curve/duration across all four verdict valences; wrapped by a reduced-motion guard (§7; 2b.5).
- Any existing effect failing the above is removed or neutralized; no new animation is introduced.
- The existing reduced-motion guard in `globals.css` is preserved (must-not-regress).

**Validation criteria:** build passes + visual regression check + accessibility check (reduced-motion honored).
**Rollback criteria (only if neutralization changes were made):** If neutralizing an effect breaks a functional reveal or the baseline, revert that change; restores prior motion. If the audit finds no violations, no changes are made and rollback does not apply.
**Completion report:** Canonical format; attach the motion inventory with per-effect pass/fail and any neutralizations.

---

## Explicit Callouts

### Zero-risk deletions (no dependencies, no migrations)

| Item | Path |
|---|---|
| Duplicate skills backup (+ obsolete primer skills) | `.agents_backup/` |
| Root prep packages | `package.json`, `package-lock.json`, `node_modules/` |
| TS build cache | `dashboard/tsconfig.tsbuildinfo` |
| Generated dump | `skills-audit.txt` |

### Approval-gated changes (excluded "Phase 5" — do not begin without sign-off)

| Item | Path(s) | Gate |
|---|---|---|
| Insert V3 as presentation-layer authority | `CLAUDE.md` | Project-owner decision |
| Amend V2 §0.1 "Frozen surfaces" (presentation color/message only) | `docs/PRIMER_V2_ARCHITECTURE_IMPLEMENTATION_SPEC.md` | Owner approval; unblocks the four below |
| Badge recolor (within-noise/refused/not-evaluated off yellow) | `primer/report/export.py` (`build_scores_json`); regenerate `scores.json` | §0.1 amendment |
| CLI delta recolor | `primer/report/render.py` | §0.1 amendment |
| Remove legacy `data.json` export (keep `build_dashboard_json`) | `primer/report/export.py` (`write_dashboard_json`), `primer/cli.py` (`--data-output`) | §0.1 amendment (frozen functions) |
| Extend comparison refusal to isolation mismatch | `primer/report/render.py` (`render_compare`) + `dashboard/lib/compare.ts` (kept in lockstep) | Owner approval (borderline Spec §19) |

### V3-compliant items that must not regress

| Item | Path | Basis |
|---|---|---|
| Honest JSON contracts, `schema_version`, frozen routes | `primer/report/export.py` builders, `dashboard/app/**` | Spec §19 |
| `primer_overhead_usd` separation + caption | `dashboard/components/ProvenanceFooter.tsx` (and its consolidated successor in C3) | 2b.12 |
| VerdictHero within-noise calm-zinc | `dashboard/components/VerdictHero.tsx` | §13 |
| ConfidenceRuler honest delta/noise marker | `dashboard/components/VerdictHero.tsx` | §13 |
| WarningBanner amber-for-warnings semantic (fix contrast only) | `dashboard/components/WarningBanner.tsx` | §13 |
| reduced-motion guard | `dashboard/app/globals.css` | §7 |
| Refusal on provider/model mismatch | `dashboard/lib/compare.ts`, `primer/report/render.py` | §6/§12 |
| Cost-confidence qualifiers | `dashboard/lib/format.ts` (`formatCost`), `primer/report/render.py` (`_format_cost`) | §11/§16 |

### Cleanup items that must be completed before implementation work begins

1. **C0 in full** — especially deletion of `.agents_backup/skills/primer-dashboard` and `…/primer-motion`, whose guidance is anti-V3 and would misdirect implementers.
2. **Approval gate opened** — V3 inserted into CLAUDE.md authority order and V2 §0.1 amended; until then the badge/CLI/legacy-path work is blocked and the V2 freeze still binds `primer/**`.
3. **C1 palette recolor** — the honest color foundation that Spec §20 requires Phases 2–3 to build on without changing.
