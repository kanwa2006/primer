# DESIGN.md — PRIMER

> **WARNING — DESIGN SPECIFICATION, NOT REAL DATA.**
> All sample datasets, numeric deltas, confidence intervals, repository names (`acme-payments`), task names, verdict labels (`IMPROVED / NEUTRAL / HARMFUL`), and evaluation results in this document are **hypothetical design examples only**. They are not real evaluation results produced by PRIMER.
>
> The real PRIMER verdict taxonomy is: **Helped ▲ / Hurt ▼ / No measurable effect ≈ / Not comparable ⊘**. The real uncertainty model is a noise envelope (`max(1/n_tasks, success_stddev)`), not a 95% confidence interval. Real results live in `dashboard/public/`.

---

> Single source of truth for PRIMER's product design. This file is fed **blind and independently** into AI design tools (Claude Design, Google Stitch) to generate multiple competing high-fidelity concepts. It is self-contained: every token, number, and copy string needed to build a premium concept lives here. **It contains no code and no implementation plans — design specification only.**

---

## 0. What PRIMER is (read first)

**PRIMER is an AI context-file evaluation platform.** It measures whether files like `CLAUDE.md` and `AGENTS.md` actually improve the performance of AI coding agents — or fail to, or make things worse.

It runs controlled **before/after evaluations inside isolated Docker containers**: the same task suite executed with and without the context file, under identical conditions, across many runs. It reports success-rate delta, run-to-run variance, cost impact, and per-task outcomes — and resolves every evaluation to one honest verdict: **Improved**, **Neutral**, or **Harmful**.

**The thesis is honesty-first.** PRIMER exists to tell the truth about context files, including the unflattering truth. Its credibility *is* the product. A Neutral or Harmful result is a first-class, fully-designed outcome — never an error, never buried.

---

## 1. Design philosophy

Five principles govern every screen. When a visual decision is ambiguous, resolve it toward these.

1. **The data is the hero, the chrome is the stagehand.** Numbers, deltas, and distributions occupy the optical center. Decoration never competes with a figure. If an element doesn't help the visitor read the evidence, it gets smaller or disappears.
2. **Uncertainty travels with every number.** A delta never appears alone. Confidence interval, variance, and sample size are bound to it the way a unit is bound to a measurement. A bare number is a bug.
3. **Honesty is a visual posture, not a disclaimer.** Improved, Neutral, and Harmful get equal layout investment. Harmful is communicated calmly — a measured warm tone, never alarm red. The mood is *honest finding*, not *error*.
4. **Show your work, invitingly.** Methodology, container spec, seeds, model, and run counts are a destination, not a footnote. The "how" is presented as proof a curious person *wants* to open.
5. **Premium calm.** Dark-first, deep spacing, one clear focal point per viewport, restraint over flourish. The feeling is an instrument panel built by people who measure things for a living — Linear/Stripe-tier, never admin-template.

**Voice in the UI:** precise, plain, unspun. Short declaratives. Mono for every figure. No marketing adjectives in product copy. "The file made the agent more consistent" beats "dramatically improved reliability."

---

## 2. The 10-second test (the homepage's pass/fail)

The hero and first viewport must answer four questions, in this priority order, each in a **dedicated visual slot**. If a visitor must scroll to learn what PRIMER is, the design has failed.

| # | Question | Hero slot | Copy (sample dataset) |
|---|----------|-----------|------------------------|
| 1 | **What is PRIMER?** | Top: definitional headline (display) + mechanism sub-line | **"Does your `CLAUDE.md` actually help?"** / sub: "PRIMER runs controlled before/after evaluations in isolated Docker containers and measures the difference." |
| 2 | **Why does it matter?** | Eyebrow above headline, or framing line directly under sub-line | "Everyone writes context files. Almost no one measures whether they work." |
| 3 | **What did PRIMER discover?** | Optical center: the hero stat — animated count-up to the delta, with verdict badge | Verdict **IMPROVED** · **+14.2 pts** success rate (61.7% → 75.9%) |
| 4 | **Why trust it?** | Bound directly beneath/around the stat, in-view, no scroll | "95% CI [+6.1, +22.3] · n = 120 runs per arm · isolated Docker · show the method →" |

**Composition rule:** Slot 3 is the emotional center and the largest type on the page. Slots 1–2 sit above it as orienting context; slot 4 sits with it as the credibility skirt. All four are above the fold at desktop and mobile.

---

## 3. Honesty-first → binding visual rules

Carry these through every page. They are non-negotiable.

- **Every headline number ships with its uncertainty.** CI and/or variance appear adjacent to any delta. No bare numbers anywhere.
- **Sample size is always visible.** `n` runs sits near every metric. Credibility comes from `n`, not polish.
- **Neutral and Harmful are fully designed, equal-weight outcomes.** Identical layout quality to Improved. Never collapsed, hidden, or red-alarmed.
- **Harmful is calm, not punitive.** Measured warm amber-red (`#E5634D`). The tone says "honest finding."
- **Show your work is a first-class surface.** Methodology, container spec, seeds, model, run count, task list are prominent and inviting.
- **No vanity metrics, no fake precision, no dark patterns.** Round honestly. Inconclusive results say so plainly.
- **Tradeoffs are shown together.** If the file raises success *and* cost, both enter view at once — never one without the other.
- **Verdict is never encoded by color alone** (see §15). Color always pairs with icon + label + shape.

---

## 4. Audiences and the job each hires the UI for

**Primary**
- **Developers using AI agents** → "Is my `CLAUDE.md` helping, and which parts?"
- **Engineering teams** → "Should we standardize this across the org? What's the cost tradeoff?"
- **AI researchers** → "Is the method sound? Show me variance, sample size, conditions."

**Secondary — the recruiter lens (design for it without a separate site)**
- **Recruiters / hiring managers / portfolio reviewers** → "Does the builder demonstrate production engineering, Docker infra, measurement rigor, testing discipline, CI/CD maturity, and research grounding?" They must absorb this **visually, without reading docs.**

Target outcome: a developer trusts the rigor, a researcher trusts the method, and a recruiter is impressed by the engineering — from the same screens.

---

## 5. Canonical sample dataset (use these exact values everywhere)

Populate **every** mockup from this one internally-consistent set. Reuse identical numbers across Home, Evaluation, and Compare so concepts cohere.

> If real PRIMER numbers are available, the person pasting this prompt should substitute them. Otherwise use this set verbatim.

**Subject under test:** `CLAUDE.md` (v3) — repository `acme-payments`
**Latest verdict:** **IMPROVED** (with one regression caveat)
**Headline:** success rate **61.7% → 75.9%**, delta **+14.2 pts**, 95% CI **[+6.1, +22.3]** (does not cross zero)
**Confidence:** High
**Runs:** **120 per arm** (12 tasks × 10 runs), randomized task order, identical harness
**Variance:** run-to-run std dev **0.18 → 0.12** (the file made the agent *more consistent*)
**Cost impact:** **+8%** median tokens/task, **+$0.02/run** (tradeoff: more context, more tokens)
**Task-level outcomes:** **8 improved · 3 neutral · 1 harmful** (one task regressed with the file — surface it)
**Methodology facts:** base image `python:3.12-slim`, pinned dependencies, fixed seeds where possible, isolated network, single coding-agent model held constant, temperature held constant, identical task suite per arm

**The single harmful task (name it in mockups):** `refactor-legacy-auth` — regressed **−9 pts** with the file present (the file's conventions section conflicted with this module's existing pattern).

### Verdict-state variants (design all three)

Build the verdict component in all three states using plausible variants of the above, to prove the system handles honest outcomes.

- **IMPROVED** — `+14.2 pts`, 95% CI `[+6.1, +22.3]`, High confidence, n = 120/arm. *"The file improved success and reduced variance. One task regressed."*
- **NEUTRAL** — `+1.3 pts`, 95% CI `[−4.8, +7.4]` (crosses zero), Moderate confidence, n = 120/arm. *"No measurable effect. The interval crosses zero — we can't distinguish this from noise."*
- **HARMFUL** — `−7.6 pts`, 95% CI `[−13.9, −1.3]` (does not cross zero), High confidence, n = 120/arm. *"The file reduced success. Most of the loss came from over-specified conventions."*

---

## 6. Visual language — tokens

Dark mode is the primary canvas. These are the anchor tokens; each art direction (§7) evolves the accent and feel but keeps the structure, the verdict semantics, and the mono-for-data rule.

### 6.1 Color

**Surfaces**
| Token | Hex | Use |
|-------|-----|-----|
| `surface/base` | `#0B0C10` | Page background |
| `surface/elevated` | `#14161C` | Cards, panels |
| `surface/raised` | `#1B1E26` | Cards on cards, popovers, hover |
| `border/hairline` | `rgba(255,255,255,0.08)` | 1px structure lines |
| `border/strong` | `rgba(255,255,255,0.16)` | Focus rings (paired with accent), active edges |

**Text**
| Token | Hex | Use |
|-------|-----|-----|
| `text/primary` | `#F5F7FA` | Headlines, key figures |
| `text/secondary` | `#A1A7B3` | Body, labels |
| `text/tertiary` | `#6B7280` | Captions, axis ticks, metadata |

**Accent (default direction; art directions may swap)**
| Token | Hex | Use |
|-------|-----|-----|
| `accent/primary` | `#6E56CF` (electric indigo) | Primary actions, focal highlights, hero halo |
| `accent/secondary` | `#36C5F0` (cyan) | Secondary emphasis, links, chart accents |

**Verdict semantics (honesty-first toning — never color alone)**
| Verdict | Token | Hex | Icon | Shape cue |
|---------|-------|-----|------|-----------|
| Improved | `verdict/improved` | `#2FB67C` (calm green) | upward chevron / ✓ | filled pill, upward bar |
| Neutral | `verdict/neutral` | `#8A93A2` (slate) | equals / dash | hollow pill, flat bar |
| Harmful | `verdict/harmful` | `#E5634D` (measured amber-red, **not** alarm) | downward chevron / ! in circle | bordered pill, downward bar |

**Supporting**
- `ci-band`: accent at 14–20% alpha (uncertainty bands, whiskers).
- `baseline-line`: `text/tertiary` dashed, for the "before" reference on every chart.

### 6.2 Typography

- **UI/display typeface:** a modern grotesk — **Inter** or **Geist Sans** (either is on-brand; pick one per concept).
- **Data typeface:** a monospace — **Geist Mono** or **JetBrains Mono** — **mandatory for every metric, delta, CI, n, cost, seed, and axis number.** Use **tabular figures** so digits align in columns. Mono-on-numbers is itself a credibility signal.

**Type scale (rem @ 16px base; px in parens)**
| Token | Size | Weight | Line height | Use |
|-------|------|--------|-------------|-----|
| `display-xl` | 4.5rem (72) | 600 | 1.02 | Hero stat count-up |
| `display-l` | 3rem (48) | 600 | 1.05 | Hero headline |
| `display-m` | 2.25rem (36) | 600 | 1.1 | Section titles |
| `heading` | 1.5rem (24) | 600 | 1.2 | Card titles |
| `subheading` | 1.125rem (18) | 500 | 1.4 | Sub-lines, lead-ins |
| `body` | 1rem (16) | 400 | 1.6 | Paragraphs |
| `label` | 0.875rem (14) | 500 | 1.4 | Labels, chips |
| `caption` | 0.75rem (12) | 500 | 1.4 | Metadata, `n`, axis ticks |
| `metric-xl` | 3.5rem (56) | 600 mono | 1.0 | Big metric figures |
| `metric` | 1.5rem (24) | 500 mono | 1.1 | Inline metric figures |
| `metric-caption` | 0.875rem (14) | 500 mono | 1.3 | CI, variance, cost beside a metric |

### 6.3 Spacing scale (4px base)
`4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 · 96 · 128`. Sections breathe at 96–128 vertical on desktop. Cards pad at 24–32. Hero gets the most negative space on the site.

### 6.4 Radii
`sm 8px` (chips, inputs) · `md 12px` (buttons) · `lg 16px` (cards) · `xl 24px` (hero stat card, modals) · `full` (pills, verdict badges).

### 6.5 Elevation / shadow (dark-first)
Shadows are subtle; depth comes mostly from surface steps + hairlines.
- `e1`: `0 1px 0 rgba(255,255,255,0.04) inset, 0 1px 2px rgba(0,0,0,0.4)` — resting cards.
- `e2`: `0 8px 24px rgba(0,0,0,0.45)` — hover lift, popovers.
- `e3`: `0 24px 64px rgba(0,0,0,0.55)` — modals, the floating hero stat.

### 6.6 Glass / blur
`backdrop-blur 16–24px` over an **8–12% white fill**, with a **1px top highlight** (`rgba(255,255,255,0.12)`). **Reserve glass for nav, overlays, and floating stat cards — not everywhere.**

### 6.7 Gradients
Low-saturation, for depth only. The signature use is a **soft accent halo behind the hero stat** (radial, accent at ~18% fading to transparent). Never rainbow, never decorative-only.

### 6.8 Iconography
Thin-line, 1.5px stroke, 24px grid, rounded joins (Lucide/Feather family). Verdict icons are slightly heavier to read at small sizes. Icons are functional, never ornamental.

### 6.9 Grid
12-column, max content width 1200px (wide breakpoint 1440px gutter-bounded). 24px gutters desktop, 16px mobile. Charts and stat grids snap to this grid; the hero may break to full-bleed for the halo.

---

## 7. Named art directions (how competing concepts diverge)

Three directions. Each must still pass the 10-second test, the honesty-first rules, and accessibility. Downstream tools and repeated runs should pick a direction and commit to it.

### Direction A — "Instrument" (Linear-minimal)
Near-monochrome; **one** electric accent (keep indigo or go to a single cool accent). Hairline structure everywhere, almost no fills. Motion restrained — count-up and bar-grow only, fast and crisp. Data is the entire hero; chrome nearly invisible. Maximum signal, minimum decoration. Glass used only on nav. Feels like a precision measurement tool.

### Direction B — "Depth" (Stripe-grade)
Layered surfaces, soft low-saturation gradients and accent glows, generous glass on floating stat cards. Choreographed reveals with staggered depth (foreground settles, then background). A sense of dimensional space — the hero stat floats above a gradient field. Swap accent toward a richer indigo→violet or indigo→cyan blend used only in halos and active states. Feels expensive and composed.

### Direction C — "Living" (Arc/Perplexity-playful)
Warmer, more characterful accent (e.g., warm coral-to-amber, or teal) while **keeping verdict semantics intact**. Springy micro-interactions, slightly editorial layout (asymmetry, pull-quotes on the Compare page), conversational framing of results ("Here's what changed since v2…"). More personality in copy and motion, same rigor in the numbers. Feels human and curious without losing credibility.

---

## 8. Page & screen architecture

Each page below is a **screen-ready block**: paste any one into Stitch on its own. Every section lists purpose · audience · the question it answers · real copy from §5 · components · motion intent · responsive note · recruiter-readability note.

---

### 8.1 Home page

**Purpose:** in one scroll, prove what PRIMER is, what it found, and why to trust it. **Primary audience:** developers + recruiters (the hero must work for both).

**Section order (priority-ranked):**

**1 — Hero** *(carries §2)*
- *Question:* What is PRIMER / why / what did it find / why trust it.
- *Copy:* Eyebrow "AI CONTEXT-FILE EVALUATION". Headline **"Does your `CLAUDE.md` actually help?"** Sub "PRIMER runs controlled before/after evaluations in isolated Docker containers and measures the difference." Framing "Everyone writes context files. Almost no one measures whether they work." Hero stat: verdict **IMPROVED**, count-up to **+14.2 pts**, secondary line `61.7% → 75.9%`, skirt `95% CI [+6.1, +22.3] · n = 120/arm · isolated Docker`. CTA primary "See the evaluation", ghost "How it works".
- *Components:* nav (glass), verdict badge, hero stat card (glass + halo), confidence inline, container chip row, buttons.
- *Motion:* count-up 1000ms after the headline settles; halo breathes once on load; skirt fades in 80ms after the number lands.
- *Responsive:* stat card stacks under headline on mobile; halo shrinks; CTAs full-width stacked.
- *Recruiter note:* the n, CI, and Docker chip in the first viewport say "this person measures rigorously" before any reading.

**2 — Current result** (latest verdict as centerpiece)
- *Question:* What's the latest finding, in full?
- *Copy:* `CLAUDE.md (v3) · acme-payments` · verdict IMPROVED · "Success rose +14.2 pts and the agent got more consistent (std dev 0.18 → 0.12). One task regressed." Confidence: High. n = 120/arm.
- *Components:* large verdict card, confidence meter, mini delta chart with CI whisker, "Open full evaluation →".
- *Motion:* delta bar grows from baseline on reveal; CI whisker draws after the bar settles.
- *Responsive:* chart simplifies to a single signed-delta bar on mobile.
- *Recruiter note:* shows a real finding with its caveat — demonstrates intellectual honesty.

**3 — What PRIMER measures** (the four metrics, explained)
- *Question:* What exactly does PRIMER report?
- *Copy:* four animated stat cards — **Success delta** `+14.2 pts [+6.1,+22.3]`; **Variance** `0.18 → 0.12 std dev`; **Cost impact** `+8% tokens · +$0.02/run`; **Task outcomes** `8 improved · 3 neutral · 1 harmful`. Each card one-line plain explanation.
- *Components:* stat/metric card ×4 with count-up and adjacent CI/n.
- *Motion:* staggered reveal (60–80ms), numbers count up in reading order.
- *Responsive:* 4-col → 2×2 → 1-col.
- *Recruiter note:* four metrics, each with uncertainty, reads as a measurement framework, not a marketing page.

**4 — Why measurement matters** (problem framing)
- *Question:* Why should I care?
- *Copy:* "A `CLAUDE.md` is committed advice to an AI that you never test. It might help. It might do nothing. It might quietly make the agent worse — and you'd never know. PRIMER turns that guess into a measurement."
- *Components:* editorial text block, optional small "guess vs. measurement" visual.
- *Motion:* gentle fade/rise on scroll.
- *Responsive:* single column, generous measure (~60ch).
- *Recruiter note:* frames the engineering problem clearly for a non-technical reader.

**5 — Research backing** (methodology grounding)
- *Question:* Is this a sound way to measure?
- *Copy:* "Built on controlled A/B evaluation: identical task suites, randomized order, fixed seeds where possible, sample sizes large enough to compute confidence intervals. Effect sizes reported with 95% CIs; we don't claim effects whose intervals cross zero."
- *Components:* principle list with icons, link "Read the methodology →".
- *Motion:* list items stagger in.
- *Responsive:* 2-col → 1-col list.
- *Recruiter note:* signals research literacy (CIs, controls, seeds).

**6 — Latest evaluation** (rich preview card → Evaluation page)
- *Question:* Can I see a full result?
- *Copy:* preview of the `CLAUDE.md (v3)` evaluation — verdict, delta, n, date, the one harmful task flagged. "Open evaluation →".
- *Components:* large linked preview card with embedded mini-charts.
- *Motion:* hover lift (e2) + accent edge.
- *Responsive:* full-width card.
- *Recruiter note:* a click-through to depth proves there's real substance behind the headline.

**7 — Trust indicators**
- *Question:* How do I know these results are real?
- *Copy:* "n = 120 runs per arm · isolated network · reproducible containers · seeds pinned · model & temperature held constant."
- *Components:* trust chips / icon row.
- *Motion:* none or subtle fade.
- *Responsive:* wraps to multi-row chips.
- *Recruiter note:* reproducibility vocabulary, scannable.

**8 — Technical credibility strip** (confident horizontal band)
- *Question:* What's the engineering underneath?
- *Copy:* horizontal band: `Docker python:3.12-slim` · `pinned deps` · `fixed seeds` · `isolated network` · `CI/CD` · `120 runs/arm` · `single model held constant`.
- *Components:* container/spec chips in a full-bleed band with a faint accent gradient.
- *Motion:* chips fade/slide in left-to-right on reveal.
- *Responsive:* horizontal scroll or wrap on mobile.
- *Recruiter note:* **this is the portfolio money shot** — infra and rigor as one confident line.

**9 — Evaluation history** (timeline)
- *Question:* Has this been done repeatedly / does the file evolve?
- *Copy:* list — `v3 · IMPROVED +14.2 pts · n=120 · 2026-06-04`; `v2 · NEUTRAL +1.3 pts · n=120 · 2026-05-12`; `v1 · HARMFUL −7.6 pts · n=120 · 2026-04-20`. (Shows all three verdict states honestly in one place.)
- *Components:* timeline/list rows with verdict badges, "Compare versions →".
- *Motion:* rows reveal top-down, stagger.
- *Responsive:* condenses to stacked rows.
- *Recruiter note:* a track record across versions — including a past Harmful — demonstrates the honesty thesis in action.

**10 — Footer**
- *Copy:* one-line restatement "PRIMER measures whether your context files help." Links: Methodology · Evaluations · Compare · GitHub. Build/version stamp in mono.
- *Components:* footer, links, version chip.
- *Responsive:* columns → stacked.

---

### 8.2 Evaluation page (flagship — everything legible to a recruiter)

**Purpose:** the showpiece. A complete, trustworthy reading of one evaluation. **Audience:** all three primary audiences + recruiter. Every section must be understandable without docs.

**Above the fold**

**1 — Verdict header**
- *Question:* What's the result?
- *Copy:* `CLAUDE.md (v3) · acme-payments` · big **IMPROVED** badge · headline `+14.2 pts` count-up · `61.7% → 75.9%`.
- *Components:* large verdict badge, hero metric, breadcrumb.
- *Motion:* count-up on load; badge icon draws in.

**2 — Plain-language explanation**
- *Copy:* "Adding the v3 context file raised the agent's task success rate by 14.2 points and made its results more consistent. The improvement is statistically clear (the confidence interval doesn't cross zero). One task got worse — see Task outcomes."
- *Components:* lead paragraph, inline verdict chip.

**3 — Interpretation ("what it means for you")**
- *Copy:* "If you ship this file: expect more tasks to succeed and fewer surprising failures, at about +8% token cost per task (~+$0.02/run). Watch `refactor-legacy-auth`, which regressed."
- *Components:* callout card.

**4 — Confidence (interval + n)**
- *Copy:* Confidence **High** · 95% CI **[+6.1, +22.3]** · **n = 120 per arm** (12 tasks × 10 runs).
- *Components:* confidence meter (level + interval), n chip.
- *Motion:* interval band draws from center outward.

**Below the fold**

**5 — Methodology (show-your-work, expandable)**
- *Question:* How was this made, exactly?
- *Copy:* base image `python:3.12-slim` · pinned dependencies · fixed seeds where possible · isolated network · single coding-agent model held constant · temperature held constant · randomized task order · identical suite per arm.
- *Components:* methodology disclosure (expandable), container/spec chips, copyable run config in mono.
- *Motion:* expand 200–300ms ease; chips already visible (collapsed shows summary, expanded shows full).
- *Recruiter note:* the single clearest "production engineering" signal on the site — Docker, seeds, isolation, controls, all named.

**6 — Metrics (delta · variance · cost)**
- *Copy:* Delta `+14.2 pts [+6.1,+22.3]`; Variance `std dev 0.18 → 0.12`; Cost `+8% tokens · +$0.02/run`.
- *Components:* three chart cards (paired columns w/ CI whisker; run-scatter distribution; paired cost+success).
- *Motion:* axes settle, then series grow from baseline on reveal.

**7 — Task-level outcomes (surface the harmful task honestly)**
- *Question:* Which tasks changed, and how?
- *Copy:* 12-row table/heatmap. 8 improved (e.g., `add-webhook-retry +18 pts`), 3 neutral, **1 harmful: `refactor-legacy-auth −9 pts`** — explicitly labeled and legible, not lost. Caption: "One task regressed: the file's conventions conflicted with this module's existing pattern."
- *Components:* task-outcome rows (task → result + magnitude bar), non-color cue per outcome.
- *Motion:* bars grow from zero; the harmful row is not de-emphasized.
- *Recruiter note:* deliberately showing the one bad result is the honesty thesis made concrete.

**8 — Cost impact (tradeoff framing)**
- *Copy:* "More context means more tokens. The file added +8% median tokens/task (+$0.02/run) to buy +14.2 pts of success. Shown together so you can judge the trade."
- *Components:* paired metric card (cost beside success delta, same view).
- *Motion:* both figures count up together.

**9 — Trust architecture (reproducibility)**
- *Copy:* "Same harness, same suite, same seeds, isolated network — run it again and you should get the same picture. Config and seeds are published."
- *Components:* reproducibility chips, "View run config".
- *Recruiter note:* CI/CD + reproducibility maturity, stated plainly.

---

### 8.3 Compare page — "Evolution of your context file"

**Purpose:** tell the story of an artifact maturing across versions — editorial, not a diff utility. **Audience:** teams + researchers + recruiter.

**Required surfaces (section order):**

**1 — Narrative header**
- *Copy:* "The story of `acme-payments/CLAUDE.md` — from a file that hurt, to a file that helps." Subtitle: "Three versions, measured the same way."
- *Components:* editorial title block, version selector (v1 ↔ v2 ↔ v3).

**2 — Before vs. after (two arms / two versions)**
- *Question:* What changed between versions?
- *Copy:* side-by-side v2 (NEUTRAL +1.3 pts) vs. v3 (IMPROVED +14.2 pts), each with CI and n. Plain-language diff of intent, not raw text diff.
- *Components:* comparison module (two columns, aligned metrics), verdict badges.
- *Motion:* the two columns reveal together; deltas count up in parallel.

**3 — Trend story (impact over versions)**
- *Copy:* a line/step chart of measured delta across versions: v1 **−7.6**, v2 **+1.3**, v3 **+14.2**, each with its CI band. Caption: "The file's measured impact went from harmful, to neutral, to clearly positive."
- *Components:* trend chart with CI bands, baseline at zero.
- *Motion:* line draws left-to-right; CI bands fade in behind.

**4 — Improvement narrative (plain language)**
- *Copy:* "v1 over-specified conventions and confused the agent (−7.6 pts). v2 trimmed them — no measurable harm, but no help either. v3 added concrete, repo-specific examples, and success jumped +14.2 pts. The one holdout: `refactor-legacy-auth`, still regressing." Editorial pull-quote allowed in Direction C.
- *Components:* prose blocks with inline metric chips, optional pull-quote.

**5 — Methodology consistency (apples-to-apples proof)**
- *Copy:* "Every version was measured with the same harness, the same 12-task suite, the same seeds, n = 120 per arm. The comparison is fair."
- *Components:* consistency chips, "Same conditions across all versions" seal.
- *Recruiter note:* shows the comparison itself is rigorous, not cherry-picked.

*Responsive (whole page):* side-by-side comparison reflows to stacked cards while preserving the narrative order; trend chart keeps its zero baseline and CI bands; pull-quotes move inline.

---

### 8.4 Recruiter / portfolio view (cross-cutting + optional toggle)

Recruiter-readability is a **requirement on every page** (each section above carries a recruiter note). **Additionally**, provide an optional **Recruiter/Portfolio toggle** in the nav that re-frames the *existing* content (no separate site) to foreground the engineering story in plain language.

**When toggled on, it surfaces (using visual proof, not prose):**
- **Infrastructure:** the Docker/container spec, isolated network, pinned deps — pulled up as a hero credibility strip.
- **Measurement rigor:** n, confidence intervals, variance — annotated with one-line "why this matters" tooltips ("n = 120 means we can compute confidence, not just eyeball it").
- **Testing discipline:** the 12-task suite, repeatability, randomized order — shown as a small testing-architecture diagram.
- **CI/CD maturity:** reproducible run config, seeds published.
- **Research grounding:** the CI / effect-size / "we don't claim effects whose intervals cross zero" principle.

**How it differs from the default developer view:** same data, but each engineering signal gets an explanatory caption a non-technical reviewer can read, and the technical credibility strip (§8.1.8) is promoted to the top. Default view assumes the reader knows what a CI is; recruiter view briefly explains it inline. Toggle persists; respects reduced motion.

---

## 9. Interaction model

- **Navigation:** sticky glass nav; Home · Evaluations · Compare · Methodology · GitHub, plus the Recruiter/Portfolio toggle. Active route underlined with accent.
- **Disclosure:** methodology and run-config expand in place (no route change). Verdict caveats ("1 harmful task") are clickable, scrolling to the relevant section.
- **Hover:** cards lift (e1→e2) and gain a 1px accent edge; chart elements reveal exact values in a mono tooltip with CI.
- **Selection:** version selector on Compare is a segmented control; switching animates the trend marker and re-counts the deltas.
- **Empty/loading:** see §11 states. Never spinner-only — show skeletons that preserve layout so numbers don't jump.
- **No dark patterns:** no fake urgency, no hidden caveats, no disabled-looking-but-clickable elements.

---

## 10. Motion specification

**Governing rule: motion communicates meaning.** Every animation states something; nothing animates for decoration alone.

**Tokens**
- micro **120ms** (button/toggle/focus feedback)
- standard **200–300ms** (hover, expand/collapse, page transitions)
- section reveal **400–600ms**
- count-up **800–1200ms** (delta numbers)
- entrance easing `cubic-bezier(0.16, 1, 0.3, 1)`
- hover spring: light, low-overshoot
- sibling stagger **60–80ms**

**Catalog (with intent)**
| Animation | What it says |
|-----------|--------------|
| Count-up (deltas) | "This is the finding." The number climbs to dramatize the measured effect. |
| Bar growth from zero | Magnitude is read by how far the bar travels from baseline. |
| CI whisker/band draw | Uncertainty is part of the result — it draws *with* the number, never after as an afterthought. |
| Chart entrance (axes settle → series grow) | Establishes the frame before the data, so scale isn't misread. |
| Section reveal + stagger | Guides reading order down the page. |
| Card hover (lift + accent edge) | "This is interactive / there's more here." |
| Micro-interactions (button/toggle/focus) | Immediate, crisp confirmation of input. |
| Page transitions | Continuity between routes; never blocks content. |

**Reduced motion (required):** under `prefers-reduced-motion`, replace all transforms and count-ups with instant final states or fade-only. Numbers appear at final value immediately. Content is never gated behind animation.

---

## 11. Chart & data-visualization guidance

- **Delta:** before/after paired columns, or a single signed-delta bar, with the **95% CI as an error whisker/band**. Baseline (before) always shown.
- **Variance:** run-scatter or distribution per arm; the **tightening of spread** (0.18 → 0.12) is the story — make the narrowing visible.
- **Cost impact:** paired with the success delta in one view so the tradeoff is read together, never isolated.
- **Task-level outcomes:** per-task row/heatmap, improved/neutral/harmful encoded with **color + icon + shape** (§15). The one harmful task (`refactor-legacy-auth`) must be legible, not lost.
- **Honesty-first viz rules:** never truncate a value axis to exaggerate; always label `n`; always show the baseline; always render uncertainty. No chartjunk, no 3D, no gratuitous gridlines.
- **Motion:** charts animate on reveal — axes settle, then series grow — respecting reduced motion.
- **States to design:**
  - *Empty:* "No evaluation yet — run one to see results." with a quiet illustration of the container/harness.
  - *Single-run:* show the point but flag "n = 1 — not enough to compute confidence." No CI claimed.
  - *Low-confidence:* CI rendered wide and prominent; verdict reads "Inconclusive" rather than a directional claim.
  - *Inconclusive:* plainly stated — "The interval crosses zero. We can't distinguish this from noise."

---

## 12. Component inventory

Each with states: default / hover / focus / active / disabled / loading. Dark-first.

- **Buttons** — primary (accent fill), secondary (raised surface + hairline), ghost (text + accent on hover). Focus: 2px accent ring on `border/strong`.
- **Verdict badge** — Improved / Neutral / Harmful. Color + icon + label + shape (pill style varies by verdict). Sizes: inline, card, hero.
- **Stat / metric card** — mono figure with count-up, adjacent CI and `n` always present. Hover lift + accent edge. Loading: skeleton preserving figure footprint.
- **Confidence meter** — level (Low/Moderate/High) + numeric interval; the bar visually encodes interval width (wider = less certain).
- **Methodology disclosure** — collapsed summary (key facts visible) → expanded full spec; smooth 200–300ms.
- **Container / spec chip** — Docker image, seeds, model, run count; mono text, hairline border, small Docker/seed icon.
- **Chart cards** — delta, variance, cost, task outcomes; shared header (title + `n` + baseline note), reveal animation, mono tooltips.
- **Task-outcome row** — task name → outcome badge + magnitude bar (signed, grows from zero).
- **Comparison module** — before/after columns + trend; aligned metric rows; verdict badges per version.
- **Navigation** — glass treatment; active accent underline; recruiter toggle.
- **Footer** — links + mono version/build stamp.
- **Recruiter/portfolio banner/toggle** — switches captions/promotion of the credibility strip; persistent state.

---

## 13. Responsive behavior

**Breakpoints:** mobile `< 640` · tablet `640–1024` · desktop `1024–1440` · wide `> 1440` (content capped, gutters grow).

- **Hero:** desktop = headline + floating stat side-by-side or stat centered below; mobile = stat stacks under headline, halo shrinks, CTAs full-width. All four 10-second slots stay above the fold.
- **Stat grids:** 4-col → 2×2 (tablet) → 1-col (mobile); count-ups still fire in reading order.
- **Charts:** simplify on small screens — paired columns collapse to a single signed-delta bar with CI; scatter reduces to a summarized spread indicator; tooltips become tap-to-reveal. Never drop the baseline or the `n`.
- **Nav:** condenses to a glass bar + menu; recruiter toggle moves into the menu but stays one tap away.
- **Compare:** side-by-side → stacked cards, trend chart full-width, narrative preserved in order.

---

## 14. Accessibility

- **Target WCAG 2.1 AA.** All text and meaningful UI meet contrast minimums on the dark surfaces (verify `text/secondary` and accents against `surface/elevated`).
- **Never encode verdict/outcome by color alone** — every verdict pairs color with an **icon, a label, and a shape cue** (critical for Improved/Neutral/Harmful and the task heatmap).
- **Focus:** visible, high-contrast 2px accent focus ring on every interactive element; full keyboard operability; logical tab order; skip-to-content link.
- **Reduced motion:** honored everywhere (§10) — instant/fade fallbacks, no count-up.
- **Semantics:** proper landmarks (nav/main/footer), heading hierarchy, ARIA where needed.
- **Charts carry text alternatives:** each chart has an accessible summary of the underlying numbers (e.g., "Success rate rose from 61.7% to 75.9%, a +14.2 point gain, 95% CI +6.1 to +22.3, n = 120 per arm"). Data tables available behind charts for screen readers.

---

## 15. Recruiter-first experience & portfolio showcase

Make the engineering legible to a non-technical reviewer through **designed, scannable visual proof**, not prose:

- **Containerization / infra** → the technical credibility strip (§8.1.8) and container chips: `Docker python:3.12-slim`, pinned deps, isolated network.
- **Measurement rigor** → `n = 120/arm`, 95% CIs, and variance shown beside every number; the "we don't claim effects whose intervals cross zero" principle stated plainly.
- **Testing discipline** → the 12-task suite, randomized order, repeatability — shown as the task-outcomes surface and a small testing-architecture cue.
- **CI/CD maturity** → reproducible run config + published seeds, presented as a "run it again, get the same picture" guarantee.
- **Research grounding** → the methodology section and the honest handling of Neutral/Harmful verdicts and the one regressed task.

**How it reads as a portfolio piece at a glance:** a reviewer landing on the hero sees a real measured finding *with its uncertainty and sample size*, a Docker chip, and — within one scroll — a confident infra strip and a version history that includes a past Harmful verdict honestly displayed. The combination (real infra + statistical rigor + intellectual honesty) is the demonstration. The optional Recruiter toggle (§8.4) annotates each signal so the story lands even without technical fluency.

---

## 16. Anti-patterns to avoid

- **Visual:** admin/ERP templates · spreadsheet-heavy layouts · bootstrap-era dashboards · stocky hero clichés · rainbow gradients · over-animation · busy chrome competing with data · alarm-red Harmful.
- **Content:** lorem ipsum · numbers that contradict §5 across pages · bare metrics without uncertainty · fake precision · hiding/collapsing Neutral or Harmful · burying methodology · vanity metrics · spinning the cost tradeoff.

---

*End of `DESIGN.md`. Self-contained, code-free. Paste any §8 page block into Stitch independently, or iterate on any section conversationally in Claude Design.*
