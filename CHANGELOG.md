# Changelog

All notable changes to PRIMER are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- V4 dashboard: aurora background, dark/light theme toggle, caliper confidence ruler, mobile-first hamburger nav
- 4 new routes: `/trends`, `/methodology`, `/score-guide`, `/export`
- New components: `AuroraBg`, `ThemeProvider`, `ThemeToggle`, `VerdictBadge`, `DeltaCountUp`, `HeroBand`, `InstrumentStatusBar`, `PipelineChips`, `GraticuleBg`, `CursorCompanion`, `Magnetic`
- `lib/verdict.ts` — centralised verdict taxonomy, noise-threshold logic, FLIP_LABELS, AGENT_DISPLAY
- `lib/cn.ts` — clsx + tailwind-merge utility
- Dark/light theme via `next-themes` with `class` strategy
- Typography scale: `.t-display/.t-h1/.t-h2/.t-h3/.t-lead/.t-body/.t-caption/.t-eyebrow/.t-data`
- WCAG AA colour tokens across all components
- `SECURITY.md`, `CODE_OF_CONDUCT.md` — community health files
- GitHub issue templates and PR template
- `docs/assets/` — curated screenshots for README

---

## [0.1.0] — 2026-06-13

### Added
- **Python evaluation engine** — full 7-phase implementation
  - `primer init` — repo analysis + context file generation (Ollama / Anthropic / OpenAI / Gemini)
  - `primer eval` — before/after Docker evaluation harness with egress enforcement
  - `primer report` — signed delta rendering (text + JSON)
  - `primer history` — evaluation log with provider and verdict
  - `primer compare` — two-evaluation diff (cross-model comparisons refused)
  - `primer export` — `scores.json` badge + full dashboard JSON tree
- **Measurement methodology** — success-rate delta ± noise threshold (not CI); 4-verdict taxonomy (Helped ▲ / Hurt ▼ / No measurable effect ≈ / Not comparable ⊘); per-task flip table (PASS_TO_PASS / PASS_TO_FAIL / FAIL_TO_PASS / FAIL_TO_FAIL)
- **Docker isolation** — hermetic containers per eval arm; optional egress proxy to block outbound agent calls
- **Multi-provider support** — Anthropic Claude Code, OpenAI, Gemini (experimental), Ollama (local, $0)
- **SQLite persistence** — all evaluation runs stored; queryable via `primer history` / `primer compare`
- **Static dashboard V3** — Next.js 15 static export on GitHub Pages; 3 routes (overview, evaluation detail, compare)
- **CI/CD** — GitHub Actions deploys dashboard to GitHub Pages on push to `main`
- **554-test Python suite** — config, ingest, generation, task derivation, Docker runner isolation, eval scoring, report rendering, site export, CLI smoke tests
- **11-test TypeScript suite** — `computeComparison` parity with Python engine
- **Security scaffold** — `detect-secrets` baseline, `.gitleaksignore`, `SecretStr` for API keys
- **Shields.io badge** — live score badge served from `scores.json` on GitHub Pages

### Constraints
- Evaluation requires Docker running and an Anthropic API key (costs real money)
- `primer init` with Ollama is free; cloud providers have per-token cost
- Current evaluation data uses experimental `gemini-2.5-flash` agent path with egress open — all results are within-noise
- `primer eval` against PRIMER itself (badge showing real delta) is a known roadmap item
