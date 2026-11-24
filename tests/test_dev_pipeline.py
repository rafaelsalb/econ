from __future__ import annotations

import json

from econ.dev.pipeline import DevPipeline
from econ.dev.runner import FakeRunner
from econ.dev.tasks import TaskStore

from dev_support import add_task, default_policy, demo_task, make_repo, run_task


def test_pipeline_merges_a_clean_task(tmp_path):
    repo = make_repo(tmp_path / "repo")
    add_task(repo, demo_task())
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "done", outcome.decision
    assert (repo / "src" / "econ" / "feature.py").exists()
    assert (repo / "tests" / "test_feature.py").exists()
    decision = json.loads((repo / "runs" / "dev" / "tasks" / "DEV-0001" / "decision.json").read_text())
    assert decision["merged_commit"]
    assert decision["status"] == "done"
    assert (repo / "tasks" / "done" / "DEV-0001.yaml").exists()
    assert not (repo / "tasks" / "ready" / "DEV-0001.yaml").exists()
    assert (repo / "runs" / "dev" / "tasks" / "DEV-0001" / "gates-pre.json").exists()
    assert (repo / "runs" / "dev" / "tasks" / "DEV-0001" / "gates-post.json").exists()


def test_shadow_mode_records_without_merging(tmp_path):
    repo = make_repo(tmp_path / "repo")
    add_task(repo, demo_task())
    outcome = run_task(repo, "DEV-0001", shadow=True)
    assert outcome.status == "shadow", outcome.decision
    assert not (repo / "src" / "econ" / "feature.py").exists()
    assert (repo / "tasks" / "done" / "DEV-0001.yaml").exists()


def test_review_loop_requests_one_revision_then_approves(tmp_path):
    repo = make_repo(tmp_path / "repo")
    add_task(repo, demo_task(fail_first_rounds=1))
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "done", outcome.decision
    assert outcome.rounds == 2
    events = (repo / "runs" / "dev" / "tasks" / "DEV-0001" / "events.jsonl").read_text()
    assert '"round": 2' in events
    assert (repo / "src" / "econ" / "feature.py").exists()


def test_dependency_change_is_escalated_not_merged(tmp_path):
    repo = make_repo(tmp_path / "repo")
    files = [
        {"path": "pyproject.toml", "content": '[project]\nname = "econ-test"\nversion = "0.2.0"\n'},
        {"path": "tests/test_dep.py", "content": "def test_ok():\n    assert True\n"},
    ]
    add_task(
        repo,
        demo_task(
            files=files,
            acceptance=["python -m pytest tests/test_dep.py -q"],
            allow=["pyproject.toml", "tests/test_dep.py"],
        ),
    )
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "escalated", outcome.decision
    assert "dependencies" in outcome.decision["reason"]
    assert not (repo / "pyproject.toml").read_text().count("0.2.0")


def test_scope_violation_is_escalated(tmp_path):
    repo = make_repo(tmp_path / "repo")
    files = [
        {"path": "src/econ/outside.py", "content": "VALUE = 1\n"},
        {"path": "tests/test_outside.py", "content": "from econ.outside import VALUE\n\n\ndef test_v():\n    assert VALUE == 1\n"},
    ]
    add_task(
        repo,
        demo_task(
            files=files,
            acceptance=["python -m pytest tests/test_outside.py -q"],
            allow=["tests/test_outside.py"],
        ),
    )
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "escalated", outcome.decision
    assert not (repo / "src" / "econ" / "outside.py").exists()


def test_risk_three_is_escalated_before_a_worktree(tmp_path):
    repo = make_repo(tmp_path / "repo")
    task = demo_task()
    task = task.model_copy(
        update={
            "risk": 3,
            "scope": task.scope.model_copy(update={"allow": ["specs/new_keynesian.yaml"]}),
            "demo": None,
        }
    )
    add_task(repo, task)
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "escalated"
    assert "scientific contract" in outcome.decision["reason"]
    assert not (repo / "runs" / "dev" / "worktrees").exists()


def test_no_auto_merge_escalates(tmp_path):
    repo = make_repo(tmp_path / "repo")
    add_task(repo, demo_task())
    outcome = run_task(repo, "DEV-0001", auto_merge=False)
    assert outcome.status == "escalated"
    assert not (repo / "src" / "econ" / "feature.py").exists()


def test_risk_two_requires_two_reviews_and_merges(tmp_path):
    repo = make_repo(tmp_path / "repo")
    add_task(repo, demo_task(risk=2))
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "done", outcome.decision
    assert len(outcome.reviews) == 2
    assert all(review["verdict"] == "approve" for review in outcome.reviews)
    assert (repo / "src" / "econ" / "feature.py").exists()


def test_always_rejecting_reviewer_escalates_after_budget(tmp_path):
    repo = make_repo(tmp_path / "repo")
    add_task(repo, demo_task(fail_first_rounds=99))
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "escalated"
    assert "review requested changes" in outcome.decision["reason"]


def test_verifier_failure_escalates(tmp_path):
    repo = make_repo(tmp_path / "repo")
    add_task(repo, demo_task(verifier="fail"))
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "escalated"
    assert "verifier" in outcome.decision["reason"]


def test_patch_artifact_and_cost_are_recorded(tmp_path):
    repo = make_repo(tmp_path / "repo")
    add_task(repo, demo_task())
    outcome = run_task(repo, "DEV-0001")
    run_dir = repo / "runs" / "dev" / "tasks" / "DEV-0001"
    patch = (run_dir / "patch.diff").read_text()
    assert "src/econ/feature.py" in patch
    assert (run_dir / "cost.json").exists()
    assert outcome.decision["changed_files"]
