from __future__ import annotations

from econ.dev.locks import PauseSwitch
from econ.dev.scheduler import DevScheduler
from econ.dev.tasks import TaskStore

from dev_support import add_task, default_policy, demo_task, make_repo


def _task(repo, task_id, stem, *, depends_on=None, status="ready"):
    files = [
        {
            "path": f"src/econ/{stem}.py",
            "content": f"def {stem}() -> str:\n    return '{stem}'\n",
        },
        {
            "path": f"tests/test_{stem}.py",
            "content": f"from econ.{stem} import {stem}\n\n\ndef test_{stem}():\n    assert {stem}() == '{stem}'\n",
        },
    ]
    task = demo_task(
        task_id=task_id,
        files=files,
        acceptance=[f"python -m pytest tests/test_{stem}.py -q"],
        allow=[item["path"] for item in files],
    ).model_copy(update={"depends_on": list(depends_on or []), "status": status})
    add_task(repo, task)


def test_select_respects_conflicts_and_budget(tmp_path):
    repo = make_repo(tmp_path / "repo")
    _task(repo, "DEV-0001", "alpha")
    _task(repo, "DEV-0002", "beta")
    scheduler = DevScheduler(repo, default_policy(), runner_kind="fake")
    selected = scheduler.select(limit=2)
    assert {task.id for task in selected} == {"DEV-0001", "DEV-0002"}

    zero = DevScheduler(repo, default_policy(), runner_kind="fake", daily_usd=0.0)
    assert zero.select(limit=2) == []


def test_scheduler_merge_two_tasks_in_parallel(tmp_path):
    repo = make_repo(tmp_path / "repo")
    _task(repo, "DEV-0001", "alpha")
    _task(repo, "DEV-0002", "beta")
    scheduler = DevScheduler(
        repo, default_policy(), runner_kind="fake", max_parallel=2
    )
    outcomes = scheduler.run_once(max_tasks=2)
    assert {outcome.task_id for outcome in outcomes} == {"DEV-0001", "DEV-0002"}
    assert all(outcome.status == "done" for outcome in outcomes), [
        outcome.decision for outcome in outcomes
    ]
    assert (repo / "src" / "econ" / "alpha.py").exists()
    assert (repo / "src" / "econ" / "beta.py").exists()


def test_scheduler_holds_dependent_until_done(tmp_path):
    repo = make_repo(tmp_path / "repo")
    _task(repo, "DEV-0001", "alpha")
    _task(repo, "DEV-0002", "beta", depends_on=["DEV-0001"])
    scheduler = DevScheduler(repo, default_policy(), runner_kind="fake")

    assert [task.id for task in scheduler.select(limit=2)] == ["DEV-0001"]
    expected = [
        {
            "task_id": "DEV-0002",
            "depends_on": ["DEV-0001"],
            "reason": "dependency DEV-0001 is ready",
        }
    ]
    assert scheduler.blocked() == expected
    assert scheduler.status()["blocked"] == expected

    store = TaskStore(repo)
    store.save(store.load("DEV-0001"), status="done")
    assert [task.id for task in scheduler.select(limit=2)] == ["DEV-0002"]
    assert scheduler.blocked() == []


def test_parallel_tick_runs_only_the_predecessor(tmp_path):
    repo = make_repo(tmp_path / "repo")
    _task(repo, "DEV-0001", "alpha")
    _task(repo, "DEV-0002", "beta", depends_on=["DEV-0001"])
    scheduler = DevScheduler(
        repo, default_policy(), runner_kind="fake", max_parallel=2
    )

    first = scheduler.run_once(max_tasks=2)
    assert [outcome.task_id for outcome in first] == ["DEV-0001"]
    assert all(outcome.status == "done" for outcome in first)
    assert TaskStore(repo).load("DEV-0002").status == "ready"
    assert not (repo / "src" / "econ" / "beta.py").exists()

    second = scheduler.run_once(max_tasks=2)
    assert [outcome.task_id for outcome in second] == ["DEV-0002"]
    assert second[0].status == "done"
    assert (repo / "src" / "econ" / "beta.py").exists()


def test_escalated_dependency_keeps_dependent_blocked(tmp_path):
    repo = make_repo(tmp_path / "repo")
    _task(repo, "DEV-0001", "alpha")
    _task(repo, "DEV-0002", "beta", depends_on=["DEV-0001"])
    store = TaskStore(repo)
    store.save(store.load("DEV-0001"), status="escalated")

    scheduler = DevScheduler(repo, default_policy(), runner_kind="fake")
    assert scheduler.select(limit=2) == []
    assert scheduler.blocked() == [
        {
            "task_id": "DEV-0002",
            "depends_on": ["DEV-0001"],
            "reason": "dependency DEV-0001 is escalated",
        }
    ]
    assert TaskStore(repo).load("DEV-0002").status == "ready"



def test_scheduler_pause_switch(tmp_path):
    repo = make_repo(tmp_path / "repo")
    _task(repo, "DEV-0001", "alpha")
    PauseSwitch(repo).pause("maintenance")
    scheduler = DevScheduler(repo, default_policy(), runner_kind="fake")
    assert scheduler.run_once() == []
    assert scheduler.status()["paused"] is True
    PauseSwitch(repo).resume()
    assert scheduler.status()["paused"] is False


def test_scheduler_lock_blocks_second_worker(tmp_path):
    repo = make_repo(tmp_path / "repo")
    _task(repo, "DEV-0001", "alpha")
    scheduler = DevScheduler(repo, default_policy(), runner_kind="fake")
    lock = scheduler.lock
    lock.path.parent.mkdir(parents=True, exist_ok=True)
    lock.path.write_text('{"pid": %d, "ts": 9999999999}' % __import__("os").getpid())
    try:
        assert scheduler.run_once() == []
        status = scheduler.status()
        assert status["lock"]["held"] is True
        assert status["lock"]["alive"] is True
    finally:
        lock.path.unlink()
