import assert from "node:assert/strict";
import { computeComparison } from "../lib/compare.js";
import type { DashboardData } from "../lib/types.js";

function base(): DashboardData {
  return {
    schema_version: 2,
    id: 1,
    repo: { name: "testrepo", url: null },
    repo_commit: "abc1234",
    created_at: "2024-01-01T00:00:00Z",
    verdict: "positive",
    n_tasks: 10,
    runs_per_config: 3,
    success_rate_without: 0.5,
    success_rate_with: 0.7,
    success_delta: 0.2,
    success_stddev: 0.05,
    success_min: 0.4,
    success_max: 0.8,
    cost_without: 0.01,
    cost_with: 0.02,
    cost_delta_pct: 100,
    cost_confidence: "exact",
    provider: "anthropic",
    model: "claude-3-5-sonnet",
    agent_adapter: "claude_code",
    base_image: "ubuntu:22.04",
    network_mode: "none",
    egress_enforced: true,
    provider_mismatch_warning: null,
    isolation_mismatch_warning: null,
    flaky_task_warning: null,
    primer_overhead_usd: 0.001,
    primer_overhead_confidence: "exact",
    per_task: [],
  };
}

function mk(overrides: Partial<DashboardData> = {}): DashboardData {
  return { ...base(), ...overrides };
}

let passed = 0;
let failed = 0;

function test(name: string, fn: () => void) {
  try {
    fn();
    console.log(`  ✓ ${name}`);
    passed++;
  } catch (e) {
    console.error(`  ✗ ${name}`);
    console.error(`    ${(e as Error).message}`);
    failed++;
  }
}

console.log("\ncomputeComparison parity tests");

test("provider mismatch → refused===true, cross_report_delta===null", () => {
  const a = mk({ provider: "anthropic", model: "claude-3-5-sonnet", success_delta: 0.1 });
  const b = mk({ provider: "openai",    model: "gpt-4",             success_delta: 0.3 });
  const r = computeComparison(a, b);
  assert.equal(r.refused, true);
  assert.equal(r.provider_mismatch, true);
  assert.equal(r.cross_report_delta, null);
});

test("model mismatch (same provider) → refused===true, cross_report_delta===null", () => {
  const a = mk({ provider: "anthropic", model: "claude-3-5-sonnet", success_delta: 0.1 });
  const b = mk({ provider: "anthropic", model: "claude-3-opus",     success_delta: 0.3 });
  const r = computeComparison(a, b);
  assert.equal(r.refused, true);
  assert.equal(r.provider_mismatch, true);
  assert.equal(r.cross_report_delta, null);
});

test("isolation mismatch via network_mode → isolation_mismatch===true", () => {
  const a = mk({ network_mode: "none" });
  const b = mk({ network_mode: "host" });
  const r = computeComparison(a, b);
  assert.equal(r.isolation_mismatch, true);
  assert.equal(r.refused, false);
});

test("isolation mismatch via egress_enforced → isolation_mismatch===true", () => {
  const a = mk({ egress_enforced: true });
  const b = mk({ egress_enforced: false });
  const r = computeComparison(a, b);
  assert.equal(r.isolation_mismatch, true);
  assert.equal(r.refused, false);
});

test("isolation mismatch via base_image → isolation_mismatch===true", () => {
  const a = mk({ base_image: "ubuntu:22.04" });
  const b = mk({ base_image: "debian:12" });
  const r = computeComparison(a, b);
  assert.equal(r.isolation_mismatch, true);
  assert.equal(r.refused, false);
});

test("matched providers + both deltas → cross_report_delta === b.delta − a.delta", () => {
  const a = mk({ success_delta: 0.1 });
  const b = mk({ success_delta: 0.3 });
  const r = computeComparison(a, b);
  assert.equal(r.refused, false);
  assert.equal(r.provider_mismatch, false);
  assert.ok(r.cross_report_delta !== null);
  assert.ok(Math.abs(r.cross_report_delta! - (0.3 - 0.1)) < 1e-12);
});

test("matched providers + null delta on a → cross_report_delta===null", () => {
  const a = mk({ success_delta: null });
  const b = mk({ success_delta: 0.3 });
  const r = computeComparison(a, b);
  assert.equal(r.refused, false);
  assert.equal(r.cross_report_delta, null);
});

test("matched providers + null delta on b → cross_report_delta===null", () => {
  const a = mk({ success_delta: 0.1 });
  const b = mk({ success_delta: null });
  const r = computeComparison(a, b);
  assert.equal(r.refused, false);
  assert.equal(r.cross_report_delta, null);
});

test("clean comparison → isolation_mismatch===false, refused===false", () => {
  const r = computeComparison(base(), base());
  assert.equal(r.refused, false);
  assert.equal(r.provider_mismatch, false);
  assert.equal(r.isolation_mismatch, false);
});

test("fields contains 10 rows in spec order", () => {
  const r = computeComparison(base(), base());
  const labels = r.fields.map((f) => f.label);
  assert.deepEqual(labels, [
    "Repo commit",
    "Evaluated at",
    "Provider",
    "Model",
    "Agent",
    "Base image",
    "Network mode",
    "Egress enforced",
    "Tasks",
    "Runs/config",
  ]);
});

test("differ flag set correctly for differing repo_commit", () => {
  const a = mk({ repo_commit: "aaa" });
  const b = mk({ repo_commit: "bbb" });
  const r = computeComparison(a, b);
  const row = r.fields.find((f) => f.label === "Repo commit")!;
  assert.equal(row.differ, true);
  assert.equal(row.a, "aaa");
  assert.equal(row.b, "bbb");
});

console.log(`\n${passed} passed, ${failed} failed\n`);
if (failed > 0) process.exit(1);
