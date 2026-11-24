from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .artifacts import RunArtifacts, utcnow
from .budget import BudgetLedger
from .gates import GateReport, GateRunner
from .locks import FileLock
from .models import Task, validate_task
from .policy import DevPolicy
from .runner import AgentResult, AgentRunner
from .tasks import TaskStore
from .workspace import (
    GitError,
    Worktree,
    merge_ff,
    rev_parse,
    worktree_status,
)


class AgentProtocolError(RuntimeError):
    pass


@dataclass
class Outcome:
    task_id: str
    status: str
    decision: dict
    run_dir: Path
    worktree: Path | None = None
    branch: str | None = None
    commit: str | None = None
    reviews: list[dict] = field(default_factory=list)
    rounds: int = 0
    cost_usd: float = 0.0

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "decision": self.decision,
            "run_dir": str(self.run_dir),
            "worktree": str(self.worktree) if self.worktree else None,
            "branch": self.branch,
            "commit": self.commit,
            "reviews": self.reviews,
            "rounds": self.rounds,
            "cost_usd": self.cost_usd,
        }


def _gate_findings(report: GateReport) -> list[dict]:
    out = []
    for gate in report.blocking_failures:
        out.append(
            {
                "severity": "blocker",
                "file": "",
                "line": 0,
                "issue": f"gate {gate.name}: {gate.detail}",
                "suggestion": "fix the failing gate and resubmit",
                "gate": gate.name,
            }
        )
    return out


def _review_findings(payload: dict) -> list[dict]:
    findings = payload.get("findings") or []
    return [f for f in findings if isinstance(f, dict)]


class DevPipeline:
    def __init__(
        self,
        repo: Path,
        policy: DevPolicy | None = None,
        runner: AgentRunner | None = None,
        *,
        shadow: bool = False,
        auto_merge: bool = True,
        base: str | None = None,
        executor: str = "local",
        budget: BudgetLedger | None = None,
    ):
        from .policy import load_policy
        from .runner import runner_for

        self.repo = repo.resolve()
        self.policy = policy or load_policy(self.repo)
        self.runner = runner or runner_for(self.repo, "opencode")
        self.shadow = shadow
        self.auto_merge = auto_merge
        self.base = base or self.policy.branch
        self.executor = executor
        self.budget = budget
        self.store = TaskStore(self.repo)

    # -- public API --------------------------------------------------------
    def run_task(self, task_ref: str | Path, *, merge: bool | None = None) -> Outcome:
        task = self._load(task_ref)
        problems = validate_task(task, self.policy)
        if problems:
            raise ValueError(f"{task.id}: " + "; ".join(problems))
        if task.status != "ready":
            raise ValueError(f"{task.id}: task must be ready, is {task.status}")

        task = task.model_copy(update={"status": "active"})
        self.store.save(task)
        artifacts = RunArtifacts(self.repo, task.id).ensure()
        self.store.freeze(task, artifacts.run_dir)
        artifacts.append_event(
            "task_started",
            risk=task.risk,
            shadow=self.shadow,
            auto_merge=self.auto_merge,
            executor=self.executor,
        )

        if task.risk >= 3:
            return self._finish(
                task,
                artifacts,
                "escalated",
                {
                    "reason": "risk 3 changes the scientific contract and requires human sign-off",
                    "human_required": True,
                },
            )

        try:
            outcome = self._execute(task, artifacts)
        except Exception as exc:  # noqa: BLE001
            artifacts.append_event(
                "task_error", error=f"{type(exc).__name__}: {exc}"
            )
            artifacts.write_json(
                "error.json", {"type": type(exc).__name__, "error": str(exc)}
            )
            return self._finish(
                task,
                artifacts,
                "failed",
                {"reason": f"{type(exc).__name__}: {exc}"},
            )

        if outcome.status == "approved" and not self.shadow:
            if not self.auto_merge:
                outcome = self._escalate(
                    task,
                    artifacts,
                    outcome,
                    "automatic merging is disabled for this run",
                )
            else:
                decision = self._merge_decision(outcome, task)
                outcome.decision["merge_policy"] = decision
                if decision["allowed"]:
                    outcome = self._merge(task, artifacts, outcome, merge=merge)
                else:
                    outcome = self._escalate(
                        task, artifacts, outcome, decision["reason"]
                    )
        elif outcome.status == "approved" and self.shadow:
            outcome = self._finish(
                task,
                artifacts,
                "shadow",
                {**outcome.decision, "reason": "shadow mode: no merge", "shadow": True},
                outcome=outcome,
            )
        return outcome

    def finalize_merge(self, task_id: str) -> Outcome:
        """Merge a task left in `awaiting_merge` by a parallel worker."""
        task = self.store.load(task_id)
        artifacts = RunArtifacts(self.repo, task.id).ensure()
        state = artifacts.load_state()
        path = state.get("worktree")
        if not path or not Path(path).exists():
            raise RuntimeError(f"{task_id}: no pending worktree to merge")
        worktree = Worktree(
            repo=self.repo,
            path=Path(path),
            branch=state["branch"],
            base=state["base"],
            task_id=task.id,
        )
        decision = artifacts.read_json("decision.json", {}) or {}
        outcome = Outcome(
            task_id=task.id,
            status="approved",
            decision=decision,
            run_dir=artifacts.run_dir,
            worktree=worktree.path,
            branch=worktree.branch,
            commit=worktree.commit_sha(),
            reviews=decision.get("reviews") or [],
            rounds=int(state.get("round", 1)),
            cost_usd=float(artifacts.cost().get("total_usd", 0)),
        )
        decision = self._merge_decision(outcome, task)
        if not decision["allowed"]:
            return self._escalate(task, artifacts, outcome, decision["reason"])
        return self._merge(task, artifacts, outcome, merge=True)

    # -- setup / packets ---------------------------------------------------
    def _load(self, task_ref: str | Path) -> Task:
        if isinstance(task_ref, Path) or str(task_ref).endswith(".yaml"):
            return self.store.load_path(Path(task_ref))
        return self.store.load(str(task_ref))

    def _write_task(self, worktree: Worktree, task: Task) -> None:
        dev = worktree.path / ".dev"
        dev.mkdir(parents=True, exist_ok=True)
        (dev / "task.yaml").write_text(
            yaml.safe_dump(
                task.model_dump(mode="json", exclude_none=True), sort_keys=False
            )
        )

    def _write_packet(
        self, worktree: Worktree, task: Task, text: str, *, round_no: int = 1
    ) -> None:
        dev = worktree.path / ".dev"
        dev.mkdir(parents=True, exist_ok=True)
        (dev / "packet.md").write_text(text)
        (dev / "round").write_text(str(round_no))
        out = dev / "out"
        out.mkdir(parents=True, exist_ok=True)
        for path in out.glob("*"):
            if path.is_file():
                path.unlink()

    def _prepare_review(
        self,
        worktree: Worktree,
        task: Task,
        artifacts: RunArtifacts,
        *,
        diff: str | None = None,
    ) -> None:
        review = worktree.path / ".dev" / "review"
        review.mkdir(parents=True, exist_ok=True)
        (review / "diff.patch").write_text(
            diff if diff is not None else worktree.diff(worktree.base)
        )
        (review / "test-report.json").write_text(
            json.dumps(artifacts.read_json("test-report.json", {}), indent=2)
        )
        (review / "task.yaml").write_text(
            yaml.safe_dump(
                task.model_dump(mode="json", exclude_none=True), sort_keys=False
            )
        )
        out = worktree.path / ".dev" / "out"
        out.mkdir(parents=True, exist_ok=True)
        for path in out.glob("*"):
            if path.is_file():
                path.unlink()

    def _prepare_verification(
        self,
        worktree: Worktree,
        task: Task,
        artifacts: RunArtifacts,
        commit: str,
    ) -> Worktree:
        diff = worktree.diff(worktree.base)
        verify = Worktree.create(
            self.repo,
            f"{task.id}-verify",
            base=commit,
            worktrees_dir=self.repo / "runs" / "dev" / "worktrees",
        )
        self._write_task(verify, task)
        self._prepare_review(verify, task, artifacts, diff=diff)
        return verify

    # -- agents ------------------------------------------------------------
    def _agent(
        self,
        role: str,
        worktree: Worktree,
        task: Task,
        artifacts: RunArtifacts,
        prompt: str,
        *,
        round_no: int = 1,
        model_override: str | None = None,
    ) -> dict:
        artifacts.append_event("agent_started", role=role, round=round_no)
        result = self.runner.run(
            role,
            worktree.path,
            prompt,
            timeout=min(task.limits.wall_seconds, self.policy.executor.timeout_s),
            model_override=model_override,
        )
        self._record_agent(role, round_no, result, artifacts, task)
        if result.exit_code != 0 or result.timed_out:
            raise AgentProtocolError(
                f"{role} failed (exit {result.exit_code}, timeout={result.timed_out}): "
                f"{result.stderr[-1200:] or result.stdout[-1200:]}"
            )
        payload = artifacts.archive_role(worktree.path, role)
        if payload is None:
            payload = artifacts.read_json(f"out/{role}.json")
        if payload is None:
            payload = result.json_output()
            if payload is not None:
                artifacts.write_json(f"out/{role}.json", payload)
        if payload is None:
            raise AgentProtocolError(f"{role} did not produce a JSON artifact")
        artifacts.append_event("agent_finished", role=role, round=round_no)
        return payload

    def _record_agent(
        self,
        role: str,
        round_no: int,
        result: AgentResult,
        artifacts: RunArtifacts,
        task: Task,
    ) -> None:
        artifacts.write_text(f"logs/{role}-r{round_no}.stdout.log", result.stdout)
        artifacts.write_text(f"logs/{role}-r{round_no}.stderr.log", result.stderr)
        artifacts.add_cost(role, result.cost_usd, result.tokens)
        if self.budget is not None:
            self.budget.add(result.cost_usd)
            if self.budget.spent > self.budget.daily_usd:
                raise RuntimeError("daily development budget exhausted")
        total = float(artifacts.cost().get("total_usd", 0.0))
        if total > task.limits.max_usd:
            raise RuntimeError(
                f"per-task budget exhausted: ${total:.2f} > ${task.limits.max_usd:.2f}"
            )
        artifacts.append_event(
            "agent_call",
            role=role,
            round=round_no,
            exit_code=result.exit_code,
            duration_s=result.duration_s,
            cost_usd=result.cost_usd,
            tokens=result.tokens,
        )

    def _run_implementer(
        self,
        worktree: Worktree,
        task: Task,
        artifacts: RunArtifacts,
        round_no: int,
        findings: list[dict],
    ) -> dict:
        findings_path = worktree.path / ".dev" / "findings.json"
        findings_path.write_text(json.dumps(findings, indent=2))
        packet = (
            f"# Implementation round {round_no}\n\n"
            f"Task: {task.id} — {task.title}\n\n"
            f"Goal:\n{task.goal}\n\n"
            "Acceptance commands:\n"
            + "\n".join(f"- `{cmd}`" for cmd in task.acceptance)
            + "\n\nScope allow: "
            + ", ".join(task.scope.allow)
            + "\nScope deny: "
            + (", ".join(task.scope.deny) or "(none)")
            + "\n\n"
            "Read `.dev/task.yaml`, `.dev/packet.md`, and `.dev/findings.json`. "
            "Apply the smallest patch. Do not touch protected paths."
        )
        self._write_packet(worktree, task, packet, round_no=round_no)
        (worktree.path / ".dev" / "findings.json").write_text(
            json.dumps(findings, indent=2)
        )
        return self._agent(
            "implementer", worktree, task, artifacts, packet, round_no=round_no
        )

    def _run_reviewer(
        self,
        worktree: Worktree,
        task: Task,
        artifacts: RunArtifacts,
        round_no: int,
        *,
        alt: bool = False,
    ) -> dict:
        role = "reviewer_alt" if alt else "reviewer"
        self._prepare_review(worktree, task, artifacts)
        packet = (
            f"# Blind review, round {round_no}\n\n"
            f"Task: {task.id} — {task.title}\n\n"
            "You did not write this patch. Review the diff against the task "
            "acceptance criteria and the test evidence. Return typed findings. "
            "Do not edit source."
        )
        self._write_packet(worktree, task, packet, round_no=round_no)
        self._prepare_review(worktree, task, artifacts)
        payload = self._agent(role, worktree, task, artifacts, packet, round_no=round_no)
        verdict = payload.get("verdict")
        if verdict not in {"approve", "changes_requested"}:
            raise AgentProtocolError(f"{role} returned invalid verdict: {verdict!r}")
        return payload

    def _run_verifier(
        self,
        worktree: Worktree,
        task: Task,
        artifacts: RunArtifacts,
        round_no: int,
    ) -> dict:
        verify = self._prepare_verification(
            worktree, task, artifacts, worktree.commit_sha()
        )
        packet = (
            f"# Independent verification, round {round_no}\n\n"
            f"Task: {task.id} — {task.title}\n\n"
            "The patch is already applied to this clean worktree. Run the "
            "acceptance commands and try to falsify the change. Do not edit "
            "source or tests."
        )
        self._write_packet(verify, task, packet, round_no=round_no)
        try:
            payload = self._agent(
                "verifier", verify, task, artifacts, packet, round_no=round_no
            )
        finally:
            verify.remove(delete_branch=True)
        verdict = payload.get("verdict")
        if verdict not in {"pass", "fail"}:
            raise AgentProtocolError(f"verifier returned invalid verdict: {verdict!r}")
        return payload

    def _run_science_guard(
        self,
        worktree: Worktree,
        task: Task,
        artifacts: RunArtifacts,
        round_no: int,
    ) -> dict:
        packet = (
            f"# Scientific integrity review, round {round_no}\n\n"
            f"Task: {task.id} — {task.title}\n\n"
            "Check protected paths and the scientific contract. A protected "
            "path or any weakening of the validation/lockbox/registry rules is "
            "a block."
        )
        self._write_packet(worktree, task, packet, round_no=round_no)
        payload = self._agent(
            "science_guard", worktree, task, artifacts, packet, round_no=round_no
        )
        if payload.get("verdict") not in {"clear", "block"}:
            raise AgentProtocolError("science guard returned invalid verdict")
        return payload

    # -- main loop ---------------------------------------------------------
    def _execute(self, task: Task, artifacts: RunArtifacts) -> Outcome:
        started = time.time()
        worktree = Worktree.create(self.repo, task.id, base=self.base)
        artifacts.update_state(
            worktree=str(worktree.path),
            branch=worktree.branch,
            base=worktree.base,
            status="active",
            started_at=utcnow(),
        )
        artifacts.append_event(
            "worktree_created", path=str(worktree.path), branch=worktree.branch
        )
        self._write_task(worktree, task)
        self._write_packet(
            worktree,
            task,
            f"# Task {task.id}\n\n{task.goal}\n\nAcceptance:\n"
            + "\n".join(f"- `{c}`" for c in task.acceptance),
        )

        try:
            lead = self._agent(
                "lead",
                worktree,
                task,
                artifacts,
                "Produce a short plan for this task. Do not edit code.",
            )
            if lead.get("escalate"):
                outcome = Outcome(
                    task_id=task.id,
                    status="escalated",
                    decision={
                        "reason": lead.get("reason") or "lead escalated the task",
                        "risk": task.risk,
                    },
                    run_dir=artifacts.run_dir,
                    worktree=worktree.path,
                    branch=worktree.branch,
                )
                return self._escalate(
                    task, artifacts, outcome, outcome.decision["reason"]
                )

            if task.risk >= 2:
                architect = self._agent(
                    "architect",
                    worktree,
                    task,
                    artifacts,
                    "Produce the design and test plan. Do not edit code.",
                )
                artifacts.write_json("out/architect.json", architect)

            findings: list[dict] = []
            reviews: list[dict] = []
            verifier: dict | None = None
            gate_report: GateReport | None = None
            commit: str | None = None
            last_failure = ""
            max_rounds = min(
                task.limits.max_review_rounds,
                self.policy.budget.max_review_rounds,
            )
            round_no = 0
            for round_no in range(1, max_rounds + 1):
                artifacts.append_event("round_started", round=round_no)
                self._run_implementer(worktree, task, artifacts, round_no, findings)
                commit = worktree.commit_all(
                    f"dev({task.id}): round {round_no} implementation"
                )
                if not commit:
                    findings = [
                        {
                            "severity": "blocker",
                            "issue": "implementer produced no changes",
                            "suggestion": "make the smallest change that satisfies the task",
                        }
                    ]
                    reason = "implementer produced no changes"
                    if last_failure:
                        reason += f"; previous failure: {last_failure}"
                    if round_no >= max_rounds:
                        return self._escalate(
                            task,
                            artifacts,
                            Outcome(
                                task_id=task.id,
                                status="escalated",
                                decision={"reason": reason},
                                run_dir=artifacts.run_dir,
                                worktree=worktree.path,
                                branch=worktree.branch,
                            ),
                            reason,
                        )
                    continue

                artifacts.write_text(
                    "patch.diff", worktree.diff(worktree.base)
                )
                artifacts.update_state(round=round_no, commit=commit)
                gate_report = GateRunner(
                    self.repo, task, worktree, artifacts, self.policy
                ).run_pre()
                artifacts.write_json("gates-pre.json", gate_report.as_dict())
                if gate_report.human_required:
                    reason = "gate requires human review: " + ", ".join(
                        g.name for g in gate_report.human_required
                    )
                    return self._escalate(
                        task,
                        artifacts,
                        Outcome(
                            task_id=task.id,
                            status="escalated",
                            decision={"reason": reason},
                            run_dir=artifacts.run_dir,
                            worktree=worktree.path,
                            branch=worktree.branch,
                        ),
                        reason,
                    )
                if gate_report.blocking_failures:
                    findings = _gate_findings(gate_report)
                    last_failure = "pre gates failed: " + ", ".join(
                        g.name for g in gate_report.blocking_failures
                    )
                    artifacts.write_json("findings.json", findings)
                    if round_no >= max_rounds:
                        return self._escalate(
                            task,
                            artifacts,
                            Outcome(
                                task_id=task.id,
                                status="escalated",
                                decision={"reason": "gates did not pass", "findings": findings},
                                run_dir=artifacts.run_dir,
                                worktree=worktree.path,
                                branch=worktree.branch,
                            ),
                            "gates did not pass after the review budget",
                        )
                    continue

                required_reviews = self.policy.auto_merge.reviewers.get(task.risk, 1)
                reviews = []
                blocked = False
                for index in range(required_reviews):
                    review = self._run_reviewer(
                        worktree, task, artifacts, round_no, alt=index > 0
                    )
                    reviews.append(review)
                    artifacts.write_json(
                        f"out/review-{round_no}-{index + 1}.json", review
                    )
                    if review.get("verdict") != "approve":
                        findings = _review_findings(review)
                        artifacts.write_json("findings.json", findings)
                        last_failure = "review requested changes"
                        blocked = True
                        break
                if blocked:
                    if round_no >= max_rounds:
                        return self._escalate(
                            task,
                            artifacts,
                            Outcome(
                                task_id=task.id,
                                status="escalated",
                                decision={"reason": "review requested changes", "findings": findings},
                                run_dir=artifacts.run_dir,
                                worktree=worktree.path,
                                branch=worktree.branch,
                                reviews=reviews,
                            ),
                            "review requested changes after the review budget",
                        )
                    continue

                verifier = self._run_verifier(worktree, task, artifacts, round_no)
                artifacts.write_json("out/verifier.json", verifier)
                if verifier.get("verdict") != "pass":
                    findings = _review_findings(verifier)
                    artifacts.write_json("findings.json", findings)
                    last_failure = "verifier rejected the patch"
                    if round_no >= max_rounds:
                        return self._escalate(
                            task,
                            artifacts,
                            Outcome(
                                task_id=task.id,
                                status="escalated",
                                decision={"reason": "verifier rejected the patch", "findings": findings},
                                run_dir=artifacts.run_dir,
                                worktree=worktree.path,
                                branch=worktree.branch,
                                reviews=reviews,
                            ),
                            "verifier rejected the patch after the review budget",
                        )
                    continue

                gate_report = GateRunner(
                    self.repo, task, worktree, artifacts, self.policy
                ).run_post()
                artifacts.write_json("gates-post.json", gate_report.as_dict())
                if gate_report.human_required:
                    reason = "post gate requires human review: " + ", ".join(
                        g.name for g in gate_report.human_required
                    )
                    return self._escalate(
                        task,
                        artifacts,
                        Outcome(
                            task_id=task.id,
                            status="escalated",
                            decision={
                                "reason": reason,
                                "findings": _gate_findings(gate_report),
                            },
                            run_dir=artifacts.run_dir,
                            worktree=worktree.path,
                            branch=worktree.branch,
                            reviews=reviews,
                        ),
                        reason,
                    )
                if gate_report.blocking_failures:
                    findings = _gate_findings(gate_report)
                    last_failure = "post gates failed: " + ", ".join(
                        g.name for g in gate_report.blocking_failures
                    )
                    artifacts.write_json("findings.json", findings)
                    if round_no >= max_rounds:
                        return self._escalate(
                            task,
                            artifacts,
                            Outcome(
                                task_id=task.id,
                                status="escalated",
                                decision={"reason": "post gates did not pass", "findings": findings},
                                run_dir=artifacts.run_dir,
                                worktree=worktree.path,
                                branch=worktree.branch,
                                reviews=reviews,
                            ),
                            "post gates did not pass after the review budget",
                        )
                    continue

                if task.risk >= 2:
                    guard = self._run_science_guard(
                        worktree, task, artifacts, round_no
                    )
                    artifacts.write_json("out/science_guard.json", guard)
                    if guard.get("verdict") != "clear":
                        return self._escalate(
                            task,
                            artifacts,
                            Outcome(
                                task_id=task.id,
                                status="escalated",
                                decision={
                                    "reason": "science guard blocked the patch",
                                    "findings": _review_findings(guard),
                                },
                                run_dir=artifacts.run_dir,
                                worktree=worktree.path,
                                branch=worktree.branch,
                                reviews=reviews,
                            ),
                            "science guard blocked the patch",
                        )

                artifacts.append_event(
                    "round_approved", round=round_no, commit=commit
                )
                decision = {
                    "status": "approved",
                    "risk": task.risk,
                    "rounds": round_no,
                    "commit": commit,
                    "branch": worktree.branch,
                    "changed_files": worktree.changed_files(worktree.base),
                    "diff_lines": sum(worktree.diff_numstat(worktree.base)),
                    "reviews": reviews,
                    "verifier": verifier,
                    "science_guard": artifacts.read_json("out/science_guard.json"),
                    "gates": gate_report.as_dict(),
                    "pre_gates": artifacts.read_json("gates-pre.json", {}),
                    "cost_usd": artifacts.cost().get("total_usd", 0.0),
                    "duration_s": round(time.time() - started, 1),
                }
                return Outcome(
                    task_id=task.id,
                    status="approved",
                    decision=decision,
                    run_dir=artifacts.run_dir,
                    worktree=worktree.path,
                    branch=worktree.branch,
                    commit=commit,
                    reviews=reviews,
                    rounds=round_no,
                    cost_usd=float(decision["cost_usd"]),
                )
            raise RuntimeError("pipeline exhausted rounds without a terminal state")
        except Exception:
            artifacts.append_event("worktree_kept_for_debug", path=str(worktree.path))
            raise

    # -- decision / merge --------------------------------------------------
    def _merge_decision(self, outcome: Outcome, task: Task) -> dict:
        decision = outcome.decision
        if task.risk > self.policy.auto_merge.max_risk:
            return {
                "allowed": False,
                "reason": f"risk {task.risk} exceeds auto-merge max "
                f"{self.policy.auto_merge.max_risk}",
            }
        if task.risk == 3:
            return {"allowed": False, "reason": "risk 3 requires human sign-off"}
        if decision.get("human_required"):
            return {"allowed": False, "reason": "a gate requires human review"}
        changed = len(decision.get("changed_files") or [])
        lines = int(decision.get("diff_lines") or 0)
        if task.risk == 2:
            if changed > self.policy.auto_merge.risk_2_max_changed_files:
                return {
                    "allowed": False,
                    "reason": f"risk 2 changed {changed} files; limit is "
                    f"{self.policy.auto_merge.risk_2_max_changed_files}",
                }
            if lines > self.policy.auto_merge.risk_2_max_diff_lines:
                return {
                    "allowed": False,
                    "reason": f"risk 2 changed {lines} lines; limit is "
                    f"{self.policy.auto_merge.risk_2_max_diff_lines}",
                }
        required = self.policy.auto_merge.reviewers.get(task.risk, 1)
        approvals = sum(
            1 for review in outcome.reviews if review.get("verdict") == "approve"
        )
        if approvals < required:
            return {
                "allowed": False,
                "reason": f"{approvals} approve review(s); {required} required",
            }
        if not decision.get("gates", {}).get("auto_merge_ok", True):
            return {"allowed": False, "reason": "gates do not allow auto-merge"}
        return {"allowed": True, "reason": "policy allows auto-merge"}

    def _merge(
        self,
        task: Task,
        artifacts: RunArtifacts,
        outcome: Outcome,
        *,
        merge: bool | None,
    ) -> Outcome:
        if merge is False:
            artifacts.update_state(status="awaiting_merge")
            artifacts.write_json("decision.json", outcome.decision)
            artifacts.append_event("awaiting_merge", commit=outcome.commit)
            outcome.status = "awaiting_merge"
            return outcome

        lock = FileLock(self.repo / "runs" / "dev" / ".merge.lock", stale_seconds=3600)
        if not lock.acquire():
            return self._escalate(
                task, artifacts, outcome, "merge queue is locked by another process"
            )
        try:
            worktree = Worktree(
                repo=self.repo,
                path=Path(outcome.worktree),
                branch=outcome.branch or "",
                base=outcome.decision.get("base", self.base),
                task_id=task.id,
            )
            ok, error = worktree.rebase_onto(self.policy.branch)
            if not ok:
                return self._escalate(
                    task,
                    artifacts,
                    outcome,
                    "rebase conflict: " + error,
                )
            report = GateRunner(
                self.repo, task, worktree, artifacts, self.policy
            ).run_full()
            artifacts.write_json("gates-merge.json", report.as_dict())
            if report.blocking_failures or report.human_required:
                reasons = ", ".join(
                    g.name for g in report.blocking_failures + report.human_required
                )
                return self._escalate(
                    task,
                    artifacts,
                    outcome,
                    "merge gate failed: " + reasons,
                )
            merged = merge_ff(self.repo, worktree.branch, self.policy.branch)
            artifacts.append_event(
                "merged", branch=worktree.branch, commit=merged
            )
            outcome.decision["merged_commit"] = merged
            outcome.decision["merge_status"] = "merged"
            worktree.remove(delete_branch=True)
            outcome.worktree = None
            return self._finish(task, artifacts, "done", outcome.decision, outcome=outcome)
        except GitError as exc:
            return self._escalate(task, artifacts, outcome, f"merge failed: {exc}")
        finally:
            lock.release()

    # -- terminal states ---------------------------------------------------
    def _escalate(
        self,
        task: Task,
        artifacts: RunArtifacts,
        outcome: Outcome,
        reason: str,
    ) -> Outcome:
        outcome.decision["status"] = "escalated"
        outcome.decision["reason"] = reason
        outcome.decision["human_required"] = True
        return self._finish(
            task, artifacts, "escalated", outcome.decision, outcome=outcome
        )

    def _finish(
        self,
        task: Task,
        artifacts: RunArtifacts,
        status: str,
        decision: dict,
        *,
        outcome: Outcome | None = None,
    ) -> Outcome:
        decision = {
            **decision,
            "task_id": task.id,
            "status": status,
            "risk": task.risk,
            "shadow": self.shadow,
            "finished_at": utcnow(),
            "run_dir": str(artifacts.run_dir),
        }
        artifacts.write_json("decision.json", decision)
        artifacts.append_event("task_finished", status=status, decision=decision)
        artifacts.append_index(
            {
                "ts": utcnow(),
                "task_id": task.id,
                "status": status,
                "risk": task.risk,
                "shadow": self.shadow,
                "rounds": outcome.rounds if outcome else 0,
                "cost_usd": outcome.cost_usd if outcome else 0.0,
                "reason": decision.get("reason", ""),
                "merged_commit": decision.get("merged_commit"),
                "run_dir": str(artifacts.run_dir),
            }
        )
        updated = task.model_copy(
            update={
                "status": status,
                "notes": (task.notes + "\n" if task.notes else "")
                + f"{date.today().isoformat()}: {status}: {decision.get('reason', '')}",
            }
        )
        self.store.save(updated, status=status)
        if outcome is None:
            outcome = Outcome(
                task_id=task.id,
                status=status,
                decision=decision,
                run_dir=artifacts.run_dir,
            )
        else:
            outcome.status = status
            outcome.decision = decision
        artifacts.write_json("outcome.json", outcome.as_dict())
        return outcome

    # -- introspection -----------------------------------------------------
    def status(self) -> dict:
        return {
            "repo": str(self.repo),
            "branch": self.base,
            "policy": {
                "max_auto_risk": self.policy.auto_merge.max_risk,
                "protected": self.policy.protected,
            },
            "tasks": {
                "ready": [t.id for t in self.store.ready()],
            },
            "worktrees": [
                worktree_status(p)
                for p in sorted((self.repo / "runs" / "dev" / "worktrees").glob("*"))
                if p.is_dir()
            ],
        }
