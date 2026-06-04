# PRIMER — CONSOLIDATED IMPLEMENTATION SPECIFICATION
## (Implementation Contract v1 — for Sonnet 4.6)

> **Status: AUTHORITATIVE OVERLAY.** This document is the single implementation contract.
> **Precedence:** Session 1 Final Revision (source of truth) > Session 2 Architecture Blueprint
> > retired Opus 4.8 Master Prompt. The Master Prompt is **superseded** wherever it conflicts;
> its conflicting items are listed in §12. This document integrates the approved Decision Addendum
> (M1, M3, M4, M5, M7, M8), removes superseded guidance, and resolves all known contradictions
> (§13). It does not redesign architecture; every change is a refinement inside the existing specs.
>
> **Build discipline:** phase‑by‑phase only. Phase N must pass its acceptance gate before Phase N+1.
> Do not implement a future phase unless explicitly requested. PART I is the cross‑phase contract;
> **PART II is the build‑now contract for Phase 0.**
>
> **Revision v1.1 (pre‑build audit applied to PART II only):** the two §14 micro‑decisions are **ratified**;
> all eight Phase‑0 audit blockers are folded into P0.2 / P0.4 / P0.5. PART I (cross‑phase) and every Phase‑3
> item are unchanged and remain gating for their phases.

---

# PART I — CONSOLIDATED CONTRACT (all phases)

## 1. Mission, wedge, moat (honesty‑corrected)

PRIMER is a **measurement harness**, not a generator. Evidence (arXiv:2602.11988, ETH Zurich SRI Lab
+ LogicStar.ai, submitted **12 Feb 2026**): LLM‑auto‑generated context files **reduce** agent task
success in 5 of 8 settings (avg −0.5% SWE‑bench Lite, −2% AGENTbench; headline −3% auto vs +4%
developer‑written) while **raising inference cost >20%**; ablation shows auto files mostly **redundant**
with docs the agent already reads. **No absolute baseline is ever quoted** (unpublished, Fig. 3 only);
PRIMER reports only its **own measured deltas**.

- **One problem:** AI coding agents don't understand a specific repo, and current context files often
  make them *worse*.
- **One demo:** run a real, verifiable task through the *same* agent **with and without** the file, in
  isolated Docker containers, **sequentially**; report a trustworthy signed before/after success +
  token‑cost delta **with variance** — which may be positive, ~0, or negative.
- **One moat:** the sandboxed before/after **evaluation harness**. Generation is commoditized;
  measurement is not.

**Honest expectation (Q3):** a good *curated* file realistically yields **0 to +5 points**;
auto‑generated can be **negative**. Design to *measure*, never to "prove it helps." A `None` delta or a
within‑noise delta is a valid, shippable result.

**Positioning (M8):** "$0 / no API keys" applies **only to file generation via local Ollama**. The MVP's
**evaluation requires the Claude Code agent + an Anthropic key and costs money.** Do not claim "$0
end‑to‑end" for the MVP. The deleted "41% → 68%" headline must never reappear.

## 2. Locked decisions (Q1–Q10)

| # | Ruling (consolidated) |
|---|---|
| **Q1** | **Sequential** eval for MVP. Paired before/after of the *same* task is **never** parallelised. Post‑MVP parallelism, if ever: across *different* tasks only, capped `min(cpu_count, 3)`. |
| **Q2** | Flaky policy: if `verify_cmd` fails on first run, **retry once after 5 s**. Fail‑twice → `passed=False, flaky=False`. Fail‑then‑pass → `passed=True, flaky=True` + warning. Flaky runs are **scored but annotated**. (Supersedes the Master Prompt's "no retries"; variance is surfaced via the flaky annotation, not hidden.) |
| **Q3** | Honest expectation: 0…+5 for a good curated file; auto‑generated can be negative. Measure, don't prove. |
| **Q5** | Badge infra (Nice‑to‑Have): zero paid infra; CI writes `scores.json` to `gh-pages`; shields.io endpoint badge `{schemaVersion,label,message,color}`; green Δ>0 / yellow ~0 / red Δ<0. |
| **Q7** | Single config source = `pyproject.toml` + `.env.example`. All `PRIMER_*`/`*_API_KEY` via pydantic‑settings. Never hardcode. |
| **Q8** | Tools per phase (see §6/§11). |
| **Q9** | (a) No prompt‑cache layer (file < 1,024‑token Sonnet minimum → caching is a no‑op). (b) Per‑provider `cost_confidence`: anthropic/gemini **exact**, openai **estimated→exact**, openrouter **estimated**, ollama **free**. (c) Ollama output validation: empty/non‑UTF‑8/<20 chars → retry once → `OllamaOutputError`. (d) **Refuse the delta on provider/model mismatch** across compared runs → per‑config reported, delta `None` + warning. |
| **Q10** | Three guarded key‑leak paths: (a) logs → `log_safe()` redaction; (b) container env → **one** key via `--env`; (c) committing `.env`/hardcoded keys → gitleaks + detect‑secrets, Phase 0 step 1. |

## 3. Architecture decisions (AD‑1…AD‑5)

- **AD‑1** Ingest is **heuristic‑only (no LLM)**. `RepoProfile` is pure structural data; `conventions`/`gotchas` are *generator* output, not profile fields.
- **AD‑2** Eval image built **once per (repo, commit)**; **fresh container per run**. Deps pre‑baked → `pip install` costs **no eval‑timeout budget**. Source is **not** baked; a fresh copy is mounted per run.
- **AD‑3** **Thin adapters / fat runner.** All Docker, network, timeout, cleanup live **only** in `runner.py`.
- **AD‑4** **The agent never decides pass/fail.** The adapter runs the agent; `runner` runs `verify_cmd`; **exit code is the sole verdict.**
- **AD‑5** **Refuse‑on‑mismatch (Q9d) is enforced in `scorer`, not `runner`.** A single run is valid in isolation; only the comparison is invalid under provider/model mismatch.

## 4. Decision Addendum (integrated)

- **M1 — Eval timeout = 600 s** (per‑run). `docker_client_timeout_s = eval_timeout_s + 30 = 630`. Supersedes Session 2's `300`. Configurable.
- **M3 — Statistical‑power policy.** MVP reports a **directional** signed success + cost delta, always with variance and an explicit honesty label — **not** a precision instrument for sub‑resolution effects.
  - **Per‑task flips are the primary signal** (`per_task` table); the aggregate is a coarse summary.
  - **Quantization stated:** at temperature 0, within‑task runs are highly correlated, so practical aggregate resolution ≈ **1/n_tasks** (≈20 pts at 5 tasks; ≈33 pts at the 3‑task floor), **not** 1/(n_tasks·runs). The report prints the grid and never implies finer precision.
  - **`runs_per_config` = 3 is for flakiness detection**, not aggregate power.
  - **Within‑noise label:** flag the headline when `|success_delta| ≤ max(1/n_tasks, success_stddev)` as "within measurement noise — not distinguishable from zero"; escalate to "driven by flaky task(s)" if contributing flips are flaky. This is a **render‑time display classification** (same class as sign→color); it adds no aggregation to `report/`. *Persisting the verdict (one extra `*_warning` field) is a flagged sign‑off option, not assumed.*
  - **No brute‑force power:** `min_tasks=3` is the eligibility floor only; resolving ≤5‑pt effects would need hundreds of paid runs/arm.
- **M4 — `--bare` policy.** The with/without distinction is controlled **only** by the presence of `context_filename()` in the mounted `/work`; **flags are identical across arms** (Spec B‑8, AD‑4). **Default: no `--bare`.** Any `--bare` use is gated by a Phase‑3 fingerprint smoke test (§9 / Phase 3 gate). The WITHOUT arm's cleanliness comes from the runner (fresh clone → assert no context file), not a flag.
- **M5 — Digest pinning.** Config carries a readable tag; the runner **resolves it to a `sha256` digest at build time and stores the digest** in `RunResult.base_image` / `reports.base_image`. The eval image is built `FROM` the resolved digest so all runs in a report share one immutable base. (Capturing platform/arch is a follow‑up.)
- **M7 — `init` filename.** `primer init` writes the filename from the **configured agent adapter's `context_filename()`** (`CLAUDE.md` for the default `ClaudeCodeAdapter`; `AGENTS.md` for AGENTS.md‑standard adapters; GEMINI.md for a future Gemini adapter — confirm at build). Generation stays filename‑agnostic; the name is chosen at the `init` write site. Supersedes Session 2 §6 (`AGENTS.md`).
- **M8 — Ollama vs isolation.** Layer‑1 Ollama (generation brain) runs **host‑side**, outside the eval container, fully compatible with isolation — the real `$0` *generation* path. **Layer‑2 local agent (agent under test) is NOT in MVP** (only `ClaudeCodeAdapter` ships). Post‑MVP local‑agent isolation = a **model sidecar on `primer-internal`** (no external egress → `network_mode="offline"`); build nothing now.

**Generator determinism (confirmed requirement):** `write_context` runs at **temperature 0** with the configured **pinned model**; the stored `agents_md` is the **reproducibility anchor** (never regenerated for comparison).

## 5. Non‑negotiable security rules

1. **Pre‑commit hook is Phase 0, step 1.** gitleaks + detect‑secrets installed **before any other file is committed.** `.env` in `.gitignore`; `.env.example` ships empty placeholders only; **`.secrets.baseline` is committed (not git‑ignored).**
2. **No vendor SDK imports outside `primer/llm/`.** Any `import anthropic|openai|google.generativeai|<vendor SDK>` elsewhere is an architecture violation, enforced by `tests/test_arch_boundaries.py`. All LLM calls go through `get_provider()`.
3. **Eval containers receive keys via `--env` only** — never in Dockerfiles/build args/layers. Inject **only the one key** the in‑container agent needs (`ANTHROPIC_API_KEY` for Claude Code), never PRIMER's other keys. Combine with proxy egress (Spec B) + `cap_drop=["ALL"]` + `no-new-privileges`.
4. **`log_safe()` lives on the `LLMProvider` base class.** Redact `sk-…`, `sk-ant-…`, `AIza…` → `[REDACTED]` before any log write; never log full `os.environ`; redact `raw_output`/logs before persisting to SQLite.

**Scope guardrails — REMOVE (out of scope):** rule‑based fallback generator, parallel eval, prompt‑cache layer, NIST/"compliance" features.

## 6. Scope classification

| Phase / item | Classification |
|---|---|
| **Phase 0** — scaffold, config, security, deps | **MVP Required** (first) |
| **Phase 1** — repo map (tree‑sitter, heuristics, no LLM) | **MVP Required** |
| **Phase 2** — lean context‑file generation | **MVP Required** |
| **Phase 3** — Dockerized before/after eval + token accounting | **MVP Required — the moat** |
| **Phase 4** — reporting (rich, text) **+ CLI end‑to‑end** (`init`/`eval`/`report`) | **MVP Required (minimal)** |
| Full multi‑provider Layer‑1/Layer‑2 matrix | **Post‑MVP** (interfaces day 1, extra impls later) |
| SQLite `history`/`compare` UX | **Post‑MVP** |
| Optimization / ablation loop | **Post‑MVP** |
| Next.js scorecard + GitHub Pages + badge | **Nice‑to‑Have** |
| GitHub Actions CI gate + drift detection | **Nice‑to‑Have** |

CLI commands are **only** `init`, `eval`, `report` (no standalone `map`; the map surfaces via the report). `history`/`compare` are Post‑MVP.

## 7. Folder structure (corrected)

```
primer/
├── pyproject.toml                # [project], deps, dev-deps, pytest cfg; entrypoint primer = "primer.cli:app"
├── README.md
├── LICENSE                       # MIT, 2026, kanwa2006
├── .env.example                  # all PRIMER_*/*_API_KEY placeholders (EMPTY)
├── .gitignore                    # .env, *.db, __pycache__, *.pyc, node_modules, .next, dist, build, *.egg-info, .pytest_cache
│                                 #   (DO NOT list .secrets.baseline — it must be committed)
├── .pre-commit-config.yaml       # gitleaks + detect-secrets   (Phase 0, step 1)
├── .secrets.baseline             # detect-secrets baseline (COMMITTED)
├── docker/                       # Phase 3
│   ├── eval.Dockerfile
│   └── proxy/{Dockerfile, tinyproxy.conf.tmpl}
├── primer/
│   ├── __init__.py               # __version__ = "0.1.0"
│   ├── config.py                 # Settings (pydantic-settings)
│   ├── errors.py                 # all custom exceptions (leaf)
│   ├── ingest/                   # Phase 1 (NO LLM): models, commands, analyzer
│   ├── generate/                 # Phase 2 (ONE Layer-1 call): prompts, context_writer
│   ├── llm/                      # ONLY vendor-SDK home: base, factory, anthropic, ollama, [POST-MVP] openai/gemini/openrouter
│   ├── eval/                     # Phase 3 (the moat): models, tasks, preflight, images, network, runner, scorer, agent_adapter, adapters/
│   ├── store/                    # Phase 3/4 (ONLY sqlite consumer): schema.sql, db.py
│   ├── report/                   # Phase 4 (pure rendering): render.py
│   └── cli.py                    # Typer composition root: init / eval / report
├── tests/                        # conftest + per-module tests (see §11 / PART II)
└── dashboard/                    # [Nice-to-Have] Phase 7 — not MVP
```

## 8. Module DAG & boundary invariants

```
config.py , errors.py            (leaves; errors used everywhere)
        │
   ┌────┴────┐
 llm/*    ingest/*                (ingest makes NO LLM calls — AD-1)
   └────┬────┘
   generate/*                     (the ONE Layer-1 LLM call)
        │
   eval/*  (models→tasks→preflight→images→network→adapters→runner→scorer)
        │
   store/*                        (only module importing sqlite3/aiosqlite)
        │
   report/*                       (pure rendering; no computation)
        │
   cli.py                         (the ONLY composition root; nothing imports cli)
```

**Testable invariants:** (1) vendor SDK imports only under `primer/llm/`; (2) only `primer/eval/` imports `docker`; (3) only `primer/store/` imports sqlite; (4) `report/` does no aggregation/I‑O beyond the terminal; (5) `cli.py` is the sole orchestrator; (6) the **two token streams never mix** — generation = PRIMER overhead, in‑container agent = eval cost, separate fields, never summed; (7) `ingest/` makes no LLM/network call.

## 9. Locked engineering specs A–D (amended)

**SPEC A — `RunResult`** (Spec A authoritative; `base_image` now stores a **digest**, M5):
identity/outcome (`task_id, passed, timeout, flaky, with_context`); eval‑agent cost stream
(`agent_adapter, agent_tokens, iterations, duration_s, cost_usd, cost_confidence`); PRIMER‑brain
provenance (`provider, model`); isolation/audit (`base_image` = resolved `…@sha256:…`, `repo_commit`,
`network_mode` ∈ {proxy-egress, open-bridge, offline}, `egress_allowed_host`, `egress_enforced`,
`caps_dropped`, `container_id`, `agent_log_path` (REDACTED), `run_timestamp` ISO‑8601 UTC). **Honesty
gate:** a report may claim "egress‑restricted" only if **every** run has `egress_enforced=True`.

**SPEC B — `runner.py` isolation (replaces all `network_disabled=True`).** docker‑py has **no** kwarg
that filters egress by hostname → enforced by a **deny‑by‑default egress proxy sidecar**. Mandatory steps:
(1) fresh clone → record `repo_commit`; (2) per‑run `primer-internal` network `internal=True`;
(3) deny‑by‑default proxy on `primer-internal` + bridge, allows CONNECT to `{agent api_host}:443` only;
(4) eval container on `primer-internal` **only**, `HTTPS_PROXY/HTTP_PROXY`→proxy, `NO_PROXY=localhost,127.0.0.1`;
(5) inject **one** key via `--env`; never write keys to any container file; (6) harden:
`cap_drop=["ALL"]`, `security_opt=["no-new-privileges:true"]`, `mem_limit` (default `2g`), `nano_cpus`,
`pids_limit`; (7) mount **only** the temp dir (rw) at `/work`; (8) `with_context=True` → write
`adapter.context_filename()` before start; `False` → guarantee none exists (**flags identical both arms**);
(9) command **ends with** `verify_cmd`: `sh -c '<agent argv> > /work/.primer_agent.log 2>&1 ; <verify_cmd>'`;
(10) timeout+cleanup per Spec D; **read+redact the log before `rmtree`**; (11) `egress_enforced=True` +
`network_mode="proxy-egress"` **only** when 2–4 succeeded, else `open-bridge` (drop the "egress‑restricted"
claim) — never optimistic; (12) post‑run `docker ps -a` shows no container with this run's id.
**Build‑confirm:** the agent CLI must honor `HTTPS_PROXY` (smoke‑test before trusting `egress_enforced`).

**SPEC C — `derive_tasks()` (no LLM, deterministic).** Invariant: every emitted Task fails `verify_cmd`
at start, passes when correct, and `verify_cmd` is the repo's own runner (exit code = sole verdict).
Types in priority order: **Type 1 `revert_reimplement`** (scan last ~200 commits; keep a commit that
touches exactly one non‑test source file with an existing covering test and a small diff ≤~40 lines;
revert only the source → covering test fails); **Type 2 `stub_function`** (replace a covered function
body with `raise NotImplementedError`; works on any repo with a passing suite + coverage). **`add_test`
is EXCLUDED.** Mandatory **pre‑flight** in a throwaway checkout/container: known‑good passes 3×
consistently (discard flaky) **and** broken state fails. **Honest refusal:** validated tasks < `min_tasks`
(3) → `InsufficientTasksError` / repo INELIGIBLE — never pad to a count.

**SPEC D — Docker timeout (exact).** `client = docker.from_env(timeout = eval_timeout_s + 30)` (=630).
`try: container.wait(timeout=eval_timeout_s)` → `ReadTimeout` **raises** (no sentinel) → `container.kill()`
(guard `APIError/NotFound`), `passed, timeout = False, True`. `finally`: read+redact log **before** rmtree;
`container.remove(force=True)`, `proxy.remove(force=True)`, remove `primer-internal`, `rmtree(temp_dir)`.
No `auto_remove` (races `wait()`); command ends with `verify_cmd`.

## 10. Database schema (Phase 3 `store/schema.sql`; canonical, unchanged)

Booleans as `INTEGER` (0/1); timestamps `TEXT` ISO‑8601 UTC; `raw_output`/logs redacted before write.

```sql
CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT, repo_path TEXT NOT NULL, repo_commit TEXT NOT NULL,
  created_at TEXT NOT NULL, profile_json TEXT NOT NULL, agents_md TEXT, agents_md_lines INTEGER,
  gen_provider TEXT, gen_model TEXT, gen_tokens INTEGER, gen_cost_usd REAL, gen_cost_confidence TEXT);

CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT, repo_path TEXT NOT NULL, repo_commit TEXT NOT NULL,
  created_at TEXT NOT NULL, n_tasks INTEGER NOT NULL, runs_per_config INTEGER NOT NULL,
  success_rate_without REAL NOT NULL, success_rate_with REAL NOT NULL, success_delta REAL,         -- NULLABLE: refused
  success_stddev REAL NOT NULL, success_min REAL NOT NULL, success_max REAL NOT NULL,
  cost_without REAL NOT NULL, cost_with REAL NOT NULL, cost_delta_pct REAL, cost_confidence TEXT NOT NULL,
  provider TEXT NOT NULL, model TEXT NOT NULL, agent_adapter TEXT NOT NULL, base_image TEXT NOT NULL,  -- digest
  network_mode TEXT NOT NULL, egress_enforced INTEGER NOT NULL,
  provider_mismatch_warning TEXT, isolation_mismatch_warning TEXT, flaky_task_warning TEXT,
  primer_overhead_usd REAL NOT NULL, primer_overhead_confidence TEXT NOT NULL);            -- never summed into cost_*

CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT, report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
  task_key TEXT NOT NULL, task_type TEXT NOT NULL, prompt TEXT NOT NULL, verify_cmd TEXT NOT NULL,
  source_ref TEXT, validated INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
  task_id TEXT NOT NULL, repo_commit TEXT NOT NULL, with_context INTEGER NOT NULL, passed INTEGER NOT NULL,
  timeout INTEGER NOT NULL, flaky INTEGER NOT NULL, agent_adapter TEXT NOT NULL, agent_tokens INTEGER NOT NULL,
  iterations INTEGER NOT NULL, duration_s REAL NOT NULL, cost_usd REAL NOT NULL, cost_confidence TEXT NOT NULL,
  provider TEXT NOT NULL, model TEXT NOT NULL, base_image TEXT NOT NULL, network_mode TEXT NOT NULL,
  egress_allowed_host TEXT, egress_enforced INTEGER NOT NULL, caps_dropped INTEGER NOT NULL,
  container_id TEXT NOT NULL, agent_log_path TEXT NOT NULL, run_timestamp TEXT NOT NULL);

CREATE INDEX IF NOT EXISTS idx_runs_report  ON runs(report_id);
CREATE INDEX IF NOT EXISTS idx_runs_task    ON runs(task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_report ON tasks(report_id);
CREATE INDEX IF NOT EXISTS idx_reports_repo ON reports(repo_path);
```

## 11. Module API contracts (condensed; addendum‑applied)

> Shapes/signatures only — **no bodies**. Items the addendum/contradictions changed are shown in full;
> unchanged Session 2 §4 shapes are listed compactly. "Done when" = per‑module acceptance.

**`config.py` (Phase 0)** — `Settings(BaseSettings)` field list and defaults (M1, M5 applied):

```
primer_llm_provider="anthropic"; primer_default_model="claude-sonnet-4-6"   # model id: confirm at build
anthropic_api_key / openai_api_key / gemini_api_key / openrouter_api_key : SecretStr | None = None   # RATIFIED §14 — accessed via .get_secret_value() at point of use (Phase 2)
ollama_base_url="http://localhost:11434"; ollama_model="llama3.3"
primer_agent="claude_code"; primer_agent_api_host="api.anthropic.com"
primer_task_count=5; primer_min_tasks=3; primer_eval_runs=3
primer_eval_timeout_s=600                       # M1 (was 300)
primer_commit_scan_depth=200; primer_eval_mem_limit="2g"
docker_base_image="python:3.11-slim"            # readable tag; resolved to digest at build (M5)
proxy_image="primer-egress-proxy:latest"; database_url="sqlite:///primer.db"
@property docker_client_timeout_s -> int        # == primer_eval_timeout_s + 30 (=630)
def validate_runtime() -> None                  # raises ConfigError if the selected provider key OR the
                                                #   selected agent's required key is missing. Phase 0 uses a
                                                #    static {claude_code: ANTHROPIC_API_KEY} map (REQUIRED, not optional);
                                                #   Phase 3 replaces it with adapter.required_env_key(). Never logs/echoes key values.
```
**Done when:** loads every `.env.example` var; `validate_runtime()` raises `ConfigError` on a missing provider key
**and** on a missing agent‑required key (static map in Phase 0); `docker_client_timeout_s == eval_timeout_s + 30`;
no key value ever appears in logs/reprs/errors (SecretStr).

**`errors.py` (Phase 0, leaf):** `PrimerError(Exception)`; subclasses `ConfigError`, `OllamaOutputError`,
`GenerationError`, `AgentNotFoundError`, `InsufficientTasksError`, `TaskValidationError`, `IsolationError`.
**Done when:** all exist, subclass `PrimerError`, carry user‑readable messages.

**`llm/base.py` (Phase 2 — only vendor‑SDK home):**
```
@dataclass TokenUsage:                           # C8: BOTH cache fields per §1.5 (caching dormant in MVP)
  input_tokens:int; output_tokens:int
  cache_creation_input_tokens:int=0; cache_read_input_tokens:int=0
  cost_usd:float=0.0; cost_confidence:Literal["exact","estimated","free"]="estimated"
@dataclass LLMResponse: content:str; usage:TokenUsage; model:str; provider:str
class LLMProvider(ABC):
  async complete(system, messages, model) -> LLMResponse
  estimate_cost(input_tokens, output_tokens) -> float
  @property supports_caching -> bool
  @staticmethod log_safe(text) -> str            # redacts sk-…, sk-ant-…, AIza… → [REDACTED]; used before ANY log write
```
`cost_usd` is **never rendered without consulting `cost_confidence`** (free→"local (no cost)",
estimated→"≈ (estimated)", exact→plain). **`llm/factory.py`:** `get_provider(config) -> LLMProvider`
(unknown ⇒ ValueError; the ONLY provider constructor used outside `primer/llm/`).
**Providers:** `anthropic.py` (default; exact), `ollama.py` ($0; free; empty/non‑UTF‑8/<20 chars → retry once → `OllamaOutputError`). `openai/gemini/openrouter` = **[POST‑MVP]**.

**`ingest/` (Phase 1; AD‑1 no LLM):** `LanguageStat`, `FileNode`, `DependencyEdge`, `CommandSet`,
`RepoProfile` (records `repo_commit`; unknowns None/empty, never fabricated; **no `conventions`/`gotchas`**).
`detect_commands(repo_path) -> CommandSet` (manifest heuristics only). `analyze_repo(path, config) -> RepoProfile`
(tree‑sitter 0.25; `.gitignore`‑respecting; deterministic; **no LLM/network**). **Done when:** deterministic
profile on the py+ts fixtures; real runnable `test_cmd`; asserted no LLM/network call.

**`generate/` (Phase 2; the ONE Layer‑1 call):** `GenerationResult{content, usage(→PRIMER overhead), lines, filename}`.
`write_context(profile, provider) -> GenerationResult` — **one** `provider.complete()` at **temperature 0**;
output a **LEAN ≤~20‑line** file (commands, non‑obvious conventions, internal APIs — NO architecture prose,
NO linter‑enforceable rules, NO directory dump). Validation (generate‑layer): `<50` chars or no code block,
**or `>8 KB`/truncated/non‑structured** → retry once with a simpler prompt → else `GenerationError`.
**`filename` is sourced from the configured `adapter.context_filename()` (M7), not hardcoded.**

**`eval/models.py` (Phase 3):** `TaskMutation{kind:Literal["revert","stub"], target_commit?, target_file?, target_symbol?}`;
`Task{id, task_type:Literal["revert_reimplement","stub_function"], prompt, verify_cmd, mutation, source_ref?, validated=False}`;
`AgentTelemetry{tokens, iterations, duration_s, cost_usd, cost_confidence, agent_error, raw_log}` **(no pass/fail — AD‑4)**;
`RunResult` → **Spec A**; `TaskScore{task_id, task_type, pass_rate_without, pass_rate_with, delta:float|None, runs, flaky_any}`;
`ScoreReport{… success_delta:float|None, success_stddev/min/max, cost_* , cost_confidence, per_task,
provider, model, agent_adapter, base_image, network_mode, egress_enforced, provider_mismatch_warning,
isolation_mismatch_warning, flaky_task_warning, primer_overhead_usd, primer_overhead_confidence}`.

**`eval/tasks.py`, `eval/preflight.py` (Phase 3):** `derive_tasks(profile, repo_path, n=5, min_tasks=3, seed=0) -> list[Task]`
(Spec C; deterministic; `revert_reimplement` first, top up with `stub_function`; `<min_tasks` ⇒ `InsufficientTasksError`).
`validate_task(task, repo_path, config) -> bool` (known‑good passes 3×; broken fails; flaky discarded).
**OPEN (M2):** the exact "covered by an existing test" determination (coverage tooling in the eval image; test→function mapping) — **Phase‑3‑blocking, not Phase 0/1.**

**`eval/images.py`, `eval/network.py` (Phase 3; AD‑2, Spec B, M5):**
`build_eval_image(repo_path, profile, config) -> str` (build/reuse `primer-eval-<repohash>:<commit>`,
`FROM <resolved base digest>`, COPY manifest+lock only, RUN install + ensure test runner; **source not baked**;
the ONLY host‑networked step; **resolve and record the base `sha256` digest**).
`EgressNetwork` ctx mgr → `EgressInfo{network_name, proxy_url, allowed_host, enforced}` (Spec B 2–4; idempotent teardown).

**`eval/agent_adapter.py` + `adapters/` (Phase 3; AD‑3, AD‑4; supersedes the Master Prompt's `AgentRunResult`):**
```
class AgentAdapter(ABC):
  @property adapter_name -> str
  required_env_key() -> str          # the SINGLE env var injected in-container
  api_host() -> str                  # egress allowlist target (feeds Spec B)
  context_filename() -> str          # file the agent reads from CWD; runner writes/omits it (also drives M7)
  build_invocation(task) -> list[str]# in-container argv; non-interactive; IDENTICAL both arms; writes nothing outside CWD; AgentNotFoundError if CLI absent
  parse_telemetry(raw_log) -> AgentTelemetry   # tokens/iterations/duration/cost/cost_confidence/agent_error — NO pass/fail
def get_adapter(name) -> AgentAdapter   # registry; unknown ⇒ ValueError
```
**ClaudeCodeAdapter (MVP default):** `required_env_key="ANTHROPIC_API_KEY"`; `api_host="api.anthropic.com"`;
`context_filename="CLAUDE.md"`; `build_invocation` → `claude -p "<prompt>" --output-format json --permission-mode bypassPermissions`
(launched `cwd=/work`; **no `--bare`**, M4; identical both arms); `parse_telemetry` reads `total_cost_usd`
(fallback `cost_usd`) → `cost_confidence="exact"`, plus `usage`, `num_turns`, `is_error`. **Eligibility:** a repo
that already commits an agent context file is the developer‑file experiment → **out of MVP scope** (see OPEN M11).
**Build‑confirm:** Claude Code JSON field names, exit codes, `--permission-mode`, `--bare` semantics.
`codex/gemini_code/openrouter` adapters = **[POST‑MVP]**.

**`eval/runner.py` (Phase 3; fat runner — Specs B+D, M4, M5):** `run_task(task, repo_path, with_context, profile, config, adapter, image_tag) -> RunResult`.
Executes Spec B 1–12 and Spec D exactly; **flags identical both arms** (only the file differs); `passed` from the
exit code; `egress_enforced`/`network_mode` from `EgressInfo.enforced`; `base_image` = resolved digest;
`cost_*` from `adapter.parse_telemetry()`. **The agent never sets `passed`.**

**`eval/scorer.py` (Phase 3/4; AD‑5, M3):** `score(profile, repo_path, tasks, config, runs_per_config=3, adapter, image_tag) -> ScoreReport`.
Per task × {without, with} × `runs_per_config` (**sequential**, Q1) via `run_task`; aggregate success rates +
`per_task` + signed per‑task delta; **variance** (`stddev/min/max`, never collapsed); **refuse‑on‑mismatch**
(provider/model differ ⇒ `success_delta`/`cost_delta_pct=None` + `provider_mismatch_warning`); isolation
consistency (network_mode/egress_enforced/base_image not uniform ⇒ `isolation_mismatch_warning`; "egress‑restricted"
only if **all** runs enforced); `cost_confidence` = worst‑of; `primer_overhead_usd` carried **separately**; flaky
runs included + `flaky_task_warning`.

**`store/db.py` (Phase 3/4 — ONLY sqlite consumer):** `init_db(config)`; `save_report(report, tasks, runs, profile) -> int`;
`latest_report(repo_path) -> ScoreReport|None`. Round‑trips provider/model/agent/base_image/isolation fields/both
token streams.

**`report/render.py` (Phase 4 — pure rendering):** `render_report(report, fmt:Literal["text","json"]="text") -> None`.
Signed Δ colored by sign with the **M3 within‑noise label**; variance spread; per‑task table; all `*_warning`s
prominent; cost with the right confidence qualifier; **PRIMER overhead on a separate line**; a `None` delta prints
the refusal reason, never a fabricated number. **No computation.**

**`cli.py` (Phase 0 stubs → Phase 4 full — composition root):**
```
@app.command() init(path=".", provider=None, model=None)     # writes adapter.context_filename() (M7) + overhead cost
@app.command() eval(path=".", provider=None, agent=None, runs=None, tasks=None)
@app.command() report(path=".", format="text")
# entrypoint: primer = "primer.cli:app"
```

## 12. Removed / superseded guidance (do NOT implement)

`network_disabled=True` (→ Spec B proxy‑egress) · `--bare` as the with/without mechanism (→ M4 filesystem control)
· `AgentAdapter.run(...) -> AgentRunResult(success, exit_code, …)` (→ split `build_invocation`/`parse_telemetry`; AD‑4)
· `add_test` task type and "curated built‑in 5 / repo‑derived is Post‑MVP" (→ Spec C two types, repo‑derived in MVP)
· "41% → 68%" headline (deleted) · "$0 end‑to‑end / no API keys" for the MVP (→ M8: $0 generation only)
· `primer_eval_timeout_s=300` (→ 600, M1) · tag‑based `base_image` (→ digest, M5) · `init`→`AGENTS.md` (→ adapter
filename, M7) · standalone `primer map` + "CLI = Phase 5" numbering (→ `init/eval/report`, MVP = Phases 0–4)
· `.secrets.baseline` in `.gitignore` (→ committed) · "no retries" in eval (→ Q2 retry‑once + flaky annotation).

## 13. Contradictions resolved

| # | Conflict | Ruling (authority) |
|---|---|---|
| C1 | network isolation | **Proxy‑egress, Spec B** (Session 1 changelog #1). |
| C2 | adapter reports pass/fail | **Split contract; verify_cmd exit code is sole verdict** (AD‑4). |
| C3 | task types / sourcing | **Two types, repo‑derived, no `add_test`, honest floor** (Spec C). |
| C4 | eval timeout | **600 s** (M1). |
| C5 | base image pinning | **Digest stored in `base_image`** (M5). |
| C6 | `--bare` | **No `--bare`; filesystem‑controlled distinction; smoke gate** (M4). |
| C7 | phase numbers / `map` | **`init/eval/report` only; MVP = Phases 0–4** (Session 1 §5). |
| C8 | `TokenUsage` shape | **Both cache fields** per §1.5 (Session 1). |
| C9 | output validation thresholds | **Not a real conflict — two layers compose:** provider Q9c (`<20`, non‑UTF‑8) + generate §4.5 (`<50`/no code block) + `>8 KB`/truncation. (M9 = minor harmonization, open.) |
| C10 | `init` filename | **Adapter `context_filename()`** (M7). |
| C11 | paper date | **12 Feb 2026** (Session 1). |
| C12 | eval retries | **Q2 retry‑once + flaky annotation** over "no retries" (Session 1). |
| C13 | `.secrets.baseline` in `.gitignore` (Session‑2 internal) | **Committed; removed from `.gitignore`.** |
| C14 | mismatch fields (`agent_version`) | **Provider+model refusal (Q9d); agent_adapter + isolation fields feed warnings; `agent_version` not tracked** (per Session 1/2 schema). |

## 14. Open decisions remaining (none block Phase 0 or Phase 1)

- **M2** — deterministic "covered by an existing test" mapping (coverage tooling + test→function). **Phase‑3‑blocking.**
- **M9** — harmonize the exact validation numbers across the two layers (cosmetic; **Phase 2**).
- **M11** — single eligibility predicate (no committed context file vs PRIMER‑generated file; passing suite; detectable `test_cmd`; no network/DB/GPU/long‑build) and its interaction with `init` writing `CLAUDE.md`. **Phase‑3** (adapter/runner).
- **Micro‑decisions — RATIFIED (now binding; no longer optional):**
  - **`*_api_key : SecretStr | None`** (refines Session 2 `str | None`) to mechanically satisfy the no‑key‑logging rule (Q10/rule 4); accessed via `.get_secret_value()` at point of use in Phase 2. Backstopped by the Phase‑0 redaction test.
  - **`.secrets.baseline` committed** and removed from `.gitignore` (C13).
- **Phase‑3‑blocking items surfaced by the pre‑build audit (RECORDED here, NOT resolved):** agent model/version recording + cross‑arm uniformity check; `agent_error` persistence + scorer handling (void, not "fail"); per‑eval read‑validity (beyond the one‑off M4 gate); deterministic run ordering (interleave arms, not block); `agent_log_path` written **outside** the per‑run temp dir; egress‑proxy image pinning/recording; the M11 `init`/eligibility contradiction. **Two of these add columns to `RunResult`/`runs`, so they must be decided BEFORE the Phase‑3 schema is written.** Out of scope for this Phase‑0 update.

---

# PART II — PHASE 0 (BUILD‑NOW CONTRACT)

## P0.1 Scope

Repo + security foundation + installable skeleton. **No** ingest/generate/eval/store/report logic; CLI commands are
**stubs**. Security scaffold is **step 1, before any other file is committed.**

## P0.2 Exact acceptance criteria (definition of done)

1. **Security ordering (NON‑NEGOTIABLE):** gitleaks + detect‑secrets pre‑commit hooks active **before any other
   file is committed**; `.env` **effectively ignored** (verified via `git check-ignore .env`); `.env.example` empty
   placeholders only; **`.secrets.baseline` committed and NOT ignored** (`git check-ignore .secrets.baseline` reports it is not ignored).
2. **Secret hook is *effective* (positive control):** a planted dummy `sk-ant-…` / `AIza…` secret in a staged file is
   **rejected** by the pre‑commit hooks. Verifying the hooks are merely *configured* is insufficient.
3. **Repo bootstrapped:** `git log` shows the initial commit; default branch `main`; `pre-commit run --all-files`
   passes on the clean tree.
4. **Installable + entrypoint wired:** `pip install -e .` runs clean from a fresh shell; the **installed** `primer`
   console script runs (`primer --help` via a real shell/subprocess) — exits **0** and lists `init`, `eval`, `report`.
5. **CLI skeleton + exit policy:** each stub command is invokable and prints a clear "not yet implemented (Phase N)"
   notice; **stub commands exit code 2; `--help` (top‑level and per‑subcommand) exits 0**; no stub imports a future‑phase module.
6. **Config:** `Settings` loads every `.env.example` var; defaults match §11 (incl. `primer_eval_timeout_s=600`,
   `docker_base_image="python:3.11-slim"`); `docker_client_timeout_s == eval_timeout_s + 30` (==630);
   `validate_runtime()` raises `ConfigError` when the selected provider key **or** the selected agent's required key
   is missing (static `{claude_code: ANTHROPIC_API_KEY}` map in Phase 0); **no API‑key value ever appears in any log,
   repr, or exception message (SecretStr)**; nothing configurable hardcoded outside `Settings`/`.env` (Q7).
7. **Errors:** every exception in §11 exists, subclasses `PrimerError`, carries a user‑readable message.
8. **Dependencies:** all MVP runtime + dev deps declared in `pyproject.toml` (versions pinned/confirmed per
   **Session 1 §1.1–1.5** / Context7); **every declared runtime dep imports successfully**; `.env.example` +
   `pyproject.toml` are the only config sources.
9. **Positioning honesty (verified):** `README.md` contains **none** of the forbidden substrings — `41%`, `68%`,
   `$0 end‑to‑end` (case‑insensitive) — and scopes "$0" to file generation.
10. **Tests green:** `pytest` passes the full **required** Phase‑0 test set (P0.5).

## P0.3 File manifest (exact — created in Phase 0)

Root (7): `pyproject.toml`, `README.md`, `LICENSE`, `.env.example`, `.gitignore`, `.pre-commit-config.yaml`, `.secrets.baseline`.
Package (4): `primer/__init__.py`, `primer/config.py`, `primer/errors.py`, `primer/cli.py`.
Tests — required (8): `tests/conftest.py`, `tests/test_config.py`, `tests/test_errors.py`, `tests/test_cli_smoke.py`,
`tests/test_entrypoint.py`, `tests/test_deps_import.py`, `tests/test_security_scaffold.py`, `tests/test_readme_honesty.py`.
Tests — recommended (1): `tests/test_arch_boundaries.py` (seed; mandatory by Phase 2). Full assertions in P0.5.
**Not** created now: any `primer/{ingest,generate,llm,eval,store,report}/…`, `docker/…`, `dashboard/…`, `tests/fixtures/…`.
**Git action (not a file):** initialize repo, default branch `main`, install hooks, first commit.

## P0.4 Per‑file contract

- **`pyproject.toml`** — `[project]` (name `primer`, version `0.1.0`, Python ≥3.11). `[project.scripts] primer = "primer.cli:app"`.
  Runtime deps: `typer`, `pydantic`, `pydantic-settings`, `rich`, `anthropic`, `docker`, `requests`,
  `tree-sitter` + per‑language wheels (`tree-sitter-python`, `tree-sitter-javascript`; **not** `tree-sitter-languages`).
  Dev deps: `pytest`, `pre-commit`, `detect-secrets`. **Versions pinned/confirmed per Session 1 §1.1–1.5 (Context7).** `[tool.pytest.ini_options]` configured.
  (`gitleaks` is provided by its pre‑commit hook repo, **not** pip.)
- **`primer/__init__.py`** — `__version__ = "0.1.0"`.
- **`primer/config.py`** — `Settings(BaseSettings)` exactly per §11 (M1, M5; `*_api_key` as `SecretStr | None`, ratified §14),
  `docker_client_timeout_s` property, `validate_runtime()` (checks the selected provider key **and** the selected agent's
  required key via the static `{claude_code: ANTHROPIC_API_KEY}` map — both REQUIRED in Phase 0; never logs key values).
- **`primer/errors.py`** — the eight exceptions in §11; leaf module (imports nothing from PRIMER).
- **`primer/cli.py`** — `app = typer.Typer()`; `@app.command()` `init/eval/report` with the §11 signatures, each a stub
  printing a "not yet implemented (Phase N)" notice and **exiting with code 2** (`--help`, top‑level and per‑subcommand,
  exits 0); **no imports of future‑phase modules.**
- **`.env.example`** — keys for every `Settings` var, **empty values only**:
  `PRIMER_LLM_PROVIDER, PRIMER_DEFAULT_MODEL, ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY,
  OLLAMA_BASE_URL, OLLAMA_MODEL, PRIMER_AGENT, PRIMER_AGENT_API_HOST, PRIMER_TASK_COUNT, PRIMER_MIN_TASKS,
  PRIMER_EVAL_RUNS, PRIMER_EVAL_TIMEOUT_S, PRIMER_COMMIT_SCAN_DEPTH, PRIMER_EVAL_MEM_LIMIT, DOCKER_BASE_IMAGE,
  PROXY_IMAGE, DATABASE_URL`.
- **`.gitignore`** — `.env`, `*.db`, `primer.db`, `__pycache__/`, `*.pyc`, `node_modules/`, `.next/`, `dist/`, `build/`,
  `*.egg-info/`, `.pytest_cache/`. **Do NOT list `.secrets.baseline`.**
- **`.pre-commit-config.yaml`** — gitleaks hook (its repo) + detect‑secrets hook with `--baseline .secrets.baseline`.
- **`.secrets.baseline`** — generated by `detect-secrets scan`; **committed**.
- **`LICENSE`** — MIT, 2026, kanwa2006.
- **`README.md`** — stub: one‑line positioning ("Every context‑file tool generates. PRIMER measures.") + honest scope
  (measurement harness; deltas may be ~0/negative; **$0 generation via Ollama; eval requires an agent API key + cost**).
  **No "$0 end‑to‑end"; no "41% → 68%".**

## P0.5 Test manifest (exact)

**Required (every one gates Phase 0):**
- `tests/conftest.py` — fixtures: env‑var injection/cleanup; project‑root path helper; a helper that initializes a
  **temporary git repo with the pre‑commit hooks installed** (for the security tests). No sample repos — Phase 1.
- `tests/test_config.py` — defaults per §11; `docker_client_timeout_s == eval_timeout_s + 30` (default 630; parametrized
  e.g. 300→330); `validate_runtime()` raises `ConfigError` on a missing provider key **and** on a missing agent‑required
  key, and passes when both are present; **`repr(Settings)` / `str(Settings)` and any `ConfigError` message never expose a
  key value** (SecretStr redaction).
- `tests/test_errors.py` — each of the eight exceptions exists, subclasses `PrimerError` (→ `Exception`), and is
  instantiable with a message whose `str()` round‑trips. (Parametrized over the eight.)
- `tests/test_cli_smoke.py` — Typer `CliRunner`: `primer --help` exits 0 and lists `init/eval/report`; each subcommand
  `--help` exits 0; **each stub invocation exits 2** and prints its notice. (Robust to Click version differences — pin
  Click per **Session 1 §1.3**.)
- `tests/test_entrypoint.py` — **subprocess** test of the *installed* console script: `primer --help` via the shell exits
  0 and lists the three commands. (Exercises `[project.scripts]`, which the in‑process `CliRunner` does **not**.)
- `tests/test_deps_import.py` — imports **every declared runtime dependency** (`typer`, `pydantic`, `pydantic_settings`,
  `rich`, `anthropic`, `docker`, `requests`, `tree_sitter` + the per‑language wheels) and asserts each import succeeds.
  (Importing `docker`/`anthropic` requires no daemon or key.)
- `tests/test_security_scaffold.py` — (a) `.pre-commit-config.yaml` references **both** gitleaks and detect‑secrets;
  (b) `.secrets.baseline` exists **and** `git check-ignore .secrets.baseline` reports it is **not** ignored;
  (c) `git check-ignore .env` confirms `.env` **is** ignored; (d) `.env.example` contains only empty values (no `KEY=value`);
  (e) **positive control** — in a temp repo with hooks installed, staging a file containing a dummy `sk-ant-…` / `AIza…`
  secret makes the secret hook **fail/reject** the commit.
- `tests/test_readme_honesty.py` — greps `README.md` for the forbidden substrings (`41%`, `68%`, `$0 end-to-end`,
  case‑insensitive) and asserts none are present.

**Recommended (cheap, not a Phase‑0 blocker):**
- `tests/test_arch_boundaries.py` — **seed** AST/grep scan of the three boundary rules (vendor SDK → `primer/llm/`,
  `docker` → `primer/eval/`, sqlite → `primer/store/`); passes trivially now; gains teeth as modules land. **Mandatory by Phase 2.**

## P0.6 Phase gate

Phase 0 is **done** when P0.2(1–10) hold and the full **required** Phase‑0 test set (P0.5) is green. **Phase 1 must not
begin** until then. The single most important downstream gate remains **Phase 3 `test_runner_isolation.py`** (Spec B/D +
the M4 fingerprint validity probes), which must pass before any reporting/CLI polish is trusted.
