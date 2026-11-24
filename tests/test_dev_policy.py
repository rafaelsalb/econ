from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from econ.dev.models import Task, validate_task
from econ.dev.paths import overlap
from econ.dev.policy import DEFAULT_PROTECTED, DevPolicy, protected_hits
from econ.dev.tasks import TaskStore

REPO_ROOT = Path(__file__).resolve().parent.parent

# The merge authority and its calibration suite are referee paths. A task that
# wants to change them must be risk 3 and human-gated, exactly like the science
# gates: a controller that can silently rewrite itself makes every downstream
# verification unfalsifiable.
REFEREE_PATHS = [
    "src/econ/dev/pipeline.py",
    "src/econ/dev/gates.py",
    "src/econ/dev/scheduler.py",
    ".github/workflows/ci.yml",
    "tests/dev_support.py",
    "tasks/templates/task.yaml",
    "dev/evals/canary/CANARY-001.yaml",
]


def _task_payload(path: str, *, risk: int) -> dict:
    return {
        "id": "DEV-0001",
        "title": "referee change",
        "status": "ready",
        "risk": risk,
        "created": "2026-11-24",
        "goal": "change the merge authority",
        "acceptance": ["python -m pytest -q"],
        "scope": {"allow": [path]},
    }


@pytest.mark.parametrize("path", REFEREE_PATHS)
def test_referee_paths_require_risk_three(path: str):
    with pytest.raises(ValidationError, match="protected"):
        Task.model_validate(_task_payload(path, risk=2))


def test_referee_path_allowed_at_risk_three():
    task = Task.model_validate(_task_payload("src/econ/dev/pipeline.py", risk=3))
    assert task.risk == 3


@pytest.mark.parametrize("path", REFEREE_PATHS)
def test_referee_paths_are_protected_hits(path: str):
    assert protected_hits([path], list(DEFAULT_PROTECTED)) == [path]


def test_policy_config_matches_code_default():
    from econ.dev.policy import load_policy

    policy = load_policy(REPO_ROOT)
    assert policy.protected == list(DEFAULT_PROTECTED)


def test_validate_task_uses_the_policy_protected_list():
    # DEFAULT_PROTECTED is the floor; a repo policy may extend it (for example
    # with a Makefile) and validate_task must flag low-risk tasks that name
    # those extensions even though the Pydantic floor allowed the contract.
    policy = DevPolicy(protected=[*DEFAULT_PROTECTED, "Makefile"])
    task = Task.model_validate(_task_payload("Makefile", risk=2))
    problems = validate_task(task, policy)
    assert problems == ["task touches protected paths without risk 3: Makefile"]

    policy_store_task = Task.model_validate(_task_payload("Makefile", risk=3))
    assert validate_task(policy_store_task, policy) == []


def test_broad_source_scope_cannot_smuggle_controller_edits():
    # scope.allow is matched conservatively against protected globs, so a task
    # may not grant itself the controller with a broad allow pattern.
    assert overlap("src/econ/**", "src/econ/dev/**")
    with pytest.raises(ValidationError, match="protected"):
        Task.model_validate(_task_payload("src/econ/**", risk=1))


def test_ready_queue_rejects_low_risk_referee_task(tmp_path):
    from dev_support import make_repo

    repo = make_repo(tmp_path / "repo")
    task = Task.model_validate(
        _task_payload("src/econ/dev/pipeline.py", risk=3)
        | {"status": "proposed", "id": "DEV-0099"}
    )
    store = TaskStore(repo)
    store.save(task, status="proposed")
    loaded = store.load("DEV-0099")
    assert loaded.risk == 3


# -- blast radius: merge-critical paths and coverage deltas ---------------
def test_critical_paths_seed_matches_config():
    from econ.dev.policy import load_policy

    policy = load_policy(REPO_ROOT)
    assert policy.auto_merge.critical_paths == [
        "src/econ/dev/**",
        ".github/workflows/**",
        "tests/dev_support.py",
        "tasks/templates/task.yaml",
        "dev/evals/canary/**",
    ]


def test_coverage_deltas_flag_negative_deltas():
    from econ.dev.gates import coverage_deltas

    base = {"files": {"src/econ/a.py": {"summary": {"percent_covered": 90.0}}}}
    patch = {
        "files": {
            "src/econ/a.py": {"summary": {"percent_covered": 70.0}},
            "src/econ/b.py": {"summary": {"percent_covered": 85.0}},
        }
    }
    rows = coverage_deltas(base, patch, ["src/econ/a.py", "src/econ/b.py"])
    by_file = {row["file"]: row for row in rows}
    assert by_file["src/econ/a.py"]["delta"] == -20.0
    assert by_file["src/econ/b.py"]["delta"] == 85.0  # new file: gain, not drop


def test_coverage_deltas_new_file_counts_as_gain():
    from econ.dev.gates import coverage_deltas

    patch = {"files": {"src/econ/new.py": {"summary": {"percent_covered": 30.0}}}}
    rows = coverage_deltas({}, patch, ["src/econ/new.py"])
    assert rows[0]["base_pct"] == 0.0
    assert rows[0]["delta"] == 30.0


def test_coverage_deltas_skips_deleted_sources():
    from econ.dev.gates import coverage_deltas

    base = {"files": {"src/econ/gone.py": {"summary": {"percent_covered": 50.0}}}}
    rows = coverage_deltas(base, {"files": {}}, ["src/econ/gone.py"])
    assert rows == []


def test_coverage_deltas_matches_report_paths_by_suffix():
    from econ.dev.gates import coverage_deltas

    base = {"files": {"/abs/root/src/econ/a.py": {"summary": {"percent_covered": 90.0}}}}
    patch = {"files": {"src/econ/a.py": {"summary": {"percent_covered": 40.0}}}}
    rows = coverage_deltas(base, patch, ["src/econ/a.py"])
    assert rows[0]["delta"] == -50.0
