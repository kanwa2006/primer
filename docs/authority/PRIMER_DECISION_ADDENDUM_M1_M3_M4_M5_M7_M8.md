# PRIMER — DECISION ADDENDUM (M1, M3, M4, M5, M7, M8)

> Status: **PROPOSED → adopt to LOCK.** Authority: subordinate to **Session 1 Final Revision**
> (source of truth) and consistent with **Session 2 Architecture Blueprint**. Where the older
> **Opus 4.8 Master Prompt** conflicts, it yields. Scope: resolves six decisions Session 1 left
> open or under-specified. **No architecture redesign**; each ruling is a refinement that lives
> inside the existing module boundaries and specs (A–D, Q1–Q10, AD-1…AD-5).

---

## QUICK REFERENCE

### T1 — Config & spec deltas

| Item | Was | Now (this addendum) | Where it binds |
|---|---|---|---|
| `primer_eval_timeout_s` | Session 2: `300`; Session 1: silent | **`600`** (per-run); `docker_client_timeout_s = 630` | `config.py` value (Phase 0); exercised Phase 3 |
| `base_image` stored value | Spec A example + Session 2 default = a **tag** | **resolved `sha256` digest** stored in `RunResult.base_image` / `reports.base_image`; eval image built `FROM` the digest | `images.py` resolve + runner record + scorer uniformity (Phase 3) |
| `init` output filename | Session 2 §6: hardcoded `AGENTS.md` | **configured `adapter.context_filename()`** (`CLAUDE.md` for default) | filename-agnostic `generate/`; name chosen at `init` write site |
| ClaudeCodeAdapter `--bare` | Master Prompt: use `--bare` both arms | **no `--bare`**; flags identical both arms; file controlled on disk; `--bare` use gated by smoke test | adapter `build_invocation()` (Phase 3) |
| Report headline honesty | "signed delta + variance" | add render-time **within-noise verdict label**; per-task flips are the primary signal | scorer populates variance (Phase 3); render label (Phase 4) |
| "$0 end-to-end / no API keys" claim | Master Prompt asserts it | **scoped to "$0 file *generation* via local Ollama"**; MVP *eval* requires Anthropic key + cost | positioning doc (non-code) |

### T2 — Phase-blocking matrix

| Decision | Phase 0 | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|---|---|---|---|---|---|
| **M1** timeout=600 | set config default | — | — | **exercised** | — |
| **M3** power policy | — | — | — | **scorer variance/per-task (already specced)** | **render verdict label** |
| **M4** `--bare`/validity | — | — | — | **smoke-test gate (blocking)** | — |
| **M5** digest pinning | readable default | — | — | **resolve + store + uniformity check** | — |
| **M7** init filename | — | — | **filename-agnostic generation + name from adapter** | — | `init` CLI write |
| **M8** Ollama/isolation | — | — | **confirms Layer-1 (host-side)** | — | — *(positioning doc; Post-MVP sidecar)* |

### T3 — Build-confirm items carried forward (Context7 / Claude in Chrome / smoke test)

- **M4:** does `--bare` suppress the CWD `CLAUDE.md`/`AGENTS.md` read? → fingerprint probes A/B/C (Phase-3 gate).
- **M4:** WITH-arm actually reads the file (harness-validity fingerprint) → standing Phase-3 gate; abort, don't report, on failure.
- **M5:** digest resolution path; capture platform/arch the image ran under.
- Carried from Session 1: Claude Code honors `HTTPS_PROXY` (Open Issue #5); `query.captures()` shape (0.22→0.25); `total_cost_usd` vs `cost_usd`; Claude model id stability; `--permission-mode` semantics.

---

## DECISION RECORDS

### M1 — Default eval timeout

**Ruling.** `primer_eval_timeout_s = 600` per-run (update Session 2's `300`). `docker_client_timeout_s = eval_timeout_s + 30 = 630` (Spec D unchanged). Env-configurable.

**Rationale.** A false timeout is the dangerous direction for a measurement tool: a merely-slow agent is recorded `passed=False, timeout=True`, polluting success with infra noise, and the truncation can be **asymmetric across arms** (WITH-file often processes more context) — a direct confound. A higher ceiling does not slow typical runs (a run ends when the agent finishes); it only bounds genuine hangs. Deps are pre-baked (AD-2), so the budget is agent-loop + `verify_cmd` only. Matches the Master Prompt's 600s; no conflict.

**Impact.** One config default. Recommend the report surface a timed-out-run count (uses existing `RunResult.timeout`).

**Blocks.** Phase 3 (value set in Phase 0 config, exercised in Phase 3).

---

### M3 — Statistical-power policy

**Ruling.** MVP reports a **directional** signed success + cost delta, always with variance and an explicit honesty label — not a precision instrument for sub-resolution effects.
1. **Per-task flips are the primary signal** (existing `per_task` table); the aggregate is a coarse summary.
2. **State the quantization:** at temp 0, within-task runs are highly correlated, so practical aggregate resolution ≈ **1/n_tasks** (≈20 pts at 5 tasks; ≈33 pts at the 3-task floor), not 1/(n_tasks·runs). Print the grid; never imply finer precision.
3. **`runs_per_config=3` is for flakiness detection**, not aggregate power.
4. **Within-noise label:** flag the headline when **|success_delta| ≤ max(1/n_tasks, success_stddev)** as "within measurement noise — not distinguishable from zero"; escalate to "driven by flaky task(s)" if the contributing flips are flaky.
5. **No brute-force power:** resolving ≤5-pt effects would need hundreds of paid runs/arm — infeasible and out of scope. `min_tasks=3` remains the eligibility floor only.

**Rationale.** The biggest threat is a green "+X%" that is noise. At temp 0 the aggregate is quantized to 1/n_tasks, so a true +5-pt effect is unrepresentable (shows as 0 or as one ≈20-pt task flip). Variance alone surfaces spread but doesn't stop misreading; a naive CI/p-value at this N (and under within-task correlation) is false precision. The policy operationalizes Session 1 Q3 (measure, don't prove).

**Impact.** **No schema change.** `per_task`, flaky flags, `success_stddev/min/max`, `flaky_task_warning` already exist. The verdict is a **render-time classification** from numbers the scorer already emits (same class as the sanctioned sign→color rule), so `report/` adds no aggregation. *Sign-off option:* persisting the verdict = one new `*_warning`-style field (in-pattern, not a redesign); not assumed.

**Blocks.** Phase 3 (scorer variance/per-task — already specced) and Phase 4 (render label). Eligibility floor in Phase 3 tasks/preflight.

---

### M4 — Claude Code `--bare` risk + validation strategy

**Ruling.** Control the with/without distinction **only** at the filesystem (presence of `context_filename()` in `/work`), with **flags identical across arms** (Spec B-8, AD-4). **Default to no `--bare`** (Session 2 already omits it). The WITHOUT arm's cleanliness comes from the runner (fresh clone → assert no context file), not a flag. Any future `--bare` use is gated by the smoke test below.

**Rationale.** If Session 1 §1.4 is right that `--bare` skips CLAUDE.md discovery, using it on the WITH arm would also nuke PRIMER's file → both arms read nothing → **fabricated zero delta** (worst failure mode). The principle is answer-independent: never make a coarse flag's discovery side-effect carry the one variable under test. Container hardening already removes what `--bare` suppresses (host skills/hooks/MCP/`~/.claude`), making it redundant and potentially harmful. The deeper check this surfaces: **"did the WITH arm actually read the file?"** — the silent cause of every fabricated zero.

**Validation strategy (Phase-3 gate).** Plant a uniquely-detectable instruction in the context file (operationalizes §1.6 "agents follow instructions"):
- **A** (file present, no `--bare`): confirm the agent obeyed it (fingerprint present) → read path works / harness valid.
- **B** (file present, with `--bare`): fingerprint gone → `--bare` suppresses CWD files → lock adapter to no-`--bare`. Fingerprint persists → `--bare` safe but redundant; default-off stands.
- **C** (file absent): no fingerprint → WITHOUT arm reads nothing.
A/C are a standing harness-validity gate: if A fails, abort — do not report.

**Impact.** Invocation stays `claude -p "<prompt>" --output-format json --permission-mode bypassPermissions` (identical both arms). Add probes to `test_runner_isolation.py`. `--bare` semantics, JSON fields, `--permission-mode` remain build-confirm items.

**Blocks.** Phase 3 (part of the runner-isolation gate).

---

### M5 — Docker image digest pinning

**Ruling.** Config carries a readable tag for UX; the runner **resolves it to a `sha256` digest at build time and stores the digest** in `RunResult.base_image` / `reports.base_image`. The eval image is built `FROM` the resolved digest so all runs in a report share one immutable base. Source is never baked into a layer (AD-2, reaffirmed).

**Rationale.** Reproducibility is a stated priority and `base_image` exists to be the reproducibility anchor; a mutable tag leaks drift. Session 1's field is `base_image: str` with a tag only as an example — a digest does not contradict it and advances its goal (and matches the Master Prompt). Digests also make the AD-5 "uniform `base_image`?" check meaningful (a tag can change between pulls mid-matrix; a digest cannot).

**Impact.** `docker_base_image` stays a readable tag (consider a patch-pinned tag for clarity). `images.build_eval_image()` resolves and records the platform-resolved digest; runner writes it to every `RunResult`; scorer compares digests. No new field. *Follow-up:* capture platform/arch so cross-arch comparisons are flagged.

**Blocks.** Phase 0 (readable default) + Phase 3 (resolution/storage/uniformity).

---

### M7 — `init` filename policy

**Ruling.** `primer init` writes the filename from the **configured agent adapter's `context_filename()`** — `CLAUDE.md` for the default `ClaudeCodeAdapter`, `AGENTS.md` for AGENTS.md-standard adapters (GEMINI.md for a future Gemini adapter; confirm at build per §1.7). Refines Session 2 §6 and aligns `init` with the eval, which already uses `context_filename()`.

**Rationale.** `init` produces a file the user commits for *their* agent; the wrong name means the agent never reads it. The adapter already encodes "which filename does this agent read," so reusing it makes the file `init` emits the same file `eval` measures. Session 1 §1.7 ("write the right filename per adapter") outranks Session 2 §6's literal `AGENTS.md`.

**Impact.** Keep `generate.write_context()` filename-agnostic; choose the physical name from `get_adapter(config.primer_agent).context_filename()` at the `init` write site instead of hardcoding `AGENTS.md` in `GenerationResult.filename`. Add a safe-write guard (don't clobber an existing file). *Interaction flagged (defer to the eligibility-predicate decision):* a user who commits the `init`-written file then runs `eval` would hit the ClaudeCodeAdapter "reject committed context file" guard, even though the runner normalizes the file per arm — resolve in the eligibility decision, not here.

**Blocks.** Phase 2 (filename-agnostic generation) + `init` CLI command. Not Phase 0/1/3.

---

### M8 — Local Ollama evaluation vs the isolation model

**Ruling.**
1. **Layer-1 Ollama (generation brain): supported in MVP, compatible with isolation.** Runs on the host in the PRIMER process, outside the eval container; `OLLAMA_BASE_URL` never touches the container network. `cost_confidence="free"`, renders "local (no cost)". This is the real $0 *generation* path.
2. **Layer-2 local agent (agent under test): NOT in MVP.** MVP ships only `ClaudeCodeAdapter`, which calls `api.anthropic.com` and costs money.
3. **Correct the claim:** scope "$0 / no API keys" to **"$0 file generation via local Ollama."** MVP measurement requires an Anthropic key + cost. (Session 1 #2 "document Ollama/Qwen as the $0 path" = documented, not shipped.)
4. **Post-MVP local-agent pattern (specify, build nothing):** a **model sidecar on `primer-internal`** (like the egress-proxy sidecar) lets the agent reach the model over the internal network with **no external egress** → `network_mode="offline"` (more isolated). Open constraints for then: model-weights provisioning (a reviewed, scoped mount exception on the *model* container only, never the eval container); GPU passthrough on the *sidecar* (eval container keeps `cap_drop=["ALL"]`); distinct from the eligibility rule rejecting repos whose *tests* need a GPU.

**Rationale.** The confusion conflates "generate with a local model" (host-side, trivially compatible) with "evaluate a local agent" (in-container, blocked by the internal-only network reaching `localhost:11434`). Spec B is built around exactly one external API host = the ClaudeCodeAdapter case, and works as-is for the MVP. Local-agent is additive (offline sidecar), not a redesign. The only required change today is the **claim** — asserting "$0 end-to-end" for an MVP whose measurement step costs money violates the harness's honesty doctrine.

**Impact.** `ollama_base_url` / `ollama_model` confirmed as host-side Layer-1 knobs; no MVP change. Fix is a **non-code** positioning correction. Sidecar/offline mode is a Post-MVP spec note.

**Blocks.** Nothing in MVP phases. Confirms Phase 2 Layer-1 Ollama. Positioning doc must be corrected.

---

## SUPERSESSION MAP (keeps the three documents consistent)

| This addendum | Refines / supersedes |
|---|---|
| M1 (600s) | Sets the value Session 1 left open; updates Session 2 `config.py` default `300→600`; agrees with Master Prompt §Moat (600s). |
| M3 (power policy) | Operationalizes Session 1 Q3; adds a render-time honesty label within Session 2's existing fields. |
| M4 (no `--bare`) | Adopts Session 2's ClaudeCodeAdapter (no `--bare`); **supersedes** Master Prompt's `--bare`-both-arms instruction. |
| M5 (digest) | Specializes Spec A's `base_image` example (tag) into a digest; agrees with Master Prompt "pin by digest." |
| M7 (adapter filename) | Applies Session 1 §1.7 mapping; **refines** Session 2 §6 ("writes AGENTS.md"). |
| M8 (scope $0 to generation) | Honors Session 1 #2 ("document the $0 path") while **correcting** the Master Prompt "$0 end-to-end / no API keys" claim for the MVP. |

**Unchanged and still governing:** Specs A–D, Q1–Q10, AD-1…AD-5, the module DAG, the two-token-stream rule, refuse-on-mismatch, and the honest-refusal floor.
