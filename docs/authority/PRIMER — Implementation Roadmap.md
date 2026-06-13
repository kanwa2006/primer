

---

# PRIMER — Implementation Roadmap

## 1. Executive Summary

The roadmap converts the approved architecture into **five sequential phases connected by one critical path that runs entirely through the `eval/` subsystem**, with the **Provider track deliberately routed off that path so it can proceed in parallel**. The governing principle is the audit's correction to V3: **freeze the measurement *invariants*, make the *dispatch* pluggable.** Every phase composes additively onto a stable core; no phase rewrites a settled layer.

Three facts dictate the entire sequence:

1. **Governance is the literal first action.** The V3 "Frozen Core" doctrine forbids the `primer/**` changes this roadmap requires. Until it is formally superseded (`G0`), no eval/generate/llm work is authorized. This is a non-code gate that blocks Phases 1–4.
2. **Correctness precedes generalization.** Two defects — the `runs=[]` persistence bug and the scorer's source-repo mutation — poison the validation gates of *every* later phase (you cannot trust a reloaded report, and you cannot safely run a real eval). They are fixed in Phase 0 before any abstraction is added.
3. **The moat must be proven once before it is generalized.** Agent provisioning and `api_host` wiring (Phase 1) are prerequisites for *any* agent to execute in the sandbox; the audit established the harness has likely never run end-to-end. Generalizing to N agents/languages before one combination works would build on unverified foundations.

The two genuinely hard, high-risk pieces of engineering — **proving the Docker moat (Phase 1)** and **extracting the LanguageToolchain (Phase 3)** — are isolated into their own phases with their own gates. The cheap, additive axes (Provider registry, Context strategy, second agent) cluster in Phase 2. Hardening, the capability matrix, and legacy retirement are Phase 4.

**Schema stays untouched through Phases 0–1** (the persistence fix is a call-site bug, not a schema change), with the **first additive migration deferred to Phase 2/3**. Estimated total effort: **~12–18 engineer-weeks** for one engineer fluent in the codebase with Docker/CI available, compressible in calendar time by running the Provider track in parallel.

---

## 2. Global Dependency Graph

Phase-level (hard gates are `⟹`):

```
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ PHASE 0  Governance + Correctness   (schema-stable; mostly parallel)     │
   │   G0 ─(governance gate)─┐                                                 │
   │   C5 (test-infra) ──────┼─ enables trustworthy validation everywhere     │
   │   C1 C2 C3 C4 ──────────┘                                                 │
   └───────────────┬───────────────────────────────────────────┬─────────────┘
                   │ G0 + C2 required                           │ G0 required
                   ▼                                            ▼
   ┌───────────────────────────────────┐        ┌───────────────────────────────┐
   │ PHASE 1  Prove the moat (eval/)    │        │ PROVIDER TRACK (llm/)  — OFF   │
   │   A1 provisioning ─┐               │        │ the critical path, parallel:   │
   │   A2 api_host wiring┼─▶ A3 real run│        │   P1 ProviderRegistry +        │
   │   A4 isolation tests┘   (gate)     │        │      OpenAICompatible base     │
   └───────────────┬───────────────────┘        │   P2 registry-driven config    │
                   │ A1+A2+A3                    │   PR1 pricing externalization  │
                   ▼                             └───────────────┬───────────────┘
   ┌───────────────────────────────────┐                        │ (joins at P2)
   │ PHASE 2  Cheap axes (generate/,    │◀───────────────────────┘
   │          adapters/, eval/)         │
   │   CS1 ContextStrategy ─▶ CS2 (M7)  │
   │   AG1 second agent ◀─(needs A1,A2,CS1)                      │
   │   SM1 first schema migration (optional)                    │
   └───────────────┬───────────────────────────────────────────┘
                   │ A3 (verify path proven) + registry pattern proven (P1/CS1)
                   ▼
   ┌───────────────────────────────────┐
   │ PHASE 3  LanguageToolchain (HARD)  │
   │   LT1 extract PytestToolchain ─▶ LT2 second toolchain ─▶ LT3 capability gate
   │   SM2 schema migration · LT4 golden repos                  │
   └───────────────┬───────────────────────────────────────────┘
                   │ all axes present
                   ▼
   ┌───────────────────────────────────┐
   │ PHASE 4  Hardening + honesty       │
   │   H1 report registry · H2 cross-axis refusal · H3 provenance+SM3
   │   H4 deprecate legacy · H5 contract tests + docs            │
   └───────────────────────────────────┘
```

Work-item dependency edges (the ones that actually constrain ordering):

| Edge | Reason |
|---|---|
| `G0 ⟹ {C2, C3, A1, A2, P1, CS1, LT1, …}` | Authorizes any frozen-core change. |
| `C5 ⟹ trustworthy validation in all phases` | Green suite is the substrate for every gate. |
| `C2 ⟹ A3` | A real eval must not mutate/delete the subject repo. |
| `C2 ⟹ CS1` | Both change how the runner receives context; C2 lands first. |
| `A1 + A2 ⟹ A3` | No agent runs without a provisioned CLI and an open egress path. |
| `A1 + A2 + CS1/CS2 ⟹ AG1` | A second agent needs runtime (P1) **and** correct filename (P2). |
| `CS1 ⟹ CS2` | The M7 filename fix rides on the strategy object. |
| `A3 ⟹ LT1` | The verify path must be proven before it is parameterized per language. |
| `LT1 ⟹ LT2 ⟹ LT3` | Toolchain interface → second impl → capability gating. |
| `{P1, CS1, AG1, LT3} ⟹ H2/H4` | Cross-axis refusal and legacy retirement need all new paths live. |

---

## 3. Current → Target Migration Overview

| Axis | Current (verified) | Target | Migration mechanism | Backward-compat strategy |
|---|---|---|---|---|
| Provider dispatch | `if/elif` in `factory.py` + duplicated key maps in `config.py` | `ProviderRegistry` + `OpenAICompatibleProvider` base | Phase 2; internal to `factory.py` | **Keep `get_provider(config)` signature** → call sites unchanged |
| Agent dispatch | Registry exists; `api_host()` dead; CLI not provisioned | Registry + `AgentRuntime` (provision + multi-host egress) | Phase 1 (wire) → Phase 2 (2nd agent) | Default `claude_code`; new methods default to current behavior |
| Context | `adapter.context_filename()` returns `CLAUDE.md` (Gemini too) | `ContextStrategy` registry (filename(s)/layout/prompt) | Phase 2 | `context_filename()` retained as **deprecating shim** |
| Language/verify | pytest hardcoded across `tasks/preflight/images` | `LanguageToolchain` registry | Phase 3 | **pytest remains the default toolchain** |
| Persistence | `runs=[]` → per-task zeroed on reload | runs round-trip; additive provenance columns | Phase 0 (bugfix, no schema) → Phase 2/3 (migrations) | Additive `ADD COLUMN` only; old readers ignore new columns |
| Repo safety | scorer writes/deletes context in the **caller's** repo | runner receives context **content**; caller repo never touched | Phase 0 | Pure correctness fix; behavior strictly safer |
| Honesty surface | refuse on provider/model mismatch | + isolation + language/runtime mismatch; `CapabilityMatrix` | Phase 4 | Extends existing refuse-on-mismatch, never relaxes it |

**Frozen throughout (the protected core API):** isolation runner mechanics, scorer variance + refuse-on-mismatch + two-stream separation, `RunResult`/`ScoreReport` field semantics, export JSON contract shapes, AD-4 (verify_cmd exit code = verdict). Plugins compose around these; they never reach inside.

---

## 4. Phase 0 — Governance & Correctness

**1. Objective.** Authorize core change and eliminate the defects that would corrupt every downstream validation gate — **without adding any abstraction or schema change.**

**2. Backend subsystems affected.** Governance/docs; `cli.py` (composition root); `eval/scorer.py`, `eval/runner.py` (source-mutation fix); `eval/adapters/claude_code.py` (eligibility guard); test infrastructure; `tests/test_arch_boundaries.py`.

**3. Files likely affected.**
- `docs/` — new authority record superseding the V3 Frozen-Core freeze (`G0`, non-code).
- `primer/cli.py` — persist runs (`C1`).
- `primer/eval/scorer.py` + `primer/eval/runner.py` — pass context **content** to the runner; stop writing/deleting in the source repo (`C2`).
- `primer/eval/adapters/claude_code.py` (+ a shared eligibility helper) — implement the committed-context guard, or convert to safe handling (`C3`).
- `tests/test_arch_boundaries.py` — add `google.genai` to the vendor-SDK name set (`C4`).
- `pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"` (`C5`).
- Regression tests: `tests/test_scorer.py`, `tests/test_runner_isolation.py`, `tests/test_phase6.py`/`test_site_export.py` (round-trip), plus a new `tests/test_repo_safety.py`.

**4. Dependency graph.** `G0` is the gate for `C2`/`C3` (frozen `eval/`). `C1`, `C4`, `C5` are independent and may start immediately (`C1` touches only the composition root; `C5`/`C4` are test-infra). All five are otherwise mutually parallel.

**5. Architectural changes.** None structural. One contract refinement: `run_task` gains the context **content** as an input instead of relying on the scorer pre-staging a file in the source tree. This is the seam `CS1` later builds on, so it is intentionally introduced here in its minimal form.

**6. Risks.**
- `C2` touches the two highest-risk files (`runner`, `scorer`); a regression here invalidates the moat. *Mitigation:* land behind comprehensive round-trip + repo-safety tests before anything else.
- `C5` (`asyncio_mode=auto`) could change collection semantics for existing async tests. *Mitigation:* run full suite isolated-vs-batched and confirm the 36 ordering failures resolve without new ones.
- `C3` interacts with `init` (which writes `CLAUDE.md`): a user who runs `init` then `eval` must not be rejected for the file PRIMER itself created. *Mitigation:* the guard distinguishes a PRIMER-generated file from a committed developer file (the open M11 interaction — resolve it here, conservatively, as "safe handling" rather than hard rejection).

**7. Test strategy.** Add a **persistence round-trip test** (save a report with N runs → reload → per-task pass-rates and deltas match in-memory values). Add a **repo-safety test** (eval against a fixture repo with a committed `CLAUDE.md` → file is byte-identical and present afterward; working tree clean). Fix and re-green the full suite (target: 505/505, eliminating KL-1).

**8. Validation gates.**
- Full Python suite green **in a single batched run** (KL-1 resolved).
- Round-trip test proves per-task data survives reload.
- Repo-safety test proves zero mutation of the caller's tree.
- Governance record merged and referenced by `CLAUDE.md`/authority index.

**9. Rollback strategy.** Each item is an independent revert; invariants are untouched. `C5` is a one-line config revert. `C2` is the only risky revert and is fully covered by the new tests, so a regression is caught pre-merge. `G0` is documentation.

**10. Estimated complexity.** **M** (several S-sized surgical fixes + a governance doc + test-infra). The risk concentration in `C2` raises it from S to M.

**11. Exit criteria.** Governance freeze formally superseded; full suite green batched; reloaded reports carry real per-task data; eval never mutates the caller's repo; boundary test sees `google.genai`. **No schema change shipped.**

---

## 5. Phase 1 — Prove the Moat End-to-End

**1. Objective.** Make exactly **one** (agent, provider) combination — `claude_code` + `anthropic` — run to a real measured delta inside the sandbox, closing the agent-provisioning and `api_host` gaps that make the moat currently inert.

**2. Backend subsystems affected.** `eval/images.py` (provisioning), `eval/network.py` (egress wiring), `eval/agent_adapter.py` (ABC), `eval/adapters/claude_code.py`, `eval/runner.py` (consumes egress hosts), the isolation test.

**3. Files likely affected.**
- `primer/eval/agent_adapter.py` — add `egress_hosts() -> list[str]` and an `AgentRuntime` provisioning hook to the ABC (default impls preserve current behavior).
- `primer/eval/images.py` — provision the agent CLI into the eval image (`A1`); add an image-layer hook the adapter contributes to.
- `primer/eval/network.py` — allowlist `adapter.egress_hosts()` (fallback to `config.primer_agent_api_host`) (`A2`); support a host **list**.
- `primer/eval/runner.py` — pass the adapter's egress hosts into `EgressNetwork`.
- `docker/eval.Dockerfile` — reference template aligned with the new provisioning step.
- `tests/test_runner_isolation.py` — provisioning + multi-host egress + the M4 fingerprint validity probe (`A4`).

**4. Dependency graph.** `G0 ⟹ A1, A2` (frozen `eval/`). `A1 + A2 ⟹ A3` (real run). `C2 ⟹ A3` (subject not mutated). `A3 ⟹ A4` (tests assert the run that now exists). The **Provider track (P1/P2/PR1) runs fully in parallel** here — disjoint files (`llm/` vs `eval/`), except a minor `config.py` touch sequenced against P0's dedup.

**5. Architectural changes.** Introduces the **AgentRuntime/provisioning concept** (the audit's missing abstraction) and **wires the previously-dead `api_host()`** into a multi-host egress allowlist. Both are additive to the existing adapter contract.

**6. Risks. (Highest-risk phase by discovery.)**
- First real Docker+paid-agent run will surface latent issues (proxy honoring `HTTPS_PROXY`, CLI exit/JSON shape, fingerprint read-validity). *Mitigation:* the M4 fingerprint probe (plant a unique instruction; confirm the WITH arm read it) is the standing harness-validity gate — abort, don't report, on failure.
- Provisioning bloats image build time / attack surface. *Mitigation:* reuse AD-2 (build once per repo+commit); keep `cap_drop=ALL` on the eval container; provision only the vetted agent runtime.
- Real evals **cost money** — CI/budget constraint. *Mitigation:* one golden fixture repo, minimal task count, gated to manual/nightly.

**7. Test strategy.** Extend `test_runner_isolation.py` (the acceptance gate): both arms identical except the file; `passed` from a real exit code; `egress_hosts` reachable and **all others refused**; container gone post-run; M4 A/B/C fingerprint probes. Add a provisioning unit test (CLI present in built image).

**8. Validation gates.**
- A real container run produces a non-fabricated signed delta; `scores.json` shows a measured value (not "not evaluated").
- Egress audit: allowlisted host reachable, any other host refused, `egress_enforced=True` only when the proxy was active.
- M4 fingerprint gate passes (WITH arm provably reads the file).

**9. Rollback strategy.** Feature-flag provisioning (config toggle → old "assume CLI present" path); `network.py` falls back to static `config.primer_agent_api_host` when `egress_hosts()` is empty, so reverting an adapter is safe. Phase-1 changes are opt-in until the gate passes.

**10. Estimated complexity.** **M–L.** The code is moderate; the *discovery risk* of the first real run dominates.

**11. Exit criteria.** `claude_code`+`anthropic` evaluates a fixture repo end-to-end with enforced egress and a validity-gated WITH arm; isolation acceptance test green; provisioning behind a revertible flag. **No schema change required.**

---

## 6. Phase 2 — Generalize the Cheap Axes (Provider, Context, Second Agent)

**1. Objective.** Convert the two low-risk hardcoded axes (provider dispatch, context filename) into registries, and prove "add an adapter, change nothing else" by landing a **real** second agent (`gemini_cli`).

**2. Backend subsystems affected.** `llm/` (provider registry), `config.py` (registry-driven validation), `generate/` (context strategy owns the prompt), `eval/agent_adapter.py` + `adapters/` (context strategy + second adapter), optionally `store/` (first migration).

**3. Files likely affected.**
- `primer/llm/factory.py` — `ProviderRegistry`; `primer/llm/` — new `openai_compatible.py` base; the 5 providers re-registered (`P1`).
- `primer/config.py` — collapse the two provider→key maps into one registry-driven check (`P2`).
- `primer/generate/context_writer.py` + `prompts.py` — `ContextStrategy` owns filename(s)/layout/prompt (`CS1`).
- `primer/eval/agent_adapter.py` — adapter references a `ContextStrategy`; `context_filename()` becomes a shim.
- `primer/eval/adapters/gemini.py` — strategy returns `GEMINI.md` (honor M7) (`CS2`); provision + egress-wire the Gemini CLI (`AG1`).
- `primer/eval/runner.py`/`scorer.py` — write/omit via the strategy (builds on the C2 content-passing seam).
- `tests/` — `test_providers_phase5.py` (registry), `test_gemini_adapter.py` (**update the `CLAUDE.md` assertion to `GEMINI.md`**), new context-strategy + registry tests.
- Optional `store/schema.sql` + `migrations.py` — `SM1` (record `context_strategy`, `agent_runtime`); **defer if it adds risk**.

**4. Dependency graph.** `G0 ⟹` everything. **P1 → P2** (config consumes the registry); **PR1** optional, parallel. **CS1 → CS2**; **CS1** depends on `C2` (shared runner seam). **AG1** depends on `A1+A2` (Phase 1 runtime) **and** `CS1/CS2` (correct filename). The Provider track (P1/P2/PR1) and the Context+Agent track (CS1/CS2/AG1) are **mutually parallel** (disjoint subsystems) and converge only at the config layer.

**5. Architectural changes.** ProviderRegistry + OpenAICompatible base (unlocks the long-tail providers by config); ContextStrategy registry (decouples context from the agent, fixes M7); second agent runtime. Public seams (`get_provider`, `context_filename` shim) stay stable for backward compatibility.

**6. Risks.**
- `agent_adapter.py` (ABC) is touched here **and** in Phase 1 — collision hotspot. *Mitigation:* Phase 1 ABC changes land and stabilize first (sequential phases); Phase 2 adds the context-strategy method on top.
- The `CLAUDE.md→GEMINI.md` change is **behavior-changing and test-enshrined**. *Mitigation:* update the asserting test in the same change; document as the M7 correction.
- `SM1` is the first-ever migration — backward-compat risk. *Mitigation:* additive `ADD COLUMN` only; or defer `SM1` to Phase 3 and keep Phase 2 schema-stable (recommended to minimize risk).

**7. Test strategy.** Provider-registry contract test (every registered provider satisfies the ABC; unknown → clean `ConfigError`). OpenAICompatible base tested against one concrete (e.g. a stub Grok/DeepSeek). Context-strategy tests (filename(s), layout, write/omit). Gemini adapter: corrected filename + provisioning + egress. A "Gemini-only user" integration scenario (generation + pytest-repo eval) as the headline acceptance.

**8. Validation gates.**
- Adding a provider = register + (config) with **zero edits** to runner/scorer/store/report.
- A Gemini-only configuration generates **and** evaluates a pytest repo, writing `GEMINI.md`, with egress on the Gemini host.
- `get_provider(config)` signature unchanged (call-site compatibility proven).

**9. Rollback strategy.** Registries are additive — unregister to revert. Keep the legacy `if/elif` reachable behind the registry during transition. `context_filename()` shim preserves old adapters. Default agent stays `claude_code`; Gemini is opt-in. Defer/skip `SM1` to keep schema rollback-free.

**10. Estimated complexity.** **L** (three tracks, two parallelizable; one behavior-changing fix).

**11. Exit criteria.** Provider registry live with the 5 providers + an OpenAICompatible path; ContextStrategy live; Gemini agent runs for real with the correct filename and host; "add a provider/agent = registration" demonstrated. Schema unchanged (or one additive, reversible migration).

---

## 7. Phase 3 — LanguageToolchain (the Hard Axis)

**1. Objective.** Break the pytest monoculture: extract per-language task derivation/preflight/image/verify/coverage behind a `LanguageToolchain` registry, then prove generality with a second toolchain and honest refusals for unsupported combinations.

**2. Backend subsystems affected.** `eval/tasks.py`, `eval/preflight.py`, `eval/images.py` (the deepest changes), `eval/scorer.py` (toolchain selection), `ingest/` (language detection feeds selection), `config.py` (language override), `store/` (language columns), CLI flag.

**3. Files likely affected.**
- New `primer/eval/toolchains/` package: `base.py` (ABC), `pytest_toolchain.py` (extracted), a second (`jest_toolchain.py` or `go_toolchain.py`), `__init__.py` (registry).
- `primer/eval/tasks.py` + `preflight.py` — delegate derivation/verify to the selected toolchain (`LT1`).
- `primer/eval/images.py` — toolchain contributes image layers (`LT2`).
- `primer/eval/scorer.py` / `cli.py` — select toolchain; new optional `--language` flag.
- `primer/store/schema.sql` + `migrations.py` — `SM2` (`language`/`toolchain` columns; schema_version bump).
- New `tests/fixtures/<lang>_repo/` golden repos (`LT4`); `tests/test_tasks.py`, new toolchain tests, extended `test_runner_isolation.py`.
- `CapabilityMatrix` (initial) — `LT3`.

**4. Dependency graph.** `A3 ⟹ LT1` (verify path proven before parameterization). Registry pattern from P1/CS1 is the reference. **LT1 → LT2 → LT3**; `SM2` rides with `LT1`/`LT2`. `LT3` needs the agent axis (AG1) and provider axis (P1) present to gate combinations. This is the **most serial** phase internally (the second toolchain can parallelize once the ABC is extracted).

**5. Architectural changes.** Introduces the `LanguageToolchain` abstraction — the audit's single most important new seam — and the initial `CapabilityMatrix`. pytest becomes one plugin among several; the eval engine stops assuming Python.

**6. Risks. (Deepest change; per-language correctness.)**
- `tasks.py`/`preflight.py`/`images.py` are refactor hotspots already touched in P0/P1; extracting them risks regressing the proven pytest path. *Mitigation:* extract pytest **first as a behavior-preserving refactor** (same outputs, characterization tests), *then* add the second toolchain.
- Each language needs real coverage/test-mapping (the unresolved M2) — error-prone. *Mitigation:* per-language golden repos as executable specs; start with the easiest second ecosystem.
- Combinatorial validation (language × agent × provider × context) explodes. *Mitigation:* `LT3` refuses unsupported combos **honestly** rather than degrading silently.

**7. Test strategy.** Characterization test pinning current pytest derivation output **before** extraction; per-language golden repos producing validated tasks and a real delta; capability-matrix refusal tests (e.g. "Go repo + Claude agent not yet supported" → clear refusal, not zero tasks). Extend the isolation test for a non-Python toolchain.

**8. Validation gates.**
- pytest extraction is **byte-for-byte behavior-preserving** (characterization tests pass unchanged).
- A non-Python golden repo yields validated tasks and a trustworthy delta.
- Unsupported (repo, language, agent) combinations refuse with an explicit reason.

**9. Rollback strategy.** **pytest remains the default toolchain**; new toolchains gate behind capability detection; language auto-detect can be disabled to force pytest. `SM2` is additive (old readers ignore new columns). Each toolchain is independently unregisterable.

**10. Estimated complexity.** **XL** (deepest logic change, per-language correctness, new fixtures, the first multi-column migration).

**11. Exit criteria.** PytestToolchain extracted without regression; ≥1 additional language toolchain produces a real delta; CapabilityMatrix refuses unsupported combinations; `language`/`toolchain` persisted via an additive migration.

---

## 8. Phase 4 — Hardening & Honesty at Scale

**1. Objective.** Make the full axis matrix honest, observable, and maintainable: report/export registry, cross-axis mismatch refusal, complete provenance, legacy retirement, and per-plugin contract tests.

**2. Backend subsystems affected.** `report/` (output registry), `eval/scorer.py` (cross-axis refusal), `store/` (final provenance columns), `llm/`+`generate/`+`eval/adapters/` (legacy path removal), docs/tests.

**3. Files likely affected.**
- `primer/report/export.py` + `render.py` — output-format registry (additive) (`H1`).
- `primer/eval/scorer.py` — extend refuse-on-mismatch to **isolation + language + runtime** (`H2`).
- `primer/store/schema.sql` + `migrations.py` — `SM3` (full provenance superset) (`H3`).
- `primer/llm/factory.py`, `eval/agent_adapter.py` — remove legacy `if/elif` remnants and the `context_filename()` shim (`H4`).
- `tests/` — per-plugin contract-test suite; `dashboard/lib/types.ts` if export schema extends (additive, `schema_version` bump) (`H5`).

**4. Dependency graph.** `{P1, CS1, AG1, LT3} ⟹ H2/H4` (all new paths must be live before extending refusal and removing legacy). `H1`, `H5` can start once their inputs stabilize. `H3`/`SM3` last.

**5. Architectural changes.** Report/export becomes a registry; the honesty surface extends across every axis; provenance records the complete (provider, agent, runtime, language, context, isolation) tuple; deprecated dispatch is deleted.

**6. Risks.**
- Removing the `context_filename()` shim / legacy factory branches could break un-migrated callers. *Mitigation:* `H4` is last and gated on a code search proving no remaining callers; reversible until the deletion commit.
- Export schema extension touches the dashboard contract. *Mitigation:* additive fields + `schema_version` bump; the frozen contract shapes are extended, never broken.

**7. Test strategy.** Contract test per registry (provider/agent/context/toolchain/report) asserting ABC conformance. Cross-axis refusal tests (e.g. differing `base_image`/`language`/`runtime` → delta refused with reason). Export schema-version regression. Full matrix smoke over supported combinations.

**8. Validation gates.**
- Adding any plugin = registration only; runner/scorer/store untouched.
- Every mismatch axis (provider/model/isolation/language/runtime) refuses honestly.
- Zero remaining legacy dispatch paths; all reachable plugins have contract tests.

**9. Rollback strategy.** Per-registry and per-item revert. `CapabilityMatrix` can be set permissive to unblock. `H4` (deletion) is the only irreversible step and is sequenced last, behind a no-caller proof.

**10. Estimated complexity.** **M–L** (mostly additive + one careful deletion + one migration).

**11. Exit criteria.** Output registry live; refusal honest across all axes; full provenance persisted; legacy paths removed; per-plugin contract tests green; export schema extended additively.

---

## 9. Cross-Phase Risks

**Files touched across multiple phases (refactor-collision hotspots):**

| File | Phases | Why hot | Collision control |
|---|---|---|---|
| `eval/runner.py` | 0, 1, 3 | content-passing → egress wiring → toolchain verify | Sequential phases; each layer lands on the prior, never concurrently |
| `eval/scorer.py` | 0, 3, 4 | source-mutation fix → toolchain → cross-axis refusal | Keep refuse-on-mismatch logic isolated from toolchain selection |
| `eval/images.py` | 1, 3 | agent provisioning → language image layers | Two independent hooks (agent layer vs toolchain layer); keep separate |
| `eval/agent_adapter.py` (ABC) | 1, 2 | runtime/egress methods → context-strategy method | Phase-1 ABC stabilizes before Phase-2 additions |
| `config.py` | 0, 2, 3 | dedup → registry-driven → language override | Each phase owns a distinct concern in the file |
| `cli.py` | 0, 2, 3, 4 | persist runs → strategy/agent flags → language flag → export registry | Composition root; changes expected and low-risk |
| `store/schema.sql` + `migrations.py` | (2), 3, 4 | additive migrations | One migration per phase max; never two open at once |

**Highest-risk subsystems (ranked):**
1. `eval/runner.py` + `images.py` + `network.py` — Docker/network/isolation; Docker-dependent tests; the moat is unverified until Phase 1. **Highest.**
2. `eval/tasks.py` + `preflight.py` — Phase 3 language extraction; deepest logic.
3. `store/schema.sql` + `migrations.py` — data migration backward-compat.

**Testing bottlenecks:**
- `test_runner_isolation.py` is the recurring acceptance gate (Phases 0/1/3), is Docker-dependent and slow, and must re-pass + extend each time. CI needs a Docker host.
- KL-1 async ordering contamination must be fixed in Phase 0 (`C5`) or every later gate runs against an untrustworthy suite.
- Phase 3 golden repos are a new, growing fixture-maintenance burden.
- Real-agent runs cost money → gate to nightly/manual, not per-commit.

**Schema-migration timing (safest):** Phases 0–1 **schema-stable** (persistence fix is a call-site bug). First additive migration **at Phase 2 only if** recording context-strategy/runtime is needed, otherwise **defer to Phase 3** (`SM2`, language/toolchain). Final provenance superset at Phase 4 (`SM3`). **Never more than one in-flight migration; additive `ADD COLUMN` only; bump `CURRENT_SCHEMA_VERSION` each time.**

**Registry-introduction timing:** Agent registry **already exists** (extend, don't introduce, in Phases 1–2). Provider registry → Phase 2. Context strategy registry → Phase 2. LanguageToolchain registry → Phase 3. Report/export registry → Phase 4.

---

## 10. Critical Path

```
G0 ─▶ C2 ─▶ (A1 ∥ A2) ─▶ A3 ─▶ CS1 ─▶ CS2 ─▶ AG1 ─▶ LT1 ─▶ LT2 ─▶ LT3 ─▶ H2 ─▶ H4
└Phase0┘   └──── Phase 1 ────┘   └──── Phase 2 ────┘   └──── Phase 3 ────┘  └─Phase 4─┘
```

The critical path runs **entirely through `eval/` + the context seam**. Key observations:
- **The Provider track (P1 → P2, PR1) is *not* on the critical path.** It is disjoint (`llm/`) and can run in parallel with Phases 1–2, compressing calendar time. It only needs `G0`.
- **`A3` (the first real run) is the single most important milestone** — it converts the moat from "specified" to "verified" and unblocks the entire language axis.
- **`LT1` (pytest extraction) is the riskiest critical-path node** — it must be behavior-preserving or it regresses the just-proven moat.

**Sequencing validation (checked):** no later-phase item is a hidden prerequisite of an earlier one; every parallelizable pair (`{C1,C2,C3,C4,C5}`; `{Provider track} ∥ {Phase 1}`; `{P-track} ∥ {Context+Agent track}`; `{LT2 second impl}` after the ABC) is verified file-disjoint except at `config.py`/`agent_adapter.py`, where sequential phasing resolves the overlap. The ordering holds.

---

## 11. Recommended Implementation Order

1. **`G0`** (governance) and **`C5`** (test-infra) — *first, immediately, in parallel.* Nothing trustworthy proceeds without them.
2. **`C1`, `C2`, `C3`, `C4`** — Phase 0 correctness, parallel; `C2` gated behind its tests.
3. **`A1`, `A2`** (parallel) → **`A3`** → **`A4`** — prove the moat. *Start the Provider track (`P1`→`P2`, `PR1`) in parallel here.*
4. **`CS1`** → **`CS2`**, then **`AG1`** — context strategy and the second agent (converging Phase-1 runtime + Phase-2 context).
5. **`LT1`** (behavior-preserving extraction) → **`LT2`** → **`LT3`**, with **`SM2`** and **`LT4`**.
6. **`H1`, `H5`** (start early when inputs stabilize) → **`H2`**, **`H3`/`SM3`** → **`H4`** (legacy deletion, last).

**Deferred deliberately:** heavyweight/dynamic third-party plugin loading; server/multi-tenant storage (SQLite stays); provider streaming/tool-use; enabling each specific long-tail provider (mechanism in P2, activation on demand); non-file context formats (Cursor/Cline rules-dirs) beyond the abstraction; `PR1` pricing externalization may slip from P2 to P4 if P2 is large.

---

## 12. Estimated Total Effort

Planning estimates — **one experienced engineer fluent in the codebase, Docker + CI + agent-API budget available.** T-shirt + rough engineer-week band (not a commitment):

| Phase | Complexity | Rough effort | Swing factor |
|---|---|---|---|
| 0 — Governance + Correctness | M | 1–2 wk | `C2` regression coverage |
| 1 — Prove the moat | M–L | 2–3 wk | first-real-run discovery, proxy/CLI behavior |
| 2 — Cheap axes | L | 3–4 wk | parallelizable (Provider ∥ Context+Agent) |
| 3 — LanguageToolchain | XL | 4–6 wk | per-language correctness, golden repos |
| 4 — Hardening | M–L | 2–3 wk | matrix breadth, legacy deletion safety |
| **Total** | — | **~12–18 wk** | **−2–3 wk** if Provider track runs parallel |

Calendar time compresses below the serial sum because the Provider track (~off critical path) overlaps Phases 1–2. Phase 3 is the dominant cost and the most estimate-uncertain.

---

## 13. Definition of Completion

The migration is **complete** when **all** hold:

1. Adding a **provider**, **agent**, **context strategy**, **language toolchain**, or **report format** is a **registration** (new file + entry point) with **zero edits** to runner, scorer, store, or report.
2. A user with **only** Gemini / only OpenAI / only Ollama can **generate and evaluate** (on a supported language) and get a trustworthy delta — the audit's headline requirement.
3. The moat is **verified**: real evals run end-to-end for ≥2 agents and ≥2 languages, with enforced per-agent egress and validity-gated WITH arms.
4. **Honesty holds across every axis**: provider/model/isolation/language/runtime mismatches refuse with a reason; the two-stream rule and variance reporting are intact; the `CapabilityMatrix` refuses unsupported combinations rather than degrading.
5. **Persistence is faithful**: reports round-trip with full per-task data; the caller's repo is never mutated; schema is at its final additive version.
6. **No legacy dispatch remains**; every reachable plugin has a contract test; the suite is green batched (KL-1 gone).
7. The frozen **invariants** (isolation mechanics, scorer honesty math, contract shapes, AD-4) are provably unchanged from baseline.

---

## 14. Final Recommended Migration Strategy

**Stabilize, prove, then generalize — additively, with the measurement invariants frozen the entire way.**

- **Lead with governance and correctness (Phase 0).** Superseding the V3 freeze and fixing the persistence + repo-mutation defects is non-negotiably first: it authorizes the work and makes every later validation gate trustworthy. Ship it schema-stable to keep risk minimal.
- **Prove the moat once before generalizing it (Phase 1).** The single highest-value milestone is the first real end-to-end run (`A3`). Treat it as a hard gate; nothing in Phases 2–3 should be built on an unverified harness. Run the **Provider track in parallel** to use the time productively without touching the critical path.
- **Generalize cheap axes before the hard one (Phase 2 → 3).** Provider, context, and the second agent prove the registry pattern at low risk; the LanguageToolchain — the deepest change and the actual generality ceiling — comes only after the pattern and the moat are both proven, and begins with a **behavior-preserving pytest extraction** to protect the verified path.
- **Defer the irreversible and the combinatorial to the end (Phase 4).** Cross-axis refusal, full provenance, and legacy deletion need every new path live; sequence the one irreversible step (legacy removal) last, behind a no-caller proof.
- **Keep every seam backward-compatible during transition:** stable `get_provider` signature, a `context_filename()` shim, pytest as default, additive-only migrations, opt-in new agents/languages. This lets each phase ship to production independently and roll back per-item without ever disturbing the frozen core.

The result is a provider-, agent-, context-, and language-agnostic platform reached by **incremental migration, not rewrite** — extending the existing ABCs and registry rather than replacing the engine, with production stability preserved at every phase boundary.

---

