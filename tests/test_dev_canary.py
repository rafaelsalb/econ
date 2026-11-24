from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from econ.dev.canary import (
    load_canaries,
    promote_canary,
    proposed_dir,
    validate_canaries,
)
from econ.dev.models import Source, Task

from dev_support import add_task, demo_task, make_repo, run_task


def _proposed(repo: Path) -> list[Path]:
    return sorted(proposed_dir(repo).glob("*.yaml"))


def test_budget_exhausted_task_generates_a_proposed_canary(tmp_path):
    repo = make_repo(tmp_path / "repo")
    add_task(repo, demo_task(risk=2, fail_first_rounds=99))
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "escalated"
    files = _proposed(repo)
    assert len(files) == 1
    canary = Task.model_validate(yaml.safe_load(files[0].read_text()))
    assert canary.id == "CANARY-001"
    assert canary.source.kind == "canary"
    assert canary.goal == "Add the demo feature and prove it with a test."
    assert canary.acceptance == ["python -m pytest tests/test_feature.py -q"]
    assert canary.demo is not None
    assert canary.notes.startswith("Auto-generated from DEV-0001")
    assert "escalated" in canary.notes
    assert outcome.decision.get("canary_proposed")


def test_clean_run_generates_no_canary(tmp_path):
    repo = make_repo(tmp_path / "repo")
    add_task(repo, demo_task())
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "done"
    assert _proposed(repo) == []
    assert "canary_proposed" not in outcome.decision


def test_human_gate_escalation_generates_no_canary(tmp_path):
    repo = make_repo(tmp_path / "repo")
    add_task(repo, demo_task(verifier="fail"))
    outcome = run_task(repo, "DEV-0001")
    assert outcome.status == "escalated"
    # Policy escalations inside the round budget (a verifier rejecting the
    # patch on round 1) are the system working, not a regression to record.
    assert _proposed(repo) == []


def test_proposed_canary_stays_out_of_the_suite_until_promoted(tmp_path):
    repo = make_repo(tmp_path / "repo")
    add_task(repo, demo_task(risk=2, fail_first_rounds=99))
    run_task(repo, "DEV-0001")
    assert [task.id for task in load_canaries(repo)] == []
    canary, path = promote_canary(repo, "CANARY-001")
    assert canary.id == "CANARY-001"
    assert path == repo / "dev" / "evals" / "canary" / "CANARY-001.yaml"
    assert path.exists()
    assert _proposed(repo) == []
    assert [task.id for task in load_canaries(repo)] == ["CANARY-001"]
    assert validate_canaries(repo) == []


def test_promote_refuses_a_canary_without_a_demo_fixture(tmp_path):
    repo = make_repo(tmp_path / "repo")
    payload = demo_task().model_dump(mode="json", exclude_none=True)
    payload.update({"id": "CANARY-009", "source": {"kind": "canary"}})
    payload["demo"] = None
    proposed_dir(repo).mkdir(parents=True, exist_ok=True)
    (proposed_dir(repo) / "CANARY-009.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False)
    )
    with pytest.raises(ValueError, match="demo"):
        promote_canary(repo, "CANARY-009")


def test_promote_refuses_an_unknown_canary(tmp_path):
    repo = make_repo(tmp_path / "repo")
    with pytest.raises(ValueError, match="no proposed canary"):
        promote_canary(repo, "CANARY-404")


def test_generated_ids_do_not_collide_with_the_suite(tmp_path):
    repo = make_repo(tmp_path / "repo")
    suite = demo_task().model_copy(update={"id": "CANARY-001"})
    suite = suite.model_copy(update={"source": Source(kind="canary")})
    target = repo / "dev" / "evals" / "canary" / "CANARY-001.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(suite.model_dump(mode="json", exclude_none=True), sort_keys=False)
    )
    add_task(repo, demo_task(risk=2, fail_first_rounds=99))
    run_task(repo, "DEV-0001")
    files = _proposed(repo)
    assert files[0].stem == "CANARY-002"
