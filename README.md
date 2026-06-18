[![CI](https://github.com/kanwa2006/primer/actions/workflows/pages.yml/badge.svg)](https://github.com/kanwa2006/primer/actions/workflows/pages.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PRIMER score](https://img.shields.io/endpoint?url=https%3A%2F%2Fkanwa2006.github.io%2Fprimer%2Fscores.json)](https://kanwa2006.github.io/primer/)
[![Python](https://img.shields.io/badge/python-%E2%89%A53.10-blue)](pyproject.toml)

# PRIMER

> Every context-file tool generates. PRIMER measures.

**PRIMER is an AI agent context-file measurement platform.**

It answers one specific question with evidence: *does your `CLAUDE.md`, `AGENTS.md`, or `GEMINI.md` actually improve your AI coding agent's performance — or does it hurt?*

PRIMER runs a controlled before/after experiment on your repository using real, deterministically-verifiable coding tasks inside hermetically isolated Docker containers. It reports a signed success-rate delta with a variance envelope. The result can be positive, zero, or negative. PRIMER is designed to tell you the truth, not to optimise for a good-looking number.

**[Live dashboard →](https://kanwa2006.github.io/primer/)**

---

## The Problem

AI coding agents are guided by context files you write or auto-generate. These files are unverified claims. You ship them into every agent session without knowing whether they help.

Without measurement:

- You cannot distinguish a helpful context file from a harmful one
- Auto-generated files often reduce performance (see [Research basis](#research-basis))
- You are making product decisions based on instinct, not data

PRIMER makes the experiment automatic.

---

## Research Basis

ETH Zurich SRI Lab + LogicStar.ai ([arXiv:2602.11988](https://arxiv.org/abs/2602.11988), Feb 2026) found that LLM-auto-generated context files **reduce** agent task success in 5 of 8 settings while **raising inference cost >20%**. Developer-written files average +4 pp. The paper demonstrates the need for systematic measurement — PRIMER runs that measurement automatically on your repo.

---

## How It Works

```
Your Repository
      │
      ▼
primer init       ← analyses git history + generates context file (Ollama / cloud)
      │
      ▼
primer eval       ← derives verifiable tasks from git history
      │
      ├──── Docker Container (WITHOUT context file)
      │         agent runs 5 tasks × 3 runs
      │
      └──── Docker Container (WITH context file)
                agent runs same 5 tasks × 3 runs
                      │
                      ▼
              success-rate Δ ± noise threshold
              cost Δ  ·  per-task flip table
              SQLite store  ·  scores.json badge
              static dashboard (GitHub Pages)
```

Each evaluation arm runs inside a hermetically isolated Docker container. Egress enforcement prevents the agent from calling external services during the run. The signed delta is written to SQLite and exported to JSON for the dashboard.

**Two task types** derived from your git history:
- `revert_reimplement` — revert a commit, ask the agent to re-implement it; success = tests pass
- `stub_function` — stub a function, ask the agent to implement it; success = tests pass

Both are deterministic and pytest-verified. No LLM judge. No human grading.

---

## Measurement Model

| Concept | Definition |
|---------|------------|
| **Delta (Δ)** | `success_rate_with − success_rate_without` (percentage points) |
| **Noise threshold** | `max(1/n_tasks, success_stddev)` — the minimum detectable signal |
| **Verdict** | One of four: **Helped ▲** / **Hurt ▼** / **No measurable effect ≈** / **Not comparable ⊘** |
| **Flip** | A task whose outcome changed between arms (PASS→FAIL, FAIL→PASS, etc.) |
| **Cost delta** | Separate stream: token cost WITH vs WITHOUT, tracked independently |

A within-noise result (`≈`) is a valid, honest outcome — it means the experiment cannot distinguish your context file from noise at this sample size. That is useful information.

---

## Screenshots

**Overview — latest verdict, evaluation ledger, pipeline status**
![PRIMER overview](docs/assets/overview-full.png)

**Evaluation detail — confidence ruler, metrics grid, per-task flip table**
![Evaluation detail](docs/assets/hero-desktop.png)

**Compare — two evaluations side by side**
![Compare view](docs/assets/compare.png)

**Mobile — responsive layout**
![Mobile view](docs/assets/mobile.png)

---

## Quick Start

### Prerequisites

| Requirement | For |
|-------------|-----|
| Python ≥ 3.10 | All commands |
| Docker (running) | `primer eval` |
| Anthropic API key | `primer eval` (costs ~$0.01–$0.10 per run) |
| Ollama (optional) | `primer init` at $0 cost |

### Install

```bash
git clone https://github.com/kanwa2006/primer.git
cd primer
pip install -e .
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY at minimum
```

For all providers:

```bash
pip install -e .[all-providers]   # adds openai + google-genai
```

### Run

```bash
# Step 1: generate a context file for your repo (~$0 with Ollama)
primer init /path/to/your/repo

# Step 2: run the before/after evaluation
primer eval /path/to/your/repo

# Step 3: view the result
primer report /path/to/your/repo
```

### Example output

```
PRIMER eval → /path/to/your/repo

1/5  Analysing repo ...
     Commit abc1234 | langs ['python']
2/5  Generating CLAUDE.md ...
     Generated 48 lines  (PRIMER overhead: ~$0.004)
3/5  Deriving tasks ...
     5 validated tasks ready
4/5  Building eval image ...
     Image: primer-eval:abc1234
5/5  Running 5 tasks × {without, with} × 3 runs (sequential) ...

  Delta      +12.0 pp ± 15.0 pp noise threshold
  Verdict    ≈ No measurable effect
  WITHOUT    53.3%   WITH    65.3%
  Tasks      5       Runs    3
```

> The delta here (+12 pp) is within the noise threshold (±15 pp), so the verdict is `≈ No measurable effect`. This is not a failure — it is an honest result at this sample size.

### Export and publish

```bash
primer export /path/to/your/repo --site-output dashboard/public

# Add the badge to your repo's README:
# [![PRIMER score](https://img.shields.io/endpoint?url=https://your-user.github.io/primer/scores.json)]
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `primer init <path>` | Analyse repo and generate context file |
| `primer eval <path>` | Run before/after evaluation |
| `primer report <path>` | Render latest score (text or `--json`) |
| `primer history <path>` | List all past evaluations |
| `primer compare <id1> <id2>` | Diff two evaluations side-by-side |
| `primer export <path>` | Write `scores.json` + dashboard JSON tree |

---

## Who Is It For

**Individual developers** building context files for their own repos — verify whether yours helps before shipping it.

**Open-source maintainers** who want to show contributors that the project's `CLAUDE.md` is evidence-backed, not vibes-based.

**AI engineers and researchers** studying the effect of context on agent performance — PRIMER gives you a reproducible, containerised experiment framework.

**Teams evaluating agent tooling** — use PRIMER to A/B test different context file strategies against each other.

---

## Competitive Positioning

PRIMER occupies a narrow, specific niche: **controlled A/B measurement of AI agent context files**. It does not overlap with general LLM evaluation or observability platforms.

| Tool | Primary category | Overlap with PRIMER |
|------|-----------------|---------------------|
| [Promptfoo](https://promptfoo.dev) | Prompt/LLM evaluation | Tests prompts against datasets; no context-file A/B, no Docker isolation |
| [LangSmith](https://smith.langchain.com) | Observability + tracing | Session tracing and dataset evals; different category |
| [Braintrust](https://braintrustdata.com) | Eval + experiment tracking | Human/LLM-graded evals; no before/after controlled design |
| [DeepEval](https://github.com/confident-ai/deepeval) | Unit-test LLM evals | Metric-based LLM testing; no context-file focus |
| [OpenAI Evals](https://github.com/openai/evals) | LLM capability benchmarks | Model evaluation, not context-file measurement |
| [Arize Phoenix](https://phoenix.arize.com) | ML observability | Tracing and drift detection; different category |
| [TruLens](https://trulens.org) | RAG/LLM feedback | Feedback-function evaluation; different category |
| [AgentOps](https://agentops.ai) | Agent session monitoring | Runtime observability; different category |
| [Helicone](https://helicone.ai) | LLM proxy + analytics | Cost/latency analytics; different category |
| [Ragas](https://ragas.io) | RAG evaluation | Retrieval-augmented generation; different domain |
| [Maxim AI](https://getmaxim.ai) | LLM CI/CD testing | Broader LLM app testing; no context-file A/B |
| [Galileo](https://galileo.ai) | LLM evaluation | Hallucination and quality metrics; different domain |
| [W&B Weave](https://wandb.ai/site/weave) | Eval + experiment tracking | General LLM/ML tracking; different scope |
| [Patronus AI](https://patronus.ai) | Enterprise LLM eval | Red-teaming and safety; different domain |

**What makes PRIMER different:**

1. **Controlled experiment design** — before/after, same tasks, same agent, same repo; no other tool does this for context files
2. **Docker isolation with egress enforcement** — prevents result contamination from external API calls during evaluation
3. **Deterministic verification** — test-passing (not LLM-as-judge); the ground truth is pytest
4. **Honest negative results** — the verdict taxonomy includes `≈` and `⊘`; no dashboard bias toward positive outcomes
5. **Zero infrastructure for the dashboard** — static export to GitHub Pages; no server, no database

---

## Scope and Honest Limitations

**What PRIMER does today:**
- ✓ Generates context files via Ollama (free), Anthropic, OpenAI, Gemini, or OpenRouter
- ✓ Derives coding tasks from your git history automatically
- ✓ Runs controlled before/after evaluation in Docker
- ✓ Reports signed delta with noise threshold
- ✓ Exports static dashboard to GitHub Pages
- ✓ Multi-evaluation history and cross-run comparison

**What PRIMER does not do today:**
- ✗ Evaluation without Docker (Docker is required for isolation)
- ✗ Non-Python repositories (tree-sitter supports JS/TS/Python; task derivation targets Python first)
- ✗ Evaluation without an API key for the agent (Ollama agent path is experimental)
- ✗ Real-time evaluation (runs are sequential; 5 tasks × 3 runs takes ~15–45 minutes)

**Honest state of current data:** The dashboard currently shows evaluations from the `gemini-2.5-flash` experimental agent path with egress open (`egress_enforced: false`). All results are within-noise (0.0 pp ± 20 pp). This is honest data — the agent failed all stub tasks in both arms. A Claude Code evaluation against PRIMER itself is planned.

---

## Engineering Quality

### Test suite

**Python — 554 tests across 20 files:**

```bash
pip install -e .[dev]
pytest tests/ -v
# 550 pass, 4 skipped (Docker / live-API integration — set PRIMER_RUN_DOCKER_TESTS=1 to run)
```

**Dashboard — 11 TypeScript tests:**

```bash
cd dashboard && npm test
# 11/11 pass — covers computeComparison parity with Python engine
```

### CI / CD

Push to `main` → GitHub Actions builds the Next.js static export → deploys to GitHub Pages. No manual steps.

### Security

- API keys stored as `SecretStr` (pydantic-settings) — never appear in logs, `repr`, or exports
- `detect-secrets` baseline active; `.pre-commit-config.yaml` runs on every commit
- `primer export` output contains only metrics — no keys, tokens, or internal paths

---

## Repository Structure

```
primer/
├── primer/               # Python package — CLI + evaluation engine
│   ├── cli.py            # Composition root: init, eval, report, history, compare, export
│   ├── config.py         # Pydantic settings; single source of config truth
│   ├── eval/             # Eval harness: Docker runner, scorer, task derivation, adapters
│   ├── generate/         # Context file writer
│   ├── ingest/           # Repo analyser (tree-sitter, git log)
│   ├── llm/              # Provider factory + adapters (Anthropic, OpenAI, Gemini, Ollama)
│   ├── report/           # Render + export (text, JSON, scores.json, dashboard JSON)
│   └── store/            # SQLite persistence
├── dashboard/            # Next.js 15 static dashboard → GitHub Pages
│   ├── app/              # 7 routes: /, /evaluations/[id], /compare, /trends, /methodology, /score-guide, /export
│   ├── components/       # VerdictHero, MetricsGrid, EvaluationLedger, ComparePanel, TrendsView, …
│   └── lib/              # format.ts, verdict.ts, computeComparison.ts
├── tests/                # 20 test files, 554 tests
├── docs/
│   └── assets/           # Screenshots for README and documentation
├── docker/               # Eval container Dockerfile + egress proxy
├── .github/
│   ├── workflows/pages.yml        # CI/CD — builds and deploys dashboard
│   ├── ISSUE_TEMPLATE/            # Bug report and feature request templates
│   └── pull_request_template.md
├── pyproject.toml        # Package metadata + pytest config
├── .env.example          # Config template — copy to .env and fill in keys
├── SECURITY.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
└── CHANGELOG.md
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, development workflow, and the honesty invariants that govern all contributions.

---

## License

MIT — see [LICENSE](LICENSE).
