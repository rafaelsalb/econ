from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .models import Task, validate_task
from .pipeline import DevPipeline
from .policy import DevPolicy
from .runner import FakeRunner
from .tasks import TaskStore


def canary_dir(repo: Path) -> Path:
    return repo / "dev" / "evals" / "canary"


def load_canaries(repo: Path) -> list[Task]:
    tasks = []
    for path in sorted(canary_dir(repo).glob("*.yaml")):
        tasks.append(Task.model_validate(yaml.safe_load(path.read_text())))
    return tasks


def validate_canaries(repo: Path, policy: DevPolicy | None = None) -> list[str]:
    problems = []
    for task in load_canaries(repo):
        for problem in validate_task(task, policy):
            problems.append(f"{task.id}: {problem}")
    return problems


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {(proc.stderr or proc.stdout)[-1200:]}"
        )
    return proc


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_fixture(repo: Path, task: Task, policy: DevPolicy) -> Path:
    """Create a disposable git repository containing the canary base."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], repo)
    _git(["checkout", "-q", "-B", "main"], repo)
    _git(["config", "user.name", "econ-canary"], repo)
    _git(["config", "user.email", "econ-canary@localhost"], repo)
    _write(repo / ".gitignore", ".dev/\nruns/\n.venv/\n__pycache__/\n")
    _write(repo / "src" / "econ" / "__init__.py", "")
    _write(repo / "tests" / ".gitkeep", "")
    demo = task.demo
    if demo:
        for item in demo.base_files:
            _write(repo / item.path, item.content)
    (repo / "config").mkdir(parents=True, exist_ok=True)
    (repo / "config" / "dev_policy.yaml").write_text(
        yaml.safe_dump(policy.model_dump(mode="json"), sort_keys=False)
    )
    task_path = repo / "tasks" / "ready" / f"{task.id}.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        yaml.safe_dump(
            task.model_copy(update={"status": "ready"}).model_dump(
                mode="json", exclude_none=True
            ),
            sort_keys=False,
        )
    )
    _write(
        repo / "AGENTS.md",
        "# Canary repository\n\nRun `python -m pytest` for tests. Use `src/` paths.\n",
    )
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "canary baseline"], repo)
    return repo


def _canary_policy() -> DevPolicy:
    policy = DevPolicy()
    policy.gates.check_command = None
    policy.gates.agents_check_command = None
    policy.gates.dev_agents_check_command = None
    policy.gates.dev_validate_command = None
    policy.gates.full_tests = True
    policy.gates.full_test_command = "python -m pytest -q"
    policy.gates.red_green = True
    policy.gates.require_tests_for_risk = 1
    policy.gates.timeout_s = 300
    policy.budget.max_wall_seconds = 600
    policy.executor.timeout_s = 600
    policy.github.comment = False
    return policy


def write_canary_report(repo: Path, results: list[dict]) -> dict:
    """Persist canary evidence for the dashboard and humans."""
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {"generated_at": generated, "results": results}
    out = repo / "runs" / "dev" / "canaries"
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(payload, indent=2) + "\n")
    with (out / "index.jsonl").open("a") as fh:
        fh.write(json.dumps(payload) + "\n")
    reports = repo / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Development canaries",
        "",
        f"Generated: `{generated}`",
        "",
        "| Task | Result | Status | Rounds | Reason |",
        "|---|---|---|---:|---|",
    ]
    for row in results:
        reason = str(row.get("reason", "")).replace("|", "\\|")[:140]
        lines.append(
            f"| {row.get('task_id','?')} | {'PASS' if row.get('ok') else 'FAIL'} | "
            f"{row.get('status','?')} | {row.get('rounds','?')} | {reason} |"
        )
    lines += [
        "",
        "These are held-out pipeline tests. They do not enter the ready queue and",
        "must not be edited to make a failing pipeline look healthy.",
        "",
    ]
    report = reports / "dev_canaries.md"
    report.write_text("\n".join(lines))
    return {"json": str(out / "latest.json"), "report": str(report), "results": results}


def run_canaries(
    repo: Path,
    *,
    only: str | None = None,
    keep: bool = False,
    fake: bool = True,
) -> list[dict]:
    policy = _canary_policy()
    base_dir = repo / "runs" / "dev" / "canaries"
    base_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for task in load_canaries(repo):
        if only and task.id != only:
            continue
        workdir = Path(tempfile.mkdtemp(prefix=f"{task.id}-", dir=base_dir))
        try:
            build_fixture(workdir, task, policy)
            pipeline = DevPipeline(
                workdir,
                policy,
                runner=FakeRunner(workdir) if fake else None,
                shadow=False,
                auto_merge=True,
                base="main",
            )
            outcome = pipeline.run_task(task.id, merge=True)
            expected = [item.path for item in (task.demo.files if task.demo else [])]
            missing = [path for path in expected if not (workdir / path).exists()]
            ok = outcome.status == "done" and not missing
            results.append(
                {
                    "task_id": task.id,
                    "ok": ok,
                    "status": outcome.status,
                    "reason": outcome.decision.get("reason", ""),
                    "rounds": outcome.rounds,
                    "missing_on_main": missing,
                    "repo": str(workdir) if keep else None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "task_id": task.id,
                    "ok": False,
                    "status": "error",
                    "reason": f"{type(exc).__name__}: {exc}",
                    "repo": str(workdir) if keep else None,
                }
            )
        finally:
            if not keep:
                shutil.rmtree(workdir, ignore_errors=True)
    write_canary_report(repo, results)
    return results


def run_smoke(repo: Path, *, keep: bool = False) -> dict:
    results = run_canaries(repo, only="CANARY-001", keep=keep, fake=True)
    return results[0] if results else {"ok": False, "reason": "no canary found"}


def task_status_in_repo(repo: Path, task_id: str) -> str:
    store = TaskStore(repo)
    try:
        return store.load(task_id).status
    except FileNotFoundError:
        return "missing"
