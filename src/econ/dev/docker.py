from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from .. import agents as agent_config
from .. import claude_cli
from .policy import DevPolicy
from .runner import AgentResult, parse_opencode_events
from .workspace import command_env


class DockerRunError(RuntimeError):
    pass


def docker_available(executable: str = "docker") -> bool:
    try:
        return (
            subprocess.run(
                [executable, "info"], capture_output=True, timeout=8, check=False
            ).returncode
            == 0
        )
    except Exception:  # noqa: BLE001
        return False


class DockerRunner:
    """Run a dev agent inside the hardened agent image.

    The worktree is the only writable bind mount. The repository's rendered
    agents, OpenCode config, and binary are read-only. The container has no
    Docker socket, drops all capabilities, and uses the internal network with
    the CONNECT proxy for model access.
    """

    def __init__(
        self,
        repo: Path,
        policy: DevPolicy,
        *,
        image: str | None = None,
        network: str | None = None,
        executable: str = "docker",
        specs: dict[str, agent_config.AgentSpec] | None = None,
        cfg: dict | None = None,
        forced_runtime: str | None = None,
        claude_bin: Path | None = None,
        claude_auth: Path | None = None,
    ):
        self.repo = repo.resolve()
        self.policy = policy
        self.image = image or policy.executor.docker_image
        self.network = network or policy.executor.network
        self.executable = executable
        self.cfg = cfg or agent_config.load_dev_config()
        if specs is None:
            specs = {
                spec.name: spec
                for spec in agent_config.dev_agents(self.cfg, root=self.repo)
            }
        elif not isinstance(specs, dict):
            specs = {spec.name: spec for spec in specs}
        if forced_runtime:
            from dataclasses import replace

            specs = {
                name: replace(spec, runtime=forced_runtime)
                for name, spec in specs.items()
            }
        self.specs = specs
        self.forced_runtime = forced_runtime
        self.opencode_bin = Path.home() / ".opencode" / "bin" / "opencode"
        self.auth_file = Path.home() / ".local" / "share" / "opencode" / "auth.json"
        self.claude_bin = claude_bin or (
            Path(shutil.which("claude")) if shutil.which("claude") else None
        )
        self.claude_auth = claude_auth or (Path.home() / ".claude" / ".credentials.json")

    def _proxy_env(self) -> dict[str, str]:
        if self.network in {"none", "host"}:
            return {}
        proxy = "http://econ-proxy:3128"
        return {
            "HTTP_PROXY": proxy,
            "HTTPS_PROXY": proxy,
            "http_proxy": proxy,
            "https_proxy": proxy,
            "NO_PROXY": "127.0.0.1,localhost",
        }

    def _runtime(self, role: str) -> str:
        spec = self.specs.get(role)
        if spec is None:
            raise KeyError(f"unknown dev agent role: {role}")
        return self.forced_runtime or spec.runtime

    def _claude_inner(
        self,
        role: str,
        worktree: Path,
        prompt: str,
        model_override: str | None,
        max_budget_usd: float | None,
        *,
        settings_dir: Path | None,
        settings_container: str,
    ) -> list[str]:
        spec = self.specs[role]
        perms = agent_config.agent_permissions(self.cfg, role)
        if perms.get("question") == "allow":
            raise DockerRunError(
                f"{role}: the Claude runner is headless and cannot use the "
                "question tool"
            )
        translated = claude_cli.permission_policy(
            edit=perms["edit"],
            shell=perms["shell"],
            deny=perms["deny"],
            root="/workspace",
            read=perms["read"],
        )
        settings_host = settings_dir / f"{role}-settings.json"
        settings_host.parent.mkdir(parents=True, exist_ok=True)
        settings_host.write_text(json.dumps(translated["settings"], indent=2))
        return claude_cli.claude_command(
            spec,
            spec.prompt_path.read_text().strip(),
            prompt,
            Path(settings_container) / f"{role}-settings.json",
            cwd="/workspace",
            model_override=model_override,
            max_budget_usd=max_budget_usd,
            policy=translated,
        )

    def command(
        self,
        role: str,
        worktree: Path,
        prompt: str,
        model_override: str | None = None,
        max_budget_usd: float | None = None,
        *,
        settings_dir: Path | None = None,
    ) -> list[str]:
        spec = self.specs.get(role)
        if spec is None:
            raise KeyError(f"unknown dev agent role: {role}")
        runtime = self._runtime(role)
        settings_mount = None
        if runtime == "claude":
            if settings_dir is None:
                settings_dir = worktree / ".dev" / "claude"
                settings_container = "/workspace/.dev/claude"
            else:
                settings_container = "/run/econ-claude"
            inner = self._claude_inner(
                role,
                worktree,
                prompt,
                model_override,
                max_budget_usd,
                settings_dir=settings_dir,
                settings_container=settings_container,
            )
            settings_mount = f"{settings_dir}:{settings_container}:ro"
        elif runtime == "opencode":
            model = model_override or spec.selector
            inner = [
                "opencode",
                "run",
                "--standalone",
                "--agent",
                spec.agent_id,
                "--model",
                model,
                "--format",
                "json",
                "--archived",
                "--auto",
                prompt,
            ]
        else:
            raise DockerRunError(f"unknown runtime: {runtime}")

        name = f"econ-dev-{role}-{uuid.uuid4().hex[:8]}"[:63]
        cmd = [
            self.executable,
            "run",
            "--rm",
            "--init",
            "--name",
            name,
            "--user",
            self.policy.executor.user,
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=256m",
            "--cap-drop=ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            str(self.policy.executor.pids),
            "--memory",
            self.policy.executor.memory,
            "--cpus",
            str(self.policy.executor.cpus),
            "--network",
            self.network,
            "--workdir",
            "/workspace",
            "-v",
            f"{worktree}:/workspace:rw",
        ]
        home = worktree / ".dev" / "home"
        for relative in (
            ".",
            ".local/share/opencode",
            ".config/opencode",
            ".cache",
            ".claude",
        ):
            (home / relative).mkdir(parents=True, exist_ok=True)
        cmd += ["-v", f"{home}:/home/econ:rw"]
        if settings_mount:
            # The settings file is the permission boundary. Mount it read-only
            # even when it lives under the writable worktree mount.
            cmd += ["-v", settings_mount]
        # A linked worktree's `.git` file points at the main checkout's
        # `.git/worktrees/<id>`, and that metadata points back at the host
        # worktree path. Mount both at their host paths so git inside the
        # container can resolve the linked-worktree graph.
        git_marker = worktree / ".git"
        if git_marker.is_file():
            main_git = (self.repo / ".git").resolve()
            cmd += ["-v", f"{main_git}:{main_git}:rw"]
            cmd += ["-v", f"{worktree}:{worktree}:rw"]
        if runtime == "opencode":
            # The worktree already contains the committed opencode.jsonc and
            # .opencode/agents for its base commit.
            if self.opencode_bin.exists():
                cmd += ["-v", f"{self.opencode_bin}:/usr/local/bin/opencode:ro"]
            if self.auth_file.exists() and "OPENCODE_API_KEY" not in os.environ:
                cmd += [
                    "-v",
                    f"{self.auth_file}:/home/econ/.local/share/opencode/auth.json:ro",
                ]
        else:
            if self.claude_bin and self.claude_bin.exists():
                cmd += ["-v", f"{self.claude_bin}:/usr/local/bin/claude:ro"]
            if self.claude_auth.exists() and not (
                os.environ.get("ANTHROPIC_API_KEY")
                or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
            ):
                cmd += [
                    "-v",
                    f"{self.claude_auth}:/home/econ/.claude/.credentials.json:ro",
                ]
        env = {
            "HOME": "/home/econ",
            "XDG_CONFIG_HOME": "/home/econ/.config",
            "XDG_DATA_HOME": "/home/econ/.local/share",
            "XDG_CACHE_HOME": "/home/econ/.cache",
            "PWD": "/workspace",
            "PYTHONPATH": "/workspace/src",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "CLAUDE_CONFIG_DIR": "/home/econ/.claude",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_AUTOUPDATER": "1",
            **self._proxy_env(),
        }
        if "OPENCODE_API_KEY" in os.environ:
            env["OPENCODE_API_KEY"] = os.environ["OPENCODE_API_KEY"]
        for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
            if key in os.environ:
                env[key] = os.environ[key]
        for key, value in env.items():
            cmd += ["-e", f"{key}={value}"]
        cmd += [self.image, *inner]
        return cmd

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
        if not docker_available(self.executable):
            raise DockerRunError("docker is not available")
        runtime = self._runtime(role)
        if runtime != "claude":
            return self._run_command(
                role,
                cwd,
                prompt,
                timeout=timeout,
                model_override=model_override,
                max_budget_usd=max_budget_usd,
                settings_dir=None,
            )
        with tempfile.TemporaryDirectory(prefix="econ-docker-claude-") as tmp:
            return self._run_command(
                role,
                cwd,
                prompt,
                timeout=timeout,
                model_override=model_override,
                max_budget_usd=max_budget_usd,
                settings_dir=Path(tmp),
            )

    def _run_command(
        self,
        role: str,
        cwd: Path,
        prompt: str,
        *,
        timeout: int,
        model_override: str | None,
        max_budget_usd: float | None,
        settings_dir: Path | None,
    ) -> AgentResult:
        argv = self.command(
            role,
            cwd,
            prompt,
            model_override=model_override,
            max_budget_usd=max_budget_usd,
            settings_dir=settings_dir,
        )
        start = time.time()
        timed_out = False
        try:
            proc = subprocess.run(
                argv,
                cwd=self.repo,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=command_env(self.repo, cwd),
                check=False,
            )
            out, err, code = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            out = exc.stdout if isinstance(exc.stdout, str) else ""
            err = exc.stderr if isinstance(exc.stderr, str) else ""
            code = 124
            if "--name" in argv:
                try:
                    name = argv[argv.index("--name") + 1]
                    subprocess.run(
                        [self.executable, "kill", name],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                except (IndexError, OSError):
                    pass
        runtime = self._runtime(role)
        settings_payload = {}
        if runtime == "claude" and settings_dir is not None:
            settings_file = settings_dir / f"{role}-settings.json"
            if settings_file.exists():
                settings_payload = json.loads(settings_file.read_text())
        if runtime == "claude":
            try:
                parsed = claude_cli.parse_claude_result(out)
            except claude_cli.ClaudeProtocolError as exc:
                return AgentResult(
                    role=role,
                    command=argv,
                    exit_code=code if code != 0 else 1,
                    duration_s=round(time.time() - start, 3),
                    timed_out=timed_out,
                    text=out,
                    stdout=out,
                    stderr=err,
                    error=str(exc),
                    request={"runner": "docker-claude", "settings": settings_payload},
                )
            error = ""
            if parsed.is_error or parsed.subtype not in {None, "success"}:
                error = (
                    f"claude subtype={parsed.subtype or 'error'} "
                    f"is_error={parsed.is_error}"
                )
                if code == 0:
                    code = 1
            return AgentResult(
                role=role,
                command=argv,
                exit_code=code,
                duration_s=round(time.time() - start, 3),
                timed_out=timed_out,
                text=parsed.text,
                stdout=out,
                stderr=err,
                cost_usd=parsed.cost_usd,
                tokens=parsed.tokens,
                steps=parsed.steps,
                error=error,
                denials=parsed.denials,
                request={"runner": "docker-claude", "settings": settings_payload},
            )
        text, cost, tokens, steps = parse_opencode_events(out)
        return AgentResult(
            role=role,
            command=argv,
            exit_code=code,
            duration_s=round(time.time() - start, 3),
            timed_out=timed_out,
            text=text,
            stdout=out,
            stderr=err,
            cost_usd=cost,
            tokens=tokens,
            steps=steps,
            request={"runner": "docker-opencode"},
        )
