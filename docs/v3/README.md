# PRIMER V3 — Planning Artifacts

## Purpose

This directory holds the V3 product-experience planning chain for PRIMER: the governing specification and the four planning documents derived from it (audit → roadmap → cleanup execution spec → implementation architecture). Together they define **what V3 changes, why, in what order, and within which frozen boundaries** — all at the planning/architecture level. They contain no code and no implementation prompts.

V3 is a **presentation-layer** effort: the measurement engine, data contracts, routes, schema, and scoring math are a frozen core (Spec §19). These documents govern only the honest presentation built above the export boundary.

## Authority order

When the documents conflict, resolve in this order (highest first):

1. **PRIMER_V3_Product_Experience_Specification.md** — the source of truth.
2. **PRIMER_V3_Implementation_Readiness_Roadmap.md** — supersedes the Audit.
3. **PRIMER_V3_Implementation_Readiness_Audit.md**.

The **Cleanup Execution Specification** and **Implementation Architecture** are execution/architecture layers derived under the Specification; they do not override it.

Governance note: per CLAUDE.md, the four V1/V2 authority documents (`docs/authority/**`) and the V2 §0.1 "Frozen surfaces" rule still bind the engine/CLI until V3 is formally inserted into the CLAUDE.md authority order — an approval-gated step recorded in the Audit (§3, §6) and Roadmap (Phase 1).

## Creation source

These files were **recovered from this Claude Code conversation history** and persisted verbatim:

- `PRIMER_V3_Product_Experience_Specification.md` — the *input* spec; copied byte-for-byte from its original location (`D:\PRIMER_V3_Product_Experience_Specification.md`, the same file read into the conversation). Not generated in-session. Self-described in its own delivery note as complete with Sections 1–7 in full and Sections 8–20 + the §17 checklist in condensed-but-binding form.
- The other four documents were **generated in this session** and transcribed here verbatim — not rewritten, summarized, or improved. Section numbering and formatting are preserved as generated (including internal `File:` references and any relative links, which resolve against the repo root, not this directory).

## File list

| File | Description |
|---|---|
| `PRIMER_V3_Product_Experience_Specification.md` | Source-of-truth spec (input, copied byte-exact) |
| `PRIMER_V3_Implementation_Readiness_Audit.md` | Conflicts, obsolete assumptions, deletion register |
| `PRIMER_V3_Implementation_Readiness_Roadmap.md` | Prioritized dispositions + phases 0–4 + callouts |
| `PRIMER_V3_Cleanup_Execution_Specification.md` | Executable cleanup phases C0–C4 + approval-gated set |
| `PRIMER_V3_Implementation_Architecture.md` | Survives/replaced/wrapped/rebuilt/frozen + post-cleanup phases |
| `README.md` | This index |
