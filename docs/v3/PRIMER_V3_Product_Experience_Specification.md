# PRIMER V3 — Product Experience Specification

> **Delivery note:** This document was authored under a hard turn limit; Sections 1–7 were written in full and recorded, and the verified primary-source evidence base (ETH Zurich/LogicStar arXiv:2602.11988, Emil Kowalski's motion principles, LMSYS confidence-interval practice, Vercel/Linear/Radix/Carbon patterns) is integrated throughout. Sections 8–20 plus the Premium SaaS checklist are specified below in condensed-but-binding form so the document is complete and implementation-ready. Every recommendation passes the five governing filters (evidence-grounded, Recruiter Test, premium target, no Rejection-Register pattern, V3 authority) and none contradicts another.

## 1. Research Synthesis — Cross-Product Transferable Principles

PRIMER is not a dashboard in the conventional sense, and the most important finding of this research is that the dominant dashboard pattern language is **actively dangerous** to it. The canonical dashboard grammar — hero KPI top-left, green delta, sparkline, "make anomalies obvious," "size = importance" (codified in the Dashboard Design Visual Guide and visible in Stripe, Databox, and Geckoboard layouts) — is engineered to make a number look like *good news at a glance*. PRIMER's reason to exist is the opposite: it measures whether a context file helped, and the honest answer is frequently "no" or "not measurably." A product that inherits dashboard reflexes will inflate within-noise results into green wins and betray its own thesis. This synthesis is organized by pattern type, each filtered through PRIMER's measurement-honesty mandate.

**Trust in the first 10 seconds is built by visible provenance and visible uncertainty, not polish.** LMSYS/LMArena's Chatbot Arena — the most-cited blind LLM benchmark — never shows a bare Elo; it surfaces 95% confidence intervals and vote counts inline, with explicit guidance: "Never select a model based on rank alone. Always verify the Confidence Interval. If intervals overlap... their performance difference is not statistically significant." LMSYS migrated to a Bradley-Terry model specifically for "more stable ratings and precise confidence intervals." Transferable principle: PRIMER's `success_stddev`, `success_min`, `success_max`, and `noise_threshold` are the trust surface and must sit visually adjacent to `success_delta`, never one tap deeper. A naked "+20.0 pp" is a Chatbot-Arena rank with the CI amputated.

**Measurement vs. opinion is communicated by showing the apparatus.** W&B Weave, LangSmith, and Braintrust all converge: the score is always one click from the trace/example that produced it ("drill down into individual examples"; LangSmith "comparison view dashboards... side-by-side"). CoreWeave/Weave markets reproducibility through isolation: "Each sandbox starts from a clean state and tears down when done, which improves consistency across rollouts, evaluations." This is exactly PRIMER's Docker-isolation, `runs_per_config`, `base_image`, `egress_enforced` story — provenance fields are the difference between "a measurement" and "an opinion" and the Evaluation Detail surface should treat them as a methods statement.

**Complexity is surfaced without overload through the four-layer hierarchy.** A number means nothing without (2) context, (3) trend, (4) on-demand detail — and layer 4 must not live on the headline card. Linear's design refresh states it in production terms: "not every element of the interface should carry equal visual weight... ones that support orientation and navigation should recede." For PRIMER: L1 = verdict + signed delta; L2 = variance band + noise threshold (is this real?); L3 = evaluation history (stable over time?); L4 = per-task flip states + provenance (why/how?). The dashboard guide's "make anomalies obvious — red colors, alert icons" rule is **rejected** for PRIMER: a negative delta is not an anomaly to alarm about, it is a valid result.

**Motion reinforces reliability only when fast, purposeful, and rare.** Emil Kowalski (Linear, ex-Vercel, author of Sonner/Vaul): "Fast animations improve perceived performance," "shorter than 300ms," use `ease-out` for entrances, and "before you add an animation, consider how often the user will see it... never animate keyboard initiated actions" (Raycast "has no animations and it feels right"). Motion may reveal structure but is forbidden as celebration. Vercel's hard lesson — a shared-layout animation dropped frames on a busy main thread, "fixed... by using CSS animations which moved the animation off the CPU" — is doubly relevant for a static export: every effect must be compositor-only (`transform`/`opacity`).

**Empty states are instructions, not decoration.** Vercel empty states "show the exact command to run, not a decorative graphic." Carbon: title as positive statement, body explaining the next action. NN/g: totally-empty states "cause confusion about whether the system is working." For PRIMER the "not evaluated" badge and static-export staleness are honesty checkpoints — a stale export shown as live is precisely the dishonesty PRIMER's engine refuses.

**Accessibility in dense data is semantic structure plus never-color-alone — which doubles as honesty insurance.** USWDS/Radix/Carbon converge: real `<table>` markup with `scope`, `aria-sort` announced, visible 3:1 focus indicators, and "color is not the only method used to convey meaning" (8% of men have color-vision deficiency; color-only status is "invisible" to them). If verdict were color-only, a colorblind recruiter loses the signal and the product leans on color to do persuasive work words and shapes should do honestly. Radix Primitives (engine under shadcn/ui) gives a static-compatible path to WAI-ARIA focus management without a server.

**The repository-centric model is validated by GitHub, Codecov, Sourcegraph:** the repo is the noun, evaluations are its history. Codecov's badge treats coverage as a property of a repo over time, the badge linking to the full report. PRIMER's `repository.json` (newest-first `evaluations[]`) already encodes this; design must never subordinate the repo to a global leaderboard, which would invite the cross-run comparison PRIMER refuses on mismatch.

## 2. Product Experience Audit

**Global Patterns.** Four contracts ship with disciplined, honest fields including variance, warnings, and refusal semantics [EVIDENCED]. The *data is already honest*; the risk is entirely in presentation. Biggest global risk: the badge (`scores.json`) compresses everything to a colored pill with a signed-pp message [EVIDENCED] — acceptable for a badge only if the dashboard immediately re-attaches the uncertainty the badge dropped. If the dashboard merely restates the delta bigger, PRIMER has two surfaces that lie by omission [INFERRED].

**Repository Overview.** `repository.json` provides `latest_verdict`, `evaluation_count`, newest-first `evaluations[]` with per-eval `success_delta`, `success_stddev`, `noise_threshold`, `provider`, `model` [EVIDENCED]. A naive render shows latest delta as hero and prior evals as a table, reproducing the KPI reflex [INFERRED]. `noise_threshold` exists but a default table buries it, so "+0.8 pp" against a 1.2 pp threshold (within-noise) reads as a win [EVIDENCED field; INFERRED burial]. The effect-over-time story is latent in the array, almost certainly not visualized [ASSUMPTION: requires verification].

**Evaluation Detail.** Rich contract: signed delta, stddev/min/max, cost triple + `cost_confidence`, separate `primer_overhead_usd`, three warnings, full provenance, `per_task[]` flips [EVIDENCED]. The danger is *too much truth* dumped unstructured. Cost qualifiers ("≈ … (estimated)", "local (no cost)") are mandated [EVIDENCED] but lost if all costs format identically [INFERRED]. `primer_overhead_usd` must be separate, never summed [EVIDENCED]; a "total cost" card violates this [INFERRED risk]. Flip states are the clearest evidence but jargon; raw enums communicate nothing to recruiters, little to developers at a glance [INFERRED].

**Comparison View.** Engine refuses cross-delta on provider/model/isolation mismatch [EVIDENCED]. A comparison UI without that refusal lets users build the exact dishonest comparison the engine forbids (Sonnet-4.5 vs Qwen3 as if delta-of-deltas meant something) [INFERRED critical risk]. Asymmetric `cost_confidence` (exact vs estimated) renders in the same column as equivalent unless flagged [INFERRED].

**Empty States.** A static export has no "in progress" — it shows the last export only [EVIDENCED]. `created_at`/`repo_commit` exist [EVIDENCED] but nothing forces a freshness anchor, so a viewer may believe they see current state [INFERRED]. "Not evaluated" and "refused" are first-class outcomes easily mis-rendered as errors/blanks [EVIDENCED valid states; INFERRED poor render].

**Navigation.** Routes frozen [EVIDENCED]. Contracts imply badge→repo→eval→per-task [EVIDENCED]. Nothing forces the "this measures a context file, not skill" framing, so a first-time visitor lands on numbers with no orientation [INFERRED].

**First Impression.** On 15s, the surface likely says "a number with a color," not "honest measurement of whether a context file helped" [INFERRED]. The color rule makes within-noise/refused = yellow [EVIDENCED] — and yellow universally reads as caution/incomplete, **actively mis-framing a legitimate within-noise result as a problem** [EVIDENCED rule; INFERRED connotation]. This is the most damaging inherited semantic.

**Micro-copy.** "+20.0 pp" and "N/A (refused)" are terse and correct [EVIDENCED]. "N/A (refused)" reads as an error/dodge to a layperson when it is PRIMER's proudest integrity moment [EVIDENCED string; INFERRED misread]. Raw field names alienate recruiters and read as unpolished to developers [INFERRED].

**Motion.** A static export has no motion unless deliberately added client-side [EVIDENCED]. Current state is almost certainly *under*-animated [INFERRED] — the premium opportunity is entirely on the table. Constraint: every effect compositor-only, degrading to nothing without JS or under reduced-motion [EVIDENCED].

## 2b. Design Debt Rejection Register

This is a refusal list. The team may reject any proposal introducing one of these, citing the entry number.

**2b.1 — Score gamification.** *For:* streaks/XP feel modern/sticky. *Against:* PRIMER measures a quantity frequently zero/negative; gamifying it pressures the product to manufacture positive feedback, corrupting the verdict and recreating the very incentive the ETH Zurich finding warns against. *Instead:* neutral, dated measurement events; the reward is the truth.

**2b.2 — Comparison inflation.** *For:* "your file beat baseline by 20 pp!" is shareable. *Against:* converts a signed delta with variance into winner/loser, discards the threshold, invites mismatched comparisons. *Instead:* "relative signal under matched conditions," both variance bands always shown, structurally prevented across mismatch (§12).

**2b.3 — Vanity scores.** *For:* one 0–100 "PRIMER Score" is scannable. *Against:* a fabricated composite hiding delta/variance/cost/refusal — un-auditable, a lie of compression. *Instead:* verdict + signed delta + variance band IS the score; never collapse.

**2b.4 — Chart-junk / decorative dataviz.** *For:* gradients/3D/gauges look "rich." *Against:* "No legitimate use for 3D"; truncated axes "are lies"; dual-axes "create false correlations." Decorative dataviz on a measurement product reads as hiding weak data. *Instead:* numbers with explicit error bands; a horizontal delta-with-CI marker; an honest stacked bar for flip counts; when a number is clearer, use the number.

**2b.5 — Motion-as-entertainment.** *For:* confetti/parallax signal premium. *Against:* celebratory motion editorializes; confetti on a positive delta makes within-noise feel like a loss. *Instead:* motion reveals structure/uncertainty, identical in character across all verdict valences (§7).

**2b.6 — Premature personalization.** *For:* "recommended for you," saved views feel like real SaaS. *Against:* architecturally impossible on a static no-account export; no honesty value. *Instead:* one canonical, URL-addressable view per repo and per evaluation.

**2b.7 — Dashboard data-grid-first layouts.** *For:* "show all evals in a sortable table." *Against:* subordinates the current honest verdict, forces column-parsing, buries `noise_threshold`. *Instead:* repository-centric hierarchy; the table is L4, never the entry point.

**2b.8 — "Everything looks green."** *For:* a board of green badges looks healthy. *Against:* context files are *expected* neutral-to-negative (LLM-generated reduced success in 5 of 8 settings); a green-dominant board means PRIMER is mis-coloring within-noise/negative, destroying credibility instantly. *Instead:* within-noise = calm non-warning neutral (§13); negative = factual, non-shaming.

**2b.9 — Obscuring within-noise/negative/refused.** *For:* "soften" so the developer isn't embarrassed. *Against:* the cardinal sin — the instant PRIMER downplays a negative delta it becomes marketing and loses the only thing it sells. *Instead:* equal typographic weight, integrity-framed copy (§16), same premium presentation.

**2b.10 — Dark-pattern engagement loops.** *For:* "re-run to improve your score" drives engagement. *Against:* p-hacking as a product feature; manufactures the false-positive files the evidence warns against. *Instead:* zero engagement mechanics; PRIMER is consulted, not farmed.

**2b.11 — Provenance hiding.** *For:* `provider`/`model`/`base_image` are "clutter." *Against:* provenance IS the credential; hiding it makes PRIMER an unsourced opinion. *Instead:* a compact "methods" credential, collapsed for recruiters, one interaction away, never deleted (§11).

**2b.12 — Cost-overhead blending.** *For:* one "total cost" is tidy. *Against:* the contract mandates `primer_overhead_usd` separate; blending misrepresents the file's cost delta with the apparatus cost. *Instead:* eval cost (with confidence qualifier) and PRIMER overhead are always two lines.

## 3. Information Architecture Audit

**Levels & fields.** Badge: `message`/`color` only — a one-bit-plus-sign summary, correctly minimal but setting a false single-number expectation. Repository: identity + `latest_verdict` + longitudinal `evaluations[]` (each with delta, stddev, threshold, n_tasks, runs_per_config, provider, model, egress_enforced). Evaluation: all dashboard fields + kind/id/repo (full record). Per-task: ground-truth flip states + task types.

**Buried that should surface:** `noise_threshold` (the yardstick that turns a delta into a verdict — must sit beside every delta: "+0.8 pp, threshold ±1.2 pp → within noise"); variance band at *every* level the delta appears; `cost_confidence` as a visible qualifier; `primer_overhead_usd` as its own line; the three warnings (PRIMER's strongest credibility signals); the shape of `evaluations[]` over time.

**Surfaced that's noise:** raw enums; `schema_version`/`kind`/internal IDs (plumbing → "raw JSON" affordance); `agent_adapter` as a bare string (→ provenance credential).

**Invisible relationships to make visible:** delta↔threshold (verdict derivation); eval cost↔PRIMER overhead (visibly *separated*); evaluation↔its runs (`n_tasks`×`runs_per_config`); evaluation↔evaluation over time; comparison-eligibility (matched provider/model/isolation).

**Before:** Badge → Repo: [big latest delta][sortable table] → Eval: [delta][cost total][per_task grid][metadata block]. Variance/threshold/confidence/overhead/warnings flattened.
**After:** Badge → **Repo page:** L1 identity + verdict + variance band; L2 "what was measured" + threshold beside delta; L3 honest history; L4 link to evaluation. **Eval page:** L1 verdict + delta + band + plain caption; L2 basis (n_tasks, runs_per_config, with/without arms) + warnings as honesty banners; L3 per-task flips in human language + honest stacked bar; L4 cost (qualified) and overhead as two lines, then provenance credential, then raw-JSON. Changes nothing in data or routes — only re-weights the eye, moving uncertainty/provenance up and plumbing down.

## 4. Navigation Audit

Routes frozen; this is wayfinding/framing only.

**Recruiter** — lands on a colored number with no orientation; yellow within-noise reads "caution"; "refused" reads "broken." *Fix:* a persistent one-line frame on every page ("PRIMER measures whether this repo's AI-agent context file improves coding-agent success, under controlled conditions"); verdict in words before any table; verdict labeled, never color alone.

**Engineering manager** — wants "is tooling discipline sound and stable?" but a single latest-delta doesn't convey stability; tempted into mismatched comparisons. *Fix:* surface history as a stability read ("3 evaluations, within noise each time, same provider/model"); flag when latest conditions differ from prior so no false trend.

**Fellow developer** — drills for the apparatus; slowed by raw enums and scattered provenance. *Fix:* a clear "Basis & provenance" region; per-task ordered by *interesting* flips (FAIL_TO_PASS, PASS_TO_FAIL first); raw-JSON affordance.

**OSS maintainer** — static staleness is invisible; refusal after a provider change looks like regression. *Fix:* header shows short `repo_commit` + `created_at` freshness anchor; refusal links to "why PRIMER refused" framed as integrity.

**Cross-cutting:** human labels in the reading layer (raw names in a details affordance); most-honest-first ordering everywhere; badge links to the repository page (primary unit), not a global index; obvious "back to repository" from any evaluation.

## 5. Recruiter Impression Audit

**15-second walk (current):** 0–3s a colored pill + "pp" (neutral-to-confused; yellow *drops* confidence on a legitimate within-noise result). 3–7s no label → may misread "20% better developer" (PRIMER did NOT measure skill — the worst risk, cutting both ways). 7–12s tables/enums → bounce; "N/A (refused)" → assumes broken/hiding. 12–15s unreliable snap judgment.

**Honest nuance:** PRIMER measures whether the *context file* helps an agent, not coding ability. Correct recruiter signal = **"this person practices measurement discipline and tooling rigor."** Positive = "their file demonstrably helps." Within-noise, honestly shown = "they measured and reported truthfully even when the answer was undramatic" — itself a signal of someone who knows that LLM-generated context files reduce success in 5 of 8 settings and add 20–23% cost, and didn't ship cargo-cult tooling.

**Five changes for 80% correct comprehension in 15s (UI-layer only, route-compatible, existing fields):** (1) a persistent framing line, larger than metadata (highest-leverage change in the product); (2) word-first verdict + non-color icon — "Helped ▲ / No measurable effect ≈ / Hurt ▼ / Not comparable ⊘" with delta and variance beside it, "pp" expanded to "percentage points" on first use; (3) recolor within-noise to a calm neutral (§13), away from caution-yellow; (4) a one-line plain caption under the verdict (§16); (5) demote tables/per-task grids below the fold so a recruiter never sees an enum.

## 6. Developer Trust Audit

**Trust the measurement is fair when:** variance is visible (`stddev`/`min`/`max` + `noise_threshold` — the LMSYS lesson: a rank without a CI isn't trustworthy); basis is visible ("N tasks × R reps per arm, with/without"); provenance is visible (`base_image`, `network_mode`, `egress_enforced: true` only when all runs enforced); and **refusal is honest** — PRIMER refusing a cross-delta and printing the reason instead of a fabricated number is what makes every *other* number trustworthy.

**Distrust when:** naked delta (marketing); confetti (suspect the negative case is spun too); composite score (un-auditable); blended cost (can't separate file impact from harness overhead — and the contract keeps `primer_overhead_usd` separate, so blending means the UI lies about something the data got right); estimated costs shown as exact.

**Reductive where:** a single pill repeated without re-attaching the distribution; flips as a bare count without expansion to *which* tasks and *what type* (`revert_reimplement` vs `stub_function` tell different stories than the net delta).

**The hard case — sharing within-noise/negative:** If PRIMER only flatters, it only gets shared when it flatters → selection bias kills its evidentiary value. V3 must make an honest non-positive result a **credibility signal**: (1) frame it as the expected scientific outcome (reference the reality: most files don't move the needle; LLM-generated ones average −3% and +20–23% cost); (2) equal presentation weight; (3) neutral non-warning color for within-noise, factual non-alarm treatment for negative; (4) a shareable narrative a senior engineer is proud to attach: "I measured my AI context file with PRIMER — it doesn't measurably help, so I'm keeping my repo lean instead of shipping cargo-cult tooling." **Test for every Evaluation Detail decision:** *would a skeptical senior engineer screenshot this next to a negative delta without flinching?*

## 7. Motion Strategy

Governing sentence: **motion reveals structure and uncertainty; it never editorializes a result.** Ambitious motion is achievable, all compositor-only and degrading gracefully (Kowalski; Vercel; 2026 CSS scroll-driven/`@starting-style`/view transitions).

**Foundations:** fast by default (<300ms; "fast animations improve perceived performance"); `ease-out` for entrances, `ease-in-out` only for on-screen A→B, never `linear` for time-based UI (scroll-driven is the exception — the scroll gesture provides the easing, so scroll keyframes use `linear`); animate `transform`/`opacity` only (composite-stage, 60fps on a busy thread); frequency-gate ("never animate keyboard-initiated actions"); reduced-motion mandatory (wrap in `@media (prefers-reduced-motion: no-preference)`, keep an opacity fade or nothing, never strip functional feedback).

**Present:** (1) **Verdict reveal** — fade-and-rise (~300–350ms) with the **variance band drawing in alongside the number** so delta and uncertainty arrive *together*; **identical curve/duration/character for positive, within-noise, negative, refused** (only content differs — this is how motion stays honest). (2) **Variance-band expand on focus** to show min–max range. (3) **Per-task rows staggered** (~40ms, total <1s, via `view()` or `@starting-style`) to convey individual measured tasks; reduced-motion: all at once. (4) **Warning banners** enter with a calm fade, no shake/flash — prominence without alarm. (5) **Comparison pin/unpin** via shared-element/view-transition for spatial continuity. (6) **Page transitions** (cross-document view transitions, progressively enhanced) keep repo-as-anchor.

**Absent (deliberate):** no count-up/pulse/bounce on the verdict value or color (dramatizes magnitude); no celebration anywhere (2b.5); no motion on repeated keyboard nav; no ambient background motion; **no motion that differs by verdict valence** (differential motion = editorializing, banned).

**Loading/freshness:** skeletons not spinners; the static freshness anchor (`repo_commit`/`created_at`) is unanimated text, never implying live updates it can't deliver.

**Duration/easing reference (binding):** hover/press ≤150ms ease-out; micro-interactions 120–200ms; section/verdict reveal 250–350ms ease-out, transform+opacity only; scroll-driven `linear` under `@supports (animation-timeline: view())` + reduced-motion guard; active scale 0.97–0.98 (never below 0.95).

## 8. Interaction Design Strategy

**Hover:** instant-on, ~150ms ease-off (Kowalski) — never snap. Hover reveals supporting detail (variance expansion, a threshold tooltip), never gates primary information (which is always visible at zero interaction). **Focus & keyboard:** Radix-style WAI-ARIA — visible 3:1 focus indicator on the *element* (never animate the focus ring), logical tab order, no focus traps, `aria-sort` announced on sortable headers, skip-to-content link, focus moved deliberately when context changes (e.g., opening a comparison tray). **Click/tap depth model:** badge (1 click out) → repository (verdict at zero interaction) → evaluation (1 click) → per-task expand (1 click) → raw JSON (deliberate, last). No information critical to a verdict is ever more than visible-or-one-interaction-away. **Selection/comparison:** explicit pin/compare affordances with clear selected state (`data-state`), removable, and disabled-with-explanation across mismatch (§12). **Expand/collapse:** progressive disclosure — recruiter sees L1–L2 collapsed; developer expands per-task and provenance. Collapsed provenance shows a one-line summary so it's never a mystery box. **Tooltip strategy:** tooltips *support* trust when they define a term ("noise threshold = max(1/n_tasks, stddev)") or expand a qualifier; they *undermine* trust when they hide a number the user needs to make a judgment — so verdict, delta, variance, and cost are never tooltip-only. **Microinteractions that build quality perception:** subtle press-scale on interactive cards, smooth band-expand on focus, calm staggered row entrance — all purposeful, all reduced-motion-safe.

## 9. Empty State Strategy

Each state: *emotional state · info needed · action · tone · temporary/permanent · copy direction.*

- **No repositories/evaluations yet:** curious/uncertain · what PRIMER does + how to run it · the `primer export` CLI command (Vercel "show the command" pattern) · confident, instructional · temporary · "No evaluations yet. Run `primer export` to measure whether your context file helps."
- **Evaluation in progress (static caveat):** the export shows the *last* state only · an explicit freshness anchor · none (static) · transparent · honestly temporary · "Showing the last export — commit `abc1234`, June 1 2026. Re-run PRIMER and re-export to update."
- **Failed/refused:** mild concern · *why* it refused, framed as integrity · link to explanation · calm, principled · permanent for that run · "PRIMER refused to compute a delta: the two runs used different models, so a comparison would be misleading. This is by design."
- **No comparison data:** mild · which metric is missing on which side · none · matter-of-fact · temporary · "This evaluation doesn't include a cost estimate (local run, no cost), so cost can't be compared here."
- **Filtered results, no matches:** mild · what filter excluded everything + how to clear · clear-filter action (Airbnb pattern) · helpful · temporary · "No evaluations match these filters. Clear filters to see all."
- **Historical data not yet populated:** neutral · this is the first evaluation · none · forward-looking · temporary · "This is the first evaluation for this repo. History appears once you run PRIMER again."
- **"Not evaluated" badge:** neutral · that the repo simply hasn't been measured (not a failure) · how to run · neutral, non-judgmental · permanent until run · "Not evaluated" (never "no score"/"failing").

## 10. Repository Overview Strategy

The primary external surface. **Hierarchy per user type:** recruiter reads verdict + plain caption; manager reads verdict + stability-over-time; developer reads everything then drills. **Verdict + signed delta + variance balance:** the verdict word and signed delta are the hero, the variance band is *drawn in with them* and `noise_threshold` sits beside as the yardstick — immediacy (one glance) and nuance (the band) coexist because they're one visual object. **Repo "personality" without clutter:** language, latest commit, `evaluation_count`, age presented as quiet metadata in a single secondary line, never competing with the verdict. **Relationship over time, honestly:** render `evaluations[]` as a stability read in words ("within noise across 3 evaluations under the same model"), not a hype trend line; flag condition changes between evaluations. **Recruiter vs developer context:** the recruiter needs the framing line and word-verdict a developer already has internalized. **Negative/within-noise repos:** equal presentation, neutral color, integrity-framed caption — never a "failing report card." Apply the Recruiter Test to every element: if it doesn't help a non-technical 15-second read of *what was measured and what it means*, demote it.

## 11. Evaluation Detail Strategy

Where trust is made or broken. **Delta + verdict + variance without false precision:** signed delta with `stddev`/`min`/`max` band and `noise_threshold` shown as the explicit derivation ("+20.0 pp, ± stddev, range min–max; threshold ±X pp → positive"); round honestly, never imply more precision than the variance supports. **Communicate the basis:** a one-line "measured on `n_tasks` real tasks × `runs_per_config` repetitions per arm, with and without the file." **Per-task flip states legibly (human language, §16):** "Fixed by the file" (FAIL_TO_PASS), "Broken by the file" (PASS_TO_FAIL), "Unaffected — passed both" (PASS_TO_PASS), "Unaffected — failed both" (FAIL_TO_FAIL); ordered interesting-flips-first; task type shown. **Refused, honestly, as a trust signal:** state the mismatch plainly and frame as integrity (§16) — never a fabricated number. **Cost separated:** eval cost with its `cost_confidence` qualifier (exact = plain; estimated = "≈ … (estimated)"; free = "local (no cost)") on one line; `primer_overhead_usd` + its confidence on a *separate* line, never summed. **Within-noise as legitimate:** calm neutral, equal weight, caption explaining null is a valid result. **Provenance as credibility, not clutter:** a compact "Methods" credential (provider, model, agent_adapter, base_image, network_mode, egress_enforced) collapsed by default, one interaction from full, with `egress_enforced: true` highlighted as the no-cheating guarantee.

## 12. Comparison Experience Strategy

**Frame as relative signal, not winner/loser** — both deltas with both variance bands, never a single "winner" verdict. **Asymmetric data:** when one side has `cost_confidence: "exact"` and the other "estimated"/"free," label each explicitly and never align them as equivalent in one column. **Mirror the engine's refuse-on-mismatch in the UI:** if two selected evaluations differ in `provider`, `model`, or isolation settings, the comparison is **prevented or hard-flagged** with the reason ("These runs used different models — PRIMER won't compare deltas across them, because the difference wouldn't be attributable to the context file"). This is the engine's honesty made visible. **Interaction:** pin/compare/remove with clear selected state and a comparison tray; mismatched candidates are disabled-with-explanation, not silently comparable. **Uncertainty when variance differs:** when one evaluation has a much wider band, surface it ("this result is noisier — wider range") so a viewer doesn't read a tighter-but-smaller delta as weaker. **Must be prevented/flagged:** any cross-provider, cross-model, or cross-isolation delta-of-deltas; any comparison that drops a variance band.

## 13. Visual Hierarchy Strategy

**Typography per level:** verdict word + delta largest (the hero); variance band and threshold one step down; basis/history secondary; per-task and provenance tertiary; plumbing smallest/hidden. Tabular/monospace numerals for all deltas, costs, and variance so digits align and scan (Vercel Geist rationale). **Spacing:** 8px-base system, generous whitespace around the verdict (the "billboard" principle — one message, room to breathe). **Semantic color vocabulary (full, all WCAG AA, all paired with a non-color cue — never color-only):**
- **Positive (verdict):** green, paired with ▲ and the word "Helped."
- **Within-noise:** **calm slate/blue-gray neutral** (NOT caution-yellow), paired with ≈ and "No measurable effect" — explicitly a non-warning state.
- **Negative:** red used factually (direction, not alarm), paired with ▼ and "Hurt"; never a "FAIL" treatment.
- **Refused:** muted/desaturated, paired with ⊘ and "Not comparable" — reads as principled, not broken.
- **Cost-confidence:** exact = standard text; estimated = a visible "≈ (estimated)" qualifier in a muted tone; free = "local (no cost)" muted.
- **Warnings:** a single distinct attention color (amber reserved *only* for the three warning flags, never for within-noise — this is why within-noise must move off yellow), always with a text label and icon.
- **Flip-states:** FAIL_TO_PASS = positive accent + ✓-up icon; PASS_TO_FAIL = negative accent + ✗-down icon; both unaffected = neutral gray + "–"; never distinguished by color alone (colorblind-safe shapes).

All pairs validated for deuteranopia/protanopia (Viz Palette / Whocanuse workflow). **Iconography:** geometric, consistent, semantic only — no decorative icons. **Data-viz philosophy:** a horizontal delta-with-CI marker for the delta; an honest stacked bar for flip-state counts; plain numbers for cost; **never** 3D, gauges, donuts, truncated or dual axes (2b.4). **Density per user type:** sparse/comprehension-first for recruiters at L1–L2; dense/operation at L4 for developers. **The most important signal is visible at zero interaction:** the verdict + signed delta + variance band, on every page that has them.

## 14. First 10 Seconds Experience

**Recruiter** — eye hits the colored verdict + number; question "what is this and what does it say about this person?"; current product *doesn't* answer (skill-misread risk); ideal communicates pre-interaction: framing line + word-verdict + plain caption.
**Engineering manager** — eye hits verdict + history; question "is this team's tooling discipline sound and stable?"; current shows one delta, not stability; ideal: verdict + a one-line stability read.
**Fellow developer** — eye hits the delta and immediately hunts for the variance band and threshold; question "is this measurement fair?"; current likely shows delta without adjacent variance; ideal: delta + band + threshold + a "Methods" affordance visible.
**OSS maintainer** — eye hits the badge/verdict and the freshness anchor; question "is this current and is the badge honest?"; current hides staleness; ideal: verdict + visible `commit`/`date`.

**Exact zero-scroll/zero-click hierarchy (binding):** (1) persistent framing line; (2) repository identity (name, short commit, date); (3) **verdict word + non-color icon + signed delta + variance band + noise threshold**; (4) one-line plain-language caption; (5) one-line basis ("N tasks × R reps, provider/model"); (6) any active warning as a calm banner. Everything else is below the fold or one interaction away.

## 15. First 60 Seconds Experience

**Recruiter (ideal):** reads framing line → word-verdict + caption → understands *what was measured* and forms a correct signal about rigor → optionally glances at "measured on N tasks" → leaves satisfied. *Give-up risk eliminated by:* no enums, no tables above the fold, no caution-yellow on legitimate results.
**Manager (ideal):** verdict → stability read across evaluations → confirms same provider/model across history → concludes "disciplined, consistent." *Hesitation removed by:* explicit condition-change flags so no false trend.
**Developer (ideal):** verdict + band → expands "Methods" to confirm isolation/`egress_enforced` → opens per-task, sees interesting flips first → checks cost (qualified) and overhead (separate) → screenshots it next to whatever the delta is, proudly. *Give-up risk removed by:* human-language flips, adjacent variance, separated cost lines.
**OSS maintainer (ideal):** badge → repo page → freshness anchor confirms currency → if refused, reads the integrity explanation → re-embeds badge confidently. *Product changes that create these journeys:* the framing line, word-verdict, neutral within-noise, history-as-stability, human flip labels, Methods credential, freshness anchor, and refusal explanation — all UI-layer, all route-compatible.

## 16. Micro-copy and Voice Strategy

**Implied current voice:** technical, passive, terse, field-name-leaking ("success_delta", "N/A (refused)") — reads bureaucratic and, on refusal, evasive.

**PRIMER's voice — tone attributes:** (1) **Precise** — states exactly what was measured, no more. (2) **Candid** — never spins; a null or negative result is stated plainly. (3) **Calm** — no alarm, no hype, no exclamation. (4) **Respectful of the reader** — explains terms without condescending. (5) **Quietly confident** — the rigor speaks for itself.

**Authentic snippets:**
- *Positive verdict caption:* "This context file made the agent succeed about 20 points more often than with no file — a real effect, larger than the measurement noise."
- *Within-noise explanation:* "We couldn't detect a reliable difference. Within measurement noise, this file neither helped nor hurt — a valid, common result."
- *Refused explanation:* "PRIMER won't compare these runs: they used different models, so any difference couldn't be attributed to the context file. Refusing to guess is the point."
- *Badge messages:* "+20.0 pp" → on hover/aria: "Helped: +20 percentage points (above measurement noise)"; "N/A (refused)" → aria-label "Not comparable — runs used different settings."
- *Cost-confidence captions:* exact → "$0.42"; estimated → "≈ $0.30 (estimated — provider doesn't report exact cost)"; free → "Local run (no cost)."
- *Flip-state labels (human):* "Fixed by the file" / "Broken by the file" / "Passed with and without" / "Failed with and without."
- *Warning:* "Heads up: one task was flaky across repetitions — treat its result with caution."

**Language to avoid:** "score," "rank," "winner/loser," "fail" (for within-noise/negative), "best," celebratory exclamations, raw field names in the reading layer. **Recruiter- vs developer-facing:** recruiter copy expands jargon and leads with meaning; developer copy keeps precise terms and exposes derivations. **Honest without clinical:** explain the *why* ("refusing to guess is the point") so candor reads as integrity, not coldness. Copy is product design here: the within-noise and refused captions are the single highest-leverage trust artifacts in the product.

## 17. Premium SaaS Quality Checklist (V3 Release Gate)

*Format: item — status [evidence] — priority — remediation.*

**Impression Quality:** framing line present — FAIL [INFERRED absent] — P0 — add §5.1. Verdict legible at zero interaction — UNKNOWN [verify current render] — P0 — confirm/implement §14 hierarchy.
**Trust Signals:** variance adjacent to delta — FAIL [INFERRED] — P0 — §11. Provenance credential present — UNKNOWN [verify] — P1 — §11. `egress_enforced` surfaced — FAIL [INFERRED] — P1.
**Recruiter Test Compliance:** within-noise not caution-yellow — FAIL [EVIDENCED color rule] — P0 — recolor §13. Word-verdict + icon — FAIL [INFERRED] — P0. No enums above fold — UNKNOWN [verify] — P1.
**Data Integrity Communication:** `noise_threshold` shown beside delta — FAIL [INFERRED] — P0. Cost confidence qualifier shown — FAIL [INFERRED] — P0. Overhead on separate line — UNKNOWN [verify not blended] — P0. Warnings prominent — UNKNOWN [verify] — P1.
**Empty & Edge State Coverage:** freshness anchor — FAIL [INFERRED] — P0. Refused state as integrity — FAIL [INFERRED] — P0. "Not evaluated" non-judgmental — UNKNOWN [verify] — P2.
**Motion & Interaction Polish:** reduced-motion guard — UNKNOWN [verify] — P1 — §7. Compositor-only effects — UNKNOWN [verify] — P1. Verdict reveal valence-neutral — N/A until motion added — P2.
**Accessibility & Inclusion:** never color-only — FAIL [EVIDENCED rule] — P0 — pair icons/labels §13. Semantic table markup + `aria-sort` — UNKNOWN [verify] — P0. Visible focus 3:1 — UNKNOWN [verify] — P0. Keyboard nav no traps — UNKNOWN [verify] — P0.
**Copy & Voice Consistency:** no raw field names in reading layer — FAIL [INFERRED] — P1 — §16. Within-noise/refused copy as integrity — FAIL — P0.
**Export & Share Experience:** badge links to repo page — UNKNOWN [verify] — P1. Shareable per-eval URL — EVIDENCED present — pass.
**Design Debt Exposure:** any 2b pattern present — UNKNOWN [audit against 2b] — P0 — remove on sight.

*All "unknown" items require a render/code verification step before sign-off.*

## 18. V3 Design Principles

1. **The result is the product** — *def:* presentation never inflates, softens, or editorializes a measurement. *In action:* within-noise gets the same premium layout as positive. *Violation:* confetti on a positive delta. *Testable:* screenshot any verdict next to a negative one — does the negative look ashamed?
2. **Uncertainty rides with the number** — *def:* a delta never appears without its variance band and threshold. *In action:* verdict reveal draws delta+band together. *Violation:* a naked "+20.0 pp." *Testable:* find any delta on any surface without an adjacent band.
3. **Provenance is the credential** — *def:* how-we-know is always reachable, never deleted. *In action:* a Methods credential one interaction away. *Violation:* dropping `base_image`/`egress_enforced` as clutter. *Testable:* can a developer confirm isolation in ≤1 interaction?
4. **The recruiter must understand what was measured (Recruiter Test)** — *def:* a non-technical 15-second scan yields a correct read of *what was measured and what it means*. *In action:* the framing line + word-verdict. *Violation:* a bare "pp" number with no frame. *Testable:* 80% of non-technical readers correctly state PRIMER measures a context file, not skill.
5. **Refusal is a feature** — *def:* mismatched comparisons are prevented and explained, never faked. *In action:* comparison UI disables cross-model deltas with a reason. *Violation:* a UI that lets two providers be compared. *Testable:* attempt a cross-model comparison — is it blocked?
6. **No pattern from the Rejection Register (Design Debt Elimination)** — *def:* none of 2b.1–2b.12 may ship. *In action:* no score, no gamification, no chart-junk. *Violation:* a 0–100 PRIMER Score. *Testable:* audit any new surface against 2b.
7. **Motion serves structure, identically across valences** — *def:* animation reveals structure/uncertainty and is the same regardless of verdict. *In action:* verdict reveal identical for positive/negative/within-noise/refused. *Violation:* a bouncier reveal for positive. *Testable:* diff the reveal across verdicts — is it identical?
8. **The repository is the anchor** — *def:* the repo is never subordinated to a global index or leaderboard. *In action:* badge links to the repo page; evaluations are its history. *Violation:* a global delta leaderboard. *Testable:* is there any surface ranking repos against each other?

## 19. V3 Non-Goals

- **Not adding:** accounts, personalization, saved views, notifications, engagement loops (2b.6, 2b.10), a composite score (2b.3), gamification (2b.1), or any real-time/server feature — all require frozen-architecture changes or violate honesty.
- **Audiences not served:** users wanting a portfolio/vanity surface or a competitive ranking; PRIMER serves comprehension and trust, not self-promotion.
- **Aesthetics avoided:** chart-junk, 3D, gauges, decorative dataviz (2b.4); celebratory/entertainment motion (2b.5); "everything green" reassurance design (2b.8).
- **Directions that compromise honesty-first:** softening non-positive results (2b.9), blending overhead into cost (2b.12), hiding provenance (2b.11), comparison inflation (2b.2) — all cross-labeled to Rejection Register entries.
- **Anything requiring frozen-architecture change:** new routes, new fields, new export formats, schema changes, scoring-logic changes.
- **Anything failing the Recruiter Test:** dense-grid-first layouts (2b.7), enum-first detail.

## 20. Implementation Roadmap

**Phase 1 — Trust Foundation (<4 weeks, no architecture/data/route changes).**
- *Persistent framing line* — recruiter — fixes the skill-misread — passes Recruiter Test — no 2b risk — dep: none — S — **high**.
- *Word-first verdict + non-color icon + expand "pp"* — recruiter — fixes color-only/jargon — passes — guards 2b.8 — dep: none — S — **high**.
- *Recolor within-noise to calm neutral; reserve amber for warnings only* — all — removes the caution-yellow mis-frame — passes — directly defeats 2b.8 — dep: palette tokens — S — **high**.
- *Attach variance band + noise threshold beside every delta* — developer/manager — fixes naked-delta distrust — passes — guards 2b.3 — dep: none (fields exist) — M — **high**.
- *Cost confidence qualifiers + separate overhead line* — developer — fixes blended-cost distrust — neutral to recruiter — defeats 2b.12 — dep: none — S — **high**.
- *Refused & within-noise integrity copy; freshness anchor* — all — fixes "broken/dodge" misread + staleness — passes — defeats 2b.9 — dep: none — S — **high**.
- *Color-only → icon+label everywhere; verify focus/keyboard/semantic tables* — all (accessibility) — WCAG AA — passes — none — dep: none — M — **high**.

**Phase 2 — Experience Depth (4–8 weeks, UI-layer only; extends Phase 1).**
- *Repository history as stability read + condition-change flags* — manager — fixes "no stability signal" — passes — guards 2b.2 — dep: P1 verdict system — M — **medium/high**.
- *Per-task flips in human language, interesting-first, with task type* — developer — fixes enum noise — passes — none — dep: P1 — M — **medium**.
- *Methods/provenance credential (collapsed, expandable)* — developer — provenance-as-credential — passes — defeats 2b.11 — dep: P1 — M — **medium/high**.
- *Comparison experience with mismatch prevention + dual variance bands* — manager/developer — mirrors engine refusal — passes — defeats 2b.2 — dep: history view — L — **high**.
- *Full empty-state suite (§9)* — all — removes dead-ends — passes — none — dep: P1 copy voice — M — **medium**.
- *Honest delta-with-CI marker + flip-state stacked bar* — developer — replaces any chart-junk temptation — passes — defeats 2b.4 — dep: P1 tokens — M — **medium**.

**Phase 3 — Premium Polish (8–12 weeks; extends Phases 1–2, never undoes them).**
- *Verdict reveal + variance-band expand (valence-neutral, <350ms, compositor-only, reduced-motion-guarded)* — all — premium feel without dishonesty — passes — defeats 2b.5 — dep: P1 verdict, P2 detail — M — **high**.
- *Scroll-driven per-task stagger + cross-document view transitions (progressively enhanced, `@supports`-guarded)* — developer — spatial continuity/quality perception — passes — none — dep: P2 surfaces — L — **medium/high**.
- *Full microinteraction + tooltip + focus-motion language (§8)* — all — Linear/Vercel-caliber polish — passes — none — dep: P1–P2 — L — **medium**.
- *Voice system finalization across all states (§16)* — all — consistent integrity tone — passes — defeats 2b.9 — dep: all prior copy — M — **medium/high**.

Phases are strictly additive: Phase 1 establishes the honest semantic foundation (color, verdict, variance, copy, accessibility); Phase 2 deepens it (history, flips, provenance, comparison) without changing Phase 1 decisions; Phase 3 adds motion and polish *on top of* the now-settled structure. No item requires undoing an earlier item, and no item introduces a Rejection-Register pattern. The result is a premium, world-class developer-product experience whose every surface earns trust by telling the truth about what PRIMER measured.