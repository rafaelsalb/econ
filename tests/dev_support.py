from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from econ.dev.models import DemoConfig, Task
from econ.dev.pipeline import DevPipeline
from econ.dev.policy import DevPolicy
from econ.dev.runner import FakeRunner
from econ.dev.tasks import TaskStore


def default_policy() -> DevPolicy:
    policy = DevPolicy()
    policy.gates.check_command = None
    policy.gates.agents_check_command = None
    policy.gates.dev_validate_command = None
    policy.gates.full_tests = True
    policy.gates.full_test_command = "python -m pytest -q"
    policy.gates.red_green = True
    policy.gates.require_tests_for_risk = 1
    policy.gates.timeout_s = 300
    policy.executor.timeout_s = 300
    policy.budget.max_wall_seconds = 600
    policy.github.comment = False
    return policy


def git(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr}{proc.stdout}")
    return proc.stdout


def make_repo(path: Path, *, policy: DevPolicy | None = None) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(["init", "-q"], path)
    git(["checkout", "-q", "-B", "main"], path)
    git(["config", "user.name", "econ-test"], path)
    git(["config", "user.email", "econ-test@localhost"], path)
    (path / ".gitignore").write_text(
        ".venv/\n__pycache__/\n.dev/\nruns/\n.pytest_cache/\n"
    )
    (path / "src" / "econ").mkdir(parents=True)
    (path / "src" / "econ" / "__init__.py").write_text("")
    (path / "tests").mkdir()
    (path / "tests" / ".gitkeep").write_text("")
    (path / "config").mkdir()
    (path / "config" / "dev_policy.yaml").write_text(
        yaml.safe_dump((policy or default_policy()).model_dump(mode="json"), sort_keys=False)
    )
    (path / "AGENTS.md").write_text("# Test repository\n")
    (path / "pyproject.toml").write_text(
        '[project]\nname = "econ-test"\nversion = "0.1.0"\n'
    )
    git(["add", "-A"], path)
    git(["commit", "-q", "-m", "baseline"], path)
    return path


def demo_task(
    task_id: str = "DEV-0001",
    *,
    risk: int = 1,
    files: list[dict] | None = None,
    base_files: list[dict] | None = None,
    acceptance: list[str] | None = None,
    allow: list[str] | None = None,
    **demo_kwargs,
) -> Task:
    files = files or [
        {
            "path": "src/econ/feature.py",
            "content": "def add(a: int, b: int) -> int:\n    return a + b\n",
        },
        {
            "path": "tests/test_feature.py",
            "content": "from econ.feature import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        },
    ]
    allow = allow or [item["path"] for item in files]
    payload = {
        "id": task_id,
        "title": f"Demo task {task_id}",
        "status": "ready",
        "risk": risk,
        "priority": 50,
        "created": "2026-11-24",
        "goal": "Add the demo feature and prove it with a test.",
        "acceptance": acceptance or ["python -m pytest tests/test_feature.py -q"],
        "scope": {"allow": allow, "deny": ["registry/**"]},
        "limits": {
            "max_review_rounds": 3,
            "max_usd": 5,
            "max_changed_files": 10,
            "max_diff_lines": 200,
        },
        "demo": {
            "files": files,
            "base_files": base_files or [],
            **demo_kwargs,
        },
    }
    return Task.model_validate(payload)


def add_task(repo: Path, task: Task) -> Task:
    store = TaskStore(repo)
    store.ensure()
    store.save(task, status=task.status)
    return task


def run_task(
    repo: Path,
    task_id: str,
    *,
    policy: DevPolicy | None = None,
    shadow: bool = False,
    auto_merge: bool = True,
    merge: bool = True,
    runner: FakeRunner | None = None,
):
    policy = policy or default_policy()
    pipeline = DevPipeline(
        repo,
        policy,
        runner=runner or FakeRunner(repo),
        shadow=shadow,
        auto_merge=auto_merge,
        base="main",
    )
    return pipeline.run_task(task_id, merge=merge)
