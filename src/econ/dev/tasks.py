from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

import yaml

from .models import STATUS_DIRS, Task, TaskValidationError, validate_task
from .policy import DevPolicy

TASK_DIRS = (
    "proposed",
    "ready",
    "active",
    "done",
    "escalated",
    "failed",
)


class TaskStore:
    def __init__(self, root: Path):
        self.root = root
        self.base = root / "tasks"

    def ensure(self) -> None:
        for name in TASK_DIRS:
            (self.base / name).mkdir(parents=True, exist_ok=True)

    def dir_for(self, status: str) -> Path:
        return self.base / STATUS_DIRS[status]

    def paths(self) -> list[Path]:
        self.ensure()
        return sorted(
            p
            for p in self.base.rglob("*.yaml")
            if p.name not in {"_template.yaml"} and "templates" not in p.parts
        )

    def load_path(self, path: Path) -> Task:
        raw = yaml.safe_load(path.read_text())
        if not isinstance(raw, dict):
            raise ValueError(f"task is not a mapping: {path}")
        task = Task.model_validate(raw)
        if path.parent.name in TASK_DIRS and path.parent.name != STATUS_DIRS[task.status]:
            raise ValueError(
                f"{path}: status {task.status!r} belongs in "
                f"tasks/{STATUS_DIRS[task.status]}/, not tasks/{path.parent.name}/"
            )
        return task

    def load(self, task_id: str) -> Task:
        matches = [p for p in self.paths() if p.stem == task_id]
        if not matches:
            raise FileNotFoundError(f"task not found: {task_id}")
        if len(matches) > 1:
            raise ValueError(f"task id is duplicated: {task_id}")
        return self.load_path(matches[0])

    def path_for(self, task: Task) -> Path:
        return self.dir_for(task.status) / f"{task.id}.yaml"

    def save(self, task: Task, *, status: str | None = None) -> Path:
        self.ensure()
        if status is not None:
            task = task.model_copy(update={"status": status})
        target = self.path_for(task)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = task.model_dump(mode="json", exclude_none=True)
        target.write_text(yaml.safe_dump(payload, sort_keys=False))
        # A task id must exist in exactly one status directory. Remove any old
        # copy, including one left behind by an earlier status transition.
        for stale in self.base.glob(f"*/{task.id}.yaml"):
            if stale.resolve() != target.resolve():
                stale.unlink()
        return target

    def move(self, task: Task, status: str) -> Path:
        return self.save(task, status=status)

    def create(self, payload: dict) -> Task:
        task = Task.model_validate(payload)
        self.save(task)
        return task

    def next_id(self, prefix: str = "DEV") -> str:
        nums = []
        for path in self.paths():
            stem = path.stem
            if stem.startswith(prefix + "-"):
                try:
                    nums.append(int(stem.rsplit("-", 1)[1]))
                except ValueError:
                    pass
        return f"{prefix}-{max(nums, default=0) + 1:04d}"

    def ready(self) -> list[Task]:
        return [self.load_path(p) for p in sorted((self.base / "ready").glob("*.yaml"))]

    def all(self) -> list[Task]:
        return [self.load_path(p) for p in self.paths()]

    def validate_all(self, policy: DevPolicy | None = None) -> list[str]:
        problems: list[str] = []
        seen: dict[str, Path] = {}
        for path in self.paths():
            try:
                task = self.load_path(path)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{path}: {exc}")
                continue
            if task.id in seen:
                problems.append(f"duplicate task id {task.id}: {seen[task.id]} and {path}")
            seen[task.id] = path
            for problem in validate_task(task, policy):
                problems.append(f"{task.id}: {problem}")
        return problems

    def freeze(self, task: Task, run_dir: Path) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = task.model_dump(mode="json", exclude_none=True)
        target = run_dir / "task.yaml"
        target.write_text(yaml.safe_dump(payload, sort_keys=False))
        (run_dir / "task.sha256").write_text(task.sha256() + "\n")
        return target

    def source_task(self, kind: str, number: int) -> Task | None:
        for task in self.all():
            if task.source.kind == kind and task.source.number == number:
                return task
        return None

    def archive(self, task: Task) -> Path:
        return self.save(task)


def new_task_payload(
    *,
    task_id: str,
    title: str,
    goal: str,
    acceptance: list[str],
    allow: list[str],
    risk: int = 1,
    deny: list[str] | None = None,
    priority: int = 50,
    source: dict | None = None,
    demo: dict | None = None,
    notes: str = "",
    status: str = "proposed",
) -> dict:
    payload = {
        "id": task_id,
        "title": title,
        "status": status,
        "risk": risk,
        "priority": priority,
        "created": date.today().isoformat(),
        "goal": goal,
        "acceptance": acceptance,
        "scope": {"allow": allow, "deny": deny or []},
        "source": source or {"kind": "local"},
        "notes": notes,
    }
    if demo:
        payload["demo"] = demo
    return payload


def import_task_file(source: Path, store: TaskStore, *, status: str = "proposed") -> Task:
    raw = yaml.safe_load(source.read_text())
    task = Task.model_validate(raw)
    return store.save(task, status=status)


def copy_task_template(root: Path, task_id: str) -> Path:
    template = root / "tasks" / "templates" / "task.yaml"
    target = root / "tasks" / "proposed" / f"{task_id}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template, target)
    return target


def task_index(tasks: list[Task]) -> dict:
    return {
        "count": len(tasks),
        "by_status": {
            status: sum(1 for task in tasks if task.status == status)
            for status in sorted({task.status for task in tasks})
        },
        "ready": [task.id for task in tasks if task.status == "ready"],
        "active": [task.id for task in tasks if task.status == "active"],
    }


def validate_task_file(path: Path, policy: DevPolicy | None = None) -> list[str]:
    try:
        task = Task.model_validate(yaml.safe_load(path.read_text()))
    except Exception as exc:  # noqa: BLE001
        return [f"{path}: {exc}"]
    problems = validate_task(task, policy)
    if problems:
        raise TaskValidationError(problems)
    return []


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def task_json(task: Task) -> str:
    return json.dumps(task.canonical(), indent=2)
