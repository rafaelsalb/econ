from __future__ import annotations

from econ.dev.deps import (
    blocked_tasks,
    blocking_reason,
    cycle_problems,
    graph_problems,
    missing_dependency_problems,
    pending_dependency_problems,
)
from econ.dev.models import Task

from dev_support import demo_task


def _task(task_id: str, depends_on=(), *, status: str = "ready") -> Task:
    return demo_task(task_id=task_id).model_copy(
        update={"depends_on": list(depends_on), "status": status}
    )


def test_blocking_reason_requires_done():
    predecessor = _task("DEV-0001", status="ready")
    dependent = _task("DEV-0002", ["DEV-0001"])
    tasks = {predecessor.id: predecessor, dependent.id: dependent}

    assert (
        blocking_reason(dependent, tasks)
        == "dependency DEV-0001 is ready"
    )
    assert blocking_reason(_task("DEV-0003"), tasks) is None

    predecessor = predecessor.model_copy(update={"status": "done"})
    tasks[predecessor.id] = predecessor
    assert blocking_reason(dependent, tasks) is None


def test_shadow_escalated_and_failed_do_not_satisfy():
    dependent = _task("DEV-0002", ["DEV-0001"])
    for status in ("shadow", "escalated", "failed", "active", "proposed"):
        predecessor = _task("DEV-0001", status=status)
        tasks = {predecessor.id: predecessor, dependent.id: dependent}
        assert blocking_reason(dependent, tasks) == f"dependency DEV-0001 is {status}"


def test_missing_dependency_is_reported():
    dependent = _task("DEV-0002", ["DEV-9999"])
    tasks = {dependent.id: dependent}
    assert (
        blocking_reason(dependent, tasks)
        == "dependency DEV-9999 is missing"
    )
    assert missing_dependency_problems([dependent]) == [
        "DEV-0002: dependency DEV-9999 does not exist"
    ]
    assert pending_dependency_problems(dependent, [dependent]) == []


def test_blocked_tasks_only_lists_ready_tasks():
    predecessor = _task("DEV-0001", status="ready")
    ready = _task("DEV-0002", ["DEV-0001"])
    proposed = _task("DEV-0003", ["DEV-0001"], status="proposed")
    rows = blocked_tasks([predecessor, ready, proposed])
    assert rows == [
        {
            "task_id": "DEV-0002",
            "depends_on": ["DEV-0001"],
            "reason": "dependency DEV-0001 is ready",
        }
    ]


def test_cycle_problems_are_canonical_and_transitive():
    a = _task("DEV-0001", ["DEV-0002"])
    b = _task("DEV-0002", ["DEV-0003"])
    c = _task("DEV-0003", ["DEV-0001"])
    problems = cycle_problems([a, b, c])
    assert len(problems) == 1
    assert "dependency cycle" in problems[0]
    # The rotation is normalized so every traversal reports the same cycle.
    assert problems[0].startswith("DEV-0001 -> DEV-0002 -> DEV-0003 -> DEV-0001")

    assert cycle_problems([a.model_copy(update={"depends_on": []}), b, c]) == []
    assert graph_problems([_task("DEV-0004", ["DEV-9999"])]) == [
        "DEV-0004: dependency DEV-9999 does not exist"
    ]


def test_pending_dependency_warns_but_does_not_block_promotion_shape():
    predecessor = _task("DEV-0001", status="proposed")
    dependent = _task("DEV-0002", ["DEV-0001"], status="proposed")
    assert pending_dependency_problems(dependent, [predecessor, dependent]) == [
        "DEV-0002: dependency DEV-0001 is proposed, not done; "
        "the scheduler will hold this task"
    ]
