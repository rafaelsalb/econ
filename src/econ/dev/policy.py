from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AutoMergeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_risk: int = Field(default=2, ge=0, le=2)
    risk_2_max_changed_files: int = 12
    risk_2_max_diff_lines: int = 400
    reviewers: dict[int, int] = Field(default_factory=lambda: {0: 1, 1: 1, 2: 2})
    second_reviewer_model: str = "opencode-go/kimi-k3"
    risk_3: str = "human"


class BudgetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    daily_usd: float = 20.0
    per_task_usd: float = 5.0
    max_review_rounds: int = 2
    max_agent_steps: int = 24
    max_wall_seconds: int = 2400


class GatesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    python: str = ".venv/bin/python"
    full_tests: bool = True
    risk0_skip_full_tests: bool = True
    full_test_command: str = "python -m pytest -q"
    check_command: str | None = "python -m econ.cli check"
    agents_check_command: str | None = "python -m econ.cli agents check"
    dev_validate_command: str | None = "python -m econ.cli dev validate --all"
    timeout_s: int = 900
    require_tests_for_risk: int = 1
    red_green: bool = True
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
    "src/econ/evaluate.py",
    "src/econ/critics.py",
    "src/econ/diagnostics.py",
    "src/econ/loop.py",
    "src/econ/lockbox.py",
    "src/econ/vintage.py",
    "src/econ/checks.py",
    "sandbox/**",
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


def is_protected(path: str, protected: list[str]) -> bool:
    from .paths import matches_any

    return matches_any(path, protected)


def protected_hits(paths: list[str], protected: list[str]) -> list[str]:
    return sorted({path for path in paths if is_protected(path, protected)})


def _compile(pattern: str) -> re.Pattern[str]:
    # Re-exported for callers that only import policy.
    from .paths import compile_glob

    return compile_glob(pattern)
