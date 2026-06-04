# PRIMER — SESSION 1 FINAL REVISION (Decision Record)

> Status: **LOCKED**. This is the authoritative decision record. Session 2 (Architecture
> Blueprint) and Session 3 (Sonnet Execution Prompt) derive from this file and must not
> contradict it. Architect: Opus 4.8. Engineer: Sonnet 4.6.

---

## REVISION CHANGELOG (what changed since the original Session 1)

1. **Network isolation rewritten.** `network_disabled=True` is **removed everywhere**. Replaced
   with a **proxy-based egress allowlist** (internal Docker network + deny-by-default egress proxy
   sidecar). See **Spec B**. `RunResult` gains isolation/reproducibility fields. See **Spec A**.
2. **Task generation locked to deterministic, no-LLM heuristics**, two task types only:
   `revert_reimplement` (primary) + `stub_function` (fallback/top-up). `add_test` is **excluded**
   from MVP. Mandatory pre-flight validation + honest refusal below 3 tasks. See **Spec C**.
3. **Docker timeout handling locked** to the `requests.exceptions.ReadTimeout` pattern with a
   `from_env(timeout = eval_timeout_s + 30)` client buffer and defensive cleanup. See **Spec D**.

The fabricated **"41% → 68%"** headline remains **deleted** — it contradicts the evidence.

---

## BOTTOM LINE

Build PRIMER as a **Phases 0–4 MVP** (scaffold/security → repo map → lean AGENTS.md → Dockerized
before/after eval → minimal text report). Phases 5–8 are deferrable or removable. PRIMER's honest
value proposition is a **measurement harness**: it tells a repo owner whether their AGENTS.md helps
or hurts, and by how much, with a **trustworthy signed delta that is frequently ~0 or negative**.
The eval harness is the moat; generation is commoditized.

---

## 1. TOOL RESEARCH FINDINGS (verified; re-confirm ⚠️ items with Context7 at build)

**1.1 py-tree-sitter — ⚠️ original prompt was outdated.**
Current **0.25.x**; API changed at **v0.22**. `Language.build_library(...)` and `Parser.set_language()`
are **gone**. Correct current usage: `PY_LANGUAGE = Language(tspython.language())`;
`parser = Parser(PY_LANGUAGE)`; `tree = parser.parse(bytes(src, "utf8"))`; query via
`PY_LANGUAGE.query("(function_definition name:(identifier) @fn)")`. Install one wheel per language
(`tree-sitter-python`, `tree-sitter-javascript`, …); `tree-sitter-languages` (grantjenks) is
unmaintained — successor is `tree-sitter-language-pack`. **MVP: individual `tree-sitter-<lang>`
wheels.** ⚠️ Confirm `query.captures()` return shape against the pinned version (tuple-list vs dict
varies 0.22→0.25).

**1.2 docker-py — mostly correct, one critical gotcha (now load-bearing).**
`docker.from_env()`, `client.containers.run(image, command, detach=True, ...)` confirmed (7.1.0).
`container.wait()` returns `{'StatusCode': int, ...}`. **`container.wait(timeout=N)` does NOT return
a sentinel — it RAISES `requests.exceptions.ReadTimeout`.** `auto_remove=True` races `wait()` —
**do NOT use it**; remove explicitly in `finally`. Resource limits: `mem_limit`, `nano_cpus`,
`pids_limit`. `container.kill()` / `container.remove(force=True)` confirmed. `docker.from_env(timeout=…)`
sets the global HTTP read timeout — must sit **above** the eval timeout. See **Spec D**.

**1.3 Typer — correct.** `@app.command()`, `typer.Argument/Option`, `CliRunner`. ⚠️ Pin Click;
`mix_stderr`/`result.stderr` behavior varies by Click version.

**1.4 Claude Code CLI (headless) — ⚠️ verify JSON field names.**
`-p`/`--print` = headless. `--output-format json` (also `text`, `stream-json`). Cost field is
**`total_cost_usd`** (read with fallback to legacy `cost_usd`); JSON also has `usage`, `duration_ms`,
`num_turns`, `session_id`, `result`, `is_error`. Working dir = launch CWD → **launch with `cwd=<repo>`
inside the container** (no stable `--cwd`; `--add-dir` does not change primary CWD). `--bare` skips
auto-discovery of hooks/skills/MCP/CLAUDE.md. Non-interactive runs need `--permission-mode`
(e.g. `bypassPermissions`) / `--allowedTools`. Exit codes: `0` ok, `1` generic, `2` auth — also check
`is_error`. **Note:** Claude Code reads `CLAUDE.md` from CWD natively; the adapter writes PRIMER's
file under the name the agent reads (see Session 2 §8).

**1.5 Anthropic SDK — correct; caching is effectively GA.**
`anthropic ≥0.79`; `client.messages.create(...)` / `.stream(...)`. Prompt caching needs no
`anthropic-beta` header anymore (`"cache_control": {"type": "ephemeral"}`). Usage fields:
`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`.
**Min cacheable prefix is 1,024 tokens (Sonnet) — a 10–20-line AGENTS.md is far below it, so caching
the file is a no-op. Do NOT build a prompt-cache layer for the MVP (Q9a).**

**1.6 ETH Zurich study — VERIFIED (independently re-checked this session).**
"Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?", Gloaguen,
Mündler, Müller, Raychev, Vechev — ETH Zurich (SRI Lab) + LogicStar.ai, **arXiv:2602.11988**,
**submitted 12 Feb 2026** (corrected from "Feb 13"). Findings: LLM-generated context files **reduce**
task success in **5 of 8 settings** (avg **−0.5%** SWE-bench Lite, **−2%** AGENTbench; cross-benchmark
headline **−3% LLM-generated vs +4% developer-written**) while **raising inference cost >20%**
(**+20%** SWE-bench Lite, **+23%** AGENTbench; developer-written **+19%**). Ablation: with all other
docs removed, LLM files **improve +2.7%** → they are mostly **redundant** with docs the agent already
reads. Behavioral lever: agents follow instructions (e.g. mentioning `uv` → ~160× more `uv` use), but
the instructions are usually redundant. The paper's own conclusion — *human files should describe only
minimal requirements* — directly endorses the **lean-AGENTS.md** thesis. **Absolute per-condition
baselines are unpublished (Fig. 3 only) → PRIMER never quotes an absolute baseline; it reports only
its own measured deltas.**

---

## 2. LOCKED DECISIONS (Q1–Q10 decision record)

| # | Decision | Ruling |
|---|----------|--------|
| **Q1** | Eval parallelism | **Sequential for MVP.** Paired before/after of the *same* task is **never** parallelised (resource contention → noisy timing → untrustworthy). If ever added Post-MVP: across *different* tasks only, capped at `min(cpu_count, 3)`. |
| **Q2** | Flaky-test policy | If `verify_cmd` fails on first run, **retry once after 5s**. Fail-twice → `passed=False, flaky=False`. Fail-then-pass → `passed=True, flaky=True` + warning. Flaky runs are scored but annotated in the report. |
| **Q3** | Honest expectation / task difficulty | A good **curated** file realistically yields **0 to +5 points**; auto-generated can be **negative**. Design to *measure*, never to "prove it helps." (Task-type strategy is **superseded by Decision 2 / Spec C** this session.) |
| **Q5** | Badge infra | **Zero paid infra.** CI writes `scores.json` to `gh-pages`; README uses a **shields.io endpoint badge**. Schema: `{schemaVersion, label, message, color}`. Color: green Δ>0, yellow ~0, red Δ<0. |
| **Q7** | Deps + env vars | Single source of truth = `pyproject.toml` + `.env.example` (Phase 0). All `PRIMER_*` / `*_API_KEY` read via `pydantic-settings`. Never hardcode. |
| **Q8** | Tools per phase | See §4 table. |
| **Q9** | Cost confidence | (a) No prompt-cache layer (file too small to cache). (b) Per-provider `cost_confidence`: anthropic/gemini **exact**, openai **estimated→exact**, openrouter **estimated**, ollama **free**. (c) Ollama output validation: empty/<20 chars → retry once → `OllamaOutputError`. (d) **Refuse to compute a delta on provider/model mismatch** across the compared runs — report per-config but set the delta to `None` with a warning. |
| **Q10** | Key-leak paths | Three guarded paths: (a) process/agent **logs** → `log_safe()` redaction; (b) Docker **container env** → one key via `--env` only; (c) committing **`.env`/hardcoded keys** → gitleaks + detect-secrets pre-commit, Phase 0 step 1. |

**Scope guardrails (REMOVE list):** rule-based fallback generator, parallel eval, prompt-cache layer,
and any NIST/"compliance" features are **out of scope** — they don't serve a trustworthy Phases 0–4 score.

---

## 3. NON-NEGOTIABLE SECURITY RULES

1. **Pre-commit hook is Phase 0, step 1.** gitleaks + detect-secrets installed **before any other file
   is created.** `.env` in `.gitignore`; `.env.example` ships empty placeholders only.
2. **No vendor SDK imports outside `primer/llm/`.** Any `import anthropic|openai|google.generativeai`
   elsewhere is an **architecture violation** (enforced by a test). All LLM calls go through
   `get_provider()` from `primer/llm/factory.py`.
3. **Eval containers receive keys via `--env` only** — never in Dockerfiles, build args, or image
   layers. Inject **only the one key the in-container agent needs** (e.g. `ANTHROPIC_API_KEY` for
   Claude Code), never PRIMER's other keys. Combine with the **egress allowlist** (Spec B) +
   `cap_drop=["ALL"]` + `no-new-privileges`.
4. **`log_safe()` lives on the `LLMProvider` base class.** All LLM log output is sanitized
   (`sk-…`, `sk-ant-…`, `AIza…` → `[REDACTED]`) before writing. Never log full `os.environ`. Redact
   `raw_output` before persisting to SQLite.

---

## 4. TOOLS PER PHASE

| Phase | Tool | When | What to do |
|------|------|------|-----------|
| 0 — Scaffold | Typer | First CLI entrypoint | `app = typer.Typer()`; stub `init/eval/report`. |
| 0 | pre-commit + gitleaks + detect-secrets | Repo init, **before any secret can be committed** | Install hooks; scan every commit; `.env` in `.gitignore`. |
| 0 | pydantic-settings | Loading config | Read all `PRIMER_*`/`*_API_KEY` from env; validate selected provider+agent keys present. |
| 0 | Context7 | Before pinning versions | Confirm `tree-sitter`, `anthropic`, `docker`, `typer` versions/APIs. |
| 1 — Repo map | tree-sitter + `tree-sitter-<lang>` | Walking the repo | `Language(...lang())`; `Parser(LANG)`; extract fns/classes/imports via queries. **No LLM.** |
| 1 | rich | Printing the map/summary | Tree/summary; no network. |
| 2 — Generate | LLMProvider (Layer 1) | After map, to draft the file | Send profile → LEAN ≤20-line file (commands, non-obvious conventions, internal APIs — NOT architecture prose). **One LLM call.** |
| 2 | Ollama (`requests`→`OLLAMA_BASE_URL`) | `PRIMER_LLM_PROVIDER=ollama` | POST to local model; validate (Q9c); retry once → fail. |
| 3 — Eval (moat) | docker (docker-py) | Each task × {with, without} | Build per-repo image once; **fresh container per run**; internal net + egress proxy; `wait(timeout)` try/except ReadTimeout → kill; `finally` remove + rmtree. |
| 3 | AgentAdapter (Layer 2) | Inside each run | Supply agent invocation (`-p --output-format json --permission-mode bypassPermissions`, `cwd=repo`) + parse usage → `AgentTelemetry`. |
| 3 | verify_cmd (in-container) | Final command of the container | Exit code = sole pass/fail. |
| 3 | sqlite3 | After each container exits | Insert `RunResult` incl. provider, model, agent, base_image, isolation fields, both token streams. |
| 4 — Report | rich | After all runs | Signed Δ + variance + cost (with confidence) + per-task + flaky/mismatch warnings + PRIMER overhead (separate). |
| 5 | openai / google-generativeai / OpenRouter | Non-Anthropic provider selected | Implement `parse_usage()` setting `cost_confidence` per Q9b. **Post-MVP.** |
| 6 | sqlite3 (+ aiosqlite if async) | History/compare | `primer history`, `primer compare`. **Post-MVP.** |
| 7 | Next.js + GitHub Pages + shields.io | Publish results | Static export; `scores.json`; endpoint badge. **Nice-to-Have.** |
| 8 | GitHub Actions | Push/PR + cron | Re-eval, refresh file + `scores.json`, gate PR on regression. **Nice-to-Have.** |

---

## 5. PHASE CLASSIFICATION (anti-scope-creep)

| Phase | Classification | Rationale |
|------|----------------|-----------|
| 0 — Scaffold, config, security, deps | **MVP Required** | Nothing runs without it; security precedes code. |
| 1 — Repo map (tree-sitter) | **MVP Required** | Feeds generation; half the user-facing output. |
| 2 — AGENTS.md generation | **MVP Required** | The artifact under test. |
| 3 — Dockerized before/after eval + token accounting | **MVP Required** | This *is* the product. |
| 4 — Reporting (rich, text-only) | **MVP Required (minimal)** | Makes the number usable. |
| 5 — Full multi-provider matrix | **Post-MVP** | Ship with Anthropic provider + ClaudeCode adapter (+ Ollama $0). Interfaces exist day 1; extra implementations later. |
| 6 — SQLite history/compare CLI | **Post-MVP** | Storing rows is MVP; query UX is Post-MVP. |
| 7 — Next.js scorecard + Pages + badge | **Nice-to-Have** | Presentation; 1-file JSON + static badge is a stopgap. |
| 8 — GitHub Actions CI gate | **Nice-to-Have** | Valuable for adopters; not needed to prove the tool works. |

---

# LOCKED ENGINEERING SPECS (this revision)

## SPEC A — `RunResult` with isolation / reproducibility fields

```python
@dataclass
class RunResult:
    # --- identity / outcome ---
    task_id: str
    passed: bool
    timeout: bool
    flaky: bool
    with_context: bool
    # --- eval-agent COST STREAM (the agent's in-container tokens; feeds the before/after delta) ---
    agent_adapter: str            # e.g. "claude_code"
    agent_tokens: int
    iterations: int
    duration_s: float
    cost_usd: float
    cost_confidence: str          # "exact" | "estimated" | "free"
    # --- PRIMER-brain provenance (which provider/model GENERATED the file under test) ---
    provider: str                 # e.g. "anthropic"
    model: str                    # e.g. "claude-sonnet-4-6"
    # --- isolation + reproducibility audit trail ---
    base_image: str               # exact image, e.g. "python:3.11-slim"
    repo_commit: str              # repo SHA the eval ran against (reproducibility anchor)
    network_mode: str             # "proxy-egress" | "open-bridge" | "offline"
    egress_allowed_host: str | None   # single permitted host; None if open/offline
    egress_enforced: bool         # True ONLY if a deny-by-default egress proxy was active.
                                  # HONESTY GATE: a ScoreReport may claim "egress-restricted"
                                  # only if EVERY constituent run has egress_enforced=True.
    caps_dropped: bool            # True if cap_drop=["ALL"] + no-new-privileges applied
    container_id: str
    agent_log_path: str           # path to the REDACTED agent log on disk
    run_timestamp: str            # ISO-8601 UTC
```

`network_mode`, `egress_enforced`, `base_image`, `repo_commit` propagate to `ScoreReport`; if not
uniform across the runs in a report, set `isolation_mismatch_warning`.

---

## SPEC B — `runner.py` isolation requirements (replaces all `network_disabled=True` items)

**Mechanism note (build-time fact):** docker-py has **no kwarg that filters egress by hostname**.
The allowlist is therefore enforced by a **deny-by-default egress proxy sidecar**, not by a run flag.

```
ISOLATION REQUIREMENTS (every one mandatory):
 1. Clone the repo to a fresh temp dir on the host; record the checked-out SHA → repo_commit.
 2. Create a per-run network `primer-internal` with internal=True (NO external route).
 3. Start a deny-by-default egress proxy on primer-internal, ALSO connected to the default bridge
    (the proxy is the ONLY thing with an outbound leg). Proxy allows CONNECT to
    {PRIMER_AGENT_API_HOST}:443 ONLY; everything else denied.
 4. Start the eval container on primer-internal ONLY (no bridge → no direct internet). Set
    HTTPS_PROXY/HTTP_PROXY to the proxy; NO_PROXY=localhost,127.0.0.1.
 5. Inject ONLY the one key the agent needs (e.g. ANTHROPIC_API_KEY) via environment.
    Never PRIMER's other keys. Never write keys to any file inside the container.
 6. Harden the eval container: cap_drop=["ALL"], security_opt=["no-new-privileges:true"],
    mem_limit (default 2g — 512m is too small once a real agent runs), nano_cpus, pids_limit.
 7. Mount ONLY the temp dir (rw) as the working dir. No other host paths, no named volumes.
 8. with_context=True → write the agent's context file into the mount before start;
    False → guarantee none exists. (Flags are IDENTICAL across arms — the only difference is the file.)
 9. The container command MUST end with verify_cmd so wait()['StatusCode'] is the pass/fail code.
    Shape: sh -c '<agent argv> > /work/.primer_agent.log 2>&1 ; <verify_cmd>'
10. TIMEOUT + CLEANUP: see Spec D. Read+redact the agent log to agent_log_path BEFORE rmtree.
11. Set egress_enforced=True and network_mode="proxy-egress" ONLY when steps 2–4 succeeded.
    Open-bridge fallback → egress_enforced=False, network_mode="open-bridge", and the documented
    isolation string MUST drop "egress restricted."
12. Post-run audit: `docker ps -a` must show no container with this run's id (assert empty).

DO NOT: network_disabled=True (breaks the agent's API call), auto_remove=True (races wait()),
host networking, or any host mount beyond the task temp dir.
```

**Documented isolation model (proxy-egress mode):**
> "Fresh container + fresh repo copy + no host environment access + no shared volumes + internal
> network with egress restricted to the agent's required API host."

**Build-time risk to verify (Context7 / smoke test):** the agent CLI must honor `HTTPS_PROXY`
(Claude Code is a Node CLI and is expected to). If it ignores proxy env, fall back to a transparent
proxy (iptables redirect) — record as an open issue, do not silently set `egress_enforced=True`.

**New config keys:** `primer_agent_api_host: str = "api.anthropic.com"`, `proxy_image: str`.

---

## SPEC C — `derive_tasks()` heuristic spec (no LLM; deterministic) + fallback

```
def derive_tasks(profile: RepoProfile, repo_path: str,
                 n: int = 5, min_tasks: int = 3, seed: int = 0) -> list[Task]: ...

INVARIANT (every emitted Task satisfies ALL three):
  • At task START state, verify_cmd exits NON-ZERO (a real gap to close).
  • A correct change makes verify_cmd exit ZERO.
  • verify_cmd is the repo's own test runner; exit code is the SOLE pass/fail criterion.
No LLM calls. Deterministic: same repo SHA + same seed → identical task list.

TASK TYPES (priority order):
  Type 1 — revert_reimplement (PRIMARY):
    Scan the last ~200 commits (NOT a 30-day window). Keep a commit iff it touches exactly one
    non-test source file AND an existing test covers that change AND the source diff is small
    (≤ ~40 changed lines). Revert ONLY the source change → the covering test now fails.
    verify_cmd = that test. Rank deterministically (recency, then SHA).
  Type 2 — stub_function (FALLBACK / top-up; no git history needed):
    Find a function covered by an existing passing test; replace its body with
    `raise NotImplementedError`. verify_cmd = the covering test. Works on ANY repo with a passing
    test suite + coverage → this is what guarantees reaching n.
  (add_test is EXCLUDED from MVP: verify_cmd would be the agent's own test → gameable and
   non-deterministic. Revisit only with a fixed hidden test.)

PRE-FLIGHT VALIDATION (mandatory, in a throwaway checkout/container, before a task is used):
  1. Known-good state → verify_cmd PASSES, run 3× consistently (discard if flaky).
  2. Broken/start state → verify_cmd FAILS.
  Discard any candidate that fails either check.

SELECTION: generate Type 1 first; top up with Type 2 until len(tasks) == n (default 5).

FALLBACK RULE (below the floor — never pad to hit a count):
  If validated tasks < min_tasks (default 3):
    raise InsufficientTasksError / mark repo INELIGIBLE with:
    "PRIMER derived only {k} deterministic, test-backed task(s); a trustworthy before/after delta
     needs at least {min_tasks}. This repo isn't eligible — it likely lacks an existing passing
     test suite. Add tests, or point PRIMER at a repo that has them."
  An honest refusal beats a number computed from too few (or no-op) tasks.
```

**Why Priority 1 from the earlier draft was dropped:** running an *already-passing* test is a no-op
task (passes with and without the file → a fabricated zero-delta, the worst failure mode). A real
task must have a **failing start state**; revert and stub both guarantee that.

---

## SPEC D — Docker timeout handling (locked, exact)

```
client = docker.from_env(timeout = config.eval_timeout_s + 30)   # client read timeout > eval timeout

try:
    result = container.wait(timeout=config.eval_timeout_s)
    exit_code = result["StatusCode"]
    passed = (exit_code == 0)
except requests.exceptions.ReadTimeout:
    try:
        container.kill()
    except (docker.errors.APIError, docker.errors.NotFound):
        pass                              # container may have died between timeout and kill
    passed, timeout = False, True
finally:
    # read + redact the agent log BEFORE deleting the temp dir
    try:
        container.remove(force=True)
    except docker.errors.NotFound:
        pass
    try:
        proxy.remove(force=True)
    except docker.errors.NotFound:
        pass
    client.networks.get("primer-internal").remove()
    shutil.rmtree(temp_dir, ignore_errors=True)
```

**Budget note:** `eval_timeout_s` covers the **whole** container run. Because per-repo deps are
**pre-baked into the eval image** (Session 2 §7), `pip install` does **not** run inside this budget.
The container command must **end with `verify_cmd`** so the captured exit code is the pass/fail signal.

---

## 6. GENUINE OPEN ISSUES (carry into build)

1. **Absolute baselines unpublished** → never quote one; report only PRIMER's own deltas. *(resolved policy)*
2. **Default eval agent** = ClaudeCodeAdapter (best-documented; costs money). Document Ollama/Qwen as the $0 path. *(resolved)*
3. **Claude model id + JSON field stability** (`total_cost_usd` vs `cost_usd`, `claude-sonnet-4-x`) — re-confirm at build.
4. **tree-sitter `query.captures()` shape** (0.22→0.25) — confirm against the pinned version.
5. **Proxy honors `HTTPS_PROXY`?** — smoke-test Claude Code through the proxy before trusting `egress_enforced=True`.
6. **Repo eligibility** — repos needing network/DB/GPU/long builds, or with no passing test suite, are auto-rejected by pre-flight; document this scope limit.
