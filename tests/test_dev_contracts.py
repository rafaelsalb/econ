from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from econ.dev.artifacts import extract_json
from econ.dev.models import Task
from econ.dev.paths import overlap, scope_violations
from econ.dev.tasks import TaskStore

from dev_support import add_task, default_policy, demo_task, make_repo


def test_task_rejects_shell_metacharacters():
    with pytest.raises(ValidationError):
        Task.model_validate(
            {
                "id": "DEV-0001",
                "title": "unsafe",
                "status": "ready",
                "risk": 1,
                "created": "2026-11-24",
                "goal": "unsafe task",
                "acceptance": ["pytest -q; rm -rf /"],
                "scope": {"allow": ["tests/**"]},
            }
        )

    with pytest.raises(ValidationError):
        Task.model_validate(
            {
                "id": "DEV-0001",
                "title": "unsafe",
                "status": "ready",
                "risk": 1,
                "created": "2026-11-24",
                "goal": "unsafe task",
                "acceptance": ["pytest -q | tee out"],
                "scope": {"allow": ["tests/**"]},
            }
        )


def test_task_rejects_protected_scope_at_low_risk():
    with pytest.raises(ValidationError):
        Task.model_validate(
            {
                "id": "DEV-0001",
                "title": "science",
                "status": "ready",
                "risk": 1,
                "created": "2026-11-24",
                "goal": "touch a spec",
                "acceptance": ["python -m pytest -q"],
                "scope": {"allow": ["specs/new_keynesian.yaml"]},
            }
        )


def test_risk_three_may_name_protected_paths():
    task = Task.model_validate(
        {
            "id": "DEV-0001",
            "title": "science",
            "status": "proposed",
            "risk": 3,
            "created": "2026-11-24",
            "goal": "protocol change",
            "acceptance": ["python -m pytest -q"],
            "scope": {"allow": ["specs/new_keynesian.yaml"]},
        }
    )
    assert task.risk == 3


def test_task_store_moves_between_status_dirs(tmp_path):
    repo = make_repo(tmp_path / "repo")
    store = TaskStore(repo)
    task = demo_task()
    add_task(repo, task)
    assert (repo / "tasks" / "ready" / "DEV-0001.yaml").exists()
    store.move(task, "active")
    assert not (repo / "tasks" / "ready" / "DEV-0001.yaml").exists()
    assert (repo / "tasks" / "active" / "DEV-0001.yaml").exists()
    loaded = store.load("DEV-0001")
    assert loaded.status == "active"


def test_scope_and_overlap_helpers():
    assert scope_violations(["src/a.py"], ["src/**"], []) == []
    assert scope_violations(["specs/x"], ["src/**"], []) == [
        "path outside scope.allow: specs/x"
    ]
    assert scope_violations(["src/a.py"], ["src/**"], ["src/a.py"])
    assert overlap("src/**", "src/econ/x.py")
    assert not overlap("src/**", "tests/x.py")
    assert overlap("src/econ/**", "src/**")


def test_extract_json_prefers_outer_object():
    text = 'prefix {"role": "verifier", "verdict": "pass", "checks": [{"command": "x", "exit_code": 0}]} suffix'
    payload = extract_json(text)
    assert payload is not None
    assert payload["role"] == "verifier"
    assert payload["verdict"] == "pass"
    assert json.dumps(payload).startswith('{"role"')


def test_promote_moves_proposed_contract_to_ready(tmp_path):
    from econ.dev.tasks import promote_task

    repo = make_repo(tmp_path / "repo")
    task = demo_task().model_copy(update={"status": "proposed"})
    add_task(repo, task)
    promoted, path = promote_task(TaskStore(repo), "DEV-0001", default_policy())
    assert promoted.status == "ready"
    assert path == repo / "tasks" / "ready" / "DEV-0001.yaml"
    assert path.exists()
    assert not (repo / "tasks" / "proposed" / "DEV-0001.yaml").exists()
    again, same = promote_task(TaskStore(repo), "DEV-0001", default_policy())
    assert again.status == "ready"
    assert same == path


def test_promote_refuses_non_proposed_task(tmp_path):
    from econ.dev.tasks import promote_task

    repo = make_repo(tmp_path / "repo")
    add_task(repo, demo_task())  # already ready
    # Ready is idempotent; a completed task is not promotable.
    task = demo_task().model_copy(update={"status": "done"})
    TaskStore(repo).save(task, status="done")
    with pytest.raises(ValueError):
        promote_task(TaskStore(repo), "DEV-0001", default_policy())


def test_task_rejects_self_duplicate_and_malformed_dependencies():
    payload = demo_task("DEV-0001").model_dump(mode="json")
    for depends_on, message in (
        (["DEV-0001"], "cannot depend on itself"),
        (["DEV-0002", "DEV-0002"], "duplicate dependency"),
        (["not-a-task"], "dependency id is invalid"),
    ):
        with pytest.raises(ValidationError, match=message):
            Task.model_validate({**payload, "depends_on": depends_on})


def test_promote_rejects_missing_dependency(tmp_path):
    from econ.dev.tasks import promote_task

    repo = make_repo(tmp_path / "repo")
    task = demo_task("DEV-0001").model_copy(
        update={"status": "proposed", "depends_on": ["DEV-9999"]}
    )
    add_task(repo, task)
    with pytest.raises(ValueError, match="does not exist"):
        promote_task(TaskStore(repo), "DEV-0001", default_policy())
    assert (repo / "tasks" / "proposed" / "DEV-0001.yaml").exists()


def test_promote_rejects_dependency_cycle(tmp_path):
    from econ.dev.tasks import promote_task

    repo = make_repo(tmp_path / "repo")
    first = demo_task("DEV-0001").model_copy(
        update={"status": "proposed", "depends_on": ["DEV-0002"]}
    )
    second = demo_task("DEV-0002").model_copy(
        update={"status": "proposed", "depends_on": ["DEV-0001"]}
    )
    add_task(repo, first)
    add_task(repo, second)
    with pytest.raises(ValueError, match="dependency cycle"):
        promote_task(TaskStore(repo), "DEV-0001", default_policy())
    assert (repo / "tasks" / "proposed" / "DEV-0001.yaml").exists()


def test_promote_allows_staged_dependent(tmp_path):
    from econ.dev.tasks import promote_task

    repo = make_repo(tmp_path / "repo")
    predecessor = demo_task("DEV-0001").model_copy(update={"status": "ready"})
    dependent = demo_task("DEV-0002").model_copy(
        update={"status": "proposed", "depends_on": ["DEV-0001"]}
    )
    add_task(repo, predecessor)
    add_task(repo, dependent)

    promoted, path = promote_task(TaskStore(repo), "DEV-0002", default_policy())
    assert promoted.status == "ready"
    assert promoted.depends_on == ["DEV-0001"]
    assert path.exists()


def test_validate_all_reports_cycles_and_warns_on_missing(tmp_path):
    repo = make_repo(tmp_path / "repo")
    first = demo_task("DEV-0001").model_copy(
        update={"status": "proposed", "depends_on": ["DEV-0002"]}
    )
    second = demo_task("DEV-0002").model_copy(
        update={"status": "proposed", "depends_on": ["DEV-0001"]}
    )
    add_task(repo, first)
    add_task(repo, second)

    store = TaskStore(repo)
    problems = store.validate_all(default_policy())
    assert any("dependency cycle" in problem for problem in problems)

    missing = demo_task("DEV-0003").model_copy(
        update={"status": "proposed", "depends_on": ["DEV-9999"]}
    )
    add_task(repo, missing)
    assert store.dependency_warnings() == [
        "DEV-0003: dependency DEV-9999 does not exist"
    ]
    # Missing ids are warnings, not gate failures: a worktree may hold an
    # older committed snapshot of the task store.
    assert not any("DEV-9999" in problem for problem in store.validate_all(default_policy()))


def test_new_task_payload_carries_dependencies():
    from econ.dev.tasks import new_task_payload

    payload = new_task_payload(
        task_id="DEV-0001",
        title="dependent",
        goal="wait for the predecessor",
        acceptance=["python -m pytest -q"],
        allow=["src/econ/example.py"],
        depends_on=["DEV-0000"],
    )
    assert payload["depends_on"] == ["DEV-0000"]

