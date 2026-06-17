# Contributing to PRIMER

Thank you for your interest. PRIMER has two independent layers — a Python CLI/engine and a Next.js dashboard — each with its own setup.

---

## Project structure

```
primer/
├── primer/          # Python package — install with pip
├── dashboard/       # Next.js 15 dashboard — install with npm
├── tests/           # Python test suite (pytest, 20 files, 554 tests)
├── docs/            # Architecture specs, screenshots
└── .github/         # CI/CD workflow + issue templates
```

---

## Python engine setup

**Requirements:** Python ≥ 3.10, Docker (running)

```bash
git clone https://github.com/kanwa2006/primer.git
cd primer

# Install in editable mode with dev dependencies
pip install -e .[dev]

# Copy the environment template
cp .env.example .env
```

Edit `.env`:

| Variable | Required for | Notes |
|----------|-------------|-------|
| `ANTHROPIC_API_KEY` | `primer eval`, `primer init` (Anthropic) | Get from console.anthropic.com |
| `PRIMER_LLM_PROVIDER` | `primer init` | Default: `anthropic`. Set `ollama` for $0 generation |
| `OLLAMA_BASE_URL` | `primer init` with Ollama | Default: `http://localhost:11434` |
| `OLLAMA_MODEL` | `primer init` with Ollama | Default: `llama3.3` |

All other variables have sensible defaults.

### Pre-commit hooks

```bash
pre-commit install
```

Activates secret scanning (`detect-secrets`) and formatting checks before each commit.

### Python tests

```bash
pytest tests/ -v
```

Expected: **550/554 pass; 4 skipped** (Docker + live-API integration tests — set `PRIMER_RUN_DOCKER_TESTS=1` to run those). 0 failures.

---

## Dashboard setup

**Requirements:** Node.js 20+

```bash
cd dashboard
npm ci
```

### Run locally

```bash
npm run dev
# Opens at http://localhost:3000
```

The dashboard reads from `dashboard/public/repository.json` and `dashboard/public/evaluations/*.json`. Sample data is included — the dashboard works without running `primer eval` first.

**Routes:**

| Route | Description |
|-------|-------------|
| `/` | Repository overview, evaluation ledger |
| `/evaluations/[id]` | Evaluation detail: metrics, confidence ruler, flip table |
| `/compare` | Side-by-side evaluation diff |
| `/trends` | Delta trend chart, verdict distribution |
| `/methodology` | Measurement methodology explainer |
| `/score-guide` | How to read the score |
| `/export` | Badge copy-paste + data download |

### Dashboard tests

```bash
npm test
# 11/11 pass — covers computeComparison parity with Python engine
```

### Build static export

```bash
npm run build
# Output: dashboard/out/
```

---

## Development workflow

1. Branch off `main` (or work directly on a feature branch off `main`)
2. Follow the module boundaries in `CLAUDE.md` — engine and dashboard are separate layers
3. Do not modify the evaluation engine, scoring logic, or data contracts without discussion
4. Validate before committing:
   - `pytest tests/ -v` (Python)
   - `cd dashboard && npm test && npm run build` (TypeScript)
5. Open a pull request against `main`

### PR format

Each PR description should include:

1. Files created
2. Files modified
3. Tests added or updated
4. Acceptance criteria satisfied
5. Unresolved blockers (if any)

---

## Architecture invariants

**Engine → Dashboard boundary:** The engine writes JSON via `primer export`. The dashboard reads JSON. Neither layer imports the other.

**Config:** All settings flow through `primer/config.py` (pydantic-settings). Never hardcode values elsewhere.

**Cost separation:** PRIMER overhead (generation) is always tracked separately from eval cost. Do not blend the two streams.

**Honesty invariant:** The dashboard must never visually emphasise a positive result over a negative or within-noise result. Verdict framing is valence-neutral. This is a hard invariant, not a style preference.

---

## Issues and questions

Open an issue using the [bug report](.github/ISSUE_TEMPLATE/bug_report.md) or [feature request](.github/ISSUE_TEMPLATE/feature_request.md) template. Include your OS, Python version, and Docker version for bug reports.
