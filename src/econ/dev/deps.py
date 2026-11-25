from __future__ import annotations

from .models import Task

# A dependency is satisfied only when the predecessor has actually merged. A
# shadow run, an escalation, or a failure does not satisfy it: those states mean
# the successor's base does not contain the work it depends on.
SATISFIED_STATUS = "done"


def index(tasks: list[Task]) -> dict[str, Task]:
    return {task.id: task for task in tasks}


def blocking_reason(task: Task, tasks: dict[str, Task]) -> str | None:
    """Return why ``task`` cannot run yet, or None when it is eligible.

    The message is deliberately stable and short because it is surfaced in
    ``econ dev status`` and ``runs/dev/daemon.json``.
    """
    for dep_id in task.depends_on:
        dep = tasks.get(dep_id)
        if dep is None:
            return f"dependency {dep_id} is missing"
        if dep.status != SATISFIED_STATUS:
            return f"dependency {dep_id} is {dep.status}"
    return None


def blocked_tasks(tasks: list[Task]) -> list[dict]:
    """Describe every ready task whose dependencies are not satisfied."""
    tasks_by_id = index(tasks)
    rows: list[dict] = []
    for task in tasks:
        if task.status != "ready":
            continue
        reason = blocking_reason(task, tasks_by_id)
        if reason is not None:
            rows.append(
                {
                    "task_id": task.id,
                    "depends_on": list(task.depends_on),
                    "reason": reason,
                }
            )
    return rows


def missing_dependency_problems(tasks: list[Task]) -> list[str]:
    """Dependencies that name no task in the store.

    Promotion and direct runs treat these as errors. ``econ dev validate``
    reports them as warnings because a worktree sees an older committed task
    snapshot when status moves are still uncommitted runtime state.
    """
    tasks_by_id = index(tasks)
    problems: list[str] = []
    for task in tasks:
        for dep_id in task.depends_on:
            if dep_id not in tasks_by_id:
                problems.append(f"{task.id}: dependency {dep_id} does not exist")
    return problems


def _canonical_cycle(cycle: list[str]) -> tuple[str, ...]:
    """Rotate a cycle so equivalent traversals produce the same tuple."""
    body = cycle[:-1]
    if not body:
        return tuple(cycle)
    start = min(range(len(body)), key=lambda i: body[i])
    return tuple(body[start:] + body[:start])


def cycle_problems(tasks: list[Task]) -> list[str]:
    """Find dependency cycles across every status, not just ready tasks."""
    tasks_by_id = index(tasks)
    graph = {
        task.id: [dep for dep in task.depends_on if dep in tasks_by_id]
        for task in tasks
    }
    state = {task_id: 0 for task_id in graph}  # 0 white, 1 gray, 2 black
    stack: list[str] = []
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for dep in graph[node]:
            if state[dep] == 1:
                start = stack.index(dep)
                cycles.add(_canonical_cycle(stack[start:] + [dep]))
            elif state[dep] == 0:
                visit(dep)
        stack.pop()
        state[node] = 2

    for node in graph:
        if state[node] == 0:
            visit(node)

    return [
        f"{' -> '.join([*cycle, cycle[0]])} (dependency cycle)"
        for cycle in sorted(cycles)
    ]


def graph_problems(tasks: list[Task]) -> list[str]:
    """Problems that make a promoted dependency graph unsatisfiable."""
    return missing_dependency_problems(tasks) + cycle_problems(tasks)


def pending_dependency_problems(task: Task, tasks: list[Task]) -> list[str]:
    """Dependencies that exist but have not merged yet.

    These are warnings, not errors: a human may stage a whole DAG in ready/ and
    let the scheduler hold the dependents until their predecessors finish.
    """
    tasks_by_id = index(tasks)
    problems: list[str] = []
    for dep_id in task.depends_on:
        dep = tasks_by_id.get(dep_id)
        if dep is not None and dep.status != SATISFIED_STATUS:
            problems.append(
                f"{task.id}: dependency {dep_id} is {dep.status}, not done; "
                "the scheduler will hold this task"
            )
    return problems
