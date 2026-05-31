# PRIMER

[![PRIMER score](https://img.shields.io/endpoint?url=https%3A%2F%2Fkanwa2006.github.io%2Fprimer%2Fscores.json)](https://kanwa2006.github.io/primer/)

> Every context-file tool generates. PRIMER measures.

PRIMER is a **measurement harness** for AI coding agent context files (e.g. `CLAUDE.md`, `AGENTS.md`).
It runs real, verifiable tasks through the same agent **with and without** your context file — in isolated
Docker containers — and reports a trustworthy signed before/after success and token-cost delta **with variance**.

The delta may be positive, ~0, or negative. PRIMER is designed to *measure*, not to prove it helps.

## Scope

- **$0 file generation** via local Ollama (no API key needed for `primer init`)
- **Evaluation requires a Claude Code agent + Anthropic API key** and costs money
- Reports a signed Δ that may be ≤0; a within-noise result is a valid, shippable outcome

## Status

Phases 0–7 implemented. Run `primer eval .` to measure your context file.

## Usage

```bash
pip install -e .
primer init .      # generate a lean context file for your repo
primer eval .      # run the before/after evaluation harness
primer report .    # render the score report
```

## Evidence base

ETH Zurich SRI Lab + LogicStar.ai (arXiv:2602.11988, 12 Feb 2026): LLM-auto-generated context files
**reduce** agent task success in 5 of 8 settings while **raising inference cost >20%**. Developer-written
files can help (+4% avg). PRIMER measures which yours is.

## License

MIT, 2026, kanwa2006
