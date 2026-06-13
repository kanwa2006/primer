# Contributing to PRIMER

Thank you for your interest. PRIMER has two layers — a Python CLI/engine and a Next.js dashboard —
each with its own setup. This guide covers both.

---

## Project structure

```
primer/
├── primer/          # Python package — install with pip
├── dashboard/       # Next.js dashboard — install with npm
├── tests/           # Python test suite (pytest)
├── docs/            # Planning specs, architecture, screenshot plan
└── .github/         # CI/CD workflow (GitHub Pages deploy)
```

---

## Python engine setup

**Requirements:** Python ≥ 3.10, Docker (running)

```bash
git clone https://github.com/kanwa2006/primer.git
cd primer

# Install the package in editable mode with dev dependencies
pip install -e .[dev]

# Copy the environment template
cp .env.example .env
```

Edit `.env` and set at minimum:

| Variable | Required for | Notes |
|----------|-------------|-------|
| `ANTHROPIC_API_KEY` | `primer eval`, `primer init` (Anthropic) | Get from console.anthropic.com |
| `PRIMER_LLM_PROVIDER` | `primer init` | Default: `anthropic`. Set `ollama` for $0 generation |
| `OLLAMA_BASE_URL` | `primer init` with Ollama | Default: `http://localhost:11434` |
| `OLLAMA_MODEL` | `primer init` with Ollama | Default: `llama3.3` |

All other variables in `.env.example` have sensible defaults and can be left blank to start.

### Install pre-commit hooks

```bash
pre-commit install
```

This activates secret scanning (`detect-secrets`) and formatting checks before each commit.

### Run the Python tests

```bash
pytest tests/ -v
```

Expected: 469/505 pass. The 36 failures are async event-loop ordering contamination when
the full suite runs sequentially — all affected tests pass in isolation. This is a test
infrastructure issue, not a code correctness issue (see `PRIMER_V3_FINAL_ACCEPTANCE_AUDIT.md`).

To run just the fast, reliable subset:

```bash
# Skip the async-sensitive files
pytest tests/ -v --ignore=tests/test_generate.py --ignore=tests/test_providers_phase5.py
```

---

## Dashboard setup

**Requirements:** Node.js 20+

```bash
cd dashboard
npm ci
```

### Run the dashboard locally

```bash
npm run dev
# Opens at http://localhost:3000
```

The dashboard reads from `dashboard/public/repository.json` and
`dashboard/public/evaluations/*.json`. Sample data is included — the dashboard works
without running `primer eval` first.

### Run the dashboard tests

```bash
npm test
```

Expected: 11/11 pass (covers `computeComparison` parity logic).

### Build the static export

```bash
npm run build
# Output: dashboard/out/
```

---

## Development workflow

1. Work in the `v3-execution` branch (or a feature branch off it)
2. Follow the module boundaries in `CLAUDE.md` — the engine and dashboard are separate layers
3. Do not modify the evaluation engine, scoring logic, or data contracts without discussion
4. Validate before committing:
   - `pytest tests/ -v` (Python)
   - `cd dashboard && npm test && npm run build` (TypeScript)
5. Commit only after validation passes
6. Open a pull request against `v3-execution`

### Completion report format

Each PR description should include:
1. Files created
2. Files modified
3. Tests added
4. Acceptance criteria satisfied
5. Unresolved blockers (if any)

---

## Architecture notes

- **Engine → Dashboard boundary:** The engine writes JSON (via `primer export`). The dashboard reads JSON. Neither layer imports the other.
- **Config:** All settings flow through `primer/config.py` (pydantic-settings). Never hardcode values elsewhere.
- **Cost separation:** PRIMER overhead (generation) is always tracked separately from eval cost. This is a hard invariant — do not blend the two streams.
- **Honesty invariant:** The dashboard must never visually emphasise a positive result over a negative or within-noise result. Verdict framing is valence-neutral.

For the full authority order and frozen boundaries, see `CLAUDE.md` and `docs/v3/README.md`.

---

## Issues and questions

Open an issue on GitHub. There are no formal issue templates yet — a brief description of
the problem and your environment (OS, Python version, Docker version) is sufficient.
