from __future__ import annotations

import json
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .artifacts import write_json
from .models import Task, validate_task
from .policy import DevPolicy
from .tasks import TaskStore

_FENCE = re.compile(r"```ya?ml\s*(.*?)```", re.DOTALL)


class GitHubSyncError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, repo: Path, executable: str = "gh"):
        self.repo = repo
        self.executable = executable

    def _run(self, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            [self.executable, *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=False,
        )
        if check and proc.returncode != 0:
            raise GitHubSyncError(
                f"gh {' '.join(args)} failed ({proc.returncode}): "
                f"{(proc.stderr or proc.stdout).strip()[:1000]}"
            )
        return proc

    def list_ready(self, label: str) -> list[dict]:
        proc = self._run(
            [
                "issue",
                "list",
                "--state",
                "open",
                "--label",
                label,
                "--limit",
                "100",
                "--json",
                "number,title,body,labels,author,url",
            ]
        )
        text = proc.stdout.strip()
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end == -1:
            raise GitHubSyncError("gh returned no JSON issue list")
        return json.loads(text[start : end + 1])

    def comment(self, number: int, body: str) -> None:
        self._run(["issue", "comment", str(number), "--body", body], check=False)

    def close(self, number: int) -> None:
        self._run(
            ["issue", "close", str(number), "--reason", "completed"], check=False
        )


def _labels(issue: dict) -> list[str]:
    out = []
    for label in issue.get("labels") or []:
        if isinstance(label, dict):
            out.append(str(label.get("name", "")))
        else:
            out.append(str(label))
    return [label for label in out if label]


def _risk_from_labels(labels: list[str]) -> int:
    for label in labels:
        match = re.match(r"risk[:/-]?([0-3])", label)
        if match:
            return int(match.group(1))
    return 2


def task_from_issue(
    issue: dict, policy: DevPolicy, *, number_fallback: str = "DEV"
) -> Task:
    body = issue.get("body") or ""
    blocks = [block.strip() for block in _FENCE.findall(body)]
    blocks.append(body.strip())
    payload: dict[str, Any] | None = None
    for block in blocks:
        try:
            candidate = yaml.safe_load(block)
        except yaml.YAMLError:
            continue
        if isinstance(candidate, dict) and "goal" in candidate:
            payload = candidate
            break
    if payload is None:
        raise GitHubSyncError("issue body has no YAML task contract")
    number = int(issue.get("number") or 0)
    labels = _labels(issue)
    author = (issue.get("author") or {}).get("login")
    payload.setdefault("id", f"{number_fallback}-{number:04d}")
    payload.setdefault("title", issue.get("title") or f"Issue {number}")
    payload.setdefault("status", "proposed")
    payload.setdefault("risk", _risk_from_labels(labels))
    payload.setdefault("created", date.today().isoformat())
    payload["source"] = {
        "kind": "github",
        "number": number,
        "url": issue.get("url"),
        "author": author,
    }
    return Task.model_validate(payload)


def sync_pull(
    repo: Path,
    policy: DevPolicy,
    store: TaskStore,
    *,
    client: GitHubClient | None = None,
    label: str | None = None,
    promote: bool | None = None,
) -> dict:
    store.ensure()
    client = client or GitHubClient(repo)
    label = label or policy.github.label
    promote = policy.github.auto_promote if promote is None else promote
    imported, skipped, promoted = [], [], []
    for issue in client.list_ready(label):
        number = int(issue.get("number") or 0)
        existing = store.source_task("github", number)
        if existing is not None:
            skipped.append({"number": number, "reason": "already imported", "task": existing.id})
            continue
        try:
            task = task_from_issue(issue, policy)
            problems = validate_task(task, policy)
            if problems:
                raise GitHubSyncError("; ".join(problems))
            try:
                existing_local = store.load(task.id)
            except FileNotFoundError:
                existing_local = None
            if existing_local is not None:
                raise GitHubSyncError(
                    f"task id {task.id} already exists from {existing_local.source.kind}"
                )
        except Exception as exc:  # noqa: BLE001
            skipped.append({"number": number, "reason": str(exc)})
            continue
        trusted = (issue.get("author") or {}).get("login") in set(
            policy.github.trusted_authors
        )
        status = "ready" if promote and trusted else "proposed"
        store.save(task, status=status)
        imported.append(task.id)
        if status == "ready":
            promoted.append(task.id)
    return {"imported": imported, "promoted": promoted, "skipped": skipped}


def _status_marker(task: Task) -> str:
    return f"<!-- econ-dev:{task.id}:{task.status} -->"


def sync_push(
    repo: Path,
    policy: DevPolicy,
    store: TaskStore,
    *,
    client: GitHubClient | None = None,
) -> dict:
    client = client or GitHubClient(repo)
    state_path = repo / "runs" / "dev" / "sync.json"
    state: dict = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except json.JSONDecodeError:
            state = {}
    updated, skipped = [], []
    for task in store.all():
        if task.source.kind != "github" or not task.source.number:
            continue
        last = state.get(task.id, {}).get("status")
        if last == task.status:
            skipped.append(task.id)
            continue
        body = (
            f"{_status_marker(task)}\n\n"
            f"Development task `{task.id}` is **{task.status}**.\n\n"
            f"Run: `runs/dev/tasks/{task.id}`"
        )
        client.comment(task.source.number, body)
        if task.status == "done" and policy.github.comment:
            client.close(task.source.number)
        state[task.id] = {"status": task.status, "number": task.source.number}
        updated.append(task.id)
    write_json(state_path, state)
    return {"updated": updated, "skipped": skipped}
