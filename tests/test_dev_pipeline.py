from __future__ import annotations

import json
from pathlib import Path

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
    add_task(repo, demo_task(risk=2, fail_first_rounds=1))
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
    from econ.dev.workspace import worktrees_root

    assert not worktrees_root(repo).exists()


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
    add_task(repo, demo_task(risk=2, fail_first_rounds=99))
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


# -- tier routing: the gates, not the agents, are the authority -------------
def _started_roles(repo: Path, task_id: str) -> list[str]:
    events = (repo / "runs" / "dev" / "tasks" / task_id / "events.jsonl").read_text()
    roles = []
    for line in events.splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("event") == "agent_started":
            roles.append(payload["role"])
    return roles


def test_risk_one_runs_no_lead_and_no_reviewer(tmp_path):
    repo = make_repo(tmp_path / "repo")
    add_task(repo, demo_task())
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "done", outcome.decision
    # Risk 0/1 is intake -> implementer -> verifier -> gates. The lead plan and
    # the LLM reviewers are a risk >= 2 control; buying them for a one-file
    # patch is pure ceremony.
    assert _started_roles(repo, "DEV-0001") == ["implementer", "verifier"]


def test_risk_two_keeps_the_full_ladder(tmp_path):
    repo = make_repo(tmp_path / "repo")
    add_task(repo, demo_task(risk=2))
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "done", outcome.decision
    roles = _started_roles(repo, "DEV-0001")
    assert roles[0] == "lead"
    assert roles[1] == "architect"
    for expected in (
        "implementer",
        "reviewer",
        "reviewer_alt",
        "verifier",
        "science_guard",
    ):
        assert expected in roles


def test_bug_sourced_risk_one_runs_the_reproducer_first(tmp_path):
    from econ.dev.models import Source

    repo = make_repo(tmp_path / "repo")
    task = demo_task().model_copy(update={"source": Source(kind="bug")})
    add_task(repo, task)
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "done", outcome.decision
    roles = _started_roles(repo, "DEV-0001")
    assert roles[0] == "reproducer"
    assert roles.index("reproducer") < roles.index("implementer")
    repro = json.loads(
        (repo / "runs" / "dev" / "tasks" / "DEV-0001" / "out" / "reproducer.json").read_text()
    )
    assert repro["reproduced"] is True
    assert repro["test_file"].startswith("tests/")
    assert repro["failing_command"]


def test_unreproduced_bug_escalates_before_any_fix(tmp_path):
    from econ.dev.models import Source

    repo = make_repo(tmp_path / "repo")
    files = [{"path": "src/econ/thing.py", "content": "VALUE = 2\n"}]
    task = demo_task(files=files, acceptance=["python -m pytest -q"]).model_copy(
        update={"source": Source(kind="bug")}
    )
    add_task(repo, task)
    outcome = run_task(repo, "DEV-0001")
    # No failing test, no fix: the pipeline must not patch an unproven bug.
    assert outcome.status == "escalated"
    assert "reproduc" in outcome.decision["reason"]
    assert not (repo / "src" / "econ" / "thing.py").exists()


def test_risk_two_critical_path_touch_escalates(tmp_path):
    repo = make_repo(tmp_path / "repo")
    # A five-line Makefile edit inside the merge-critical table. The task tier
    # allows auto-merge (Makefile is deliberately unprotected); the blast
    # radius does not: the referee's build entry point needs a human.
    files = [
        {"path": "Makefile", "content": "all:\n\techo ok\n"},
        {"path": "src/econ/mkflag.py", "content": "FLAG = 'from-makefile'\n"},
        {
            "path": "tests/test_mkflag.py",
            "content": "from econ.mkflag import FLAG\n\n\ndef test_flag():\n    assert FLAG == 'from-makefile'\n",
        },
    ]
    policy = default_policy()
    policy.auto_merge.critical_paths = [
        *policy.auto_merge.critical_paths,
        "Makefile",
    ]
    add_task(
        repo,
        demo_task(
            risk=2,
            files=files,
            acceptance=["python -m pytest tests/test_mkflag.py -q"],
            allow=[item["path"] for item in files],
        ),
    )
    outcome = run_task(repo, "DEV-0001", policy=policy)
    assert outcome.status == "escalated", outcome.decision
    assert "critical" in outcome.decision["reason"]
    assert not (repo / "Makefile").exists()
    assert not (repo / "src" / "econ" / "mkflag.py").exists()


def test_risk_two_coverage_drop_escalates(tmp_path):
    from dev_support import git

    repo = make_repo(tmp_path / "repo")
    # Base: one fully covered statement. Patch: six statements, one never
    # executed by the tests. The diff is small, in scope, and green — the
    # coverage delta is what stops the auto-merge.
    (repo / "src" / "econ" / "covmod.py").write_text("def f(x):\n    return 1\n")
    (repo / "tests" / "test_covmod.py").write_text(
        "from econ.covmod import f\n\n\ndef test_f():\n    assert f(1) == 1\n"
    )
    git(["add", "-A"], repo)
    git(["commit", "-q", "-m", "covmod baseline"], repo)
    files = [
        {
            "path": "src/econ/covmod.py",
            "content": (
                "def f(x):\n"
                "    if x > 0:\n"
                "        return 1\n"
                "    if x < -100:\n"
                "        return -1\n"
                "    return 0\n"
            ),
        },
        {
            "path": "tests/test_covmod.py",
            "content": (
                "from econ.covmod import f\n\n\n"
                "def test_f():\n"
                "    assert f(1) == 1\n"
                "    assert f(-1) == 0\n"
            ),
        },
    ]
    add_task(
        repo,
        demo_task(
            risk=2,
            files=files,
            acceptance=["python -m pytest tests/test_covmod.py -q"],
            allow=[item["path"] for item in files],
        ),
    )
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "escalated", outcome.decision
    assert "coverage_delta" in outcome.decision["reason"]
    gates = json.loads(
        (repo / "runs" / "dev" / "tasks" / "DEV-0001" / "gates-post.json").read_text()
    )
    cov = next(g for g in gates["gates"] if g["name"] == "coverage_delta")
    assert "coverage dropped on: src/econ/covmod.py" in cov["detail"]
    assert cov["evidence"]["rows"][0]["delta"] < 0
    assert not (repo / "src" / "econ" / "covmod.py").read_text().count("return -1")


def test_risk_two_large_non_critical_change_still_auto_merges(tmp_path):
    repo = make_repo(tmp_path / "repo")
    # The caps are a secondary guard now: a 200-line non-critical risk-2
    # change that passes every gate still auto-merges.
    files = [
        {
            "path": f"src/econ/pad{i}.py",
            "content": "LINES = [\n" + "".join(f"    {n},\n" for n in range(95)) + "]\n",
        }
        for i in (1, 2)
    ]
    files.append(
        {
            "path": "tests/test_pad.py",
            "content": (
                "from econ.pad1 import LINES as L1\n"
                "from econ.pad2 import LINES as L2\n\n\n"
                "def test_pad():\n"
                "    assert len(L1) == len(L2) == 95\n"
            ),
        }
    )
    add_task(
        repo,
        demo_task(
            risk=2,
            files=files,
            acceptance=["python -m pytest tests/test_pad.py -q"],
            allow=[item["path"] for item in files],
        ),
    )
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "done", outcome.decision
    assert (repo / "src" / "econ" / "pad1.py").exists()
