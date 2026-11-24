from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from .. import agents as agent_config
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
    ):
        self.repo = repo.resolve()
        self.policy = policy
        self.image = image or policy.executor.docker_image
        self.network = network or policy.executor.network
        self.executable = executable
        self.specs = specs or {
            spec.name: spec for spec in agent_config.dev_agents(root=self.repo)
        }
        self.opencode_bin = Path.home() / ".opencode" / "bin" / "opencode"
        self.auth_file = Path.home() / ".local" / "share" / "opencode" / "auth.json"

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

    def command(
        self, role: str, worktree: Path, prompt: str, model_override: str | None = None
    ) -> list[str]:
        spec = self.specs.get(role)
        if spec is None:
            raise KeyError(f"unknown dev agent role: {role}")
        model = model_override or spec.selector
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
        home.mkdir(parents=True, exist_ok=True)
        cmd += ["-v", f"{home}:/home/econ:rw"]
        agents_dir = self.repo / ".opencode" / "agents"
        if agents_dir.exists():
            cmd += ["-v", f"{agents_dir}:/workspace/.opencode/agents:ro"]
        config = self.repo / "opencode.jsonc"
        if config.exists():
            cmd += ["-v", f"{config}:/workspace/opencode.jsonc:ro"]
        if self.opencode_bin.exists():
            cmd += ["-v", f"{self.opencode_bin}:/usr/local/bin/opencode:ro"]
        if self.auth_file.exists() and "OPENCODE_API_KEY" not in os.environ:
            cmd += [
                "-v",
                f"{self.auth_file}:/home/econ/.local/share/opencode/auth.json:ro",
            ]
        env = {
            "HOME": "/home/econ",
            "XDG_CONFIG_HOME": "/home/econ/.config",
            "XDG_DATA_HOME": "/home/econ/.local/share",
            "XDG_CACHE_HOME": "/home/econ/.cache",
            "PYTHONPATH": "/workspace/src",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            **self._proxy_env(),
        }
        if "OPENCODE_API_KEY" in os.environ:
            env["OPENCODE_API_KEY"] = os.environ["OPENCODE_API_KEY"]
        for key, value in env.items():
            cmd += ["-e", f"{key}={value}"]
        cmd += [
            self.image,
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
        return cmd

    def run(
        self,
        role: str,
        cwd: Path,
        prompt: str,
        *,
        timeout: int = 1200,
        model_override: str | None = None,
    ) -> AgentResult:
        if not docker_available(self.executable):
            raise DockerRunError("docker is not available")
        argv = self.command(role, cwd, prompt, model_override=model_override)
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
        text, cost, tokens = parse_opencode_events(out)
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
        )
