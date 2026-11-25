from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AutoMergeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_risk: int = Field(default=2, ge=0, le=2)
    risk_2_max_changed_files: int = 12
    risk_2_max_diff_lines: int = 400
    # Reviewers are a risk-2 control. Risk 0/1 merges on gates plus the blind
    # clean-tree verifier; buying an LLM review for a one-file patch is
    # ceremony. Unknown tiers fail safe to one review.
    reviewers: dict[int, int] = Field(default_factory=lambda: {0: 0, 1: 0, 2: 2})
    # Must stay a different model family from the roster's first reviewer, and
    # in sync with config/dev_agents.yaml's reviewer_alt entry. The runtime is
    # part of the identity: the same model string can mean different things to
    # OpenCode and Claude.
    second_reviewer_runtime: str = "opencode"
    second_reviewer_model: str = "opencode-go/gpt-6-luna"
    risk_3: str = "human"
    # Merge-critical paths: a diff that touches one forces human sign-off at
    # merge time even when the task tier would allow auto-merge. Blast radius
    # beats diff size — five lines in the referee are riskier than five
    # hundred in a pad file. Defense in depth under the protected set, and
    # extensible to paths the owner deliberately left unprotected.
    critical_paths: list[str] = Field(
        default_factory=lambda: [
            "src/econ/dev/**",
            ".github/workflows/**",
            "tests/dev_support.py",
            "tasks/templates/task.yaml",
            "dev/evals/canary/**",
        ]
    )


class BudgetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    daily_usd: float = 20.0
    per_task_usd: float = 5.0
    max_review_rounds: int = 2
    # Extra implementation attempts that do not consume a review round. A
    # pre-gate failure is a mechanical repair, not a review: without this a
    # size-cap overrun on the last round escalates before the second review.
    max_repair_rounds: int = Field(default=1, ge=0, le=3)
    max_agent_steps: int = 60
    max_wall_seconds: int = 2400


class GatesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    python: str = ".venv/bin/python"
    full_tests: bool = True
    risk0_skip_full_tests: bool = True
    full_test_command: str = "python -m pytest -q"
    check_command: str | None = "python -m econ.cli check"
    agents_check_command: str | None = "python -m econ.cli agents check"
    dev_agents_check_command: str | None = "python -m econ.cli dev agents check"
    dev_validate_command: str | None = "python -m econ.cli dev validate --all"
    timeout_s: int = 900
    require_tests_for_risk: int = 1
    red_green: bool = True
    # Coverage delta gate (pytest-cov). Risk 2 only: it guards the auto-merge
    # decision that the size caps used to carry alone.
    coverage_delta: bool = True
    coverage_test_command: str = "python -m pytest -q --cov=src"
    max_changed_files: int = 25
    max_diff_lines: int = 800
    dependency_files: list[str] = Field(
        default_factory=lambda: [
            "pyproject.toml",
            "uv.lock",
            "requirements.txt",
            "requirements-dev.txt",
        ]
    )
    secret_patterns: list[str] = Field(
        default_factory=lambda: [
            r"sk-[A-Za-z0-9]{16,}",
            r"gh[pousr]_[A-Za-z0-9]{16,}",
            r"-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----",
            r"OPENCODE_API_KEY\s*=\s*\S+",
            r"ANTHROPIC_API_KEY\s*=\s*\S+",
            r"CLAUDE_CODE_OAUTH_TOKEN\s*=\s*\S+",
            r"sk-ant-[A-Za-z0-9_-]{16,}",
        ]
    )


class GitHubConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = "dev:ready"
    auto_promote: bool = False
    trusted_authors: list[str] = Field(default_factory=list)
    comment: bool = True


class ExecutorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default: str = "local"
    docker_image: str = "econ-agent:latest"
    network: str = "econ-internal"
    cpus: float = 2
    memory: str = "4g"
    pids: int = 256
    timeout_s: int = 1200
    user: str = "1000:1000"


DEFAULT_PROTECTED: tuple[str, ...] = (
    "specs/**",
    "data/**",
    "registry/**",
    "eval/**",
    "reports/final_report.md",
    "reports/lockbox_report.md",
    "config/dev_policy.yaml",
    "config/dev_agents.yaml",
    # Agent permission/config files are part of the sandbox boundary.
    ".claude/**",
    ".mcp.json",
    "src/econ/evaluate.py",
    "src/econ/critics.py",
    "src/econ/diagnostics.py",
    "src/econ/loop.py",
    "src/econ/lockbox.py",
    "src/econ/vintage.py",
    "src/econ/checks.py",
    "sandbox/**",
    # The merge authority and its calibration suite: the controller itself, the
    # CI that independently verifies auto-merges, the shared gate-test harness,
    # the task-contract template, and the canaries that calibrate the pipeline.
    # Keep this tuple in sync with the protected list in config/dev_policy.yaml;
    # tests/test_dev_policy.py fails on drift.
    "src/econ/dev/**",
    ".github/workflows/**",
    "tests/dev_support.py",
    "tasks/templates/task.yaml",
    "dev/evals/canary/**",
)


class DevPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 1
    branch: str = "main"
    protected: list[str] = Field(default_factory=lambda: list(DEFAULT_PROTECTED))
    auto_merge: AutoMergeConfig = Field(default_factory=AutoMergeConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    gates: GatesConfig = Field(default_factory=GatesConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    executor: ExecutorConfig = Field(default_factory=ExecutorConfig)


def policy_path(root: Path) -> Path:
    return root / "config" / "dev_policy.yaml"


def load_policy(root: Path) -> DevPolicy:
    import yaml

    path = policy_path(root)
    if not path.exists():
        return DevPolicy()
    raw = yaml.safe_load(path.read_text()) or {}
    return DevPolicy.model_validate(raw)


def reviewer_model_problems(cfg: dict, policy: DevPolicy) -> list[str]:
    """Cross-file checks for the reviewer pin.

    Model choice itself is configuration (config/dev_agents.yaml); these are
    the two relationships that must hold or the risk-2 review is not what the
    policy claims: the policy pin must match reviewer_alt, and reviewer_alt
    must be a different model family from reviewer.
    """
    defaults = cfg.get("defaults") or {}
    agents = cfg.get("agents") or {}
    default_model = defaults.get("model")
    default_runtime = defaults.get("runtime", "opencode")

    def identity_of(name: str) -> tuple[str, str | None]:
        raw = agents.get(name) or {}
        runtime = raw.get("runtime", default_runtime)
        if runtime == "claude":
            return runtime, raw.get("claude_model", defaults.get("claude_model"))
        return runtime, raw.get("model", default_model)

    reviewer = identity_of("reviewer")
    alt = identity_of("reviewer_alt")
    pinned = (
        policy.auto_merge.second_reviewer_runtime,
        policy.auto_merge.second_reviewer_model,
    )
    problems: list[str] = []
    if not alt[1]:
        problems.append("reviewer_alt is missing from config/dev_agents.yaml")
    elif pinned != alt:
        problems.append(
            "config/dev_policy.yaml auto_merge.second_reviewer_model "
            f"({pinned[0]}:{pinned[1]}) does not match reviewer_alt "
            f"({alt[0]}:{alt[1]}); also check second_reviewer_runtime"
        )
    if reviewer[1] and alt[1] and reviewer == alt:
        problems.append(
            "reviewer_alt must use a different runtime/model than reviewer "
            f"(both are {alt[0]}:{alt[1]})"
        )
    return problems


def is_protected(path: str, protected: list[str]) -> bool:
    from .paths import matches_any

    return matches_any(path, protected)


def protected_hits(paths: list[str], protected: list[str]) -> list[str]:
    return sorted({path for path in paths if is_protected(path, protected)})


def _compile(pattern: str) -> re.Pattern[str]:
    # Re-exported for callers that only import policy.
    from .paths import compile_glob

    return compile_glob(pattern)
