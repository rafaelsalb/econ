from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .artifacts import RunArtifacts, sha256_file, tail, utcnow
from .models import Task
from .paths import matches_any, scope_violations
from .policy import DevPolicy, protected_hits
from .workspace import Worktree, command_env, git, rev_parse


@dataclass
class GateResult:
    name: str
    ok: bool
    detail: str
    blocking: bool = True
    human_required: bool = False
    evidence: dict[str, Any] = field(default_factory=dict)
    duration_s: float = 0.0

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
            "blocking": self.blocking,
            "human_required": self.human_required,
            "evidence": self.evidence,
            "duration_s": self.duration_s,
        }


@dataclass
class GateReport:
    gates: list[GateResult] = field(default_factory=list)
    stage: str = "full"

    @property
    def ok(self) -> bool:
        return all(g.ok for g in self.gates)

    @property
    def blocking_failures(self) -> list[GateResult]:
        return [g for g in self.gates if not g.ok and g.blocking]

    @property
    def human_required(self) -> list[GateResult]:
        return [g for g in self.gates if g.human_required]

    @property
    def auto_merge_ok(self) -> bool:
        return self.ok and not self.human_required

    def add(self, gate: GateResult) -> None:
        self.gates.append(gate)

    def find(self, name: str) -> GateResult | None:
        return next((g for g in self.gates if g.name == name), None)

    def as_dict(self) -> dict:
        return {
            "stage": self.stage,
            "ok": self.ok,
            "auto_merge_ok": self.auto_merge_ok,
            "human_required": [g.name for g in self.human_required],
            "gates": [g.as_dict() for g in self.gates],
        }


@dataclass
class CommandResult:
    command: str
    argv: list[str]
    exit_code: int
    duration_s: float
    stdout: str
    stderr: str
    timed_out: bool = False

    def as_dict(self) -> dict:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "duration_s": self.duration_s,
            "timed_out": self.timed_out,
            "stdout_tail": tail(self.stdout),
            "stderr_tail": tail(self.stderr),
        }


class GateRunner:
    def __init__(
        self,
        repo: Path,
        task: Task,
        worktree: Worktree,
        artifacts: RunArtifacts,
        policy: DevPolicy,
        *,
        base: str | None = None,
    ):
        self.repo = repo
        self.task = task
        self.worktree = worktree
        self.artifacts = artifacts
        self.policy = policy
        self.base = base or worktree.base
        self.commands: list[CommandResult] = []

    # -- command execution -------------------------------------------------
    def _command(self, command: str, *, timeout: int | None = None) -> CommandResult:
        if any(ch in command for ch in ";|&><`$(){}"):
            raise ValueError(f"refusing shell-meta command: {command!r}")
        argv = shlex.split(command)
        if not argv:
            raise ValueError("empty command")
        start = time.time()
        timed_out = False
        try:
            proc = subprocess.run(
                argv,
                cwd=self.worktree.path,
                capture_output=True,
                text=True,
                timeout=timeout or self.policy.gates.timeout_s,
                env=command_env(self.repo, self.worktree.path),
                check=False,
            )
            out, err, code = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            out = exc.stdout if isinstance(exc.stdout, str) else ""
            err = exc.stderr if isinstance(exc.stderr, str) else ""
            code = 124
        result = CommandResult(
            command=command,
            argv=argv,
            exit_code=code,
            duration_s=round(time.time() - start, 3),
            stdout=out,
            stderr=err,
            timed_out=timed_out,
        )
        self.commands.append(result)
        return result

    def _gate_from_command(
        self,
        name: str,
        command: str | None,
        *,
        blocking: bool = True,
        human_required: bool = False,
        timeout: int | None = None,
    ) -> GateResult:
        if not command:
            return GateResult(name, True, "not configured", blocking=False)
        start = time.time()
        try:
            result = self._command(command, timeout=timeout)
        except ValueError as exc:
            return GateResult(name, False, str(exc), blocking=blocking)
        ok = result.exit_code == 0
        detail = f"{command} -> exit {result.exit_code}"
        if result.timed_out:
            detail += " (timeout)"
        return GateResult(
            name,
            ok,
            detail,
            blocking=blocking,
            human_required=human_required,
            evidence=result.as_dict(),
            duration_s=round(time.time() - start, 3),
        )

    # -- individual gates --------------------------------------------------
    def changed_files(self) -> list[str]:
        return self.worktree.changed_files(self.base)

    def gate_patch(self) -> GateResult:
        changed = self.changed_files()
        return GateResult(
            "patch",
            bool(changed),
            f"{len(changed)} changed files" if changed else "empty patch",
            evidence={"files": changed},
        )

    def gate_scope(self) -> GateResult:
        changed = self.changed_files()
        problems = scope_violations(
            changed, self.task.scope.allow, self.task.scope.deny
        )
        return GateResult(
            "scope",
            not problems,
            "; ".join(problems) if problems else "all changed paths are in scope",
            evidence={"files": changed, "problems": problems},
        )

    def gate_protected(self) -> GateResult:
        changed = self.changed_files()
        hits = protected_hits(changed, self.policy.protected)
        return GateResult(
            "protected",
            not hits,
            "protected paths touched: " + ", ".join(hits)
            if hits
            else "no protected path touched",
            blocking=bool(hits),
            human_required=bool(hits),
            evidence={"paths": hits},
        )

    def gate_dependencies(self) -> GateResult:
        changed = set(self.changed_files())
        hits = sorted(changed & set(self.policy.gates.dependency_files))
        return GateResult(
            "dependencies",
            True,
            "dependency files changed: " + ", ".join(hits)
            if hits
            else "no dependency change",
            blocking=False,
            human_required=bool(hits),
            evidence={"files": hits},
        )

    def gate_secrets(self) -> GateResult:
        diff = self.worktree.diff(self.base)
        hits: list[str] = []
        for pattern in self.policy.gates.secret_patterns:
            for match in re.finditer(pattern, diff):
                hits.append(match.group(0)[:16] + "...")
        return GateResult(
            "secrets",
            not hits,
            f"{len(hits)} secret-like strings" if hits else "no secret-like strings",
            evidence={"matches": hits[:10]},
        )

    def gate_size(self) -> GateResult:
        changed = self.changed_files()
        added, deleted = self.worktree.diff_numstat(self.base)
        lines = added + deleted
        limit_files = min(
            self.task.limits.max_changed_files, self.policy.gates.max_changed_files
        )
        limit_lines = min(
            self.task.limits.max_diff_lines, self.policy.gates.max_diff_lines
        )
        problems = []
        if len(changed) > limit_files:
            problems.append(f"{len(changed)} files > {limit_files}")
        if lines > limit_lines:
            problems.append(f"{lines} changed lines > {limit_lines}")
        return GateResult(
            "size",
            not problems,
            "; ".join(problems) if problems else f"{len(changed)} files, {lines} lines",
            evidence={
                "files": len(changed),
                "lines": lines,
                "added": added,
                "deleted": deleted,
            },
        )

    def gate_patch_apply(self) -> GateResult:
        patch = self.artifacts.run_dir / "patch.diff"
        self.worktree.write_patch(patch, self.base)
        ok, output = self.worktree.apply_check(patch)
        return GateResult(
            "patch_apply",
            ok,
            "patch applies to a clean base" if ok else output,
            evidence={"patch": str(patch)},
        )

    def gate_tests_present(self) -> GateResult:
        if self.task.risk < self.policy.gates.require_tests_for_risk:
            return GateResult("tests_present", True, "not required at this risk")
        changed = self.changed_files()
        tests = [p for p in changed if p.startswith("tests/")]
        return GateResult(
            "tests_present",
            bool(tests),
            "tests changed: " + ", ".join(tests) if tests else "no test file changed",
            evidence={"tests": tests},
        )

    def gate_acceptance(self) -> GateResult:
        results = [self._command(cmd) for cmd in self.task.acceptance]
        ok = all(r.exit_code == 0 for r in results)
        detail = "; ".join(
            f"{r.command} -> {r.exit_code}" for r in results
        )
        return GateResult(
            "acceptance",
            ok,
            detail,
            evidence={"commands": [r.as_dict() for r in results]},
        )

    def gate_full_tests(self) -> GateResult:
        if not self.policy.gates.full_tests:
            return GateResult("full_tests", True, "not configured", blocking=False)
        if self.task.risk == 0 and self.policy.gates.risk0_skip_full_tests:
            return GateResult("full_tests", True, "skipped for risk 0", blocking=False)
        return self._gate_from_command(
            "full_tests", self.policy.gates.full_test_command
        )

    def gate_check(self) -> GateResult:
        return self._gate_from_command("econ_check", self.policy.gates.check_command)

    def gate_agents_check(self) -> GateResult:
        return self._gate_from_command(
            "agents_check", self.policy.gates.agents_check_command
        )

    def gate_dev_validate(self) -> GateResult:
        return self._gate_from_command(
            "dev_validate", self.policy.gates.dev_validate_command
        )

    def gate_lockbox(self) -> GateResult:
        base_path = self.repo / "registry" / "lockbox.json"
        wt_path = self.worktree.path / "registry" / "lockbox.json"
        if not base_path.exists():
            return GateResult("lockbox", True, "no lockbox in this repository")
        if not wt_path.exists():
            return GateResult(
                "lockbox",
                False,
                "lockbox file was deleted",
                human_required=True,
            )
        base_hash = sha256_file(base_path)
        wt_hash = sha256_file(wt_path)
        ok = base_hash == wt_hash
        return GateResult(
            "lockbox",
            ok,
            "lockbox unchanged" if ok else "lockbox changed",
            blocking=not ok,
            human_required=not ok,
            evidence={"base": base_hash, "worktree": wt_hash},
        )

    def gate_registry_append_only(self) -> GateResult:
        proc = git(
            ["diff", "--name-status", f"{self.base}..HEAD", "--", "registry"],
            self.worktree.path,
            check=False,
        )
        bad = []
        for line in proc.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0] in {"M", "D", "R", "C"}:
                bad.append(line)
        return GateResult(
            "registry_append_only",
            not bad,
            "registry changes are append-only"
            if not bad
            else "registry history modified: " + "; ".join(bad),
            blocking=bool(bad),
            human_required=bool(bad),
            evidence={"changes": bad},
        )

    def gate_red_green(self) -> GateResult:
        if not self.policy.gates.red_green:
            return GateResult("red_green", True, "not configured", blocking=False)
        if self.task.risk < self.policy.gates.require_tests_for_risk:
            return GateResult("red_green", True, "not required at this risk")
        changed = self.changed_files()
        test_files = [p for p in changed if p.startswith("tests/")]
        if not test_files:
            return GateResult(
                "red_green",
                False,
                "no tests changed; cannot prove red/green",
            )
        scratch = self.repo / "runs" / "dev"
        scratch.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix="econ-redgreen-", dir=scratch))
        base_wt = tmp / "tree"
        try:
            git(
                ["worktree", "add", "--detach", str(base_wt), self.base],
                self.repo,
            )
            for relative in test_files:
                source = self.worktree.path / relative
                target = base_wt / relative
                if not source.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            argv = [*shlex.split(self.policy.gates.full_test_command), *test_files]
            argv = argv[: -len(test_files)] + ["-q", *test_files]
            proc = subprocess.run(
                argv,
                cwd=base_wt,
                capture_output=True,
                text=True,
                timeout=self.policy.gates.timeout_s,
                env=command_env(self.repo, base_wt),
                check=False,
            )
            ok = proc.returncode != 0
            return GateResult(
                "red_green",
                ok,
                "new tests fail on the base commit"
                if ok
                else "new tests pass on the base commit; they prove nothing",
                evidence={
                    "tests": test_files,
                    "base_exit_code": proc.returncode,
                    "stdout_tail": tail(proc.stdout),
                    "stderr_tail": tail(proc.stderr),
                },
            )
        except subprocess.TimeoutExpired:
            return GateResult("red_green", False, "red/green check timed out")
        finally:
            git(
                ["worktree", "remove", "--force", str(base_wt)],
                self.repo,
                check=False,
            )
            shutil.rmtree(tmp, ignore_errors=True)

    def gate_no_forbidden_paths(self) -> GateResult:
        changed = self.changed_files()
        forbidden = [
            p
            for p in changed
            if p.startswith((".dev/", "runs/", ".venv/"))
            or p in {".dev", "runs", ".venv"}
        ]
        return GateResult(
            "no_forbidden_paths",
            not forbidden,
            "no scratch paths committed"
            if not forbidden
            else "forbidden paths: " + ", ".join(forbidden),
            evidence={"paths": forbidden},
        )

    # -- stages ------------------------------------------------------------
    def run_pre(self) -> GateReport:
        report = GateReport(stage="pre")
        for gate in (
            self.gate_patch,
            self.gate_no_forbidden_paths,
            self.gate_scope,
            self.gate_protected,
            self.gate_dependencies,
            self.gate_secrets,
            self.gate_size,
            self.gate_patch_apply,
            self.gate_tests_present,
            self.gate_acceptance,
            self.gate_full_tests,
        ):
            report.add(gate())
        self.artifacts.write_json("test-report.json", self._commands_report(report))
        return report

    def run_post(self) -> GateReport:
        report = GateReport(stage="post")
        for gate in (
            self.gate_check,
            self.gate_agents_check,
            self.gate_dev_validate,
            self.gate_red_green,
            self.gate_lockbox,
            self.gate_registry_append_only,
        ):
            report.add(gate())
        return report

    def run_full(self) -> GateReport:
        pre = self.run_pre()
        post = self.run_post()
        merged = GateReport(stage="full")
        merged.gates = pre.gates + post.gates
        self.artifacts.write_json("gates.json", merged.as_dict())
        return merged

    def _commands_report(self, report: GateReport) -> dict:
        return {
            "generated_at": utcnow(),
            "head": rev_parse(self.worktree.path, "HEAD"),
            "task": self.task.id,
            "acceptance": [r.as_dict() for r in self.commands],
            "gates": [g.as_dict() for g in report.gates],
        }
