# Changelog

All notable changes to PRIMER are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- V4 dashboard redesign: aurora background, dark/light theme toggle, mobile-first navigation
- New routes: `/trends`, `/methodology`, `/score-guide`, `/export`
- WCAG AA colour tokens and improved accessibility across all components
- `SECURITY.md`, `CODE_OF_CONDUCT.md` — community health files
- GitHub issue templates and PR template

---

## [0.1.0] — 2026-06-13

### Added
- **Evaluation CLI** — `primer init`, `primer eval`, `primer report`, `primer history`, `primer compare`, `primer export`
- **Docker isolation** — hermetic containers per evaluation arm; optional egress proxy blocks outbound agent calls during runs
- **Multi-provider LLM support** — Anthropic Claude Code, OpenAI, Gemini (experimental), Ollama (local, $0)
- **Measurement methodology** — success-rate delta with noise-envelope uncertainty; 4-verdict taxonomy (Helped ▲ / Hurt ▼ / No measurable effect ≈ / Not comparable ⊘); per-task flip table (PASS_TO_PASS / PASS_TO_FAIL / FAIL_TO_PASS / FAIL_TO_FAIL)
- **SQLite persistence** — all evaluation runs stored; queryable via `primer history` and `primer compare`
- **Next.js dashboard** — static export on GitHub Pages; evaluation overview, detail view, and side-by-side comparison
- **GitHub Actions CI/CD** — deploys dashboard to GitHub Pages on push to `main`
- **Shields.io badge** — live score served from `scores.json` on GitHub Pages

### Constraints
- `primer eval` requires Docker and an LLM API key (cloud providers charge per token)
- Ollama integration is free; Anthropic, OpenAI, and Gemini are pay-per-token
- Current evaluation data uses an experimental Gemini agent path with egress open — all results are within-noise
- Evaluating PRIMER against itself (closing the loop on the badge) is planned
