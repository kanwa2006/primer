"""P0-T1 unit tests for pure site-export builder functions (V2 Spec §4.10).

Covers acceptance criteria (1)-(3), (5), (6) — the pure-function layer only.
CLI orchestration (criterion 4) is tested in P0-T2 (test_site_export_cli.py).
"""
import json
import re
from pathlib import Path

import pytest

from primer.eval.models import ScoreReport, TaskScore
from primer.report.export import (
    _compute_verdict,
    build_dashboard_json,
    build_evaluation_json,
    build_repository_json,
    write_evaluation_json,
    write_repository_json,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_TASK = TaskScore(
    task_id="task_001",
    task_type="revert_reimplement",
    pass_rate_without=0.0,
    pass_rate_with=1.0,
    delta=1.0,
    runs=4,
    flaky_any=False,
)

_REPORT = ScoreReport(
    repo_commit="abc1234",
    created_at="2025-01-15T12:00:00Z",
    n_tasks=2,
    runs_per_config=4,
    success_rate_without=0.0,
    success_rate_with=1.0,
    success_delta=1.0,
    success_stddev=0.05,
    success_min=0.8,
    success_max=1.0,
    cost_without=0.01,
    cost_with=0.02,
    cost_delta_pct=100.0,
    cost_confidence="exact",
    per_task=[_TASK],
    provider="anthropic",
    model="claude-3-5-sonnet-20241022",
    agent_adapter="claude-code",
    base_image="python:3.11-slim@sha256:deadbeef",
    network_mode="proxy-egress",
    egress_enforced=True,
)

_REPORT_ID = 42
_REPO_NAME = "test-repo"
_REPO_URL = "https://github.com/example/test-repo"


def _make_report(**overrides) -> ScoreReport:
    """Return a ScoreReport built from _REPORT's values plus overrides."""
    import dataclasses
    base = dataclasses.asdict(_REPORT)
    # dataclasses.asdict recursively converts; rebuild per_task as TaskScore objects
    base["per_task"] = list(_REPORT.per_task)
    base.update(overrides)
    return ScoreReport(**base)


# ---------------------------------------------------------------------------
# §4.10 (3): build_evaluation_json
# ---------------------------------------------------------------------------

class TestBuildEvaluationJson:

    def test_schema_version_overridden_to_2(self):
        result = build_evaluation_json(_REPORT_ID, _REPORT, _REPO_NAME, _REPO_URL)
        assert result["schema_version"] == 2

    def test_kind_is_evaluation(self):
        result = build_evaluation_json(_REPORT_ID, _REPORT, _REPO_NAME, _REPO_URL)
        assert result["kind"] == "evaluation"

    def test_id_matches_report_id(self):
        result = build_evaluation_json(_REPORT_ID, _REPORT, _REPO_NAME, _REPO_URL)
        assert result["id"] == _REPORT_ID

    def test_repo_field(self):
        result = build_evaluation_json(_REPORT_ID, _REPORT, _REPO_NAME, _REPO_URL)
        assert result["repo"] == {"name": _REPO_NAME, "url": _REPO_URL}

    def test_repo_url_none(self):
        result = build_evaluation_json(_REPORT_ID, _REPORT, _REPO_NAME, None)
        assert result["repo"]["url"] is None

    def test_all_base_fields_inherited(self):
        base = build_dashboard_json(_REPORT)
        result = build_evaluation_json(_REPORT_ID, _REPORT, _REPO_NAME, _REPO_URL)
        for key, value in base.items():
            if key == "schema_version":
                continue  # intentionally overridden
            assert result[key] == value, f"field {key!r} not inherited correctly"

    def test_exactly_right_new_keys(self):
        """Only kind, id, repo are added; schema_version is overridden, not added."""
        base = build_dashboard_json(_REPORT)
        result = build_evaluation_json(_REPORT_ID, _REPORT, _REPO_NAME, _REPO_URL)
        new_keys = set(result.keys()) - set(base.keys())
        assert new_keys == {"kind", "id", "repo"}

    def test_no_base_keys_removed(self):
        base = build_dashboard_json(_REPORT)
        result = build_evaluation_json(_REPORT_ID, _REPORT, _REPO_NAME, _REPO_URL)
        missing = set(base.keys()) - set(result.keys())
        assert missing == set()

    def test_different_report_ids_produce_correct_id(self):
        for rid in (1, 999, 0):
            assert build_evaluation_json(rid, _REPORT, _REPO_NAME, _REPO_URL)["id"] == rid


# ---------------------------------------------------------------------------
# §4.10 (2): build_repository_json
# ---------------------------------------------------------------------------

class TestBuildRepositoryJson:

    def setup_method(self):
        self.report_a = _make_report(
            repo_commit="aaa111",
            created_at="2025-01-02T00:00:00Z",
            success_delta=0.5,
            success_stddev=0.1,
            n_tasks=2,
        )
        self.report_b = _make_report(
            repo_commit="bbb222",
            created_at="2025-01-01T00:00:00Z",
            success_delta=0.02,
            success_stddev=0.05,
            n_tasks=2,
        )
        self.items = [(10, self.report_a), (5, self.report_b)]
        self.generated_at = "2025-01-03T00:00:00Z"
        self.result = build_repository_json(
            _REPO_NAME, _REPO_URL, self.items, self.generated_at
        )

    def test_schema_version(self):
        assert self.result["schema_version"] == 2

    def test_kind(self):
        assert self.result["kind"] == "repository"

    def test_repo_name_and_url(self):
        assert self.result["repo"]["name"] == _REPO_NAME
        assert self.result["repo"]["url"] == _REPO_URL

    def test_repo_latest_commit_from_first_item(self):
        assert self.result["repo"]["latest_commit"] == self.report_a.repo_commit

    def test_latest_evaluation_id(self):
        assert self.result["latest_evaluation_id"] == 10

    def test_latest_verdict_matches_first_item(self):
        expected = _compute_verdict(
            self.report_a.success_delta,
            self.report_a.n_tasks,
            self.report_a.success_stddev,
        )
        assert self.result["latest_verdict"] == expected

    def test_evaluation_count(self):
        assert self.result["evaluation_count"] == 2

    def test_generated_at(self):
        assert self.result["generated_at"] == self.generated_at

    def test_evaluations_newest_first(self):
        evals = self.result["evaluations"]
        assert len(evals) == 2
        assert evals[0]["id"] == 10
        assert evals[1]["id"] == 5

    def test_evaluation_summary_required_fields(self):
        summary = self.result["evaluations"][0]
        report = self.report_a
        expected_fields = {
            "id", "repo_commit", "created_at", "verdict", "success_delta",
            "success_stddev", "n_tasks", "runs_per_config", "noise_threshold",
            "provider", "model", "agent_adapter", "egress_enforced",
        }
        assert set(summary.keys()) == expected_fields

    def test_evaluation_summary_values(self):
        summary = self.result["evaluations"][0]
        r = self.report_a
        assert summary["repo_commit"] == r.repo_commit
        assert summary["created_at"] == r.created_at
        assert summary["success_delta"] == r.success_delta
        assert summary["success_stddev"] == r.success_stddev
        assert summary["n_tasks"] == r.n_tasks
        assert summary["runs_per_config"] == r.runs_per_config
        assert summary["provider"] == r.provider
        assert summary["model"] == r.model
        assert summary["agent_adapter"] == r.agent_adapter
        assert summary["egress_enforced"] == r.egress_enforced

    def test_verdict_per_evaluation(self):
        for summary, (_, report) in zip(self.result["evaluations"], self.items):
            expected = _compute_verdict(
                report.success_delta, report.n_tasks, report.success_stddev
            )
            assert summary["verdict"] == expected

    def test_noise_threshold_per_evaluation(self):
        for summary, (_, report) in zip(self.result["evaluations"], self.items):
            n = report.n_tasks
            expected = max(1 / n, report.success_stddev) if n > 0 else report.success_stddev
            assert summary["noise_threshold"] == pytest.approx(expected)

    def test_noise_threshold_zero_tasks_uses_stddev(self):
        r = _make_report(n_tasks=0, success_stddev=0.12, success_delta=None, per_task=[])
        result = build_repository_json(_REPO_NAME, None, [(99, r)], "2025-01-01T00:00:00Z")
        assert result["evaluations"][0]["noise_threshold"] == pytest.approx(0.12)

    def test_latest_fields_match_first_evaluation(self):
        first = self.result["evaluations"][0]
        assert self.result["latest_evaluation_id"] == first["id"]
        assert self.result["latest_verdict"] == first["verdict"]
        assert self.result["repo"]["latest_commit"] == first["repo_commit"]

    def test_empty_items(self):
        result = build_repository_json(_REPO_NAME, None, [], "2025-01-01T00:00:00Z")
        assert result["latest_evaluation_id"] is None
        assert result["latest_verdict"] is None
        assert result["evaluation_count"] == 0
        assert result["evaluations"] == []


# ---------------------------------------------------------------------------
# §4.10 (5) REGRESSION: build_dashboard_json schema_version still == 1
# ---------------------------------------------------------------------------

class TestRegressionFrozenBehavior:

    def test_build_dashboard_json_schema_version_still_1(self):
        """REGRESSION §4.10(5): build_dashboard_json must still emit schema_version==1."""
        assert build_dashboard_json(_REPORT)["schema_version"] == 1

    def test_build_evaluation_json_does_not_corrupt_subsequent_calls(self):
        """build_evaluation_json must not mutate state visible to build_dashboard_json."""
        before = build_dashboard_json(_REPORT)
        build_evaluation_json(_REPORT_ID, _REPORT, _REPO_NAME, _REPO_URL)
        after = build_dashboard_json(_REPORT)
        assert before == after

    def test_build_dashboard_json_schema_version_after_repository_build(self):
        build_repository_json(_REPO_NAME, _REPO_URL, [(_REPORT_ID, _REPORT)], "2025-01-01T00:00:00Z")
        assert build_dashboard_json(_REPORT)["schema_version"] == 1


# ---------------------------------------------------------------------------
# §4.10 (6) BOUNDARY: export.py must not import sqlite3 or docker
# ---------------------------------------------------------------------------

class TestBoundary:
    _EXPORT_SOURCE = (
        Path(__file__).parent.parent / "primer" / "report" / "export.py"
    ).read_text(encoding="utf-8")

    def test_no_sqlite3_import(self):
        """BOUNDARY §4.10(6): export.py must not import sqlite3."""
        assert "import sqlite3" not in self._EXPORT_SOURCE

    def test_no_docker_import(self):
        """BOUNDARY §4.10(6): export.py must not import docker."""
        assert "import docker" not in self._EXPORT_SOURCE


# ---------------------------------------------------------------------------
# PRIVACY: no exported payload contains absolute filesystem paths
# ---------------------------------------------------------------------------

class TestPrivacy:
    # Matches /absolute/unix/path (not URLs) or Windows C:\path
    _ABS_PATH_RE = re.compile(
        r'"(?:'
        r'(?<![:/])/(?:home|usr|tmp|var|root|opt|etc|Users|private)[^"]*'
        r'|[A-Za-z]:\\[^"]*'
        r')"'
    )

    def _assert_no_abs_path(self, payload: dict, label: str) -> None:
        serialized = json.dumps(payload)
        match = self._ABS_PATH_RE.search(serialized)
        assert match is None, f"Absolute path found in {label}: {match.group()!r}"

    def test_evaluation_json_no_absolute_path(self):
        payload = build_evaluation_json(_REPORT_ID, _REPORT, _REPO_NAME, _REPO_URL)
        self._assert_no_abs_path(payload, "evaluation payload")

    def test_repository_json_no_absolute_path(self):
        payload = build_repository_json(
            _REPO_NAME, _REPO_URL, [(_REPORT_ID, _REPORT)], "2025-01-01T00:00:00Z"
        )
        self._assert_no_abs_path(payload, "repository payload")

    def test_repo_path_never_in_payload(self, tmp_path):
        """Simulated repo_path must never leak into any exported payload."""
        repo_path = str(tmp_path / "my_project")
        eval_payload = build_evaluation_json(_REPORT_ID, _REPORT, _REPO_NAME, _REPO_URL)
        repo_payload = build_repository_json(
            _REPO_NAME, _REPO_URL, [(_REPORT_ID, _REPORT)], "2025-01-01T00:00:00Z"
        )
        for payload in (eval_payload, repo_payload):
            assert repo_path not in json.dumps(payload)


# ---------------------------------------------------------------------------
# §4.10 (1): write helpers create files with correct structure
# ---------------------------------------------------------------------------

class TestWriteHelpers:

    def test_write_evaluation_json_creates_file(self, tmp_path):
        payload = build_evaluation_json(_REPORT_ID, _REPORT, _REPO_NAME, _REPO_URL)
        out = tmp_path / "evaluations" / "42.json"
        result = write_evaluation_json(payload, out)
        assert result is payload
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["schema_version"] == 2
        assert data["kind"] == "evaluation"
        assert data["id"] == _REPORT_ID

    def test_write_repository_json_creates_file(self, tmp_path):
        payload = build_repository_json(
            _REPO_NAME, _REPO_URL, [(_REPORT_ID, _REPORT)], "2025-01-01T00:00:00Z"
        )
        out = tmp_path / "repository.json"
        result = write_repository_json(payload, out)
        assert result is payload
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["schema_version"] == 2
        assert data["kind"] == "repository"

    def test_write_evaluation_creates_parent_dirs(self, tmp_path):
        payload = build_evaluation_json(_REPORT_ID, _REPORT, _REPO_NAME, _REPO_URL)
        out = tmp_path / "deep" / "nested" / "evaluations" / "42.json"
        write_evaluation_json(payload, out)
        assert out.exists()

    def test_write_repository_creates_parent_dirs(self, tmp_path):
        payload = build_repository_json(_REPO_NAME, None, [], "2025-01-01T00:00:00Z")
        out = tmp_path / "site" / "repository.json"
        write_repository_json(payload, out)
        assert out.exists()

    def test_write_evaluation_json_encoding(self, tmp_path):
        payload = build_evaluation_json(_REPORT_ID, _REPORT, _REPO_NAME, _REPO_URL)
        out = tmp_path / "eval.json"
        write_evaluation_json(payload, out)
        raw = out.read_bytes()
        assert json.loads(raw.decode("utf-8")) == payload

    def test_write_functions_return_same_payload_object(self, tmp_path):
        eval_payload = build_evaluation_json(_REPORT_ID, _REPORT, _REPO_NAME, _REPO_URL)
        repo_payload = build_repository_json(_REPO_NAME, None, [], "2025-01-01T00:00:00Z")
        assert write_evaluation_json(eval_payload, tmp_path / "e.json") is eval_payload
        assert write_repository_json(repo_payload, tmp_path / "r.json") is repo_payload
