# BLK-1 Proof Report

**Date:** 2026-06-06T18:17:11Z
**Branch:** `v3-execution`
**Commit:** `4498309`
**Prover:** Claude Sonnet 4.6 (automated validation run)
**Purpose:** Determine whether BLK-1 (agent provisioning) resolves the fabricated-zero failure mode identified in the Execution Readiness Assessment.

---

## Context

Prior to BLK-1, PRIMER's eval image contained only Python, pip-installed project deps, and pytest. No eval agent CLI was provisioned. The container command `sh -c 'claude … ; verify_cmd'` used `;` (not `&&`) as the separator, so when `claude` was absent:

1. `sh` emitted `claude: not found`
2. `verify_cmd` ran against the still-broken (mutated) repo → pytest failed
3. Both WITH and WITHOUT arms failed identically
4. `success_delta = 0.0` — **a fabricated zero, not a real measurement**

BLK-1 resolved this by provisioning the Claude Code CLI into the eval image via Anthropic's official signed apt repository.

---

## Image Built

```
Tag:       primer-eval-b2efb5044c85-claude_code:4498309093b1
Base:      python:3.11-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0
Size:      574 MB
Build:     Success — all apt layers applied without error
```

**Dockerfile layers added by `ClaudeCodeAdapter.image_layers()`:**
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://downloads.claude.ai/keys/claude-code.asc \
       -o /etc/apt/keyrings/claude-code.asc \
    && echo "deb [signed-by=/etc/apt/keyrings/claude-code.asc] \
       https://downloads.claude.ai/claude-code/apt/stable stable main" \
       > /etc/apt/sources.list.d/claude-code.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends claude-code \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV DISABLE_AUTOUPDATER=1
```

---

## V1.1 — Binary Present and Executable

**Command:**
```bash
docker run --rm primer-eval-b2efb5044c85-claude_code:4498309093b1 claude --version
```

**Output:**
```
2.1.153 (Claude Code)
```

**Exit code:** 0

**Result: PASS ✓**

The Claude Code CLI binary is present at `/usr/bin/claude` (default system PATH, installed via the `claude-code` apt package). The version string is returned cleanly, confirming the binary is executable under the container's root user. This directly proves that the previous failure mode (`claude: not found`) is eliminated.

---

## V1.2 — Binary Runs and Produces Valid Telemetry Format

**Command (no API key):**
```bash
docker run --rm -e ANTHROPIC_API_KEY="" primer-eval-b2efb5044c85-claude_code:4498309093b1 \
  sh -c "claude --print 'hello' --output-format json --allowedTools none"
```

**Output (abbreviated):**
```json
{
  "type": "result",
  "subtype": "success",
  "is_error": true,
  "duration_ms": 267,
  "num_turns": 1,
  "result": "Not logged in · Please run /login",
  "total_cost_usd": 0,
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0
  }
}
```

**Key observations:**
- **No `claude: not found`** — the binary IS found and executes
- **No "command not found" shell error** — the system PATH is correct
- **Valid JSON telemetry emitted** — the output matches the expected `parse_telemetry` input format
- **Auth error, not binary error** — `"Not logged in"` vs the previous `sh: claude: not found`
- `parse_telemetry` result: `agent_error=True`, `tokens=0`, `cost_usd=0.0`, `duration_s=0.267`

**Note:** `--allowedTools none` was used because `--permission-mode bypassPermissions` is blocked in Claude Code 2.1.153 when running as root (see Discovered Blocker below). `acceptEdits`, `default`, `auto`, and `dontAsk` modes all produce valid JSON under root.

**Result: PARTIAL ✓**

BLK-1's core claim is confirmed: the binary runs and produces parseable JSON output. The auth failure (`"Not logged in"`) is a test environment limitation, not a BLK-1 failure. The failure mode changed from `claude: not found` (silent fabricated zero) to `is_error: true, result: "Not logged in"` (explicit, detectable auth error).

---

## V1.3 — `agent_error=False`, `tokens > 0`

**Result: BLOCKED ✗**

Blocked by two independent issues:

### Blocker A (Discovered during proof — outside BLK-1 scope)

**`--permission-mode bypassPermissions` blocked under root in Claude Code 2.1.153**

The `ClaudeCodeAdapter.build_invocation()` currently includes `--permission-mode bypassPermissions`. In Claude Code 2.1.153, this mode internally maps to `--dangerously-skip-permissions`, which is blocked when running as root:

```
--dangerously-skip-permissions cannot be used with root/sudo privileges for security reasons
```

Docker containers run as root by default. This error would occur even with a valid `ANTHROPIC_API_KEY`.

**Working alternatives confirmed:**
- `--permission-mode acceptEdits` → produces valid JSON under root ✓
- `--permission-mode auto` → produces valid JSON under root ✓
- `--permission-mode dontAsk` → produces valid JSON under root ✓
- `--permission-mode default` → produces valid JSON under root ✓

**Required fix (NOT part of BLK-1 scope):** Change `ClaudeCodeAdapter.build_invocation()` from `--permission-mode bypassPermissions` to `--permission-mode acceptEdits` (or add a non-root user to the Dockerfile). This is a new pre-BLK-2 item.

### Blocker B (Environment limitation)

**`ANTHROPIC_API_KEY` is empty in this environment**

The test environment has `PRIMER_AGENT=gemini` configured; the `ANTHROPIC_API_KEY` resolves to an empty string. V1.3 requires the agent to make a successful API call.

**Proof path with both blockers resolved:**
- Fix `build_invocation`: `bypassPermissions` → `acceptEdits`
- Set a valid `ANTHROPIC_API_KEY`
- Run `primer eval tests/fixtures/py_repo --agent claude_code --tasks 1 --runs 1`
- Expected: `agent_error=False`, `tokens>0` in parsed telemetry

---

## V1.4 — Working Directory Modified by Agent

**Result: BLOCKED ✗**

Depends on V1.3. The agent never reaches task execution due to the auth failure.

With Blocker A and Blocker B resolved, the expected path:
1. Container starts, `claude --permission-mode acceptEdits` is invoked
2. Agent authenticates via `ANTHROPIC_API_KEY`
3. Agent reads the mutated file (e.g. `multiply` stubbed to `raise NotImplementedError`)
4. Agent writes the reimplemented function body
5. `verify_cmd` (pytest) exits 0 → `passed=True`

---

## Evidence Summary

| Evidence | Value |
|---|---|
| Image tag | `primer-eval-b2efb5044c85-claude_code:4498309093b1` |
| Base image digest | `python:3.11-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0` |
| Claude Code version in image | `2.1.153 (Claude Code)` |
| Installation method | Anthropic official apt repo (stable channel), Node-free |
| Binary path | `/usr/bin/claude` (on default PATH) |
| `claude --version` exit code | `0` |
| Container binary execution | ✓ Confirmed (produces JSON output) |
| Previous failure mode (`not found`) | ✓ Eliminated |
| New failure mode (auth error) | ✓ Detectable, explicit, expected |
| `parse_telemetry` on auth-error output | `agent_error=True`, `tokens=0`, `duration_s=0.267` |
| `bypassPermissions` under root | ✗ Blocked (Claude Code 2.1.153 security restriction) |
| `acceptEdits` under root | ✓ Works, produces valid JSON |

---

## Validation Gate Results

| Gate | Requirement | Status | Blocker |
|---|---|---|---|
| **V1.1** | `claude --version` exits 0 in image | **PASS ✓** | None |
| **V1.2** | Binary runs, no "not found", telemetry present | **PARTIAL ✓** | Auth failure (expected; binary runs) |
| **V1.3** | `agent_error=False`, `tokens>0` | **BLOCKED ✗** | A: bypassPermissions under root; B: empty API key |
| **V1.4** | Working directory modified by agent | **BLOCKED ✗** | Depends on V1.3 |

---

## Discovered Blocker — New Pre-BLK-2 Requirement

During proof, a new compatibility issue was identified outside BLK-1's scope:

> **`ClaudeCodeAdapter.build_invocation()` uses `--permission-mode bypassPermissions`, which is blocked in Claude Code 2.1.153 when running as root (the default Docker user).**

This issue:
- Was **not present** in the original BLK-1 specification (invocation flags were assumed working)
- Is **not resolvable** by the current BLK-1 changes (those cover `image_layers()` only)
- **Blocks V1.3/V1.4** even after a valid API key is provided
- Is **confined to `claude_code.py:build_invocation()`** — a one-line fix

**Required fix:** Change `"--permission-mode", "bypassPermissions"` to `"--permission-mode", "acceptEdits"` in `ClaudeCodeAdapter.build_invocation()`. This must be completed before BLK-2 begins and before any full end-to-end eval run is attempted.

---

## Remaining Risks

| Risk | Severity | Notes |
|---|---|---|
| `bypassPermissions` blocker | **High** | Blocks all real eval runs; `acceptEdits` fix is one line in `claude_code.py` |
| Empty `ANTHROPIC_API_KEY` | **High** | Environment-specific; user must set before running eval with `claude_code` |
| `acceptEdits` vs `bypassPermissions` semantics | Medium | `acceptEdits` auto-accepts file edits; may need validation that it allows all tool use the task requires |
| claude-code version drift | Low | Stable channel used; image caches the installed version; rebuild needed for upgrades |

---

## Final Verdict

**BLK-1: NOT PROVEN**

The BLK-1 **implementation** is architecturally correct and resolves the primary fabricated-zero failure mode:

- The eval image is now built with the Claude Code binary provisioned ✓
- `claude --version` succeeds inside the container ✓
- The previous `claude: not found` failure mode is eliminated ✓
- The binary produces valid JSON telemetry when invoked ✓

The **proof** is incomplete because:

1. A new compatibility issue was discovered during proof testing: `--permission-mode bypassPermissions` is blocked under root in Claude Code 2.1.153. This affects `ClaudeCodeAdapter.build_invocation()` — a one-line fix outside BLK-1's original scope.
2. The test environment has an empty `ANTHROPIC_API_KEY`, preventing V1.3/V1.4 from completing.

**Before BLK-2 begins:**
1. Fix `ClaudeCodeAdapter.build_invocation()`: `bypassPermissions` → `acceptEdits`
2. Set a valid `ANTHROPIC_API_KEY` in the environment
3. Re-run V1.2–V1.4 gates to obtain the completed proof

---

*Proof run completed 2026-06-06T18:17:11Z on branch `v3-execution` at commit `4498309`.*
*Prover: automated validation (Claude Sonnet 4.6). No files modified other than this report.*
