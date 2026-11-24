from __future__ import annotations

from econ.dev.locks import PauseSwitch
from econ.dev.scheduler import DevScheduler

from dev_support import add_task, default_policy, demo_task, make_repo


def _task(repo, task_id, stem):
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
    add_task(
        repo,
        demo_task(
            task_id=task_id,
            files=files,
            acceptance=[f"python -m pytest tests/test_{stem}.py -q"],
            allow=[item["path"] for item in files],
        ),
    )


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
