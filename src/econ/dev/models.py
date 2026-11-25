from __future__ import annotations

import hashlib
import json
import re
import shlex
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TASK_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]*-\d{3,4}$")
STATUSES = (
    "proposed",
    "ready",
    "active",
    "done",
    "escalated",
    "failed",
    "shadow",
)
STATUS_DIRS = {
    "proposed": "proposed",
    "ready": "ready",
    "active": "active",
    "done": "done",
    "escalated": "escalated",
    "failed": "failed",
    "shadow": "done",
}

# A task acceptance command is data, not a shell program. Refuse anything that
# could chain or redirect commands. This is the main injection barrier for
# tasks imported from GitHub issues.
_SHELL_META = set(";|&><`$(){}\n\r")


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # "bug" marks a bug report contract: risk 0/1 bug tasks must prove the bug
    # with a failing test (reproducer) before any fix is implemented.
    kind: Literal["local", "github", "demo", "canary", "bug"] = "local"
    number: int | None = None
    url: str | None = None
    author: str | None = None


class Scope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allow: list[str] = Field(min_length=1)
    deny: list[str] = Field(default_factory=list)


class Limits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_review_rounds: int = Field(default=2, ge=1, le=5)
    max_usd: float = Field(default=5.0, gt=0)
    max_changed_files: int = Field(default=25, ge=1)
    max_diff_lines: int = Field(default=800, ge=1)
    wall_seconds: int = Field(default=2400, ge=60)


class DemoFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    content: str


class DemoConfig(BaseModel):
    """Deterministic fixture used by the fake runner for smoke and canary runs.

    A real OpenCode runner ignores this block. Keeping it in the task contract
    makes the end-to-end pipeline testable without spending model credits.
    """

    model_config = ConfigDict(extra="forbid")
    base_files: list[DemoFile] = Field(default_factory=list)
    files: list[DemoFile] = Field(default_factory=list)
    review: Literal["approve", "changes_requested"] = "approve"
    second_review: Literal["approve", "changes_requested"] = "approve"
    verifier: Literal["pass", "fail"] = "pass"
    science_guard: Literal["clear", "block"] = "clear"
    fail_first_rounds: int = 0


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str = Field(min_length=1)
    status: Literal[
        "proposed", "ready", "active", "done", "escalated", "failed", "shadow"
    ] = "proposed"
    risk: int = Field(ge=0, le=3)
    priority: int = Field(default=50, ge=0, le=100)
    created: str = Field(default_factory=lambda: date.today().isoformat())
    goal: str = Field(min_length=1)
    acceptance: list[str] = Field(min_length=1)
    scope: Scope
    limits: Limits = Field(default_factory=Limits)
    source: Source = Field(default_factory=Source)
    notes: str = ""
    retries: int = Field(default=0, ge=0)
    demo: DemoConfig | None = None

    @field_validator("id")
    @classmethod
    def _id_format(cls, value: str) -> str:
        if not TASK_ID_RE.match(value):
            raise ValueError("task id must look like DEV-0001")
        return value

    @field_validator("created", mode="before")
    @classmethod
    def _created_date(cls, value) -> str:
        if isinstance(value, date):
            return value.isoformat()
        date.fromisoformat(str(value))
        return str(value)

    @field_validator("acceptance")
    @classmethod
    def _commands_are_safe(cls, values: list[str]) -> list[str]:
        for command in values:
            if not command.strip():
                raise ValueError("acceptance command cannot be empty")
            if any(ch in command for ch in _SHELL_META):
                raise ValueError(
                    f"acceptance command contains shell metacharacters: {command!r}"
                )
            try:
                argv = shlex.split(command)
            except ValueError as exc:
                raise ValueError(f"cannot parse acceptance command: {command!r}") from exc
            if not argv:
                raise ValueError("acceptance command cannot be empty")
        return values

    @field_validator("scope")
    @classmethod
    def _scope_not_unbounded(cls, value: Scope) -> Scope:
        if any(pattern in {"*", "**", "/"} for pattern in value.allow):
            raise ValueError("scope.allow cannot be unbounded; name the paths")
        return value

    @model_validator(mode="after")
    def _risk_matches_scope(self) -> Task:
        if self.risk < 3:
            from .policy import DEFAULT_PROTECTED

            overlap = [
                rule
                for rule in DEFAULT_PROTECTED
                if any(_patterns_touch(p, rule) for p in self.scope.allow)
            ]
            if overlap:
                raise ValueError(
                    "scope.allow overlaps protected paths; use risk 3: "
                    + ", ".join(sorted(overlap))
                )
        return self

    def canonical(self) -> dict:
        return self.model_dump(mode="json", exclude_none=True)

    def sha256(self) -> str:
        blob = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()


def _patterns_touch(left: str, right: str) -> bool:
    """Conservative glob overlap used for task validation and path claims."""
    from .paths import overlap

    return overlap(left, right)


class TaskValidationError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


def limit_warnings(task: Task, policy=None) -> list[str]:
    """Non-fatal contract-calibration warnings.

    The size cap is a hard gate. A risk-2 task whose cap sits below the policy
    auto-merge cap has little room for a review fix, and a `scope.allow` count
    equal to `max_changed_files` leaves no room for an extra fixture file.
    These are warnings, not validation failures: a deliberately small task may
    still choose a tight budget.
    """
    if policy is None:
        return []
    warnings: list[str] = []
    if (
        task.risk == 2
        and task.limits.max_diff_lines
        < policy.auto_merge.risk_2_max_diff_lines
    ):
        warnings.append(
            f"{task.id}: max_diff_lines={task.limits.max_diff_lines} is below "
            f"the risk-2 auto-merge cap "
            f"{policy.auto_merge.risk_2_max_diff_lines}; a review fix can "
            "exhaust the line budget. Add headroom or split the task."
        )
    if len(task.scope.allow) >= task.limits.max_changed_files:
        warnings.append(
            f"{task.id}: max_changed_files={task.limits.max_changed_files} has "
            f"no headroom over {len(task.scope.allow)} scope.allow entry(s)."
        )
    return warnings


def validate_task(task: Task, policy=None) -> list[str]:
    problems: list[str] = []
    if task.status == "active" and task.retries < 0:
        problems.append("retries cannot be negative")
    if task.limits.max_usd > 1000:
        problems.append("per-task budget is unreasonably large")
    if task.source.kind == "github" and not task.source.number:
        problems.append("github-sourced tasks need source.number")
    if task.risk >= 3 and task.demo is not None:
        problems.append("risk 3 tasks cannot use the fake demo runner")
    if policy is not None:
        from .paths import overlap

        hits = sorted(
            {
                rule
                for rule in policy.protected
                for pattern in task.scope.allow
                if overlap(pattern, rule)
            }
        )
        if hits and task.risk < 3:
            problems.append(
                "task touches protected paths without risk 3: " + ", ".join(hits)
            )
    return problems
