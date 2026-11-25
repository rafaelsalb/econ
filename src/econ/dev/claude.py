from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from .. import agents as agent_config
from ..claude_cli import (
    ClaudeProtocolError,
    PermissionMappingError,
    claude_command,
    parse_claude_result,
    permission_policy,
)
from .artifacts import write_json
from .runner import AgentResult
from .workspace import command_env


class ClaudeRunner:
    """Run one development role through the Claude Code CLI.

    The controller is the only producer of the effective policy. Project
    settings, user settings, MCP servers, skills, and hooks are intentionally
    ignored by `--restricted`; the generated settings file under `.dev/` is the
    whole permission surface for the call.
    """

    def __init__(
        self,
        repo: Path,
        specs: dict[str, agent_config.AgentSpec] | None = None,
        *,
        cfg: dict | None = None,
        executable: str = "claude",
        extra_env: dict[str, str] | None = None,
    ):
        self.repo = repo
        self.cfg = cfg or agent_config.load_dev_config()
        if specs is None:
            specs = {
                spec.name: spec
                for spec in agent_config.dev_agents(self.cfg, root=repo)
            }
        elif not isinstance(specs, dict):
            specs = {spec.name: spec for spec in specs}
        self.specs = specs
        self.executable = executable
        self.extra_env = extra_env or {}

    def policy(self, role: str, cwd: Path) -> dict:
        spec = self.specs.get(role)
        if spec is None:
            raise KeyError(f"unknown dev agent role: {role}")
        if spec.runtime != "claude":
            raise ValueError(
                f"{role}: runtime is {spec.runtime!r}, not claude; use the routed runner"
            )
        perms = agent_config.agent_permissions(self.cfg, role)
        if perms.get("question") == "allow":
            raise PermissionMappingError(
                f"{role}: the Claude runner is headless and cannot use the "
                "question tool; keep this role on OpenCode"
            )
        return permission_policy(
            edit=perms["edit"],
            shell=perms["shell"],
            deny=perms["deny"],
            root=cwd.resolve(),
            read=perms["read"],
        )

    def settings_path(self, role: str, cwd: Path) -> Path:
        return cwd / ".dev" / "claude" / f"{role}-settings.json"

    def prepare(
        self,
        role: str,
        cwd: Path,
        prompt: str,
        *,
        model_override: str | None = None,
        max_budget_usd: float | None = None,
        settings_path: Path | None = None,
    ) -> tuple[list[str], dict, Path]:
        spec = self.specs.get(role)
        if spec is None:
            raise KeyError(f"unknown dev agent role: {role}")
        policy = self.policy(role, cwd)
        settings_path = settings_path or self.settings_path(role, cwd)
        system_prompt = spec.prompt_path.read_text().strip()
        argv = claude_command(
            spec,
            system_prompt,
            prompt,
            settings_path,
            cwd=cwd,
            model_override=model_override,
            max_budget_usd=max_budget_usd,
            policy=policy,
        )
        # The CLI name is injectable for tests and for a non-PATH install.
        argv[0] = self.executable
        return argv, policy, settings_path

    def command(
        self,
        role: str,
        cwd: Path,
        prompt: str,
        *,
        model_override: str | None = None,
        max_budget_usd: float | None = None,
    ) -> list[str]:
        argv, _, _ = self.prepare(
            role,
            cwd,
            prompt,
            model_override=model_override,
            max_budget_usd=max_budget_usd,
        )
        return argv

    def _env(self, cwd: Path) -> dict[str, str]:
        env = command_env(self.repo, cwd)
        # subprocess.run(cwd=...) does not update PWD. Claude Code's project
        # discovery consults the inherited PWD, exactly like OpenCode.
        env["PWD"] = str(cwd.resolve())
        env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
        env.setdefault("DISABLE_AUTOUPDATER", "1")
        env.update(self.extra_env)
        return env

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
        # The settings file is deliberately outside the worktree. If it lived
        # under `.dev/`, an implementer with edit rights there could rewrite
        # its own permission policy mid-session; Claude reloads settings.
        with tempfile.TemporaryDirectory(prefix="econ-claude-") as tmp:
            settings_path = Path(tmp) / "settings.json"
            argv, policy, settings_path = self.prepare(
                role,
                cwd,
                prompt,
                model_override=model_override,
                max_budget_usd=max_budget_usd,
                settings_path=settings_path,
            )
            write_json(settings_path, policy["settings"])
            return self._run_with_settings(
                role,
                cwd,
                argv,
                policy,
                settings_path,
                timeout=timeout,
            )

    def _run_with_settings(
        self,
        role: str,
        cwd: Path,
        argv: list[str],
        policy: dict,
        settings_path: Path,
        *,
        timeout: int,
    ) -> AgentResult:
        env = self._env(cwd)
        start = time.time()
        timed_out = False
        out = ""
        err = ""
        code = 1
        try:
            proc = subprocess.Popen(
                argv,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                start_new_session=True,
            )
        except FileNotFoundError:
            return AgentResult(
                role=role,
                command=argv,
                exit_code=127,
                duration_s=0.0,
                timed_out=False,
                text="",
                stdout="",
                stderr=f"claude executable not found: {self.executable}",
                error=f"claude executable not found: {self.executable}",
                request={
                    "runner": "claude",
                    "model": getattr(self.specs.get(role), "claude_model", None),
                    "settings": policy["settings"],
                },
            )
        try:
            out, err = proc.communicate(timeout=timeout)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            out, err = proc.communicate()
            code = 124
        duration = time.time() - start
        request = {
            "runner": "claude",
            "model": getattr(self.specs.get(role), "claude_model", None),
            "effort": getattr(self.specs.get(role), "claude_effort", None),
            "settings_path": str(settings_path),
            "settings": policy["settings"],
            "argv": argv,
        }
        try:
            parsed = parse_claude_result(out)
        except ClaudeProtocolError as exc:
            return AgentResult(
                role=role,
                command=argv,
                exit_code=code if code != 0 else 1,
                duration_s=round(duration, 3),
                timed_out=timed_out,
                text=out,
                stdout=out,
                stderr=err,
                error=str(exc),
                request=request,
            )
        error = ""
        if parsed.is_error or parsed.subtype not in {None, "success"}:
            error = f"claude subtype={parsed.subtype or 'error'} is_error={parsed.is_error}"
            if parsed.denials:
                error += f"; permission_denials={len(parsed.denials)}"
            if code == 0:
                code = 1
        return AgentResult(
            role=role,
            command=argv,
            exit_code=code,
            duration_s=round(duration, 3),
            timed_out=timed_out,
            text=parsed.text,
            stdout=out,
            stderr=err,
            cost_usd=parsed.cost_usd,
            tokens=parsed.tokens,
            steps=parsed.steps,
            error=error,
            denials=parsed.denials,
            request=request,
        )
