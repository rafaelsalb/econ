from __future__ import annotations

import json
import subprocess

from econ.dev.canary import write_canary_report
from econ.dev.report import dashboard_markdown, metrics, write_dashboard
from econ.dev.release import bump_version, read_version, release

from dev_support import git, make_repo


def _append(repo, rows):
    path = repo / "runs" / "dev" / "index.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def test_metrics_and_dashboard(tmp_path):
    repo = make_repo(tmp_path / "repo")
    _append(
        repo,
        [
            {"task_id": "DEV-0001", "status": "done", "risk": 1, "rounds": 1, "merged_commit": "a"},
            {"task_id": "DEV-0002", "status": "done", "risk": 2, "rounds": 2, "merged_commit": "b"},
            {"task_id": "DEV-0003", "status": "escalated", "risk": 3, "rounds": 0},
            {"task_id": "DEV-0004", "status": "failed", "risk": 1, "rounds": 1},
        ],
    )
    m = metrics(repo)
    assert m["total"] == 4
    assert m["merged"] == 2
    assert m["escalated"] == 1
    assert m["failed"] == 1
    assert m["first_pass_rate"] == 0.5
    md = dashboard_markdown(repo)
    assert "# Development dashboard" in md
    assert "DEV-0003" in md
    info = write_dashboard(repo)
    assert (repo / "reports" / "dev_dashboard.md").exists()
    assert (repo / "reports" / "dev_dashboard.html").exists()
    assert info["metrics"]["total"] == 4


def test_metrics_report_step_limited_runs(tmp_path):
    repo = make_repo(tmp_path / "repo")
    _append(
        repo,
        [
            {
                "task_id": "DEV-0001",
                "status": "done",
                "risk": 1,
                "rounds": 1,
                "step_limit_reached": True,
                "max_step_utilization": 0.91,
            },
            {
                "task_id": "DEV-0002",
                "status": "done",
                "risk": 1,
                "rounds": 1,
                "step_limit_reached": False,
                "max_step_utilization": 0.4,
            },
        ],
    )
    m = metrics(repo)
    assert m["step_limited"] == 1
    assert m["max_step_utilization"] == 0.91
    md = dashboard_markdown(repo)
    assert "Step-limited runs | 1" in md
    assert "Highest step utilization | 91%" in md


def test_canary_results_are_persisted_in_the_dashboard(tmp_path):
    repo = make_repo(tmp_path / "repo")
    write_canary_report(
        repo,
        [
            {"task_id": "CANARY-001", "ok": True, "status": "done", "rounds": 1},
            {"task_id": "CANARY-002", "ok": False, "status": "failed", "rounds": 0, "reason": "boom"},
        ],
    )
    assert (repo / "reports" / "dev_canaries.md").exists()
    m = metrics(repo)
    assert m["canaries"]["passed"] == 1
    assert m["canaries"]["failed"] == 1
    md = dashboard_markdown(repo)
    assert "Held-out canaries" in md
    assert "CANARY-002" in md


def test_release_dry_run_and_real(tmp_path):
    repo = make_repo(tmp_path / "repo")
    assert read_version(repo) == "0.1.0"
    assert bump_version("0.1.0", "patch") == "0.1.1"
    assert bump_version("0.1.0", "minor") == "0.2.0"
    assert bump_version("0.1.0", "major") == "1.0.0"

    dry = release(repo, bump="minor", dry_run=True, check=False)
    assert dry["new_version"] == "0.2.0"
    assert read_version(repo) == "0.1.0"

    info = release(repo, bump="minor", check=False)
    assert info["new_version"] == "0.2.0"
    assert read_version(repo) == "0.2.0"
    assert (repo / "CHANGELOG.md").exists()
    tags = git(["tag", "-l"], repo).split()
    assert "v0.2.0" in tags
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout
    assert status.strip() == ""
