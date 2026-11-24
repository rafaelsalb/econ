from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from econ.dev.artifacts import extract_json
from econ.dev.models import Task
from econ.dev.paths import overlap, scope_violations
from econ.dev.tasks import TaskStore

from dev_support import add_task, demo_task, make_repo


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
