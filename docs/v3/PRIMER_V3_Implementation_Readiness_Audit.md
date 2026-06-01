# PRIMER V3 — Implementation Readiness Audit

**Source of truth:** `PRIMER_V3_Product_Experience_Specification.md`. **Scope:** V3 is UI/presentation-only (§19 freezes routes, fields, schema, scoring). The JSON contracts emitted by `primer/report/export.py` (`repository.json`, `evaluations/<id>.json`) are **already honest** — they carry `success_stddev`, `success_min/max`, `noise_threshold`, `cost_confidence`, separated `primer_overhead_usd`, the three warnings, `egress_enforced`, and 4-verdict labels. **No data-layer deletion is warranted.** Every conflict below is in the *presentation, governance, skills, or build cruft* layers.

No files were modified — this is the cleanup audit only.

---

## 1. Project artifacts that conflict with V3

**P0 — the caution-yellow semantic (V3's single most-cited rejection: §2b.8, §13, §5, §17).**

| Artifact | Conflict |
|---|---|
| [tailwind.config.ts:18](dashboard/tailwind.config.ts:18) | `neutral: "#fbbf24"` (amber-400) is the within-noise color. V3 §13 mandates within-noise = **calm slate/blue-gray**, amber **reserved only for warnings**. Also shadows Tailwind's built-in `neutral` gray scale (footgun). |
| [lib/format.ts:29-45](dashboard/lib/format.ts:29) | `verdictColor`/`verdictBg` map `within-noise → text-neutral` (amber). Consumed by RepositoryOverview, EvaluationLedger, ComparePanel, EvaluationPicker. |
| [primer/report/export.py:71-82](primer/report/export.py:71) | `build_scores_json`: **yellow** for `delta==0`, within-noise, and refused. The live badge [scores.json](scores.json) currently renders `"not evaluated"` in **yellow** — §9 requires "Not evaluated" be neutral/non-judgmental. |
| [primer/report/render.py:226-242](primer/report/render.py:226) | CLI `_format_delta`/`_delta_text`/`_noise_label` color within-noise/zero/refused **yellow**. (Terminal, not the recruiter surface — secondary, but the same dishonest semantic.) |

**P0 — verdict legibility & framing.**

| Artifact | Conflict |
|---|---|
| [components/SiteHeader.tsx](dashboard/components/SiteHeader.tsx), [app/layout.tsx:20-26](dashboard/app/layout.tsx:20) | **No persistent framing line** anywhere in global chrome. §5 calls this "the highest-leverage change in the product"; §4/§14/§17 make it mandatory. Header instead says **"scorecard"** (§16 avoids "score"; §10 "never a report card"). Metadata title `"PRIMER — Scorecard"` repeats it. |
| [components/VerdictHero.tsx:8-13](dashboard/components/VerdictHero.tsx:8) | Verdict headings are uppercase enums (`POSITIVE`/`WITHIN MEASUREMENT NOISE`) with **no ▲ ≈ ▼ ⊘ icon**. §5/§13/§16 require word-first verdict ("Helped / No measurable effect / Hurt / Not comparable") + non-color icon. The naked delta is the giant hero; the verdict word is a tiny label — inverts §13/§14 "word + delta share the hero." |
| [components/RepositoryOverview.tsx:41-42](dashboard/components/RepositoryOverview.tsx:41), [EvaluationLedger.tsx:64](dashboard/components/EvaluationLedger.tsx:64), [ComparePanel.tsx:132-133](dashboard/components/ComparePanel.tsx:132), [EvaluationPicker.tsx:100-101](dashboard/components/EvaluationPicker.tsx:100) | Render the **raw verdict enum** (`within-noise`) in the reading layer. §16 bans raw field values facing the reader. |

**P1 — IA & honesty surfacing.**

| Artifact | Conflict |
|---|---|
| [components/RepositoryOverview.tsx:38-50](dashboard/components/RepositoryOverview.tsx:38) | Repo L1 shows latest verdict + delta with **no adjacent variance band / noise_threshold** (Principle 2, §3, §10) and **no freshness anchor** (`created_at`/staleness caveat — §9/§14). |
| [components/TaskFlipTable.tsx:7-12,106](dashboard/components/TaskFlipTable.tsx:7) | Flip labels are `"FAIL → PASS"` (enum jargon), not §11/§16 human language ("Fixed by the file"…). Rows are **not ordered interesting-first** (FAIL_TO_PASS/PASS_TO_FAIL first per §4/§11). |
| [components/ComparePanel.tsx:48-55](dashboard/components/ComparePanel.tsx:48) | The cross-evaluation delta-of-deltas is shown as a naked 2xl number with **no variance bands** — §12 says "any comparison that drops a variance band… Must be prevented/flagged." Headlines (EvalHeadline) also omit bands. |
| [components/ComparePanel.tsx:23-34](dashboard/components/ComparePanel.tsx:23) + [lib/compare.ts:15](dashboard/lib/compare.ts:15) | Isolation mismatch only **soft-warns** while still computing/showing the delta; refusal fires on provider/model only. §12 wants cross-isolation deltas prevented/hard-flagged. |
| [components/EmptyState.tsx:38-39](dashboard/components/EmptyState.tsx:38) | Only **1 of 7** §9 states exists, and it cites the **dead** `primer export --data-output dashboard/public/data.json` path (see §5 debt). |

**P1 — accessibility (WCAG AA, §13/§17).**

| Artifact | Conflict |
|---|---|
| [lib/format.ts:57-65](dashboard/lib/format.ts:57) `flipStateBadge` | Dark-theme tokens (`bg-zinc-800/900`, `text-zinc-400`) rendered on the **light** `#fafafa` page → unreadable pills. |
| [components/WarningBanner.tsx:31](dashboard/components/WarningBanner.tsx:31) | `text-amber-300` on near-white bg → fails AA contrast (dark-theme leakage). Same in [ComparePanel.tsx:30](dashboard/components/ComparePanel.tsx:30). |
| [tailwind.config.ts:16-19](dashboard/tailwind.config.ts:16) | `positive`/`negative` are light-on-light (emerald-400/red-400 as text on `#fafafa`) — verify/upgrade for AA. |

## 2. Obsolete V1/V2 assumptions

1. **The Q5 color rule** — `SESSION_1_FINAL_REVISION:97` and `CONSOLIDATED_IMPLEMENTATION_SPEC:55`: *"Color: green Δ>0, **yellow ~0**, red Δ<0."* This V1 decision is the root of every caution-yellow artifact above. **Rejected by V3 §2b.8/§13.**
2. **"Within-noise label is the same class as sign→color"** — `DECISION_ADDENDUM:64`, `CONSOLIDATED:76`. Couples within-noise to the color classification; V3 §13 **decouples** it onto a calm non-warning neutral.
3. **Dashboard/badge = "Nice-to-Have / stopgap / Phase 7"** — `SESSION_1:160`, `CONSOLIDATED:106`. V3 elevates the product experience to a **first-class premium deliverable** with its own 3-phase roadmap (§20). The priority inversion is itself an obsolete assumption.
4. **"Scorecard" product framing** — `PRIMER_V2_IMPLEMENTATION_PROMPTS:191`, `PRIMER_V2_ARCHITECTURE_IMPLEMENTATION_SPEC:469`. V3 §16/§10 reject "score"/report-card framing.
5. **Single-file `data.json` model** — pre-dates the repository-centric split. V3 §3 IA is repository → evaluation; `data.json` is dead (the V2 prompts themselves say "data.json no longer exists" at line 298, but code/copy didn't follow through).
6. **"High information density" as a blanket rule** — `primer-dashboard` SKILL line 143. V3 §5/§13/§2b.7 require **recruiter-sparse L1–L2**, density only at L4.
7. **3-verdict mental model** — `primer-dashboard` SKILL lines 99-104 omit **`refused`**. V3 treats refusal as a first-class, proudest-moment outcome (§6, Principle 5).
8. **Refuse on provider/model only** — `PRIMER_V2_ARCHITECTURE_IMPLEMENTATION_SPEC §0.3`. V3 §12 extends refusal/hard-flag to **isolation** mismatch.

## 3. Implementation constraints that should be removed (or amended)

1. **V2 "Frozen surfaces" freeze on the badge/CLI color logic** — `PRIMER_V2_ARCHITECTURE_IMPLEMENTATION_SPEC §0.1` freezes `build_scores_json`, `write_scores_json`, and `render.py` "reused **unchanged**." This **directly blocks** the V3 P0 recolor. **Amend** to un-freeze *presentation only* (color, message string, copy) while keeping verdict/noise **math** frozen (still honored under V3 §19). This is the #1 constraint to lift.
2. **`primer-motion` skill constraints** — *forbids scroll-trigger animations* (line 97, which V3 §7/§20 Phase 3 **requires**), mandates *spring easing* (71; V3 wants ease-out) and *Framer Motion only* (111; V3 is CSS-compositor-first). Remove this skill's authority entirely (see §4).
3. **`primer-dashboard` skill "high information density"** (line 143) and scores.json-centric IA — remove; V3 spec is the dashboard authority.
4. **Refusal predicate = provider/model only** — in [lib/compare.ts:15](dashboard/lib/compare.ts:15) and `render.py` `render_compare:396-444`. Extending to isolation alters comparison behavior — **flag for explicit approval** (CLAUDE.md: "never redesign without approval"; borderline vs §19), framed as honesty alignment, not scoring change.
5. **CLAUDE.md authority order omits V3** (governance meta-constraint) — see §6 register; V3 must be inserted as the governing authority for the presentation/product-experience layer.

## 4. Components to **delete** rather than upgrade

Most dashboard components are structurally sound and should be **upgraded in place** (VerdictHero, RepositoryOverview, EvaluationDetail, MetricsGrid, MeasurementIdentity — see §1). Genuine delete-don't-upgrade targets:

- **`.agents_backup/`** (entire directory) — a full duplicate of `.agents/` plus two obsolete skills. Pure clutter.
- **`.agents_backup/skills/primer-dashboard/` and `…/primer-motion/`** — their guidance is *actively anti-V3* (§2, §3 above). Do not upgrade; delete and let V3 §7/§13 be the authority.
- **Root `package.json` + root `node_modules/` + root `package-lock.json`** — `.gitignore`-acknowledged "root-level prep packages." Carries `gsap`, both `framer-motion` *and* `motion`, and unused `@radix-ui`/`cva`/`lucide` that **nothing in the project imports** (the dashboard has its own `package.json`). GSAP/heavy-JS motion contradicts V3 §7 (and the old skill even forbade GSAP ScrollTrigger).
- **`write_dashboard_json` + the `--data-output`/`data.json` path** — legacy single-file export, superseded by site export. ⚠️ Keep `build_dashboard_json` — it is still the shared field-builder for `build_evaluation_json`. Delete only the standalone writer + flag.
- **`dashboard/tsconfig.tsbuildinfo`**, **`skills-audit.txt`** — build cache / 323 KB generated dump; should not be in-tree.

**Consolidate (delete one after merging):** [TrustArchitecture.tsx](dashboard/components/TrustArchitecture.tsx) and [ProvenanceFooter.tsx](dashboard/components/ProvenanceFooter.tsx) both render provenance (base_image, network/egress, commit) — triplicated with [MeasurementIdentity.tsx](dashboard/components/MeasurementIdentity.tsx). V3 §11 wants **one** collapsible "Methods" credential. Note: `primer_overhead_usd` is rendered **only** in ProvenanceFooter (correctly separated, §2b.12) and the 6 pillars only in TrustArchitecture — merge before deleting either.

## 5. Technical debt that would slow V3 execution

- **Light/dark token leakage** — components mix dark-theme tokens (`bg-zinc-800/900`, `text-amber-300`) into a light app. A V3 palette pass (§13 P0) must first normalize these or recolors will silently break contrast. *Highest-friction debt.*
- **`neutral` token shadows Tailwind's gray scale** ([tailwind.config.ts:18](dashboard/tailwind.config.ts:18)) — any future `text-neutral-*` usage resolves to a single amber hex. Rename the semantic token (e.g. `within`) during the recolor.
- **Two parallel comparison engines kept "in lockstep"** — [lib/compare.ts](dashboard/lib/compare.ts) explicitly mirrors `render.py:render_compare`. Every §12 comparison fix must touch **both**, or they silently diverge.
- **Motion implemented out of V3 phase order** — `motion` (Framer) animations are already woven through Phase-1/2 components (VerdictHero delta-marker scale-in, staggered rows), but V3 makes motion **Phase 3** and demands compositor-only + **valence-neutral** + reduced-motion. The early dependency must be audited against §7 before Phase 3, not extended.
- **Stale CLI copy** — [EmptyState.tsx:38](dashboard/components/EmptyState.tsx:38) and the `primer-dashboard` skill point at the dead `data.json` flow; will mislead anyone wiring the export.
- **Local artifacts in tree** (`primer.db`, `primer.egg-info/`, `.pytest_cache/`, `__pycache__/`) — all correctly **gitignored** (not committed cruft); noted only as disk clutter, not deletion candidates.

## 6. Deletion register

| # | File / artifact | Reason | Conflicts with V3 § | Safe to delete? | Migration requirement |
|---|---|---|---|---|---|
| 1 | `.agents_backup/` (whole dir) | Full duplicate of `.agents/` + 2 obsolete skills; untracked | §2b (debt elimination) | **Yes** | Confirm tooling reads `.agents/` (it does; `skills-lock.json` tracks only the 5 generic skills). None. |
| 2 | `.agents_backup/skills/primer-dashboard/SKILL.md` | scores.json-centric, "high density", omits `refused` | §2b.7, §13, §5, §3 | **Yes** | V3 spec becomes dashboard authority; author a V3-aligned skill only if desired. |
| 3 | `.agents_backup/skills/primer-motion/SKILL.md` | Forbids scroll-driven (V3 requires it); spring easing; Framer-only; no reduced-motion/valence rules | §7, §20 | **Yes** | V3 §7 becomes motion authority. |
| 4 | Root `package.json` + `node_modules/` + `package-lock.json` | "Prep packages" cruft; `gsap`+dup motion libs+unused shadcn deps; nothing imports them | §7, §2b.5 | **Yes** (untracked/ignored; dashboard self-contained) | Verify no root build script references them; `node_modules`/`package-lock` already gitignored. |
| 5 | `write_dashboard_json` + `--data-output` flag + any `data.json` | Legacy single-file export; superseded by `--site-output` (repository.json + evaluations) | §3, §10 | **Partial** | **Keep `build_dashboard_json`** (shared by `build_evaluation_json`). Remove only the standalone writer + flag + schema_v1 path; update EmptyState copy to `primer export --site-output dashboard/public`. |
| 6 | `dashboard/tsconfig.tsbuildinfo` | TS incremental build cache, untracked, regenerated on build | — (hygiene) | **Yes** | Add `*.tsbuildinfo` to `dashboard/.gitignore`. |
| 7 | `skills-audit.txt` (323 KB) | Generated skills-audit dump | — (hygiene) | **Yes** | Regenerable; optionally gitignore. |
| 8 | `TrustArchitecture.tsx` **or** `ProvenanceFooter.tsx` (one, post-merge) | Provenance triplicated across two components + MeasurementIdentity | §11 (one Methods credential) | **No — merge first** | Merge into one collapsible "Methods" credential preserving the separated overhead line (§2b.12) + egress highlight; then delete the redundant one. |

**Regenerate, do not delete:** [scores.json](scores.json) is the live badge artifact (CI/`primer export` output). Its `color: "yellow"` is wrong (§1), but the fix is in `build_scores_json`; the file is then regenerated, not removed.

**Modify, do not delete (covered in §1–§3, listed so nothing is lost):** the amber token + `verdictColor`/`verdictBg`; `build_scores_json`/`render.py` color branches; raw-enum verdict strings; VerdictHero headings/icons; flip labels + ordering; missing framing line; "scorecard" copy; repo-L1 variance/freshness; EmptyState suite; comparison variance bands + isolation refusal.

---

## Guard — already V3-compliant, do **not** regress

The JSON contracts and several surfaces already pass V3 — preserve them: separated `primer_overhead_usd` with its never-summed caption ([ProvenanceFooter.tsx:57-66](dashboard/components/ProvenanceFooter.tsx:57)); VerdictHero's within-noise treatment already uses **calm zinc, not amber** ([VerdictHero.tsx:64-69](dashboard/components/VerdictHero.tsx:64)); the ConfidenceRuler is an honest delta-with-noise-envelope marker (§13); WarningBanner reserves amber **correctly** for the three warnings; `prefers-reduced-motion` guard exists ([globals.css:32](dashboard/app/globals.css:32)); refusal-on-provider/model is implemented in the compare flow; cost-confidence qualifiers (`≈ estimated` / `local (no cost)`) are correct.

The headline takeaway: **V3 is blocked by one V1 decision (Q5 yellow), its propagation into ~6 presentation sites, the V2 §0.1 freeze that protects it, and ~7 housekeeping/cruft artifacts** — not by the engine or data model.
