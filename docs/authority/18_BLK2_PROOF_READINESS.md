# BLK-2 Proof Readiness

**Date:** 2026-06-12
**Branch:** `v3-execution`
**Status:** Implementation complete (G-1…G-7 PASS). Live proof (G-6, G-8, G-9) BLOCKED on `ANTHROPIC_API_KEY`.
**Authority basis:** `16_BLK2_SPECIFICATION.md`, `17_BLK2_COMPLETION_REPORT.md`, `09_BLK1_PROOF_REPORT.md`,
`12_BLK2_READINESS_ASSESSMENT.md`, BLK-2 Pre-Proof Consistency Review, Shell Quoting Analysis,
Shell Quoting Fix Completion Report.

**Purpose:** Capture the exact proof procedure so a future session can execute the BLK-2 live proof
the moment an `ANTHROPIC_API_KEY` is available — without re-deriving the image, the gate semantics,
the invocation, or the pass/fail criteria. This document is the single-source runbook.

> This document is **procedure only**. It introduces no code, no test, and no schema change.
> Executing the proof requires Docker + API key and is explicitly **out of scope for the session that
> authored this file** (see constraints below).

---

## 1. Current Status Summary

| Item | State | Evidence |
|---|---|---|
| **BLK-2 implementation** | **COMPLETE** | `17_BLK2_COMPLETION_REPORT.md` §1–§4; 9 production files + 1 test file changed |
| **Offline acceptance gates (G-1…G-5, G-7)** | **PASS** | Completion report §4; `pytest tests/test_runner_isolation.py tests/test_scorer.py tests/test_arch_boundaries.py` → 59 passed, 1 skipped |
| **Execution-path bug (shell quoting)** | **FIXED** | `runner.py:144` (`_shell_quote` per-arg) + `runner.py:157` (`command=["sh","-c",sh_script]` list form). See §6 and the runner comment at `runner.py:146–151` |
| **Fingerprint gate wiring** | **COMPLETE** | Inject `runner.py:106–111`; check `runner.py:212`; abort `scorer.py` `score()` inner loop; field `models.py RunResult.harness_fingerprint_valid` |
| **Live proof (G-6, G-8, G-9)** | **BLOCKED** | Requires valid `ANTHROPIC_API_KEY`; live tests present and skip-gated at `test_runner_isolation.py:1304–1510` |
| **`FINGERPRINT_INSTRUCTION` text** | **PROVISIONAL — empirically unverified** | `claude_code.py:34–42`, marked `⚠️ [EMPIRICAL VERIFICATION REQUIRED]`; verified only by a live run |

### What "complete" means here

The gate is **architecturally operative**: it will correctly abort any eval where a WITH-arm run
returns `harness_fingerprint_valid is False`. What remains unproven is the **empirical claim** that the
provisional instruction text actually causes a live Claude Code 2.1.x agent to emit the marker
`primer_fingerprint_v1_acknowledged` into its log. That single fact is what the live proof establishes.

### Remaining blockers

1. **`ANTHROPIC_API_KEY` absent** — blocks G-6, G-8, G-9 (the only Docker+API gates).
2. **`FINGERPRINT_INSTRUCTION` empirically unverified** — the text at `claude_code.py:38–41` may not
   produce the marker. If it does not, the proof's Stage B fails at G-6 and the text must be revised
   per `16_BLK2_SPECIFICATION.md §4.4`, then re-run. This is the one outcome that can require a code edit.

---

## 2. Exact Prerequisites

All four must be satisfied **before** Stage A. The first three live tests are hard-gated on three env
vars (`test_runner_isolation.py:1304–1312`); missing any one silently skips the proof.

| Prerequisite | Required value | Why | Verify with |
|---|---|---|---|
| **`ANTHROPIC_API_KEY`** | A valid, funded key | The agent must complete a real API call inside the container | `echo $env:ANTHROPIC_API_KEY` (non-empty) |
| **Docker daemon** | Running, Linux containers | The eval runs in an isolated container on an internal-only network | `docker info` exits 0 |
| **`PRIMER_EVAL_IMAGE`** | The built eval image tag (see §3) | The live tests read the image tag from this env var (`test_runner_isolation.py:1371`) — they do **not** build it | `docker image inspect $env:PRIMER_EVAL_IMAGE` exits 0 |
| **`PRIMER_RUN_DOCKER_TESTS`** | `1` | Master switch for all Docker-touching tests | `echo $env:PRIMER_RUN_DOCKER_TESTS` → `1` |

### Image identity (from BLK-1 proof)

The image is produced by `primer/eval/images.py` with tag shape
`primer-eval-<repohash>-<agent>:<commit>` (`images.py:51`). The BLK-1 proof built and validated:

```
Tag:   primer-eval-b2efb5044c85-claude_code:4498309093b1
Base:  python:3.11-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0
Claude Code in image: 2.1.153
Binary path: /usr/bin/claude (on default PATH)
```

`<repohash>` = `sha1(abs_repo_path)[:12]` (`images.py:50`) — it is **machine/path-specific**. If the proof
runs on a different checkout path, the repohash differs and the image must be rebuilt; the tag you export
as `PRIMER_EVAL_IMAGE` must match whatever `build_eval_image()` actually produced.

### Pre-flight environment (PowerShell)

```powershell
$env:ANTHROPIC_API_KEY  = "<valid key>"
$env:PRIMER_RUN_DOCKER_TESTS = "1"
$env:PRIMER_EVAL_IMAGE  = "primer-eval-<repohash>-claude_code:<commit>"
```

---

## 3. Stage A — Image / Fingerprint Verification

**Goal:** confirm the eval image exists, the agent binary runs, and the *deterministic image fingerprint*
matches what the runner will use — **before** spending an API call.

### A.1 Procedure

1. **Resolve / build the image.** If `PRIMER_EVAL_IMAGE` is already a built tag, skip to A.2. Otherwise
   build it (this requires network to pull base + apt repo, but **no API key**):
   - The deterministic tag is `primer-eval-<sha1(abs_repo_path)[:12]>-claude_code:<repo_commit[:12]>`
     (`images.py:50–51`). `build_eval_image()` reuses an existing tag if present (`images.py:57–59`),
     so the fingerprint is stable across rebuilds at the same commit + path.
2. **Binary present (BLK-1 V1.1):**
   ```
   docker run --rm <PRIMER_EVAL_IMAGE> claude --version
   ```
   Expected: a version string (e.g. `2.1.153 (Claude Code)`), exit 0.
3. **Binary runs + emits JSON (BLK-1 V1.2):**
   ```
   docker run --rm -e ANTHROPIC_API_KEY="" <PRIMER_EVAL_IMAGE> \
     sh -c "claude --print 'hello' --output-format json --allowedTools none"
   ```
   Expected: well-formed JSON with `"is_error": true` and `"result": "Not logged in · Please run /login"`.
   This proves the binary executes under root and the JSON telemetry shape is intact, with **no** API key spent.

### A.2 Expected evidence

| Check | Expected | Meaning if seen |
|---|---|---|
| `docker image inspect $PRIMER_EVAL_IMAGE` | exit 0 | Image fingerprint resolved; tag matches runner's expectation |
| `claude --version` | version string, exit 0 | Binary provisioned on PATH (`/usr/bin/claude`) |
| `claude --print … (empty key)` | JSON, `is_error:true`, `Not logged in` | Binary runs; failure mode is auth (expected), **not** `claude: not found` |

### A.3 Pass / Fail criteria

- **PASS** — image inspectable, `--version` exits 0, empty-key run yields parseable JSON with the
  `Not logged in` auth error.
- **FAIL** — any of: image not found (tag mismatch → rebuild / re-export `PRIMER_EVAL_IMAGE`);
  `claude: not found` (image built without the BLK-1 apt layers — rebuild);
  non-JSON output (image / flag drift — stop, do not proceed to Stage B).

Stage A spends **no** API credit. Do not advance to Stage B until Stage A is fully PASS.

---

## 4. Stage B — Live Fingerprint Proof (G-6, G-8, G-9)

**Goal:** prove the standing M4 gate end-to-end against a live agent. This is the only stage that spends
API credit and exercises the fingerprint instruction empirically.

The three live tests already exist and are skip-gated; **no test authoring is required**. They live at
`tests/test_runner_isolation.py:1354–1510`.

### B.1 Gate definitions

| Gate | Test | Asserts |
|---|---|---|
| **G-6** | `test_live_with_arm_fingerprint_found_in_log` | WITH-arm `run_task()` → `result.harness_fingerprint_valid is True`; `FINGERPRINT_MARKER` present in the persisted redacted log at `result.agent_log_path` |
| **G-8** | `test_live_without_arm_fingerprint_not_checked` | WITHOUT arm → `harness_fingerprint_valid is None` (Probe C); WITH arm → `True` (Probe A); neither `run_task()` raises `HarnessValidityError` |
| **G-9** | `test_live_full_eval_delta_computed_after_fingerprint_gate` | Full `score()` on a 1-task × {without, with} × 1-run matrix returns a `ScoreReport` (no abort); `report.success_delta` is a `float`; `report.n_tasks == 1` |

The live task (`_make_live_task`, `test_runner_isolation.py:1319`) uses `verify_cmd="true"` so pass/fail is
deterministic and **independent** of whether the agent actually fixes the code — the proof isolates the
fingerprint gate, not the agent's coding ability.

### B.2 Exact pytest invocation

Run from the repo root with all four prerequisites (§2) set in the environment:

```
pytest tests/test_runner_isolation.py \
       -k "test_live_with_arm or test_live_without_arm or test_live_full_eval" \
       -v --tb=short
```

(Equivalently, the comment block at `test_runner_isolation.py:1293–1299` documents the same command.)

Expected on success: **3 passed** (G-6, G-8, G-9). If the env gate is unsatisfied, pytest reports
**3 skipped** with reason `BLK-2 live gate: requires PRIMER_RUN_DOCKER_TESTS=1, ANTHROPIC_API_KEY, and
PRIMER_EVAL_IMAGE to be set` — that is a *not-run*, **not** a pass.

### B.3 Ordering

Run G-6 first (cheapest, one WITH arm). If G-6 fails on marker absence, **stop** — G-8 and G-9 will also
fail for the same reason, and the fix is to revise `FINGERPRINT_INSTRUCTION` (§7 / `16_BLK2_SPECIFICATION.md §4.4`),
rebuild nothing (text lives in `claude_code.py`, not the image), and re-run from G-6.

---

## 5. Evidence Checklist

Capture all of the following into the eventual BLK-2 Proof Report. Nothing here should be paraphrased —
record literal values.

- [ ] `ANTHROPIC_API_KEY` present and non-empty (do **not** record the key itself).
- [ ] `docker info` exit 0 (daemon up).
- [ ] `PRIMER_EVAL_IMAGE` exact tag string.
- [ ] `docker image inspect` exit 0 for that tag.
- [ ] `claude --version` output string + exit 0 (Stage A.2).
- [ ] Empty-key JSON sample showing `is_error:true` / `Not logged in` (Stage A.3).
- [ ] G-6: `result.harness_fingerprint_valid is True`.
- [ ] G-6: literal `primer_fingerprint_v1_acknowledged` substring located in the persisted log; record
      `result.agent_log_path`.
- [ ] G-8: WITHOUT arm `harness_fingerprint_valid is None`; WITH arm `is True`; no exception.
- [ ] G-9: `score()` returned a `ScoreReport`; `success_delta` is a float; `n_tasks == 1`.
- [ ] Final pytest summary line: `3 passed` for the `-k` selection.
- [ ] Confirmation that `FINGERPRINT_INSTRUCTION` text was **not** changed (or, if changed, the new locked
      text + the run that verified it).

---

## 6. Timeout × Fingerprint Ruling

This is a deliberate, non-obvious interaction. Record it so a future prover does not misread a timeout as a
gate bug.

**Mechanism (grounded in `runner.py`):**
- The fingerprint check (`adapter.check_fingerprint(redacted_log, with_context)`, `runner.py:212`) runs
  **after Step 8 log read** and is **inside** the same `with EgressNetwork` block as the
  container-wait/timeout handling (`runner.py:173–212`).
- On `requests.exceptions.ReadTimeout` the container is killed and `passed=False, timed_out=True`
  (`runner.py:182–192`) — but execution **falls through** to Step 8 (read log) and the fingerprint check.
  The check is **not** bypassed by a timeout.

**Ruling — the four cases:**

| Arm | Marker in (partial) log | `harness_fingerprint_valid` | Scorer effect |
|---|---|---|---|
| WITH | present | `True` | No abort; run counts as a (failed-but-valid) timed-out run |
| WITH | absent | `False` | **`HarnessValidityError` — eval aborts**, even though the cause was a timeout |
| WITHOUT | (not checked) | `None` | Never aborts (Probe C) |
| WITHOUT | (not checked) | `None` | Never aborts |

**Design intent that makes this safe:** the provisional instruction tells the agent to emit the marker
"as the first line of your response" / "before starting the task" (`claude_code.py:38–41`). The marker is
therefore expected **early**, before any long task work. A timeout late in a run should still find the marker
already in the log (→ `True`, no false abort). A timeout so early that the agent emitted nothing yields
`False` → abort — which is the **correct** conservative outcome (the harness cannot certify the file was read).

**Timeout value:** `primer_eval_timeout_s = 600` (`config.py:45`, M1; Docker client timeout is `+30`,
`config.py:56–58`). No change to timeout is part of BLK-2; it is recorded here only so the prover knows the
window the agent has to emit the marker.

**Implication for the proof:** if G-6 fails specifically with a timeout *and* marker absent, treat it as an
instruction-latency problem (marker not emitted early enough), not solely an instruction-wording problem —
but the remedy is the same path: revise the instruction to force the marker out first, per §7.

---

## 7. Failure-Diagnosis Matrix

| Symptom | Likely cause | Diagnosis step | Remedy |
|---|---|---|---|
| **Marker missing** — G-6/G-8 fail; `harness_fingerprint_valid is False` | Agent did not emit `primer_fingerprint_v1_acknowledged`; provisional instruction wording ineffective, or marker emitted via a channel not in the log | Open `result.agent_log_path`; inspect the JSON `result` field and stdout for any acknowledgement variant | Revise `FINGERPRINT_INSTRUCTION` (`claude_code.py:38–41`) per `16_BLK2_SPECIFICATION.md §4.4`; try the file-system alternative (§4.2 alt candidate); re-run from G-6. **This is the one remedy that edits code — out of scope for the doc-authoring session.** |
| **Empty log** — no JSON, `agent_error=True`, no marker | Log not captured: volume-mount read fell back and was empty, or agent produced no output (immediate crash) | Check `result.agent_log_path` exists and size; `_read_container_log` reads `work_dir/.primer_agent.log` then falls back to `container.logs()` (`runner.py:326–339`) | Confirm the volume mount `/work` is writable; confirm Stage A.2 JSON worked; if log is genuinely empty, treat as command-failure (next row) |
| **Command failure** — container exits non-zero before agent runs; verify_cmd never reached | Shell-quoting / execution-path regression, or malformed `sh_script` | Inspect the literal `sh_script` (`runner.py:152`): it must be `<quoted argv> > /work/.primer_agent.log 2>&1 ; <verify_cmd>` and be passed as `command=["sh","-c",sh_script]` (`runner.py:157`) | The fix is already in place (`_shell_quote` `runner.py:319–323`, list-form command). If regressed, restore list form so the daemon does not `shlex.split` the wrapper. Multi-word prompts (`task.prompt`) must stay single-quoted |
| **Image failure** — image not found / wrong layers / `claude: not found` | `PRIMER_EVAL_IMAGE` tag mismatch (repohash is path-specific) or image built without BLK-1 apt layers | `docker image inspect $PRIMER_EVAL_IMAGE`; `docker run --rm <img> claude --version` | Rebuild via `build_eval_image()` and re-export the exact produced tag; confirm `image_layers()` apt steps applied (`claude_code.py:110–133`) |
| **Auth failure** — JSON `is_error:true`, `result:"Not logged in · Please run /login"`, marker absent | `ANTHROPIC_API_KEY` empty/invalid inside the container, or egress proxy blocking `api.anthropic.com` | Re-run Stage A.2 with the real key (drop `-e ANTHROPIC_API_KEY=""`); confirm key injected (`runner.py:134–140`); confirm `api_host()` = `api.anthropic.com` (`claude_code.py:55–56`) reachable through egress | Set a valid funded key; verify the egress allowlist permits the Anthropic host; re-run from Stage A.2 |

---

## 8. Exact Completion Criteria for BLK-2

BLK-2 is **PROVEN / COMPLETE** when **all** of the following hold simultaneously:

1. **Offline gates remain green** — G-1…G-5 and G-7 pass (already satisfied;
   `17_BLK2_COMPLETION_REPORT.md §4`).
2. **G-6 PASS** — a live WITH-arm `run_task()` returns `harness_fingerprint_valid is True` and the literal
   marker `primer_fingerprint_v1_acknowledged` is present in the persisted redacted log.
3. **G-8 PASS** — in a paired live run, WITHOUT arm returns `None` (Probe C) and WITH arm returns `True`
   (Probe A), with no `HarnessValidityError` raised.
4. **G-9 PASS** — a full live `score()` returns a `ScoreReport` with a float `success_delta` and
   `n_tasks == 1`, i.e. the delta is computed **only after** the WITH-arm gate passed.
5. **Instruction text locked** — the `FINGERPRINT_INSTRUCTION` value that produced the passing G-6 is
   recorded and the `⚠️ [EMPIRICAL VERIFICATION REQUIRED]` markers in `claude_code.py:34` and `:138` are
   removed (the only post-proof code edit BLK-2 anticipates).
6. **Proof report authored** — a `19_BLK2_PROOF_REPORT.md` (or successor) records the §5 evidence checklist
   with literal values.

Until criteria 2–6 are met, BLK-2 status remains exactly as in §1: implementation complete, live proof
pending API key.

---

## Contradictions Discovered

1. **Stale module docstring vs. actual invocation (`claude_code.py`).** The module-level docstring at
   `claude_code.py:3` still reads `--permission-mode bypassPermissions`, but `build_invocation()`
   (`claude_code.py:81–88`) actually emits `--permission-mode dontAsk --allowedTools Bash,Edit,MultiEdit,Write,Read`.
   The `dontAsk + allowedTools` form is the *correct* one (the BLK-1 proof, `09_BLK1_PROOF_REPORT.md`
   "Discovered Blocker", showed `bypassPermissions` is blocked under root in Claude Code 2.1.x). The
   running code is right; only the top-of-file docstring is stale. This does **not** affect the proof but
   should be corrected when the instruction text is locked (criterion 5). *Documentation-only; not fixed in
   this session per the no-code-change constraint.*

2. **BLK-1's recommended fix differs from what shipped.** `09_BLK1_PROOF_REPORT.md` recommends
   `bypassPermissions → acceptEdits`. The implementation instead chose `dontAsk + allowedTools` (a stricter,
   non-interactive, root-safe configuration documented in `claude_code.py:68–79`). This is an *improvement
   over* the BLK-1 recommendation, not a regression — but a reader comparing the two documents will see a
   mismatch. Recorded for traceability.

3. **`RunResult` field placement deviates from spec §6.2.** The spec places `harness_fingerprint_valid`
   "after `flaky`, before `agent_adapter`"; the implementation places it at the end of the dataclass
   (Python requires defaulted fields after required ones). Already disclosed in
   `17_BLK2_COMPLETION_REPORT.md §2`. Name, type, default, and semantics match the spec — semantically
   equivalent, cosmetically different. No proof impact.

4. **G-6 scope narrowed between readiness and final spec.** `12_BLK2_READINESS_ASSESSMENT.md` G-6 expected
   "`parse_telemetry` … `agent_error=False` and marker found." The final spec/live test G-6
   (`test_runner_isolation.py:1354`) asserts only `harness_fingerprint_valid is True` + marker present; it
   does **not** assert `agent_error is False`. The narrower final form is correct (the gate is about the
   marker, not task success), but a prover expecting the readiness wording should use the spec/test wording.

No contradiction blocks the proof. All four are documentation/traceability notes; the executable path
(image → invocation → inject → check → abort) is internally consistent.

---

## GO / NO-GO for Proof Once API Key Is Available

**GO.**

Rationale: every offline gate is green; the live tests exist and are correctly skip-gated; the image,
invocation, injection, check, and abort paths are wired and mutually consistent; Stage A spends no credit
and de-risks the image before any API call; and the one residual risk (provisional instruction text not
producing the marker) is contained — it surfaces deterministically at G-6, its remedy is a localized text
edit in `claude_code.py` (not the image, not the schema), and the re-run loop is documented in §7.

**Conditions on the GO:**
- Supply the four prerequisites in §2.
- Run Stage A to full PASS **before** Stage B (protects the API budget).
- Be prepared for one possible iteration on `FINGERPRINT_INSTRUCTION` if G-6 fails on marker absence; this
  is the single anticipated code change and lies **outside** the scope of the session that authored this
  readiness document.

---

*Readiness runbook only. No production code, tests, Docker, or background tasks were run or modified in
authoring this document. All file paths and line numbers are grounded in the codebase on branch
`v3-execution` as of 2026-06-12.*
