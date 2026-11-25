from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import yaml

from .. import agents as agent_config
from .artifacts import tail, write_json
from .workspace import command_env


@dataclass
class AgentResult:
    role: str
    command: list[str]
    exit_code: int
    duration_s: float
    timed_out: bool
    text: str
    stdout: str
    stderr: str
    cost_usd: float = 0.0
    tokens: int = 0
    steps: int = 0
    error: str = ""
    denials: list[dict] = field(default_factory=list)
    request: dict = field(default_factory=dict)

    def json_output(self) -> dict | None:
        from .artifacts import extract_json

        # Tool events are JSON too. Only the assistant text is a role artifact.
        return extract_json(self.text)


class AgentRunner(Protocol):
    def run(
        self,
        role: str,
        cwd: Path,
        prompt: str,
        *,
        timeout: int = 1200,
        model_override: str | None = None,
        max_budget_usd: float | None = None,
    ) -> AgentResult: ...


def _usage(event: dict) -> tuple[float, int]:
    cost = 0.0
    tokens = 0
    for key in ("cost", "cost_usd", "total_cost"):
        value = event.get(key)
        if isinstance(value, (int, float)):
            cost += float(value)
    usage = event.get("usage") or {}
    if isinstance(usage, dict):
        for key in ("total_tokens", "totalTokens", "input_tokens", "output_tokens"):
            value = usage.get(key)
            if isinstance(value, int):
                tokens += value
    tokens_value = event.get("tokens")
    if isinstance(tokens_value, int):
        tokens += tokens_value
    elif isinstance(tokens_value, dict):
        tokens += sum(v for v in tokens_value.values() if isinstance(v, int))
    return cost, tokens


def parse_opencode_events(stdout: str) -> tuple[str, float, int, int]:
    texts: list[str] = []
    cost = 0.0
    tokens = 0
    steps = 0
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text" and isinstance(event.get("part"), dict):
            text = event["part"].get("text")
            if text:
                texts.append(text)
        if event.get("type") == "step_finish":
            steps += 1
        c, t = _usage(event)
        cost += c
        tokens += t
    return "\n\n".join(texts), cost, tokens, steps


class OpencodeRunner:
    def __init__(
        self,
        repo: Path,
        specs: dict[str, agent_config.AgentSpec] | None = None,
        *,
        executable: str = "opencode",
        extra_env: dict[str, str] | None = None,
        standalone: bool | None = None,
    ):
        self.repo = repo
        if specs is None:
            specs = {
                spec.name: spec for spec in agent_config.dev_agents(root=repo)
            }
        elif not isinstance(specs, dict):
            specs = {spec.name: spec for spec in specs}
        self.specs = specs
        self.executable = executable
        self.extra_env = extra_env or {}
        if standalone is None:
            # Each task runs in a linked worktree. A shared background server
            # can resolve the session back to the main checkout, which would
            # let agents edit `main` instead of the worktree. A private server
            # per call keeps the project root pinned to the worktree.
            standalone = os.environ.get("ECON_DEV_SHARED_SERVER") != "1"
        self.standalone = standalone

    def command(
        self, role: str, prompt: str, *, model_override: str | None = None
    ) -> list[str]:
        spec = self.specs.get(role)
        if spec is None:
            raise KeyError(f"unknown dev agent role: {role}")
        model = model_override or spec.selector
        argv = [
            self.executable,
            "run",
            "--agent",
            spec.agent_id,
            "--model",
            model,
            "--format",
            "json",
            "--archived",
            "--auto",
        ]
        if self.standalone:
            argv.append("--standalone")
        argv.append(prompt)
        return argv

    def run(
        self,
        role: str,
        cwd: Path,
        prompt: str,
        *,
        timeout: int = 1200,
        model_override: str | None = None,
        max_budget_usd: float | None = None,
    ) -> AgentResult:
        argv = self.command(role, prompt, model_override=model_override)
        env = command_env(self.repo, cwd)
        # subprocess.run(cwd=...) does not update PWD. OpenCode's project
        # discovery consults the inherited PWD, so without this it can resolve
        # the session back to the main checkout.
        env["PWD"] = str(cwd.resolve())
        env.update(self.extra_env)
        start = time.time()
        timed_out = False
        try:
            proc = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                check=False,
            )
            out, err, code = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            out = exc.stdout if isinstance(exc.stdout, str) else ""
            err = exc.stderr if isinstance(exc.stderr, str) else ""
            code = 124
        duration = time.time() - start
        text, cost, tokens, steps = parse_opencode_events(out)
        return AgentResult(
            role=role,
            command=argv,
            exit_code=code,
            duration_s=round(duration, 3),
            timed_out=timed_out,
            text=text,
            stdout=out,
            stderr=err,
            cost_usd=cost,
            tokens=tokens,
            steps=steps,
        )


class FakeRunner:
    """Deterministic stand-in used by tests, canaries, and `econ dev smoke`.

    It reads the task's `demo` block and writes the same role artifacts that a
    real agent is asked to write. It never calls a model and costs nothing.
    """

    def __init__(self, repo: Path | None = None):
        self.repo = repo
        self.calls: list[str] = []
        self.costs: dict[str, float] = {}

    def _task(self, cwd: Path) -> dict:
        task_path = cwd / ".dev" / "task.yaml"
        return yaml.safe_load(task_path.read_text())

    def _round(self, cwd: Path) -> int:
        path = cwd / ".dev" / "round"
        try:
            return int(path.read_text().strip())
        except Exception:  # noqa: BLE001
            return 1

    def _write(self, cwd: Path, role: str, payload: dict) -> None:
        out = cwd / ".dev" / "out"
        out.mkdir(parents=True, exist_ok=True)
        write_json(out / f"{role}.json", payload)
        (out / f"{role}.md").write_text(json.dumps(payload, indent=2) + "\n")

    def run(
        self,
        role: str,
        cwd: Path,
        prompt: str,
        *,
        timeout: int = 1200,
        model_override: str | None = None,
        max_budget_usd: float | None = None,
    ) -> AgentResult:
        self.calls.append(role)
        task = self._task(cwd)
        demo = task.get("demo") or {}
        round_no = self._round(cwd)
        started = time.time()

        if role == "implementer":
            for item in demo.get("files") or []:
                target = cwd / item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(item["content"])
            if round_no > 1 and int(demo.get("fail_first_rounds", 0)) > 0:
                first = (demo.get("files") or [None])[0]
                if first:
                    target = cwd / first["path"]
                    target.write_text(
                        target.read_text()
                        + f"\n# revised in round {round_no}\n"
                    )
            payload = {
                "role": "implementer",
                "summary": f"applied {len(demo.get('files') or [])} demo files",
                "files": [item["path"] for item in demo.get("files") or []],
                "tests_added": [
                    item["path"]
                    for item in demo.get("files") or []
                    if item["path"].startswith("tests/")
                ],
                "commands": [],
                "known_limitations": [],
                "round": round_no,
            }
        elif role in {"reviewer", "reviewer_alt"}:
            outcome = (
                demo.get("review", "approve")
                if role == "reviewer"
                else demo.get("second_review", "approve")
            )
            if round_no <= int(demo.get("fail_first_rounds", 0)):
                outcome = "changes_requested"
            payload = {
                "role": "reviewer",
                "verdict": outcome,
                "findings": []
                if outcome == "approve"
                else [
                    {
                        "severity": "major",
                        "file": "demo",
                        "line": 1,
                        "issue": "demo requested a revision",
                        "suggestion": "apply the next round",
                    }
                ],
                "tests_reviewed": True,
                "notes": f"fake {role}",
            }
        elif role == "verifier":
            outcome = demo.get("verifier", "pass")
            payload = {
                "role": "verifier",
                "verdict": outcome,
                "checks": [{"command": "fake", "exit_code": 0 if outcome == "pass" else 1}],
                "findings": []
                if outcome == "pass"
                else [{"severity": "blocker", "issue": "demo verifier failure"}],
                "notes": "fake verifier",
            }
        elif role == "science_guard":
            outcome = demo.get("science_guard", "clear")
            payload = {
                "role": "science_guard",
                "verdict": outcome,
                "protected_paths": [],
                "checks": [{"name": "demo", "ok": outcome == "clear", "detail": ""}],
                "findings": []
                if outcome == "clear"
                else [{"severity": "blocker", "issue": "demo integrity block"}],
            }
        elif role == "architect":
            payload = {
                "role": "architect",
                "design": "deterministic demo design",
                "files": [item["path"] for item in demo.get("files") or []],
                "interfaces": [],
                "test_plan": task.get("acceptance", []),
                "risks": [],
                "rollback": "revert the commit",
            }
        elif role == "lead":
            payload = {
                "role": "lead",
                "plan": ["apply the task patch", "run acceptance"],
                "files_expected": [item["path"] for item in demo.get("files") or []],
                "risk_notes": [],
                "escalate": False,
                "reason": "",
            }
        elif role == "scribe":
            payload = {
                "role": "scribe",
                "files": [],
                "summary": "no documentation change needed for the demo",
                "claims_verified": [],
            }
        elif role == "triage":
            payload = {
                "role": "triage",
                "task": task,
                "needs_human": False,
                "reason": "fake triage",
            }
        elif role == "reproducer":
            tests = [
                item
                for item in demo.get("files") or []
                if item["path"].startswith("tests/")
            ]
            for item in tests:
                target = cwd / item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(item["content"])
            if tests:
                payload = {
                    "role": "reproducer",
                    "reproduced": True,
                    "test_file": tests[0]["path"],
                    "failing_command": (task.get("acceptance") or [""])[0],
                    "observed_failure": "the base commit fails the new test",
                    "notes": "fake reproducer",
                }
            else:
                payload = {
                    "role": "reproducer",
                    "reproduced": False,
                    "test_file": "",
                    "failing_command": "",
                    "observed_failure": "no failing test in the demo contract",
                    "notes": "fake reproducer",
                }
        else:
            raise KeyError(f"unknown dev agent role: {role}")

        self._write(cwd, role, payload)
        return AgentResult(
            role=role,
            command=["fake", role],
            exit_code=0,
            duration_s=round(time.time() - started, 3),
            timed_out=False,
            text=json.dumps(payload),
            stdout=json.dumps(payload),
            stderr="",
            cost_usd=0.0,
            tokens=0,
        )


class RoutedRunner:
    """Dispatch each role to the runtime selected in config/dev_agents.yaml."""

    def __init__(
        self,
        specs: dict[str, agent_config.AgentSpec],
        runners: dict[str, AgentRunner],
        *,
        forced: str | None = None,
    ):
        self.specs = specs
        self.runners = runners
        self.forced = forced

    def runtime_for(self, role: str) -> str:
        spec = self.specs.get(role)
        if spec is None:
            raise KeyError(f"unknown dev agent role: {role}")
        return self.forced or spec.runtime

    def run(
        self,
        role: str,
        cwd: Path,
        prompt: str,
        *,
        timeout: int = 1200,
        model_override: str | None = None,
        max_budget_usd: float | None = None,
    ) -> AgentResult:
        runtime = self.runtime_for(role)
        runner = self.runners.get(runtime)
        if runner is None:
            raise ValueError(
                f"{role}: runtime {runtime!r} is configured but no runner "
                "is available for it"
            )
        return runner.run(
            role,
            cwd,
            prompt,
            timeout=timeout,
            model_override=model_override,
            max_budget_usd=max_budget_usd,
        )


def runner_for(
    repo: Path,
    kind: str = "opencode",
    *,
    extra_env: dict[str, str] | None = None,
    specs: dict[str, agent_config.AgentSpec] | None = None,
    cfg: dict | None = None,
    forced: str | None = None,
) -> AgentRunner:
    if kind in {"fake", "demo"}:
        return FakeRunner(repo)
    if kind in {"docker", "container"}:
        from .docker import DockerRunner
        from .policy import load_policy

        return DockerRunner(
            repo,
            load_policy(repo),
            cfg=cfg,
            specs=specs,
            forced_runtime=forced,
        )
    if kind not in {"opencode", "claude", "auto"}:
        raise ValueError(f"unknown runner: {kind}")
    cfg = cfg or agent_config.load_dev_config()
    if specs is None:
        specs = {
            spec.name: spec
            for spec in agent_config.dev_agents(cfg, root=repo)
        }
    elif not isinstance(specs, dict):
        specs = {spec.name: spec for spec in specs}

    selected = forced or (kind if kind != "auto" else None)
    if selected:
        from dataclasses import replace

        specs = {
            name: replace(spec, runtime=selected)
            for name, spec in specs.items()
        }
        if selected == "claude":
            missing = sorted(
                name for name, spec in specs.items() if not spec.claude_model
            )
            if missing:
                raise ValueError(
                    "cannot force Claude for roles without claude_model: "
                    + ", ".join(missing)
                )
    runtimes = {selected} if selected else {spec.runtime for spec in specs.values()}
    runners: dict[str, AgentRunner] = {}
    for runtime in sorted(runtimes):
        if runtime == "opencode":
            runners[runtime] = OpencodeRunner(
                repo, specs=specs, extra_env=extra_env
            )
        elif runtime == "claude":
            from .claude import ClaudeRunner

            runners[runtime] = ClaudeRunner(
                repo, specs=specs, cfg=cfg, extra_env=extra_env
            )
        else:
            raise ValueError(f"unknown configured runtime: {runtime}")
    if len(runners) == 1:
        return next(iter(runners.values()))
    return RoutedRunner(specs, runners, forced=selected)
