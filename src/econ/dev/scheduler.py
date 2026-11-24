from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .artifacts import utcnow, write_json
from .budget import BudgetLedger
from .locks import FileLock, PauseSwitch
from .models import Task
from .paths import claims_conflict
from .pipeline import DevPipeline, Outcome
from .policy import DevPolicy
from .runner import runner_for
from .sync import GitHubClient, sync_pull
from .tasks import TaskStore


def _sort_key(task: Task) -> tuple:
    return (-task.priority, task.risk, task.created, task.id)


class DevScheduler:
    def __init__(
        self,
        repo: Path,
        policy: DevPolicy | None = None,
        *,
        runner_kind: str = "opencode",
        executor: str = "local",
        shadow: bool = False,
        auto_merge: bool = True,
        max_parallel: int = 1,
        daily_usd: float | None = None,
        sync_github: bool = False,
    ):
        from .policy import load_policy

        self.repo = repo.resolve()
        self.policy = policy or load_policy(self.repo)
        self.runner_kind = runner_kind
        self.executor = executor
        self.shadow = shadow
        self.auto_merge = auto_merge
        self.max_parallel = max(1, max_parallel)
        self.sync_github = sync_github
        self.budget = BudgetLedger(
            self.repo, daily_usd if daily_usd is not None else self.policy.budget.daily_usd
        )
        self.store = TaskStore(self.repo)
        self.pause = PauseSwitch(self.repo)
        self.lock = FileLock(
            self.repo / "runs" / "dev" / ".daemon.lock", stale_seconds=6 * 3600
        )
        self.state_path = self.repo / "runs" / "dev" / "daemon.json"

    # -- selection ---------------------------------------------------------
    def select(self, limit: int | None = None) -> list[Task]:
        ready = sorted(self.store.ready(), key=_sort_key)
        claims: list[list[str]] = [
            task.scope.allow for task in self.store.all() if task.status == "active"
        ]
        selected: list[Task] = []
        for task in ready:
            if limit is not None and len(selected) >= limit:
                break
            if self.budget.remaining <= 0:
                break
            if task.limits.max_usd > self.budget.remaining:
                continue
            if any(claims_conflict(task.scope.allow, claim) for claim in claims):
                continue
            selected.append(task)
            claims.append(task.scope.allow)
        return selected

    # -- execution ---------------------------------------------------------
    def _runner(self):
        kind = self.runner_kind
        if self.executor == "docker" and kind == "opencode":
            kind = "docker"
        return runner_for(self.repo, kind)

    def run_once(self, *, max_tasks: int | None = None) -> list[Outcome]:
        if self.pause.paused():
            return []
        if not self.lock.acquire():
            return []
        try:
            if self.sync_github:
                try:
                    sync_pull(
                        self.repo,
                        self.policy,
                        self.store,
                        promote=self.policy.github.auto_promote,
                    )
                except Exception:  # noqa: BLE001
                    # GitHub being unavailable must not stop local work.
                    pass
            tasks = self.select(limit=max_tasks or self.max_parallel)
            if not tasks:
                self._write_state([])
                return []
            outcomes: list[Outcome] = []
            if self.max_parallel == 1:
                pipeline = DevPipeline(
                    self.repo,
                    self.policy,
                    runner=self._runner(),
                    shadow=self.shadow,
                    auto_merge=self.auto_merge,
                    executor=self.executor,
                    budget=self.budget,
                )
                for task in tasks:
                    outcomes.append(pipeline.run_task(task.id, merge=True))
                    self.budget.count_task()
            else:
                with ThreadPoolExecutor(max_workers=self.max_parallel) as pool:
                    futures = {}
                    for task in tasks:
                        pipeline = DevPipeline(
                            self.repo,
                            self.policy,
                            runner=self._runner(),
                            shadow=self.shadow,
                            auto_merge=self.auto_merge,
                            executor=self.executor,
                            budget=self.budget,
                        )
                        futures[
                            pool.submit(pipeline.run_task, task.id, merge=False)
                        ] = task
                    for future in as_completed(futures):
                        outcomes.append(future.result())
                for outcome in list(outcomes):
                    if outcome.status == "awaiting_merge":
                        merged = DevPipeline(
                            self.repo,
                            self.policy,
                            runner=self._runner(),
                            shadow=self.shadow,
                            auto_merge=self.auto_merge,
                            executor=self.executor,
                            budget=self.budget,
                        ).finalize_merge(outcome.task_id)
                        outcomes[outcomes.index(outcome)] = merged
                for _ in tasks:
                    self.budget.count_task()
            self._notify(outcomes)
            self._write_state(outcomes)
            return outcomes
        finally:
            self.lock.release()

    def loop(self, *, interval_s: int = 60, once: bool = False, max_tasks: int | None = None) -> list[Outcome]:
        outcomes: list[Outcome] = []
        while True:
            if self.pause.paused():
                if once:
                    break
                time.sleep(max(1, interval_s))
                continue
            outcomes.extend(self.run_once(max_tasks=max_tasks))
            if once:
                break
            time.sleep(max(1, interval_s))
        return outcomes

    # -- state / notifications --------------------------------------------
    def _notify(self, outcomes: list[Outcome]) -> None:
        client = GitHubClient(self.repo)
        for outcome in outcomes:
            try:
                task = self.store.load(outcome.task_id)
            except Exception:  # noqa: BLE001
                continue
            if task.source.kind != "github" or not task.source.number:
                continue
            if not self.policy.github.comment:
                continue
            body = (
                f"Development task `{task.id}` finished with **{outcome.status}**.\n\n"
                f"Reason: {outcome.decision.get('reason', '')}\n\n"
                f"Artifacts: `runs/dev/tasks/{task.id}`"
            )
            try:
                client.comment(task.source.number, body)
                if outcome.status == "done":
                    client.close(task.source.number)
            except Exception:  # noqa: BLE001
                pass

    def _write_state(self, outcomes: list[Outcome]) -> None:
        write_json(
            self.state_path,
            {
                "ts": utcnow(),
                "paused": self.pause.paused(),
                "max_parallel": self.max_parallel,
                "runner": self.runner_kind,
                "executor": self.executor,
                "budget": self.budget.as_dict(),
                "ready": [task.id for task in self.store.ready()],
                "outcomes": [outcome.as_dict() for outcome in outcomes],
            },
        )

    def status(self) -> dict:
        from .locks import pid_alive

        lock_info = self.lock.read()
        active = [t.id for t in self.store.all() if t.status == "active"]
        daemon = {}
        if self.state_path.exists():
            try:
                daemon = json.loads(self.state_path.read_text())
            except json.JSONDecodeError:
                daemon = {}
        return {
            "repo": str(self.repo),
            "paused": self.pause.paused(),
            "lock": {
                "held": bool(lock_info),
                "pid": lock_info.get("pid") if lock_info else None,
                "alive": bool(lock_info and pid_alive(int(lock_info.get("pid", 0)))),
            },
            "ready": [t.id for t in self.store.ready()],
            "active": active,
            "budget": self.budget.as_dict(),
            "last_tick": daemon,
            "max_parallel": self.max_parallel,
        }
