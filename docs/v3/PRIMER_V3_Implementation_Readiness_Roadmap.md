### Phase 0 — Zero-risk deletions & hygiene

| Depends on | Unblocks | Parallelizable | Completion criterion |
|---|---|---|---|
| Nothing | Nothing (pure hygiene) | Runs parallel with all phases | The four artifacts gone from the working tree; CI green |

| Item | Disposition | Risk | Rationale | Affected paths | Validation |
|---|---|---|---|---|---|
| `.agents_backup/` incl. obsolete `primer-dashboard` & `primer-motion` skills | Delete now | Low | Full duplicate of `.agents/` plus two anti-V3 skills, untracked and imported by nothing (audit §4, §6 #1–3). | `.agents_backup/` | build passes + tests pass |
| Root frontend "prep packages" | Delete now | Low | `.gitignore`-acknowledged cruft (gsap + duplicate motion libs + unused shadcn deps) that nothing imports (§4, §6 #4). | `package.json`, `package-lock.json`, `node_modules/` | build passes + tests pass |
| TS incremental build cache | Delete now | Low | Regenerated on every build; should not be in-tree (§5, §6 #6). | `dashboard/tsconfig.tsbuildinfo` | build passes + static export succeeds |
| Generated skills dump | Delete now | Low | 323 KB regenerable dump referenced by nothing (§6 #7). | `skills-audit.txt` | build passes + tests pass |

### Phase 1 — Governance & approval gate

| Depends on | Unblocks | Parallelizable | Completion criterion |
|---|---|---|---|
| Nothing | Phase 2 badge/CLI recolor; the isolation-refusal work | Runs parallel with Phase 0 | V3 recorded as presentation authority; §0.1 freeze amended for presentation-only color; isolation-refusal decision recorded |

| Item | Disposition | Risk | Rationale | Affected paths | Validation |
|---|---|---|---|---|---|
| Insert V3 as presentation-layer authority | Decide later (approval) | Low | CLAUDE.md authority order omits V3, which must govern the product-experience layer (§3.5). | `CLAUDE.md` | — |
| Amend V2 §0.1 "Frozen surfaces" to permit presentation-only (color/message/copy) changes | Decide later (approval) | Medium | §0.1 freezes `build_scores_json`/`render.py` "unchanged," directly blocking the P0 recolor (§3.1). | `docs/PRIMER_V2_ARCHITECTURE_IMPLEMENTATION_SPEC.md` | — |
| Extend comparison refusal to isolation mismatch | Decide later (approval) | High | Alters comparison behavior across engine + mirror and is borderline V3 §19, so it needs explicit approval (§3.4, §1 P1). | `dashboard/lib/compare.ts`, `primer/report/render.py`, `docs/PRIMER_V2_ARCHITECTURE_IMPLEMENTATION_SPEC.md` | tests pass + visual regression check |

### Phase 2 — Trust Foundation: recolor, verdict legibility, accessibility

| Depends on | Unblocks | Parallelizable | Completion criterion |
|---|---|---|---|
| Phase 1 (§0.1 amendment for engine items) | Phase 3 | Dashboard-token track runs parallel with engine-badge track once the gate is open; both parallel with Phase 0 | Within-noise renders calm neutral on every surface (badge, repo, ledger, compare, CLI); verdict shows word + non-color icon; no raw enums in the reading layer; framing line on every page; all verdict/warning/flip colors pass AA |

| Item | Disposition | Risk | Rationale | Affected paths | Validation |
|---|---|---|---|---|---|
| Recolor within-noise off amber + rename shadowing token | Refactor now | Medium | amber-400 within-noise is V3's flagship rejection and the token shadows Tailwind's gray scale (§1 P0, §5). | `dashboard/tailwind.config.ts`, `dashboard/lib/format.ts` | visual regression check + accessibility check |
| Badge color mapping | Refactor now | Medium | `build_scores_json` paints within-noise/refused/not-evaluated yellow (§1 P0, §6 regenerate). | `primer/report/export.py`, `scores.json` (regenerate) | tests pass |
| CLI delta coloring | Refactor now | Low | `render.py` colors within-noise/refused yellow — same dishonest semantic on a secondary surface (§1 P0). | `primer/report/render.py` | tests pass |
| Word-first verdict + ▲≈▼⊘ icons | Refactor now | Medium | VerdictHero uses uppercase enums with no non-color icon (§1 P0). | `dashboard/components/VerdictHero.tsx`, `dashboard/lib/format.ts` | visual regression check + accessibility check |
| Raw verdict enum → human words | Refactor now | Low | Verdict enum strings are rendered to readers across four surfaces (§1 P0). | `dashboard/components/RepositoryOverview.tsx`, `dashboard/components/EvaluationLedger.tsx`, `dashboard/components/ComparePanel.tsx`, `dashboard/components/EvaluationPicker.tsx`, `dashboard/lib/format.ts` | visual regression check + accessibility check |
| Persistent framing line | Refactor now | Low | No orientation line exists in global chrome; §5 calls it the highest-leverage change (§1 P0). | `dashboard/components/SiteHeader.tsx`, `dashboard/app/layout.tsx` | visual regression check + accessibility check |
| Remove "scorecard" framing | Refactor now | Low | "scorecard" is the report-card framing V3 §16/§10 reject (§1, §2.4). | `dashboard/components/SiteHeader.tsx`, `dashboard/app/layout.tsx` | visual regression check |
| Fix AA contrast / dark-token leakage | Refactor now | Medium | Flip badges and warning text use dark-theme tokens on a light page, failing AA (§1 P1, §5). | `dashboard/lib/format.ts`, `dashboard/components/WarningBanner.tsx`, `dashboard/components/ComparePanel.tsx`, `dashboard/tailwind.config.ts` | accessibility check + visual regression check |

### Phase 3 — IA & honesty depth + legacy removal

| Depends on | Unblocks | Parallelizable | Completion criterion |
|---|---|---|---|
| Phase 2 (settled verdict/color system) | Completes V3 §20 Phase 2 depth | Parallel with Phase 0; not parallel with Phase 2 | Variance band + threshold beside every delta and a freshness anchor on the repo page; flips in human language, interesting-first; full §9 empty-state suite; comparison never drops a band; one Methods credential; `data.json` path gone |

| Item | Disposition | Risk | Rationale | Affected paths | Validation |
|---|---|---|---|---|---|
| Repo L1 variance + threshold + freshness anchor | Refactor now | Low | Repo verdict is shown without adjacent variance/threshold or staleness anchor (§1 P1). | `dashboard/components/RepositoryOverview.tsx` | visual regression check |
| Flip labels human + interesting-first ordering | Refactor now | Low | Flip enums and unordered rows violate §11/§16 (§1 P1). | `dashboard/components/TaskFlipTable.tsx` | visual regression check + accessibility check |
| Empty-state suite + fix dead `data.json` copy | Refactor now | Low | Only 1 of 7 states exists and it cites the dead `--data-output` command (§1 P1, §5). | `dashboard/components/EmptyState.tsx` | static export succeeds + visual regression check |
| Comparison variance bands on cross-delta + headlines | Refactor now | Medium | Cross-delta and headlines drop variance bands, which §12 forbids (§1 P1). | `dashboard/components/ComparePanel.tsx` | visual regression check |
| Consolidate to one Methods credential (delete the redundant component) | Refactor now | Medium | Provenance is triplicated; §11 wants one credential and the overhead-separate line must survive (§4, §6 #8). | `dashboard/components/TrustArchitecture.tsx`, `dashboard/components/ProvenanceFooter.tsx`, `dashboard/components/EvaluationDetail.tsx` | visual regression check + accessibility check + build passes |
| Remove legacy `data.json` export (keep `build_dashboard_json`) | Delete now | Medium | `write_dashboard_json` + `--data-output` are superseded by site export; depends on the EmptyState copy fix above (§4, §6 #5). | `primer/report/export.py`, `primer/cli.py` | tests pass + static export succeeds |

### Phase 4 — Motion audit (V3 §20 Phase 3)

| Depends on | Unblocks | Parallelizable | Completion criterion |
|---|---|---|---|
| Phases 2–3 (settled structure) | V3 Phase 3 motion work | Runs last; not parallel | Existing motion verified valence-neutral, compositor-only, and reduced-motion-safe, or refactored to comply |

| Item | Disposition | Risk | Rationale | Affected paths | Validation |
|---|---|---|---|---|---|
| Audit/realign existing motion against §7 | Decide later | Medium | Motion was added out of V3 phase order and must be checked for valence-neutrality/compositor-only before extending (§5). | `dashboard/components/*.tsx` (all using `motion/react`) | visual regression check + accessibility check |

### Callout — Zero-risk deletions (no dependencies, no migrations)

| Item | Affected paths |
|---|---|
| `.agents_backup/` (+ obsolete primer skills) | `.agents_backup/` |
| Root prep packages | `package.json`, `package-lock.json`, `node_modules/` |
| TS build cache | `dashboard/tsconfig.tsbuildinfo` |
| Generated skills dump | `skills-audit.txt` |

### Callout — Already V3-compliant: must not regress

| Item | Disposition | Risk | Rationale | Affected paths |
|---|---|---|---|---|
| Honest JSON contracts, schema, routes | Keep | Low | Data is already honest and §19 freezes it. | `primer/report/export.py` (builders), `dashboard/app/**` routes |
| `primer_overhead_usd` separation | Keep | Low | Overhead is correctly never summed into eval cost (§2b.12). | `dashboard/components/ProvenanceFooter.tsx` |
| VerdictHero within-noise calm zinc | Keep | Low | Already non-amber; must not be repainted during the recolor (§Guard). | `dashboard/components/VerdictHero.tsx` |
| ConfidenceRuler honest delta-with-noise marker | Keep | Low | Honest §13 marker, not chart-junk (§Guard). | `dashboard/components/VerdictHero.tsx` |
| WarningBanner amber-for-warnings semantic | Keep (fix contrast only) | Low | Amber is correctly reserved for warnings; only the AA contrast is fixed in Phase 2 (§Guard, §1 P1). | `dashboard/components/WarningBanner.tsx` |
| `prefers-reduced-motion` guard | Keep | Low | Required reduced-motion guard already present (§Guard). | `dashboard/app/globals.css` |
| Refusal on provider/model mismatch | Keep | Low | The refusal that makes other numbers trustworthy is already implemented (§Guard). | `dashboard/lib/compare.ts`, `primer/report/render.py` |
| Cost-confidence qualifiers | Keep | Low | `≈ estimated` / `local (no cost)` already correct (§Guard). | `dashboard/lib/format.ts`, `primer/report/render.py` |
| Four authority docs + Research brief | Keep | Low | Engine/architecture authority stays valid; V3 supersedes presentation only (§2, §3.5). | `docs/authority/**`, `Research/` |

### Callout — Blocked on an explicit approval gate before work begins

| Approval gate | Blocks | Risk |
|---|---|---|
| Amend V2 §0.1 freeze (presentation-only) | Phase 2 badge color + CLI delta coloring | Medium |
| Insert V3 into CLAUDE.md authority order | All V3 presentation work (foundational) | Low |
| Extend comparison refusal to isolation mismatch | Any change to comparison refusal behavior in engine + mirror | High |
