# PRIMER V2 — ARCHITECTURE IMPLEMENTATION SPECIFICATION

> **Status: BUILD CONTRACT.** Converts the approved repository-centric architecture review into an
> executable, decision-free implementation spec. An executing agent follows this document verbatim
> and makes **no architectural decisions**. Every route, file, contract, and acceptance gate is fixed.
>
> **Authority / precedence:** This document is **subordinate** to the four authority documents
> (`PRIMER_SESSION_1_FINAL_REVISION`, `PRIMER_SESSION_2_ARCHITECTURE_BLUEPRINT`,
> `PRIMER_DECISION_ADDENDUM_M1_M3_M4_M5_M7_M8`, `PRIMER_CONSOLIDATED_IMPLEMENTATION_SPEC`).
> Where this document touches presentation/export only, it governs V2. It **never** overrides the
> frozen engine, statistics, Docker isolation, or scoring semantics.
>
> **Scope:** the dashboard/export ("Nice-to-Have", Phase 7+) track. It introduces the **Repository**
> as the organizing object and an **object graph** the existing backend already models, exposing
> `list_reports` / `get_report_by_id` / `compare` semantics through the export pipeline and the
> dashboard routes. It preserves all B.1–B.4 components verbatim.

---

## 0. GOVERNING CONSTRAINTS (read first — these are invariant across P0–P3)

### 0.1 Frozen surfaces — DO NOT MODIFY behavior

The executing agent MUST NOT change the behavior, signatures, fields, or output of any of:

- `primer/eval/**` (evaluation engine, runner, scorer, models — `ScoreReport`, `TaskScore`, `RunResult`).
- `primer/store/schema.sql` and the **behavior** of `primer/store/db.py` functions
  (`init_db`, `save_report`, `latest_report`, `list_reports`, `get_report_by_id`).
- `primer/store/migrations.py` (`CURRENT_SCHEMA_VERSION` stays `1`; no DB migration in V2).
- `primer/report/render.py` (text/json CLI rendering, verdict/noise math).
- The **existing** functions in `primer/report/export.py`:
  `build_scores_json`, `write_scores_json`, `build_dashboard_json`, `write_dashboard_json`,
  `_compute_verdict`, `_compute_flip_state`. These are **reused unchanged**.
- Docker, network, statistics, generation, ingest.

### 0.1.1 V3 presentation-only amendment (approved 2026-06-04 — V3 P4 gates 1+2, owner sign-off)

Under the V3 presentation-layer authority (PRIMER_V3 stack), the following **presentation-only**
changes are permitted to the §0.1 surfaces, provided every data field, `schema_version`, the
signatures/output of the data builders, and all verdict/noise/flip math remain **byte-identical in
behavior**:

1. `build_scores_json` (export.py): the `color` attribute may move off caution-yellow to a calm/muted
   value for the within-noise/zero/refused/not-evaluated cases (§13). Schema keys, `message` wording,
   and the green/red by-sign logic are unchanged; no verdict math is added.
2. `render.py`: terminal color **styles** for the within-noise label and the zero/refused delta cells
   may move off caution-yellow to calm/muted. Amber/yellow stays reserved for genuine warnings
   (provider/isolation/flaky/egress-not-enforced). No numbers, labels, ordering, or math change.
3. The legacy single-file `data.json` export path may be **removed**: `write_dashboard_json`
   (export.py) and the `--data-output` flag + call site (cli.py) are deleted. `build_dashboard_json`,
   `write_scores_json`, and the V2 site builders (`build_evaluation_json`, `build_repository_json`)
   remain frozen and unchanged — `build_dashboard_json` is still the shared field-builder.

Gate 3 (extending comparison refusal to isolation mismatch) was **NOT** approved; `render_compare`
and `lib/compare.ts` refusal behavior is unchanged. All other §0.1 constraints remain in force.

### 0.2 Additive-only rule

All V2 work is **additive composition**. Allowed changes are limited to:

1. **New functions** appended to `primer/report/export.py` (no SQLite/Docker imports — boundary held).
2. **New options** appended to the existing `export` command in `primer/cli.py` (existing flags keep
   their current behavior). `cli.py` is the composition root and the only place permitted to call
   `store/` functions; it passes plain dataclasses/ints into `export.py` (boundary invariant #3 held).
3. **New / modified files** under `dashboard/**` (routing, new components, types).
4. **The CI workflow** `.github/workflows/pages.yml`.
5. **New tests** (additive files only).

If any instruction here appears to require editing a frozen surface, the agent STOPS and reports a
blocker. It does not improvise.

### 0.3 Honesty invariants (carry from M3 / Q9d — non-negotiable)

- **Verdict labels** are the four canonical values only: `positive | negative | within-noise | refused`.
  Computed exclusively by the existing `_compute_verdict` (export.py). No new verdict logic.
- **Refuse-on-mismatch:** any cross-evaluation comparison MUST refuse the delta when `provider` or
  `model` differ (mirrors `render_compare`, render.py). The compare surface shows the refusal, never
  a fabricated number.
- **No false precision:** the longitudinal view is a **verdict ledger**, never a smoothed metric line
  chart. Every delta in the ledger is shown together with its noise envelope
  `noise_threshold = max(1 / n_tasks, success_stddev)`. A `within-noise` row is labeled as such.
- **Two-stream rule:** `primer_overhead_usd` is never summed into `cost_with`/`cost_without`. Carried
  through `build_dashboard_json` unchanged.

### 0.4 Identity & privacy invariants

- **Evaluation identity = the SQLite `reports.id` integer** (from `list_reports` / `get_report_by_id`).
  This is the stable URL key. It is the only id used in routes and filenames.
- **Repository identity in published JSON = a display name + optional URL.** The absolute local
  `repo_path` MUST NEVER appear in any exported JSON (privacy: it leaks the author's filesystem).

### 0.5 Static-export invariants (Next.js 15, `output: "export"`)

Confirmed from `dashboard/next.config.mjs` / `package.json`: `output: "export"`, `basePath` from
`NEXT_PUBLIC_BASE_PATH` (`/primer` in CI, `""` locally), `trailingSlash: true`, Next `^15.5.18`,
React `^19`. Therefore:

- A dynamic route (`/evaluations/[id]`) MUST export `generateStaticParams()` from a **server
  component** (a file with no `"use client"` directive). The enumerated params are baked at build.
- Build-time data is read from the **filesystem** with `node:fs/promises` + `process.cwd()`-relative
  paths. The build MUST succeed even when data files are absent (graceful empty fallback).
- Runtime data fetches (compare page only) MUST prefix the asset path with `BASE_PATH`
  (`process.env.NEXT_PUBLIC_BASE_PATH ?? ""`), exactly as the current `app/page.tsx` does for
  `data.json`.
- `useSearchParams()` (compare page) MUST be wrapped in a `<Suspense>` boundary (Next 15 export
  requirement).

### 0.6 TOOLING PROTOCOL — required skills & MCP connectors (per-phase)

Two hard rules govern all tooling:

1. **Tools assist craft and verification; they never change this spec.** Where any skill or MCP
   suggestion conflicts with a route, file path, data contract, acceptance criterion, or a non-goal
   (§9), **this spec wins.**
2. **Do NOT generate UI from MCP connectors.** The reference MCPs (21st.dev Magic, Figma, Canva, Miro)
   are used **only** to study product-architecture, navigation, repository-centric-platform, and
   information-architecture patterns. No component, page, layout, asset, or token is generated,
   exported, or imported from them. New components are hand-built in the **existing** design system.

**Required project skills** (load with the Skill tool before the relevant work):

| Skill | Role in V2 | Phases |
|---|---|---|
| `primer-dashboard` | Canonical field names, verdict labels, flip states, "render data only." Governs every data contract. | P0, P1, P2 |
| `primer-motion` | The exact entrance/hover/transition tokens the existing components use. New components match these; introduce none. | P1, P2 |
| `emil-design-eng` | Craft/polish review of new components (invisible-detail bar); its required Before/After review format. | P1, P2 |
| `impeccable` | Identity-preserving audit/critique of new components against the committed design system; IA / hierarchy / contrast pass. Run its `audit`/`polish` flow at each frontend phase close. | P1, P2 |
| `shadcn` | Composition / semantic-token discipline **only if** a primitive is genuinely needed. PRIMER has no `components.json`; **prefer the existing hand-rolled components** and do not introduce shadcn wholesale. | P1, P2 (conditional) |
| `frontend-design` | **Scoped use only:** its IA/structure and anti-"AI-slop" discipline. **Ignore** its "pick a bold new aesthetic / new fonts / new colors" guidance — that conflicts with §9 (PRIMER preserves its system). | P1, P2 (structure only) |
| `design-taste-frontend` | **Scoped use only:** its "design read / anti-default" reasoning for IA. Heed its own note ("not for dashboards") — use it to reason about overview IA, **not** to restyle. | P1 (IA reasoning only) |

**Global skill:** `ui-ux-pro-max-skill` — overall UX/IA quality pass at each frontend phase close
(navigation legibility, empty states, information scent). Advisory; this spec wins on conflict.

**MCP connectors:**

| MCP | Status | Permitted use (pattern study only — never generation) |
|---|---|---|
| **Context7** | **REQUIRED** | Verify framework APIs **before** coding: Next.js 15 `output: "export"`, `generateStaticParams` for `[id]`, `useSearchParams` + `<Suspense>`, `node:fs` in server components at build, `basePath`/`trailingSlash`. Resolve `/vercel/next.js`, then query. |
| 21st.dev Magic | reference | Study repository/dashboard IA + navigation patterns. **No component generation.** |
| Figma | reference | Study platform navigation / IA references. **No asset import / code-from-design.** |
| Canva | reference | Reference only. **No generation.** |
| Miro | reference | Object-graph / IA diagram patterns for reasoning. **No generation.** |

**Context7-verified facts (load-bearing; already reflected in P1/P2):**
- A dynamic `[id]` route under `output: "export"` MUST export `generateStaticParams()` returning
  **string** ids: `{ id: string }[]` (use `String(e.id)`).
- **Next 15: `params` is a `Promise`.** Server pages destructure via `const { id } = await params`
  (type `params: Promise<{ id: string }>`).
- `useSearchParams()` MUST sit inside a `<Suspense>` boundary or the export build errors.
- `basePath` is auto-applied by `next/link` / `next/image`, **not** to manual `fetch()` of public
  assets → runtime fetches use `BASE_PATH` (§3.4), exactly as the current `data.json` fetch does.

**Per-phase tooling matrix:**

| Phase | Skills to load | Context7 | Reference MCPs |
|---|---|---|---|
| P0 (Python export) | `primer-dashboard` | optional (stdlib only) | none |
| P1 (routing/spine) | `primer-dashboard`, `primer-motion`, `emil-design-eng`, `impeccable`, `ui-ux-pro-max-skill`; `frontend-design` / `design-taste-frontend` (IA only) | **required** | optional (IA patterns) |
| P2 (compare) | `primer-dashboard`, `primer-motion`, `emil-design-eng`, `impeccable`, `ui-ux-pro-max-skill` | **required** | optional |
| P3 (CI) | `primer-dashboard` | optional | none |

---

## 1. TARGET ARCHITECTURE (fixed)

### 1.1 Object model (published shape)

```
Repository                         identity = {name, url}; key = reports.repo_path (server-side only)
├── Evaluations[]                  each = one reports row → one ScoreReport; URL key = reports.id
│     ├── Verdict                  positive | negative | within-noise | refused  (existing logic)
│     ├── per_task[] + flip_state  (existing build_dashboard_json output)
│     ├── metrics / cost / variance(existing)
│     └── provenance / isolation   (existing)
├── Latest                         pointer to newest Evaluation (highest id)
└── Comparison(EvalA, EvalB)       derived client-side view; refuses on provider/model mismatch
```

No `Organization`, `Team`, `auth`, or stored `Baseline`/`Comparison` objects in V2.

### 1.2 Routes (fixed; flat)

| Route | Type | Rendering source | Phase |
|---|---|---|---|
| `/` | server component | build-time read of `repository.json` | P1 |
| `/evaluations/[id]/` | server component (+`generateStaticParams`) | build-time read of `evaluations/<id>.json` | P1 |
| `/compare/` | client component (`useSearchParams` in Suspense) | runtime fetch of two `evaluations/<id>.json` | P2 |
| `/repositories/` | server component | build-time read of multi-repo index | **P3 — OPTIONAL/deferred** |

`trailingSlash: true` emits `/evaluations/<id>/index.html`. Cross-links use `next/link` (basePath
applied automatically by `Link`); raw fetches add `BASE_PATH` manually.

### 1.3 Data flow (fixed)

```
SQLite primer.db   ──(read-only)──►  primer/cli.py  ──(ScoreReport + id)──►  primer/report/export.py
  (frozen engine writes it)            init_db / list_reports / get_report_by_id     (pure builders, no sqlite)
                                              │
                                              ▼  primer export --site-output dashboard/public
                              dashboard/public/repository.json
                              dashboard/public/evaluations/<id>.json   (one per report)
                              dashboard/public/scores.json             (badge; latest)
                                              │
                          ┌───────────────────┼───────────────────────────┐
                build-time read         build-time read              runtime fetch (+BASE_PATH)
                      ▼                       ▼                              ▼
                  /  (overview)        /evaluations/[id]/             /compare?a=&b=
                                              │
                              GitHub Pages workflow: npm build → deploy dashboard/out
```

---

## 2. SITE DATA LAYOUT (fixed)

All V2 site data lives under `dashboard/public/` (web-served and readable at build):

```
dashboard/public/
├── repository.json            # P0 — repository index + ordered evaluation summaries
├── evaluations/
│   └── <id>.json              # P0 — one full evaluation payload per reports.id
└── scores.json                # P0 — shields.io badge (latest); replaces the manually-copied one
```

- `dashboard/public/data.json` (the V1 single-report file) is **removed** in P1 (superseded).
- These `*.json` files are **committed** to the repo (not git-ignored; `.gitignore` lists `*.db`, not
  `*.json` — verify in P3). CI builds from the committed files (see P3 rationale).

---

## 3. CANONICAL DATA CONTRACTS (fixed; referenced by all phases)

> Contracts are expressed as field tables + compact shape blocks. These are **data contracts**, not
> implementations. Field names are exact and case-sensitive. The agent must not rename or add fields.

### 3.1 `repository.json` — schema_version 2, `kind: "repository"`

| Field | Type | Source / rule |
|---|---|---|
| `schema_version` | number | constant `2` |
| `kind` | string | constant `"repository"` |
| `repo.name` | string | `--repo-name` or `basename(repo_path)` |
| `repo.url` | string \| null | `--repo-url` or `null` |
| `repo.latest_commit` | string | `repo_commit` of newest evaluation (`items[0]`) |
| `latest_evaluation_id` | number \| null | newest `reports.id`, or `null` if none |
| `latest_verdict` | VerdictLabel \| null | `_compute_verdict` of newest, or `null` |
| `evaluation_count` | number | `len(items)` |
| `evaluations` | EvaluationSummary[] | newest-first (mirror `list_reports` `id DESC`) |
| `generated_at` | string | export time, ISO-8601 UTC |

**EvaluationSummary** (each element of `evaluations[]`):

| Field | Type | Source |
|---|---|---|
| `id` | number | `reports.id` |
| `repo_commit` | string | `ScoreReport.repo_commit` |
| `created_at` | string | `ScoreReport.created_at` |
| `verdict` | VerdictLabel | `_compute_verdict(success_delta, n_tasks, success_stddev)` |
| `success_delta` | number \| null | `ScoreReport.success_delta` |
| `success_stddev` | number | `ScoreReport.success_stddev` |
| `n_tasks` | number | `ScoreReport.n_tasks` |
| `runs_per_config` | number | `ScoreReport.runs_per_config` |
| `noise_threshold` | number | `max(1 / n_tasks, success_stddev)` (n_tasks>0 else `success_stddev`) |
| `provider` | string | `ScoreReport.provider` |
| `model` | string | `ScoreReport.model` |
| `agent_adapter` | string | `ScoreReport.agent_adapter` |
| `egress_enforced` | boolean | `ScoreReport.egress_enforced` |

Compact shape (contract):

```
repository.json = {
  schema_version: 2, kind: "repository",
  repo: { name: string, url: string|null, latest_commit: string },
  latest_evaluation_id: number|null,
  latest_verdict: "positive"|"negative"|"within-noise"|"refused"|null,
  evaluation_count: number,
  evaluations: EvaluationSummary[],   // newest-first
  generated_at: string                // ISO-8601 UTC
}
```

### 3.2 `evaluations/<id>.json` — schema_version 2, `kind: "evaluation"`

**Definition:** the exact output of the existing `build_dashboard_json(report)` (export.py),
**merged** with three additions. No existing field is removed or altered.

| Addition | Type | Rule |
|---|---|---|
| `schema_version` | number | overridden to `2` (build_dashboard_json emits `1`; the V2 wrapper overrides) |
| `kind` | string | constant `"evaluation"` |
| `id` | number | `reports.id` (injected by the wrapper; `ScoreReport` has no id field) |
| `repo` | object | `{ name: string, url: string|null }` (for breadcrumb/back-link) |

All other keys are inherited verbatim from `build_dashboard_json`: `repo_commit`, `created_at`,
`verdict`, `n_tasks`, `runs_per_config`, `success_rate_without`, `success_rate_with`, `success_delta`,
`success_stddev`, `success_min`, `success_max`, `cost_without`, `cost_with`, `cost_delta_pct`,
`cost_confidence`, `provider`, `model`, `agent_adapter`, `base_image`, `network_mode`,
`egress_enforced`, `provider_mismatch_warning`, `isolation_mismatch_warning`, `flaky_task_warning`,
`primer_overhead_usd`, `primer_overhead_confidence`, `per_task[]` (each with `task_id`, `task_type`,
`pass_rate_without`, `pass_rate_with`, `delta`, `flip_state`, `runs`, `flaky_any`).

### 3.3 TypeScript type contracts (`dashboard/lib/types.ts`)

Additive. Existing `DashboardData`, `TaskData`, `VerdictLabel`, `FlipState`, `CostConfidence` are kept.

- **Extend `DashboardData`** with two **required** fields so the detail payload is fully typed:
  `id: number` and `repo: { name: string; url: string | null }`. (Existing components ignore them →
  no component change required to compile.)
- **Add `EvaluationSummary`** mirroring §3.1 exactly.
- **Add `RepositoryData`** mirroring §3.1 (`repository.json`) exactly.
- **Add `ComparisonResult`** mirroring §3.5 exactly.

These are **type declarations only** (no runtime logic).

### 3.4 `BASE_PATH` constant (`dashboard/lib/basePath.ts`)

Contract: exports a string constant `BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? ""`. Used to
prefix **runtime** asset fetches (compare page). Build-time reads do not use it.

### 3.5 `ComparisonResult` (client-side; `dashboard/lib/compare.ts`)

Contract for `computeComparison(a: DashboardData, b: DashboardData) -> ComparisonResult`, mirroring
`render_compare` (render.py) **exactly**:

| Field | Type | Rule (verbatim parity with render.py) |
|---|---|---|
| `provider_mismatch` | boolean | `a.provider !== b.provider || a.model !== b.model` |
| `isolation_mismatch` | boolean | `a.network_mode !== b.network_mode || a.egress_enforced !== b.egress_enforced || a.base_image !== b.base_image` |
| `refused` | boolean | `=== provider_mismatch` |
| `cross_report_delta` | number \| null | `null` if `provider_mismatch` OR `a.success_delta == null` OR `b.success_delta == null`; else `b.success_delta - a.success_delta` |
| `fields` | DiffRow[] | one row per provenance field (see below), `differ = a !== b` |

`fields` rows (label, a-value, b-value), in this order: `repo_commit`, `created_at`, `provider`,
`model`, `agent_adapter`, `base_image`, `network_mode`, `egress_enforced`, `n_tasks`,
`runs_per_config`. (Same set as `render_compare`'s provenance table.)

`computeComparison` is **pure** (no fetch, no side effects). Fetching is the page's job.

---

## 4. PHASE P0 — ADDITIVE EXPORT PIPELINE

### 4.1 Exact objective

Expose the backend's existing multi-evaluation, per-repository model as a static JSON site tree, by
adding pure builder functions to `export.py` and new options to the `export` CLI command. **No engine,
schema, store-behavior, statistics, or existing-export-function change.** This phase unblocks all
dashboard work and is independently shippable (the JSON can be inspected without any frontend).

### 4.2 Exact routes

None. P0 is CLI/export only.

### 4.3 Exact components

None (Python; no UI).

### 4.4 Exact files to CREATE

- `tests/test_site_export.py` — additive test module (assertions in §4.9).

### 4.5 Exact files to MODIFY

- `primer/report/export.py` — **append** the following pure functions (no sqlite/docker imports;
  boundary invariant held). Signatures + contracts (no bodies):
  - `build_evaluation_json(report_id: int, report: ScoreReport, repo_name: str, repo_url: str | None) -> dict`
    Contract: returns `build_dashboard_json(report)` merged with `{ "schema_version": 2,
    "kind": "evaluation", "id": report_id, "repo": { "name": repo_name, "url": repo_url } }`.
    The merge **overrides** `schema_version` to `2`. Does not mutate `build_dashboard_json`'s source.
  - `build_repository_json(repo_name: str, repo_url: str | None, items: list[tuple[int, ScoreReport]], generated_at: str) -> dict`
    Contract: `items` is newest-first `(id, ScoreReport)`. Produces §3.1 exactly. Per-evaluation
    `verdict` via the existing `_compute_verdict`; `noise_threshold = max(1/n_tasks, stddev)`
    (guard n_tasks==0 → use stddev). `latest_*` from `items[0]` (or null/0 when `items` empty).
  - `write_repository_json(payload: dict, output_path: Path) -> dict` and
    `write_evaluation_json(payload: dict, output_path: Path) -> dict`
    Contract: `mkdir(parents=True, exist_ok=True)` on the parent, write `json.dumps(payload, indent=2)`
    UTF-8, return payload. (Mirror the existing `write_*` helpers.)
- `primer/cli.py` — **extend the existing `export` command** (do not create a new command; do not alter
  existing flags). Add options:
  - `--site-output DIR` (`Optional[str]`, default `None`)
  - `--repo-name TEXT` (`Optional[str]`, default `None`)
  - `--repo-url TEXT` (`Optional[str]`, default `None`)

  Additive behavior when `--site-output` is provided (existing `--output` / `--data-output` behavior
  unchanged): orchestration (cli.py is the only place allowed to touch `store/`):
  1. `conn = init_db(config)`.
  2. `rows = list_reports(conn, repo_path=<resolved path>)` → ordered ids (`id DESC`).
  3. If `rows` empty → print a clear "no reports for <path>" message, exit code `1` (matches existing
     "no report" behavior), after closing conn.
  4. `items = [(r["id"], get_report_by_id(conn, r["id"])) for r in rows]` (skip any `None`).
  5. `repo_name = --repo-name or Path(repo_path).name`; `repo_url = --repo-url` (may be `None`).
  6. For each `(id, report)` → `write_evaluation_json(build_evaluation_json(id, report, repo_name,
     repo_url), DIR/"evaluations"/f"{id}.json")`.
  7. `write_repository_json(build_repository_json(repo_name, repo_url, items, now_iso), DIR/"repository.json")`.
  8. `write_scores_json(items[0][1], DIR/"scores.json")` (badge for the latest report; reuse existing).
  9. `conn.close()`. Print a one-line summary (count written + DIR).

  Privacy gate: the agent verifies no payload contains the absolute `repo_path` (it is never passed
  into the builders; only `repo_name`/`repo_url` are).

### 4.6 Exact data contracts

`repository.json` per §3.1; `evaluations/<id>.json` per §3.2; `scores.json` unchanged (existing
`build_scores_json`).

### 4.7 Exact export format

JSON, `indent=2`, UTF-8, one file per evaluation keyed by `reports.id`, plus one `repository.json`
and one `scores.json`, written under the `--site-output` directory (CI uses `dashboard/public`).

### 4.8 Exact migration strategy

- No DB migration (`CURRENT_SCHEMA_VERSION` stays `1`). The export reads existing rows only.
- `--data-output` (V1 single `data.json`) is **retained but deprecated** in P0 (no breakage). It is
  removed from docs/empty-state in P3; the file `dashboard/public/data.json` is deleted in P1.
- Backward compatibility: existing `primer export` (scores-only) and `--data-output` callers keep
  working byte-for-byte.

### 4.9 Exact risks

| Risk | Mitigation (mandatory) |
|---|---|
| Accidentally editing the frozen `build_dashboard_json` (e.g. to bump schema_version) | The wrapper `build_evaluation_json` **overrides** keys on the returned dict; the source function is untouched. A test asserts `build_dashboard_json` still returns `schema_version == 1`. |
| SQLite import leaking into `report/` (boundary violation) | All DB access stays in `cli.py`; builders accept `(int, ScoreReport)`. A test greps `export.py` for `sqlite3` and asserts absent. |
| `repo_path` privacy leak | Builders never receive `repo_path`; test asserts no payload string contains a path separator-bearing absolute path / the test repo's absolute path. |
| `ScoreReport` has no `id` | `id` is injected by the wrapper from the `list_reports` row; never read off the dataclass. |
| Empty DB at export | `--site-output` on a repo with zero reports exits `1` with a clear message (no partial/empty tree written that would mislead the build). |

### 4.10 Exact acceptance criteria

P0 is **done** when all hold:

1. `primer export --site-output <DIR> <fixture_repo>` writes `<DIR>/repository.json`,
   `<DIR>/evaluations/<id>.json` for **every** `reports` row of that repo, and `<DIR>/scores.json`.
2. `repository.json` validates against §3.1: `schema_version==2`, `kind=="repository"`,
   `evaluations` newest-first, every summary's `verdict` equals `_compute_verdict(...)` for that report,
   `noise_threshold == max(1/n_tasks, stddev)`, `latest_*` match `evaluations[0]`.
3. Each `evaluations/<id>.json` equals `build_dashboard_json(report)` plus exactly
   `{schema_version:2, kind:"evaluation", id, repo:{name,url}}`; `id` equals the DB row id.
4. No exported JSON contains the absolute `repo_path`.
5. Existing behavior unchanged: `build_dashboard_json` still emits `schema_version==1`;
   `primer export` (no new flags) and `--data-output` produce byte-identical output to pre-P0.
6. `export.py` imports neither `sqlite3` nor `docker`.
7. `tests/test_site_export.py` passes and asserts (1)–(6). Full existing test suite still green.
8. Git commit created only after the suite passes (per project rules).

---

## 5. PHASE P1 — ROUTING + REPOSITORY SPINE (report → platform)

### 5.1 Exact objective

Introduce the Repository as the home object and an object graph, and relocate the current
single-evaluation view to `/evaluations/[id]` **unchanged**. This is the phase that converts "a report"
into "a platform": multiple objects, a list, and real navigation. All B.1–B.4 components are reused
verbatim.

### 5.2 Exact routes

- `/` — Repository Overview (server component; build-time read of `repository.json`).
- `/evaluations/[id]/` — Evaluation Detail (server component + `generateStaticParams`; build-time read
  of `evaluations/<id>.json`).

### 5.3 Exact components

**Reused verbatim (no edits):** `VerdictHero`, `MeasurementIdentity`, `TrustArchitecture`,
`MetricsGrid`, `TaskFlipTable`, `WarningBanner`, `ProvenanceFooter`, `EmptyState`. (`EmptyState` text
is edited only in P3.)

**New (client components; reuse existing design system + `lib/format.ts`; introduce no new visual
language, colors, type, or animation tokens):**

- `EvaluationDetail` — props `{ data: DashboardData; prevId: number | null }`. Body is **exactly** the
  JSX currently inside `app/page.tsx`'s `state.status === "ok"` branch (the ordered stack:
  `WarningBanner → VerdictHero → MeasurementIdentity → TrustArchitecture → MetricsGrid → TaskFlipTable →
  ProvenanceFooter`), plus a back-link to `/` and (wired in P2) a "Compare" affordance using `prevId`.
- `RepositoryOverview` — props `{ data: RepositoryData }`. Renders the repo identity (name, optional
  url link, latest commit), a compact latest-verdict line (reuse `verdictColor`/`formatDelta`), and
  `<EvaluationLedger evaluations={data.evaluations} />`. If `data.evaluation_count === 0`, renders
  `<EmptyState />`.
- `EvaluationLedger` — props `{ evaluations: EvaluationSummary[] }`. Renders one row per evaluation,
  newest-first, each linking (`next/link`) to `/evaluations/<id>/`. Each row shows:
  `shortenCommit(repo_commit)`, `formatDate(created_at)`, verdict label, `formatDelta(success_delta)`
  **with** its noise envelope (`± (noise_threshold*100).toFixed(1) pp`), and an egress flag.
  **Honesty constraint:** this is a row ledger, **not** a line/area chart; `within-noise` rows are
  explicitly labeled "within noise". No interpolation or trend smoothing.
- `SiteHeader` — the masthead currently inline in `app/page.tsx` (`PRIMER` wordmark + `scorecard`
  label + GitHub link), with the wordmark linking to `/`. Rendered from `layout.tsx`.
- `SiteFooter` — the footer currently inline in `app/page.tsx`, rendered from `layout.tsx`.

### 5.4 Exact files to CREATE

- `dashboard/app/evaluations/[id]/page.tsx` — **server** component (no `"use client"`). Exports:
  - `generateStaticParams()` — reads `dashboard/public/repository.json` via `node:fs/promises`
    (`process.cwd()`/`public/repository.json`); returns `evaluations.map(e => ({ id: String(e.id) }))`.
    On missing/invalid file → returns `[]` (build still succeeds, zero detail pages).
  - default page — **awaits `params`** (Next 15: `params` is `Promise<{ id: string }>`), then reads
    `public/evaluations/<id>.json`; on success renders
    `<EvaluationDetail data={parsed} prevId={...} />`; on missing/invalid → renders `<EmptyState />`.
    `prevId` = the id of the chronologically previous evaluation (the next-older entry in
    `repository.json`'s newest-first list), or `null`.
- `dashboard/components/EvaluationDetail.tsx` (client) — per §5.3.
- `dashboard/components/RepositoryOverview.tsx` (client) — per §5.3.
- `dashboard/components/EvaluationLedger.tsx` (client) — per §5.3.
- `dashboard/components/SiteHeader.tsx` (client or server; contains a `next/link` + external anchor).
- `dashboard/components/SiteFooter.tsx`.
- `dashboard/lib/basePath.ts` — per §3.4.

### 5.5 Exact files to MODIFY

- `dashboard/app/page.tsx` — convert to **server** component (remove `"use client"`, remove the
  `useEffect`/`useState` fetch, remove the loading/error states). New behavior: read
  `public/repository.json` via `node:fs/promises`; on success render `<RepositoryOverview data={...} />`;
  on missing/invalid → render `<EmptyState />`. The masthead/footer markup moves out to
  `SiteHeader`/`SiteFooter` (now in `layout.tsx`).
- `dashboard/app/layout.tsx` — render `<SiteHeader />` and `<SiteFooter />` around `{children}` so
  navigation/chrome is shared across all routes.
- `dashboard/lib/types.ts` — additive per §3.3 (`DashboardData` gains `id` + `repo`; add
  `EvaluationSummary`, `RepositoryData`; `ComparisonResult` may be added here or in P2).
- **Delete** `dashboard/public/data.json` (V1 single-report file; superseded). If absent, no-op.

### 5.6 Exact data contracts

Consumes `repository.json` (§3.1) at `/` and `generateStaticParams`; consumes `evaluations/<id>.json`
(§3.2) at `/evaluations/[id]`. Produces none.

### 5.7 Exact export format

None (consumer phase). Data is produced by P0's `primer export --site-output dashboard/public`, which
the agent runs (or commits sample fixtures) so the build has data to read.

### 5.8 Exact migration strategy

- The current `app/page.tsx` "ok"-branch JSX is **moved**, not rewritten, into `EvaluationDetail`
  (preserving B.1–B.4 exactly). Diff review must show the component subtree unchanged.
- Local dev/build requires data: run `primer export --site-output dashboard/public <repo>` before
  `npm run build`. For environments without a DB, commit a representative `repository.json` +
  `evaluations/*.json` so the build is reproducible.
- `NEXT_PUBLIC_BASE_PATH` continues to govern asset/link base (unchanged from V1).

### 5.9 Exact risks

| Risk | Mitigation (mandatory) |
|---|---|
| `output:"export"` build fails on a dynamic route without `generateStaticParams` | `generateStaticParams` is implemented in the server `[id]/page.tsx` and returns `[]` when data absent. |
| Build fails when data files are missing | All build-time reads are wrapped so a missing/invalid file yields `EmptyState` (home) or `[]` (params); the build never throws. |
| Server component using client-only APIs | All motion/hooks/interactivity live in the client child components (`EvaluationDetail`, `RepositoryOverview`, `EvaluationLedger`); the route files are server components that only read files and pass serializable props. |
| Accidental visual/behavior change to B.1–B.4 | `EvaluationDetail` is a pure move of existing JSX; reviewer confirms the component stack and props are identical to the prior "ok" branch. |
| `trailingSlash` link breakage | All internal navigation uses `next/link` with `/evaluations/<id>/`-style hrefs; Next applies `basePath` + trailing slash. |
| Stale `data.json` left behind | P1 deletes `dashboard/public/data.json`. |

### 5.10 Exact acceptance criteria

1. `npm run build` (in `dashboard/`) succeeds with `output: "export"` **both** when site data is
   present (generates `/` + one `/evaluations/<id>/` page per evaluation) **and** when site data is
   absent (generates `/` rendering `EmptyState`, zero detail pages, no error).
2. `/` renders the repository identity + an `EvaluationLedger` listing all evaluations newest-first,
   each linking to its detail page; with zero evaluations it renders `EmptyState`.
3. `/evaluations/<id>/` renders the **exact** B.1–B.4 component stack against
   `evaluations/<id>.json`, with a working back-link to `/`.
4. The masthead/footer are shared via `layout.tsx`; the `PRIMER` wordmark links to `/`.
5. `EvaluationLedger` shows each delta with its noise envelope and labels `within-noise` rows; it
   contains no line/area/trend chart.
6. No edits to any of the eight reused components except (later) `EmptyState` text. `git diff` of the
   moved JSX shows the evaluation stack unchanged.
7. `dashboard/public/data.json` no longer exists.
8. Commit created only after a clean build.

---

## 6. PHASE P2 — COMPARISON + HONEST LEDGER

### 6.1 Exact objective

Surface the existing `compare` capability (the context-file improvement loop) as a first-class route,
with byte-for-byte honesty parity to `render_compare` (refuse on provider/model mismatch). No new
export files are required; the comparison is computed client-side from two already-exported evaluation
payloads.

### 6.2 Exact routes

- `/compare/` — client component. Reads `a` and `b` evaluation ids from the URL query
  (`?a=<id>&b=<id>`) via `useSearchParams()` (wrapped in `<Suspense>`), runtime-fetches both
  `evaluations/<id>.json` (prefixed with `BASE_PATH`), and renders the comparison.

### 6.3 Exact components

- `ComparePanel` (client) — props `{ a: DashboardData; b: DashboardData }`. Calls
  `computeComparison(a, b)` (§3.5) and renders: the provenance diff rows (highlighting `differ`), the
  cross-report delta **or** the refusal message when `refused`, an isolation-mismatch warning when
  `isolation_mismatch`, and each side's headline (reuse `formatPct`/`formatDelta`). May reuse
  `TaskFlipTable` per side for per-task context. No new verdict math.
- `EvaluationPicker` (client) — props `{ evaluations: EvaluationSummary[]; a: number|null; b: number|null }`.
  Two selects (baseline A / new B) that update the `?a=&b=` query (via `next/navigation` router). Used
  when the page is opened without both params.
- **Reused:** `TaskFlipTable`, `WarningBanner`, `EmptyState`, `lib/format.ts`.

### 6.4 Exact files to CREATE

- `dashboard/app/compare/page.tsx` — client component. Contract:
  - Wrap `useSearchParams()` usage in `<Suspense fallback={…}>`.
  - Parse `a`,`b` (numbers). If both present: runtime-fetch
    `${BASE_PATH}/evaluations/${a}.json` and `${BASE_PATH}/evaluations/${b}.json`; on success render
    `<ComparePanel a={…} b={…} />`; on fetch failure render an inline error + `<EvaluationPicker />`.
    If either missing: runtime-fetch `${BASE_PATH}/repository.json` and render `<EvaluationPicker
    evaluations={…} a={a} b={b} />`.
- `dashboard/components/ComparePanel.tsx` (client) — per §6.3.
- `dashboard/components/EvaluationPicker.tsx` (client) — per §6.3.
- `dashboard/lib/compare.ts` — `computeComparison` per §3.5 (pure).
- `tests/`/dashboard test (see §6.10) — a parity check for `computeComparison`.

### 6.5 Exact files to MODIFY

- `dashboard/components/EvaluationDetail.tsx` — wire the "Compare" affordance: when `prevId !== null`,
  render a `next/link` to `/compare/?a=<prevId>&b=<data.id>` ("Compare with previous evaluation").
- `dashboard/components/EvaluationLedger.tsx` — (optional, in-scope) add a per-row "compare with
  previous" link `/compare/?a=<olderId>&b=<thisId>` where an older sibling exists.
- `dashboard/lib/types.ts` — add `ComparisonResult` (§3.5) if not added in P1.
- `dashboard/components/SiteHeader.tsx` — add a `Compare` nav link to `/compare/`.

### 6.6 Exact data contracts

Consumes two `evaluations/<id>.json` (§3.2) + `repository.json` (§3.1, for the picker). Produces
`ComparisonResult` (§3.5) in memory only. No files written.

### 6.7 Exact export format

**None.** P2 adds no exporter. The comparison is derived client-side. (Rationale: N² comparison files
are avoided; the client helper mirrors `render_compare` exactly, preserving honesty without
duplicating data.)

### 6.8 Exact migration strategy

- Pure addition of one route + helpers; P0/P1 artifacts unchanged.
- `computeComparison` is kept in lockstep with `render_compare`: any future change to the CLI compare
  rules must update both (documented in the file header).

### 6.9 Exact risks

| Risk | Mitigation (mandatory) |
|---|---|
| `useSearchParams` without Suspense breaks the static export build | Mandatory `<Suspense>` boundary around the param-reading subtree. |
| Runtime fetch 404 on GitHub Pages (basePath) | All fetches prefixed with `BASE_PATH` (`lib/basePath.ts`), exactly as V1 fetched `data.json`. |
| Compare diverges from CLI honesty (shows a delta on mismatch) | `computeComparison` mirrors `render_compare` field-for-field; a unit test asserts: provider/model mismatch → `refused===true` and `cross_report_delta===null`; isolation mismatch → `isolation_mismatch===true`; matched providers → `cross_report_delta === b.delta - a.delta`. |
| Picker referencing nonexistent ids | Picker options come from `repository.json`; links only to existing ids. |

### 6.10 Exact acceptance criteria

1. `/compare/?a=<id>&b=<id>` renders the provenance diff, each side's headline, and either the
   cross-report delta (matched provider/model) or the refusal message (mismatch) — never a fabricated
   number on mismatch.
2. Opening `/compare/` with missing/partial params renders `EvaluationPicker`; choosing A and B
   updates the query and renders the comparison.
3. An isolation mismatch surfaces a warning; a provider/model mismatch refuses the delta.
4. From an Evaluation Detail page with a previous sibling, the "Compare with previous" link navigates
   to the correct `/compare/?a=&b=`.
5. A `computeComparison` unit test passes the parity assertions in §6.9.
6. `npm run build` succeeds (static export, Suspense satisfied); existing routes unaffected.
7. Commit created only after a clean build + green tests.

---

## 7. PHASE P3 — LIVE CI SURFACE (+ optional multi-repo)

### 7.1 Exact objective

Make the published dashboard genuinely live and consistent: the GitHub Pages deploy builds from
committed V2 site data, the badge and the scorecard come from the **same** export, and the half-wired
"badge updates but data doesn't" gap is closed. Optionally (deferred) add a multi-repository index.

### 7.2 Exact routes

- No new required routes.
- **OPTIONAL/deferred:** `/repositories/` — multi-repo index (only if `list_reports(repo_path=None)`
  yields more than one distinct `repo_path`). Built only when explicitly requested; default build is
  single-repo.

### 7.3 Exact components

- **OPTIONAL/deferred:** `RepositoryList` (client) — props `{ repos: RepositoryData[] }` linking each
  to its overview. Not built in the default P3.

### 7.4 Exact files to CREATE

- `dashboard/README.md` — short "how to regenerate site data" doc: the exact command
  `primer export --site-output dashboard/public --repo-name <name> [--repo-url <url>] <repo_path>`,
  the commit-the-JSON workflow, and the local `npm run build` step.
- **OPTIONAL/deferred:** `dashboard/app/repositories/page.tsx` + `dashboard/components/RepositoryList.tsx`
  + a multi-repo `repositories.json` exporter (only on explicit request; contract: array of
  `repository.json` summaries). Not part of default P3 acceptance.

### 7.5 Exact files to MODIFY

- `.github/workflows/pages.yml`:
  - **Remove** the `Copy scores.json to output` step (`cp scores.json dashboard/out/scores.json`):
    `scores.json` now lives in `dashboard/public/` and is emitted into `out/` by the build itself.
  - **Add**, before the build step, a **guard** step that fails the job with a clear message if
    `dashboard/public/repository.json` is absent (prevents silently deploying an empty/stale site).
  - Keep `npm ci` / `npm run build` (`NEXT_PUBLIC_BASE_PATH=/primer`) / `.nojekyll` / upload / deploy.
  - **Do NOT** add a `primer eval` or `primer export` step to CI (rationale §7.8): evaluation requires
    Docker + an Anthropic key + real spend, which is out of scope for CI. Site data is generated
    locally and committed.
- `dashboard/components/EmptyState.tsx` — **text only**: replace the V1 instruction
  (`primer export --data-output dashboard/public/data.json`) with the V2 command
  (`primer export --site-output dashboard/public`). No structural/visual change.
- `.gitignore` — verify `dashboard/public/*.json` is **not** ignored (currently `*.db`/`primer.db`
  only; if any rule would ignore these JSONs, add an explicit un-ignore). Commit the V2 site data tree.
- `README.md` (root) — update the one-line usage to mention `primer export --site-output dashboard/public`
  (the badge/dashboard publish path). Honesty wording unchanged (no forbidden substrings).

### 7.6 Exact data contracts

Consumes/commits the P0 site tree (§2/§3). Optional multi-repo `repositories.json` (deferred):
`{ schema_version: 2, kind: "repository-list", repositories: RepositoryData[] (summary form),
generated_at: string }`.

### 7.7 Exact export format

Unchanged from P0 (single-repo). Optional deferred multi-repo adds `repositories.json` per §7.6.

### 7.8 Exact migration strategy

- **Generation runs locally, not in CI.** The author runs `primer eval` (Docker + key + cost) then
  `primer export --site-output dashboard/public`, and **commits** `dashboard/public/repository.json`,
  `dashboard/public/evaluations/*.json`, `dashboard/public/scores.json`. CI builds from the commit.
  Rationale: CI cannot/should not spend money or run Docker eval on every push; the previous
  architecture review explicitly excludes auto-eval-in-CI and PMF/infra that does not pay.
- The badge endpoint URL in `README.md`
  (`https://kanwa2006.github.io/primer/scores.json`) is unchanged: `scores.json` ships from
  `dashboard/public/` through the build into `out/`, so the shields endpoint keeps resolving.

### 7.9 Exact risks

| Risk | Mitigation (mandatory) |
|---|---|
| Removing the `cp scores.json` step breaks the badge | `scores.json` is exported into `dashboard/public/` (P0 step 8) and copied to `out/` by `next build` (public assets are emitted); the guard step + a post-build check confirm `out/scores.json` exists. |
| Deploying stale/empty data when the author forgot to re-export | Guard step fails the workflow if `dashboard/public/repository.json` is missing; the committed data is the single source for the deploy. |
| Multi-repo scope creep | `/repositories` is explicitly deferred and excluded from default P3 acceptance; default build is single-repo. |
| `NEXT_PUBLIC_BASE_PATH` mismatch between badge URL and assets | Build keeps `NEXT_PUBLIC_BASE_PATH=/primer`; all runtime fetches use `BASE_PATH`; verified by loading `/compare` on the deployed base path. |

### 7.10 Exact acceptance criteria

1. The Pages workflow builds and deploys using only committed `dashboard/public/*.json` (no `primer
   eval`/`export` in CI); the job **fails fast** if `repository.json` is missing.
2. After deploy, `out/scores.json` exists and the README shields badge resolves to the latest delta.
3. The deployed `/` shows the repository overview + ledger; `/evaluations/<id>/` and `/compare/` work
   under the `/primer` base path.
4. `EmptyState` instructs the V2 command (`--site-output dashboard/public`).
5. `dashboard/public/*.json` are tracked in git (not ignored) and present in the commit.
6. The optional `/repositories` index is **not** built unless explicitly requested.
7. Commit created only after a clean local build + workflow validation.

---

## 8. CROSS-PHASE DEFINITION OF DONE

V2 is complete when:

- P0–P3 acceptance criteria all hold.
- The frozen surfaces (§0.1) are byte-unchanged in behavior; `build_dashboard_json` still emits
  `schema_version==1`; `_compute_verdict` is the only verdict authority.
- Boundary invariants hold: `report/export.py` imports no `sqlite3`/`docker`; only `store/` touches
  SQLite; only `cli.py` orchestrates.
- The site renders a Repository → Evaluations(ledger) → Evaluation detail (B.1–B.4 verbatim) → Compare
  graph, with shared navigation, under both local (`""`) and CI (`/primer`) base paths.
- Honesty invariants (§0.3) hold everywhere: verdict labels only, refuse-on-mismatch in compare,
  ledger shows noise envelopes, no smoothed trend line, two-stream cost separation intact.
- Framework APIs used in P1/P2 were verified via Context7 before coding; each frontend phase closed
  with an `impeccable` audit against the existing design system (§0.6); no UI was generated from an
  MCP connector.

---

## 9. EXPLICIT NON-GOALS (DO NOT BUILD)

The executing agent must **not** add, in any phase:

- Authentication, organizations, teams, seats, billing, or multi-tenant features.
- A hosted PR bot / GitHub App, or any server that runs evaluations on demand.
- `primer eval` or `primer export` execution inside CI.
- A smoothed/interpolated trend or time-series **chart** of deltas (verdict ledger only).
- Any new verdict/statistics/scoring computation (reuse `_compute_verdict` / `render_compare` rules).
- Any change to the eval engine, Docker isolation, statistics, schema, or generation.
- Any new visual language, color system, typography, or animation tokens (reuse the existing
  design system and `lib/format.ts`).
- Any component, page, layout, or asset generated or imported from an MCP connector
  (21st.dev Magic / Figma / Canva / Miro) — those connectors are pattern-study aids only (§0.6).

---

## 10. PHASE GATE ORDERING (strict)

`P0 → P1 → P2 → P3`. Each phase must pass its §x.10 acceptance criteria and a clean build/test before
the next begins. P0 is independently shippable (JSON only). P1 is the report→platform crossing and is
the highest-value gate. Commits/pushes happen only after the active phase's acceptance passes (project
rules: validate → commit → push).
```
