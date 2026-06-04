# PRIMER — SESSION 2 ARCHITECTURE BLUEPRINT

> Architect: Opus 4.8. **Architecture only — no implementation code.** This document contains
> schemas (dataclasses), signatures (ABCs / function contracts), SQL DDL, config specs, flows,
> and per-module acceptance criteria. Function *bodies* are Sonnet 4.6's job (Session 3+).
> Source of truth: **Session 1 Final Revision** (Specs A–D, Q1–Q10). Nothing here contradicts it.

**Scope of this blueprint:** the MVP (Phases 0–4). Post-MVP modules appear as *interfaces only*,
marked `[POST-MVP]`.

---

## 0. ARCHITECTURE DECISIONS INTRODUCED HERE (below the three locked decisions)

| # | Decision | Rationale |
|---|----------|-----------|
| **AD-1** | **Ingest is heuristic-only (no LLM).** `RepoProfile` is pure structural data. | Deterministic + cheap. The single Layer-1 LLM call lives in `generate/`. `conventions`/`gotchas` are *generator output*, not profile fields. |
| **AD-2** | **Eval image built once per `(repo, commit)`; fresh container per run.** | Keeps "fresh container per run" isolation while removing `pip install` from the timeout budget. With/without arms share an identical read-only base layer. |
| **AD-3** | **Thin adapters / fat runner.** All Docker, network, timeout, and cleanup logic lives ONLY in `runner.py`. Adapters supply the agent invocation + parse telemetry. | The moat's isolation guarantees live in one auditable place and can't be weakened by a sloppy adapter. |
| **AD-4** | **The agent never decides pass/fail.** The adapter runs the agent (edits code); `runner` runs `verify_cmd`; exit code is the verdict. | Objectivity: pass/fail is a real exit code, never the agent's self-report. |
| **AD-5** | **Refuse-on-mismatch (Q9d) is enforced in `scorer`, not `runner`.** | A single run is valid in isolation; only the *comparison* is invalid under a provider/model mismatch. Delta becomes `None` + warning. |

---

## 1. FINAL FOLDER STRUCTURE

```
primer/
├── pyproject.toml                # [project], deps, dev-deps, pytest cfg; entrypoint primer = "primer.cli:app"
├── README.md
├── LICENSE                       # MIT, 2026, kanwa2006
├── .env.example                  # all PRIMER_*/*_API_KEY placeholders (empty)
├── .gitignore                    # .env, *.db, __pycache__, node_modules, .next, dist, .secrets.baseline
├── .pre-commit-config.yaml       # gitleaks + detect-secrets   (Phase 0, step 1)
├── .secrets.baseline
├── docker/
│   ├── eval.Dockerfile           # base eval image template (deps layer-cached per repo)
│   └── proxy/
│       ├── Dockerfile            # egress proxy image (tinyproxy)
│       └── tinyproxy.conf.tmpl   # deny-by-default + single-host allowlist
├── primer/
│   ├── __init__.py               # __version__ = "0.1.0"
│   ├── config.py                 # pydantic-settings Settings (single source of runtime config)
│   ├── errors.py                 # all custom exceptions (leaf module)
│   ├── ingest/                   # MVP — heuristic repo analysis (NO LLM, AD-1)
│   │   ├── __init__.py
│   │   ├── models.py             # RepoProfile, LanguageStat, FileNode, DependencyEdge, CommandSet
│   │   ├── commands.py           # detect_commands() — manifest heuristics
│   │   └── analyzer.py           # analyze_repo() — tree-sitter 0.25
│   ├── generate/                 # MVP — the file under test
│   │   ├── __init__.py
│   │   ├── prompts.py            # lean-generation system prompt (constants/templates)
│   │   └── context_writer.py     # write_context() — ONE Layer-1 LLM call
│   ├── llm/                      # ONLY place vendor SDKs may be imported (security rule 2)
│   │   ├── __init__.py
│   │   ├── base.py               # LLMProvider ABC, LLMResponse, TokenUsage, log_safe()
│   │   ├── factory.py            # get_provider(config) -> LLMProvider
│   │   ├── anthropic.py          # AnthropicProvider   (default; cost exact)
│   │   ├── ollama.py             # OllamaProvider      ($0; cost free)
│   │   ├── openai.py             # [POST-MVP]
│   │   ├── gemini.py             # [POST-MVP]
│   │   └── openrouter.py         # [POST-MVP]
│   ├── eval/                     # MVP — THE MOAT
│   │   ├── __init__.py
│   │   ├── models.py             # Task, TaskMutation, RunResult, AgentTelemetry, ScoreReport, TaskScore
│   │   ├── tasks.py              # derive_tasks() — revert_reimplement + stub_function (NO LLM, Spec C)
│   │   ├── preflight.py          # validate_task() — 3× good→pass / broken→fail (Spec C)
│   │   ├── images.py             # build_eval_image() — per-(repo,commit) deps layer (AD-2)
│   │   ├── network.py            # EgressNetwork ctx mgr — internal net + proxy sidecar (Spec B)
│   │   ├── runner.py             # run_task() — fat runner; all isolation/timeout/cleanup (Spec B, D)
│   │   ├── scorer.py             # score() -> ScoreReport — aggregation, variance, refuse-on-mismatch
│   │   ├── agent_adapter.py      # AgentAdapter ABC (AD-3, AD-4)
│   │   └── adapters/
│   │       ├── __init__.py       # registry: name -> AgentAdapter
│   │       ├── claude_code.py    # ClaudeCodeAdapter (MVP default)
│   │       ├── codex.py          # [POST-MVP]
│   │       ├── gemini_code.py    # [POST-MVP]
│   │       └── openrouter.py     # [POST-MVP]
│   ├── store/                    # MVP — persistence (ONLY place that touches SQLite)
│   │   ├── __init__.py
│   │   ├── schema.sql            # DDL (see §3)
│   │   └── db.py                 # connection, migrations, save/load
│   ├── report/                   # MVP — rendering only (rich); NO computation
│   │   ├── __init__.py
│   │   └── render.py             # render_report()
│   └── cli.py                    # Typer app — composition root: init / eval / report
├── tests/
│   ├── conftest.py
│   ├── fixtures/                 # tiny sample repos (1 py, 1 ts) for deterministic tests
│   ├── test_arch_boundaries.py   # asserts no vendor SDK import outside primer/llm/
│   ├── test_ingest.py
│   ├── test_generate.py
│   ├── test_tasks.py
│   ├── test_runner_isolation.py  # THE most important test (Phase 3 acceptance)
│   └── test_scorer.py
└── dashboard/                    # [NICE-TO-HAVE, Phase 7] — not MVP
```

---

## 2. MODULE BOUNDARIES

**Dependency DAG (arrows = "may import"). No cycles.**

```
            config.py        errors.py
                │ │             │
        ┌───────┘ └──────┬──────┤
        ▼                ▼      ▼
     llm/*           ingest/*   (errors used everywhere as a leaf)
        │                │
        └──────┬─────────┘
               ▼
          generate/*
               │
               ▼
      eval/*  (models → tasks → preflight → images → network → adapters → runner → scorer)
               │
               ▼
           store/*
               │
               ▼
          report/*
               │
               ▼
           cli.py   ← the ONLY composition root
```

**Boundary invariants (each is testable):**

1. **LLM-SDK isolation.** `import anthropic | openai | google.generativeai | <any vendor SDK>` appears
   **only** under `primer/llm/`. Enforced by `tests/test_arch_boundaries.py` (AST/grep scan). A violation
   fails CI. Everything else obtains an LLM via `get_provider(config)`.
2. **Docker isolation.** Only `primer/eval/` (specifically `images.py`, `network.py`, `runner.py`)
   imports `docker`. No other module spins containers.
3. **SQLite isolation.** Only `primer/store/` imports `sqlite3`/`aiosqlite`. Other modules pass/receive
   dataclasses; persistence is `store`'s concern.
4. **`report/` is pure rendering.** It receives a fully-computed `ScoreReport` and writes to stdout.
   It performs **no** aggregation, no I/O beyond the terminal, no LLM calls.
5. **`cli.py` is the only orchestrator.** No module imports `cli`. `cli` wires the pipeline.
6. **Two token streams never mix.** `generate/` (and any future report-time LLM use) = **PRIMER overhead**.
   The in-container agent's tokens (captured by `adapters/`) = **eval cost**. `scorer` keeps them in
   separate fields; they are never summed. (Session 1 §Q9, Moat.)
7. **`ingest/` makes no LLM calls** (AD-1). The first and only Layer-1 call in the MVP pipeline is in
   `generate/context_writer.write_context()`.

---

## 3. DATABASE SCHEMA (SQLite)

`store/schema.sql`. Booleans stored as `INTEGER` (0/1). Timestamps `TEXT` ISO-8601 UTC.
`raw_output`/logs are **redacted** (`log_safe()`) before any write.

```sql
CREATE TABLE IF NOT EXISTS _meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL                 -- e.g. ('schema_version','1')
);

CREATE TABLE IF NOT EXISTS profiles (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_path           TEXT NOT NULL,
    repo_commit         TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    profile_json        TEXT NOT NULL,          -- serialized RepoProfile
    agents_md           TEXT,                   -- the generated file (the artifact under test)
    agents_md_lines     INTEGER,
    gen_provider        TEXT,                   -- PRIMER-overhead provenance
    gen_model           TEXT,
    gen_tokens          INTEGER,
    gen_cost_usd        REAL,
    gen_cost_confidence TEXT                    -- exact|estimated|free
);

CREATE TABLE IF NOT EXISTS reports (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_path                   TEXT NOT NULL,
    repo_commit                 TEXT NOT NULL,
    created_at                  TEXT NOT NULL,
    n_tasks                     INTEGER NOT NULL,
    runs_per_config             INTEGER NOT NULL,
    -- outcome (signed; delta NULL when refused on mismatch — Q9d)
    success_rate_without        REAL NOT NULL,
    success_rate_with           REAL NOT NULL,
    success_delta               REAL,           -- NULLABLE: NULL ⇒ refused (see warning)
    success_stddev              REAL NOT NULL,   -- variance NEVER collapsed
    success_min                 REAL NOT NULL,
    success_max                 REAL NOT NULL,
    -- cost (eval stream only; PRIMER overhead kept separate below)
    cost_without                REAL NOT NULL,
    cost_with                   REAL NOT NULL,
    cost_delta_pct              REAL,            -- NULLABLE
    cost_confidence             TEXT NOT NULL,   -- worst-of constituent runs
    -- provenance / isolation (must be uniform or a *_warning is set)
    provider                    TEXT NOT NULL,
    model                       TEXT NOT NULL,
    agent_adapter               TEXT NOT NULL,
    base_image                  TEXT NOT NULL,
    network_mode                TEXT NOT NULL,   -- proxy-egress|open-bridge|offline
    egress_enforced             INTEGER NOT NULL,
    -- honesty warnings (NULL = clean)
    provider_mismatch_warning   TEXT,
    isolation_mismatch_warning  TEXT,
    flaky_task_warning          TEXT,
    -- PRIMER overhead (NEVER added to cost_with/without)
    primer_overhead_usd         REAL NOT NULL,
    primer_overhead_confidence  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id   INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    task_key    TEXT NOT NULL,                  -- deterministic id, e.g. "revert_<sha>_<test>"
    task_type   TEXT NOT NULL,                  -- revert_reimplement|stub_function
    prompt      TEXT NOT NULL,
    verify_cmd  TEXT NOT NULL,
    source_ref  TEXT,                           -- commit SHA or "path/to/file.py::func"
    validated   INTEGER NOT NULL                -- passed pre-flight
);

CREATE TABLE IF NOT EXISTS runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id           INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    task_id             TEXT NOT NULL,
    repo_commit         TEXT NOT NULL,
    with_context        INTEGER NOT NULL,
    passed              INTEGER NOT NULL,
    timeout             INTEGER NOT NULL,
    flaky               INTEGER NOT NULL,
    -- eval-agent cost stream
    agent_adapter       TEXT NOT NULL,
    agent_tokens        INTEGER NOT NULL,
    iterations          INTEGER NOT NULL,
    duration_s          REAL NOT NULL,
    cost_usd            REAL NOT NULL,
    cost_confidence     TEXT NOT NULL,
    -- PRIMER-brain provenance (who generated the file under test)
    provider            TEXT NOT NULL,
    model               TEXT NOT NULL,
    -- isolation audit trail
    base_image          TEXT NOT NULL,
    network_mode        TEXT NOT NULL,
    egress_allowed_host TEXT,
    egress_enforced     INTEGER NOT NULL,
    caps_dropped        INTEGER NOT NULL,
    container_id        TEXT NOT NULL,
    agent_log_path      TEXT NOT NULL,          -- REDACTED log on disk
    run_timestamp       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_report   ON runs(report_id);
CREATE INDEX IF NOT EXISTS idx_runs_task     ON runs(task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_report  ON tasks(report_id);
CREATE INDEX IF NOT EXISTS idx_reports_repo  ON reports(repo_path);
```

---

## 4. API CONTRACTS (internal module surfaces — signatures + behavior, NO bodies)

### 4.1 `config.py`

```python
class Settings(BaseSettings):
    # provider / model (Layer 1 — PRIMER's brain)
    primer_llm_provider: str = "anthropic"        # anthropic|openai|gemini|openrouter|ollama
    primer_default_model: str = "claude-sonnet-4-6"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.3"
    # agent (Layer 2 — the in-container eval agent)
    primer_agent: str = "claude_code"             # adapter name
    primer_agent_api_host: str = "api.anthropic.com"   # egress allowlist target (Spec B)
    # eval knobs
    primer_task_count: int = 5
    primer_min_tasks: int = 3
    primer_eval_runs: int = 3
    primer_eval_timeout_s: int = 300
    primer_commit_scan_depth: int = 200
    primer_eval_mem_limit: str = "2g"
    # infra
    docker_base_image: str = "python:3.11-slim"
    proxy_image: str = "primer-egress-proxy:latest"
    database_url: str = "sqlite:///primer.db"

    @property
    def docker_client_timeout_s(self) -> int: ...     # == primer_eval_timeout_s + 30 (Spec D)
    def validate_runtime(self) -> None: ...
    # Contract: raises ConfigError if the selected provider's key is missing OR the selected
    # agent's required key is missing. Never logs key values.
```

### 4.2 `errors.py` (leaf)

```python
class PrimerError(Exception): ...
class ConfigError(PrimerError): ...
class OllamaOutputError(PrimerError): ...      # empty/malformed local model output (Q9c)
class GenerationError(PrimerError): ...        # AGENTS.md generation failed after one retry
class AgentNotFoundError(PrimerError): ...     # eval agent CLI not installed in image
class InsufficientTasksError(PrimerError): ... # < min_tasks validated (Spec C honest refusal)
class TaskValidationError(PrimerError): ...    # a candidate failed pre-flight
class IsolationError(PrimerError): ...         # network/proxy/container setup could not be guaranteed
```

### 4.3 `llm/base.py` (the only vendor-SDK home — security rule 2)

```python
@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    cost_usd: float = 0.0
    cost_confidence: Literal["exact", "estimated", "free"] = "estimated"

@dataclass
class LLMResponse:
    content: str
    usage: TokenUsage
    model: str
    provider: str

class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, messages: list[dict], model: str) -> LLMResponse: ...
    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float: ...
    @property
    @abstractmethod
    def supports_caching(self) -> bool: ...
    @staticmethod
    def log_safe(text: str) -> str: ...
    # Contract: redacts sk-…, sk-ant-…, AIza… patterns → "[REDACTED]". Used before ANY log write.
```

```python
# llm/factory.py
def get_provider(config: Settings) -> LLMProvider: ...
# Contract: match on config.primer_llm_provider → concrete provider. Unknown ⇒ ValueError.
# This is the ONLY constructor of provider objects used outside primer/llm/.
```

Per-provider `cost_confidence` (Q9b): anthropic/gemini **exact**, openai **estimated→exact**,
openrouter **estimated**, ollama **free** (`cost_usd = 0.0`; output validation per Q9c).

### 4.4 `ingest/`  (AD-1: no LLM)

```python
# ingest/models.py
@dataclass
class LanguageStat:    name: str; percent: float
@dataclass
class FileNode:        path: str; module: str; kind: Literal["file","dir"]; symbols: list[str]
@dataclass
class DependencyEdge:  src_module: str; dst_module: str; weight: int
@dataclass
class CommandSet:
    package_manager: str | None
    build_cmd: str | None
    test_cmd: str | None
    lint_cmd: str | None
    dev_cmd: str | None
@dataclass
class RepoProfile:
    repo_commit: str
    languages: list[LanguageStat]
    frameworks: list[str]
    commands: CommandSet
    top_level_dirs: list[str]
    key_modules: list[str]
    domain_terms: list[str]              # heuristic: frequent identifiers + README headings
    file_nodes: list[FileNode]
    dependency_edges: list[DependencyEdge]
    # NOTE (AD-1): no conventions/gotchas here — those are produced by generate/.
    # NOTE: honesty — unknown fields are None/empty, never fabricated.

# ingest/commands.py
def detect_commands(repo_path: str) -> CommandSet: ...
# Contract: parse manifests only (package.json scripts, pyproject/Makefile, etc.). No LLM, no network.
# Unknown commands are None — never guessed.

# ingest/analyzer.py
def analyze_repo(path: str, config: Settings) -> RepoProfile: ...
# Contract: walk repo respecting .gitignore; tree-sitter 0.25 parse for supported langs; build coarse
# module map + dependency edges; extract candidate domain terms. Pure heuristics. Records repo_commit.
```

### 4.5 `generate/`  (the ONE Layer-1 LLM call)

```python
@dataclass
class GenerationResult:
    content: str
    usage: TokenUsage        # → recorded as PRIMER OVERHEAD, never eval cost
    lines: int
    filename: str            # the artifact's logical name ("AGENTS.md")

# generate/context_writer.py
async def write_context(profile: RepoProfile, provider: LLMProvider) -> GenerationResult: ...
# Contract: ONE call via provider.complete() with the lean system prompt. Output MUST be a LEAN
# ≤~20-line file (commands, non-obvious conventions, internal APIs — NO architecture prose, NO
# linter-enforceable rules, NO directory dump). Failure mode: if output <50 chars or has no code
# block → retry once with a simplified prompt; still malformed ⇒ GenerationError.
```

### 4.6 `eval/models.py`

```python
@dataclass
class TaskMutation:
    # how runner reproduces the FAILING start state deterministically
    kind: Literal["revert", "stub"]
    target_commit: str | None = None    # revert: the source-only change to revert
    target_file: str | None = None      # stub: file containing the function
    target_symbol: str | None = None    # stub: function to replace with raise NotImplementedError

@dataclass
class Task:
    id: str                              # deterministic, e.g. "revert_<sha>_<test>"
    task_type: Literal["revert_reimplement", "stub_function"]
    prompt: str
    verify_cmd: str                      # repo's own test runner; exit code = sole verdict
    mutation: TaskMutation
    source_ref: str | None = None
    validated: bool = False

@dataclass
class AgentTelemetry:                    # adapter parse output (AD-4: NO pass/fail here)
    tokens: int
    iterations: int
    duration_s: float
    cost_usd: float
    cost_confidence: Literal["exact", "estimated", "free"]
    agent_error: bool
    raw_log: str                         # redacted by runner before persistence

# RunResult  → see Session 1 Spec A (authoritative).

@dataclass
class TaskScore:
    task_id: str
    task_type: str
    pass_rate_without: float
    pass_rate_with: float
    delta: float | None                  # None if comparison refused
    runs: int
    flaky_any: bool

@dataclass
class ScoreReport:
    repo_commit: str
    created_at: str
    n_tasks: int
    runs_per_config: int
    success_rate_without: float
    success_rate_with: float
    success_delta: float | None          # None ⇒ refused on mismatch (Q9d)
    success_stddev: float
    success_min: float
    success_max: float
    cost_without: float
    cost_with: float
    cost_delta_pct: float | None
    cost_confidence: str                 # worst-of constituent runs
    per_task: list[TaskScore]
    provider: str
    model: str
    agent_adapter: str
    base_image: str
    network_mode: str
    egress_enforced: bool
    provider_mismatch_warning: str | None
    isolation_mismatch_warning: str | None
    flaky_task_warning: str | None
    primer_overhead_usd: float           # separate stream; never added to cost_*
    primer_overhead_confidence: str
```

### 4.7 `eval/tasks.py`, `eval/preflight.py`  (Spec C)

```python
def derive_tasks(profile: RepoProfile, repo_path: str,
                 n: int = 5, min_tasks: int = 3, seed: int = 0) -> list[Task]: ...
# Contract: Spec C. Deterministic given (repo SHA, seed). No LLM. revert_reimplement first, top up
# with stub_function. Each emitted Task already satisfies the fail-at-start invariant.
# Raises InsufficientTasksError if validated tasks < min_tasks.

def validate_task(task: Task, repo_path: str, config: Settings) -> bool: ...
# Contract: in a throwaway checkout/container: (1) known-good → verify_cmd PASSES 3× consistently;
# (2) broken state → verify_cmd FAILS. Returns True only if both hold. Discards flaky candidates.
```

### 4.8 `eval/images.py`, `eval/network.py`  (AD-2, Spec B)

```python
def build_eval_image(repo_path: str, profile: RepoProfile, config: Settings) -> str: ...
# Contract (AD-2): build (or reuse cached) image "primer-eval-<repohash>:<commit>" =
# FROM docker_base_image; COPY manifest+lock ONLY; RUN install deps + ensure test runner.
# Source is NOT baked (a fresh copy is mounted at run). Returns the image tag. This is the ONLY
# step allowed host-level network (one-time, pre-isolation). Deps therefore cost no eval-timeout budget.

class EgressNetwork:                     # context manager (Spec B steps 2–4)
    def __enter__(self) -> "EgressInfo": ...    # creates primer-internal (internal=True) + proxy sidecar
    def __exit__(self, *exc) -> None: ...        # removes proxy + network (idempotent, defensive)
@dataclass
class EgressInfo:
    network_name: str
    proxy_url: str                        # e.g. "http://<proxy>:8888"
    allowed_host: str
    enforced: bool                        # False ⇒ open-bridge fallback was used
```

### 4.9 `eval/agent_adapter.py` + `adapters/`  (AD-3, AD-4)

```python
class AgentAdapter(ABC):
    @property
    @abstractmethod
    def adapter_name(self) -> str: ...
    @abstractmethod
    def required_env_key(self) -> str: ...
    # the SINGLE env var injected in-container (e.g. "ANTHROPIC_API_KEY")
    @abstractmethod
    def api_host(self) -> str: ...
    # host the egress proxy allowlists (e.g. "api.anthropic.com"); feeds Spec B
    @abstractmethod
    def context_filename(self) -> str: ...
    # filename the agent reads from CWD (e.g. "CLAUDE.md"); runner writes/omits this file
    @abstractmethod
    def build_invocation(self, task: Task) -> list[str]: ...
    # in-container argv to run the agent HEADLESSLY on task.prompt. Must be non-interactive and
    # IDENTICAL for with/without arms (the only difference is the file's presence). Writes nothing
    # outside CWD. Raises AgentNotFoundError if the CLI is absent.
    @abstractmethod
    def parse_telemetry(self, raw_log: str) -> AgentTelemetry: ...
    # parse tokens/iterations/duration/cost/cost_confidence/agent_error from the agent's output

# adapters/__init__.py
def get_adapter(name: str) -> AgentAdapter: ...    # registry lookup; unknown ⇒ ValueError
```

**ClaudeCodeAdapter (MVP default):** `required_env_key="ANTHROPIC_API_KEY"`;
`api_host="api.anthropic.com"`; `context_filename="CLAUDE.md"`;
`build_invocation` → `claude -p "<prompt>" --output-format json --permission-mode bypassPermissions`
(launched with `cwd=/work`; **identical flags both arms**); `parse_telemetry` reads `total_cost_usd`
(fallback `cost_usd`) → `cost_confidence="exact"`, plus `usage`, `num_turns`, `is_error`.
**Eligibility guard:** if the repo already commits an agent context file, that is the *developer-file*
experiment, out of MVP scope → repo rejected (keeps with/without differing only by PRIMER's file).

### 4.10 `eval/runner.py`  (fat runner — all isolation here; Specs B + D)

```python
def run_task(task: Task, repo_path: str, with_context: bool,
             profile: RepoProfile, config: Settings, adapter: AgentAdapter,
             image_tag: str) -> RunResult: ...
```
Contract — executes Spec B steps 1–12 and Spec D exactly:
fresh clone @ `repo_commit` → apply `task.mutation` (failing start state) → (write/omit
`adapter.context_filename()`) → `EgressNetwork` up → container from `image_tag` on the internal
network, one key via `--env`, `cap_drop=["ALL"]`, `no-new-privileges`, limits → command
`sh -c '<adapter argv> > /work/.primer_agent.log 2>&1 ; <verify_cmd>'` → `wait(timeout)`
(try/except `ReadTimeout` → `kill`) → **read+redact log before rmtree** →
`finally` remove container + proxy + network + temp dir → post-run `docker ps -a` audit.
Sets `passed` from the exit code, `egress_enforced`/`network_mode` from `EgressInfo.enforced`,
and `cost_*` from `adapter.parse_telemetry()`. The agent never sets `passed` (AD-4).

### 4.11 `eval/scorer.py`  (aggregation, variance, refuse-on-mismatch — AD-5)

```python
def score(profile: RepoProfile, repo_path: str, tasks: list[Task],
          config: Settings, runs_per_config: int = 3,
          adapter: AgentAdapter, image_tag: str) -> ScoreReport: ...
```
Contract: for each task, for `cfg ∈ {without, with}`, repeat `runs_per_config` (SEQUENTIAL, Q1) via
`run_task`. Then:
- **Aggregate:** `success_rate_{with,without}` = passed-runs / total-runs per config; plus `per_task`
  pass-rates and signed per-task delta.
- **Variance:** `stddev/min/max` across the repeated runs — never collapsed to one number.
- **Refuse-on-mismatch (Q9d/AD-5):** if `provider`/`model` differ across the compared runs, set
  `success_delta = None`, `cost_delta_pct = None`, and `provider_mismatch_warning` (per-config numbers
  still reported).
- **Isolation consistency:** if `network_mode`/`egress_enforced`/`base_image` not uniform → set
  `isolation_mismatch_warning`. The report may describe itself as "egress-restricted" **only if every
  run has `egress_enforced=True`.**
- **Cost:** `cost_confidence` = worst-of constituent runs; `primer_overhead_usd` (the generation call)
  carried **separately**, never summed into `cost_*`.
- **Flaky:** include flaky runs, set `flaky_task_warning`.

### 4.12 `store/db.py`, `report/render.py`, `cli.py`

```python
# store/db.py  (ONLY SQLite consumer)
def init_db(config: Settings) -> None: ...                       # apply schema.sql, set schema_version
def save_report(report: ScoreReport, tasks: list[Task], runs: list[RunResult],
                profile: RepoProfile) -> int: ...                # returns report_id
def latest_report(repo_path: str) -> ScoreReport | None: ...

# report/render.py  (pure rendering; NO computation)
def render_report(report: ScoreReport, fmt: Literal["text","json"] = "text") -> None: ...
# Contract: signed delta colored by sign; variance spread; cost with confidence qualifier
# ("≈" for estimated, "local (no cost)" for free); per-task table; any *_warning surfaced
# prominently; PRIMER overhead shown as a SEPARATE line. If success_delta is None, print the
# refusal reason instead of a fabricated number.

# cli.py  (Typer; the composition root)
@app.command()  def init(path: str = ".", provider: str | None = None, model: str | None = None): ...
@app.command()  def eval(path: str = ".", provider: str | None = None, agent: str | None = None,
                         runs: int | None = None, tasks: int | None = None): ...
@app.command()  def report(path: str = ".", format: str = "text"): ...
```

---

## 5. SCORING PIPELINE

```
tasks (validated) ──► for each task ──► for cfg ∈ {WITHOUT, WITH} ──► repeat runs_per_config (sequential)
                                                       │
                                                       ▼
                                              runner.run_task() → RunResult  (passed from exit code)
                                                       │
              ┌────────────────────────────────────────┴───────────────────────────────────────┐
              ▼                                                                                  ▼
   PER-TASK aggregation                                                          PROVENANCE / ISOLATION checks
   pass_rate_without, pass_rate_with,                                            • provider/model uniform? else success_delta=None
   per-task delta (signed)                                                         + provider_mismatch_warning   (Q9d / AD-5)
              │                                                                  • network_mode/egress_enforced/base_image uniform?
              ▼                                                                    else isolation_mismatch_warning
   OVERALL aggregation                                                           • "egress-restricted" claim ⇔ all runs enforced
   success_rate_{with,without} = passed/total per cfg                                          │
   success_delta = with − without (signed; None if refused)                                    ▼
              │                                                                  COST (eval stream only)
              ▼                                                                  cost_{with,without}=Σ agent cost
   VARIANCE                                                                      cost_delta_pct; cost_confidence = worst-of
   stddev / min / max across repeated runs (never collapsed)                     primer_overhead_usd carried SEPARATELY
              │                                                                                │
              └───────────────────────────────► ScoreReport ◄───────────────────────────────┘
                                                    │
                                          store.save_report() → report/render
```

**Honesty rules baked into the pipeline:** delta is signed and may be ≤0; a `None` delta is a valid,
shippable result (mismatch or refusal); variance is always reported; PRIMER overhead is never folded
into the eval cost; an estimated/free cost is never displayed as exact.

---

## 6. EXECUTION FLOW (`primer eval .`)

```
primer eval .
  └─ Settings(config) ── validate_runtime() ──► fail fast if provider/agent key missing
       │
       ├─ ingest.analyze_repo(path)            [tree-sitter 0.25, heuristics, NO LLM] ─► RepoProfile (+repo_commit)
       │     └─ ingest.detect_commands(path)   [manifest heuristics]                  ─► CommandSet
       │
       ├─ generate.write_context(profile, get_provider(config))   [Layer-1 LLM, ONE call] ─► AGENTS.md + TokenUsage
       │     └─ usage recorded as PRIMER OVERHEAD (never mixed into eval cost)
       │
       ├─ eval.derive_tasks(profile, path, seed)   [revert_reimplement + stub_function, NO LLM]
       │     └─ eval.preflight.validate_task(t)    [3× good→pass ; broken→fail]
       │           └─ if validated < min_tasks(3): raise InsufficientTasksError       (honest refusal)
       │
       ├─ eval.images.build_eval_image(...)        [once per (repo,commit); deps layer-cached; host net]
       │
       ├─ eval.scorer.score(profile, path, tasks, runs_per_config=3, adapter, image_tag)
       │     └─ for task: for cfg ∈ {without, with}: repeat runs_per_config            [SEQUENTIAL, Q1]
       │           └─ eval.runner.run_task(...) ─► RunResult
       │                 EgressNetwork↑ │ fresh clone │ apply mutation │ write/omit file │
       │                 container(proxy-egress, 1 key, caps-dropped) │ agent ; verify_cmd │
       │                 read+redact log │ teardown (container, proxy, net, tmp) │ ps -a audit
       │     └─ aggregate → variance │ refuse-on-mismatch │ isolation check │ cost(worst conf) │ flaky ─► ScoreReport
       │
       ├─ store.save_report(report, tasks, runs, profile)         [SQLite — only store/ touches it]
       └─ report.render_report(report)                            [rich: signed Δ, variance, cost+confidence,
                                                                    per-task, warnings, PRIMER overhead separate]

primer init .   = Settings → analyze_repo → write_context → write AGENTS.md to repo → print summary (+ overhead cost).
primer report . = Settings → store.latest_report(path) → render_report.
```

---

## 7. DOCKER ARCHITECTURE

**Two phases per eval: a one-time BUILD (host network), then N isolated RUNS (proxy-egress only).**

```
HOST (PRIMER process)
  │
  │  BUILD PHASE  (once per (repo, commit); host Docker; network ON — pre-isolation)
  │    docker build → image  primer-eval-<repohash>:<commit>
  │      FROM <docker_base_image>;  COPY manifest+lock ONLY;  RUN <install deps> + ensure test runner
  │      (source NOT baked — a fresh copy is mounted per run)   ◄── AD-2: deps cost no eval-timeout budget
  │
  └─ RUN PHASE  (fresh + sequential per task×cfg×repeat)
       ┌──────────────────────── network: primer-internal  (internal=True → NO route out) ───────────────────────┐
       │                                                                                                          │
       │   ┌─────────────────────────────┐        HTTPS_PROXY=proxy:8888       ┌────────────────────────────┐     │
       │   │  EVAL CONTAINER             │ ─────────────────────────────────► │  EGRESS PROXY (tinyproxy)   │     │
       │   │  image: primer-eval-…:…     │                                     │  FilterDefaultDeny Yes      │     │
       │   │  network: internal ONLY     │                                     │  Allow <agent api_host>     │     │
       │   │  mount: <tmp repo> → /work  │                                     │  ConnectPort 443            │     │
       │   │  env: ONE agent key only    │                                     └──────────────┬─────────────┘     │
       │   │  cap_drop=ALL,              │                                                    │ (ONLY outbound leg;│
       │   │  no-new-privileges,         │                                                    │  also on bridge)   │
       │   │  mem_limit, nano_cpus,      │                                                    ▼                    │
       │   │    pids_limit               │                                            api.anthropic.com:443        │
       │   │  cmd: sh -c 'agent          │                                                                         │
       │   │        >/work/log 2>&1 ;    │      everything except <api_host>:443  ──►  DENIED by proxy             │
       │   │        verify_cmd'          │                                                                         │
       │   └─────────────────────────────┘                                                                         │
       └──────────────────────────────────────────────────────────────────────────────────────────────────────┘
       TEARDOWN (finally, idempotent): read+redact /work log → [kill on timeout] → remove container
                                       → remove proxy → remove network → rmtree tmp → assert `docker ps -a` clean
```

**Eval container run config (spec, not code):**

| Parameter | Value | Why |
|-----------|-------|-----|
| `image` | `primer-eval-<repohash>:<commit>` | deps pre-baked (AD-2) |
| `command` | `sh -c '<agent argv> > /work/.primer_agent.log 2>&1 ; <verify_cmd>'` | exit code = verify_cmd (AD-4, Spec B-9) |
| `working_dir` | `/work` | agent + verify run against the fresh mount |
| `volumes` | `{tmp_repo: {bind: /work, mode: rw}}` | the ONLY host mount |
| `network` | `primer-internal` (internal=True) | no direct egress |
| `environment` | `{<agent key>, HTTPS_PROXY, HTTP_PROXY, NO_PROXY}` | one key only; egress via proxy |
| `cap_drop` | `["ALL"]` | least privilege |
| `security_opt` | `["no-new-privileges:true"]` | block privilege escalation |
| `mem_limit` | `primer_eval_mem_limit` (default `2g`) | real agent needs headroom |
| `nano_cpus` / `pids_limit` | `2_000_000_000` / `512` | bound CPU + fork-bombs |
| `detach` | `True` | required for `wait(timeout)` |
| `auto_remove` | **not set** | races `wait()` (Session 1 §1.2) |

**Egress proxy (`docker/proxy/tinyproxy.conf.tmpl`) — config spec:**
```
Port 8888
Listen 0.0.0.0
FilterDefaultDeny Yes          # deny everything not explicitly allowed
Allow 0.0.0.0/0                # clients are the internal network only
ConnectPort 443                # CONNECT to TLS port only
Filter "/etc/tinyproxy/allow.txt"   # contains exactly: ${ALLOW_HOST}  (= agent api_host)
```
**Fallback:** if proxy egress cannot be guaranteed (e.g. agent ignores `HTTPS_PROXY`), `runner` records
`network_mode="open-bridge"`, `egress_enforced=False`, and the report drops the "egress-restricted"
claim. Never set `egress_enforced=True` optimistically.

---

## 8. AGENT ADAPTER ARCHITECTURE

```
                       ┌──────────────────────────────────────────────┐
                       │  runner.py  (FAT — owns ALL isolation, AD-3)   │
                       │  Docker · network · timeout · cleanup · verify │
                       └───────────────┬───────────────┬───────────────┘
            asks adapter for ──────────┘               └────────── after run, hands raw log to adapter
            • required_env_key()  → which 1 key to inject
            • api_host()          → egress allowlist target
            • context_filename()  → file to write (WITH) / omit (WITHOUT)
            • build_invocation()  → in-container argv (identical both arms)
                                                       │
                                   ┌───────────────────┴───────────────────┐
                                   ▼                                        ▼
                       parse_telemetry(raw_log) → AgentTelemetry   (NO pass/fail — AD-4)
                                   │
        ┌──────────────────────────┼───────────────────────────┐
        ▼                          ▼                            ▼
  ClaudeCodeAdapter         [POST-MVP] codex /            registry: get_adapter(name)
  (MVP default)             gemini_code / openrouter
  key=ANTHROPIC_API_KEY
  host=api.anthropic.com
  file=CLAUDE.md
  parse: total_cost_usd→exact
```

**Design rules:**
- Adapters are **thin**: they never import `docker`, never open sockets, never decide pass/fail.
- The container command always **ends with `verify_cmd`**; the agent log is captured to `/work` and
  parsed *after* the container exits.
- `api_host()` makes the egress allowlist **per-adapter** — swapping to a Gemini agent automatically
  re-points the proxy allowlist. No conditional vendor logic leaks into `runner`.
- Adding a new agent = implement the ABC + register it. Zero changes to `runner`/`scorer`. (Layer-2
  pluggability; matches Layer-1 provider pluggability.)

---

## 9. ACCEPTANCE CRITERIA PER MODULE ("done when …")

| Module | Done when |
|--------|-----------|
| `config.py` | Loads every `.env.example` var; `validate_runtime()` raises `ConfigError` when the selected provider/agent key is missing; `docker_client_timeout_s == eval_timeout_s + 30`; no key value ever appears in logs. |
| `errors.py` | All listed exceptions exist, subclass `PrimerError`, and carry user-readable messages. |
| `llm/base.py` | `log_safe()` redacts `sk-`, `sk-ant-`, `AIza` patterns (unit-tested with samples); ABC defines `complete/estimate_cost/supports_caching`. |
| `llm/factory.py` | Returns the correct provider per `primer_llm_provider`; unknown ⇒ `ValueError`. **`tests/test_arch_boundaries.py` finds zero vendor-SDK imports outside `primer/llm/`.** |
| `llm/anthropic.py` | `complete()` returns `LLMResponse` with exact token counts; `cost_confidence="exact"`. |
| `llm/ollama.py` | `cost_usd=0.0`, `cost_confidence="free"`; empty/<20-char output → retry once → `OllamaOutputError`. |
| `ingest/commands.py` | Correct `package_manager` + a **real, runnable** `test_cmd` on the 2 fixture repos; unknowns are `None`, never guessed. |
| `ingest/analyzer.py` | `analyze_repo()` on the py + ts fixtures returns a `RepoProfile` a human recognizes; deterministic across runs; **makes no LLM/network call** (AD-1, asserted). |
| `generate/context_writer.py` | Produces a **≤~20-line** file with the real test/build commands and **no** linter-enforceable / generic-style / directory-dump lines; malformed output retries once then raises `GenerationError`; usage tagged as overhead. |
| `eval/tasks.py` | Same `(repo SHA, seed)` → identical task list; every Task fails `verify_cmd` at start and passes when correct; `<min_tasks` ⇒ `InsufficientTasksError` with the honest message. |
| `eval/preflight.py` | Accepts a task only if known-good passes 3× consistently **and** broken-state fails; flaky candidates discarded. |
| `eval/images.py` | Builds/reuses `primer-eval-<repohash>:<commit>`; deps present; source **not** baked; build is the only networked step. |
| `eval/network.py` | `EgressNetwork` creates an internal net + proxy; from inside the container, `<api_host>:443` is reachable and **any other host is refused**; teardown leaves no net/proxy behind. |
| `eval/runner.py` | **THE acceptance test** (`test_runner_isolation.py`): same task run with & without context in fresh containers — both arms identical except the file; `passed` comes from a real exit code; repeat same config → consistent (within flaky tolerance); `docker ps -a` empty afterward; temp dirs deleted; `provider`/`model`/`egress_enforced`/`network_mode`/`repo_commit` set on every `RunResult`; a `ReadTimeout` yields `passed=False, timeout=True` and a cleaned-up container. |
| `eval/adapters/claude_code.py` | Headless invocation identical across arms; `parse_telemetry` reads `total_cost_usd` (fallback `cost_usd`) → `cost_confidence="exact"`; missing CLI ⇒ `AgentNotFoundError`; repo with a committed agent file ⇒ rejected as out of scope. |
| `eval/scorer.py` | Emits signed `success_delta` with `stddev/min/max`; **refuses (delta=None) on provider/model mismatch** with a warning; sets `isolation_mismatch_warning` when isolation isn't uniform; `cost_confidence` = worst-of; PRIMER overhead reported separately; two full runs reproduce the delta within its stated spread. |
| `store/db.py` | `init_db` applies `schema.sql` + sets `schema_version`; `save_report` round-trips a `ScoreReport` + its runs/tasks/profile (incl. provider, model, agent, base_image, isolation fields, both token streams); `latest_report` returns the most recent; only `store/` imports sqlite. |
| `report/render.py` | Prints signed Δ colored by sign, variance, per-task table, all `*_warning`s, cost with the right confidence qualifier, PRIMER overhead on a separate line; a `None` delta prints the refusal reason, never a fabricated number; performs no computation. |
| `cli.py` | `pip install -e .` then `primer init .` and `primer eval .` run end-to-end on a fixture repo from a clean shell and persist a `ScoreReport`; `primer report .` renders it; all three exit 0; honest refusal (too few tasks / ineligible repo) exits non-zero with a clear message. |

**Phase-level gate (matches Session 1 §5):** Phase 3 (`runner` isolation acceptance test) is the
single most important gate — it must pass before any reporting/CLI polish is trusted.
