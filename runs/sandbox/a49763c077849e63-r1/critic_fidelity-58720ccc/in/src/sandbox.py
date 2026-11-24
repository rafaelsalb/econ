from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import config
from .agents import AgentSpec, agent_argv, agents as list_agents, brief_message, load_config

SANDBOX_ROOT = config.RUNS / "sandbox"
OPENCODE_BIN = Path.home() / ".opencode" / "bin" / "opencode"
AUTH_FILE = Path.home() / ".local" / "share" / "opencode" / "auth.json"


@dataclass
class Workspace:
    run_id: str
    role: str
    invocation_id: str
    root: Path
    inbox: Path
    outbox: Path
    home: Path
    logs: Path

    def audit(self) -> dict:
        return {
            "run_id": self.run_id,
            "role": self.role,
            "invocation_id": self.invocation_id,
            "root": str(self.root),
            "inbox": str(self.inbox),
            "outbox": str(self.outbox),
        }


@dataclass
class InvocationResult:
    workspace: Workspace
    exit_code: int
    duration_s: float
    timed_out: bool
    stdout_path: Path
    stderr_path: Path
    audit_path: Path

    def stdout(self) -> str:
        return self.stdout_path.read_text() if self.stdout_path.exists() else ""

    def stderr(self) -> str:
        return self.stderr_path.read_text() if self.stderr_path.exists() else ""


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def project_workspace(
    run_id: str,
    role: str,
    inputs: dict[str, str | Path] | None = None,
    packet: str | None = None,
) -> Workspace:
    """Copy a minimal, role-specific view of the repo into an isolated inbox.

    Symlinks are resolved and rejected if they leave the repository. The role
    never receives eval/, the registry, or the lockbox unless explicitly listed.
    """
    invocation_id = f"{role}-{uuid.uuid4().hex[:8]}"
    root = SANDBOX_ROOT / run_id / invocation_id
    inbox = root / "in"
    outbox = root / "out"
    home = root / "home"
    logs = root / "logs"
    for p in (
        inbox,
        outbox,
        home / ".local" / "share" / "opencode",
        home / ".config" / "opencode",
        home / ".cache",
        home / ".opencode",
        logs,
    ):
        p.mkdir(parents=True, exist_ok=True)

    for dest, source in (inputs or {}).items():
        src = Path(source)
        if not src.is_absolute():
            src = config.ROOT / src
        src = src.resolve()
        if not src.is_relative_to(config.ROOT.resolve()):
            raise ValueError(f"input escapes repository: {src}")
        target = inbox / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, target)
        else:
            shutil.copy2(src, target)

    if packet is not None:
        (inbox / "packet.md").write_text(packet)
    return Workspace(
        run_id=run_id,
        role=role,
        invocation_id=invocation_id,
        root=root,
        inbox=inbox,
        outbox=outbox,
        home=home,
        logs=logs,
    )


def docker_available() -> bool:
    try:
        return (
            subprocess.run(
                ["docker", "info"], capture_output=True, timeout=8, check=False
            ).returncode
            == 0
        )
    except Exception:  # noqa: BLE001
        return False


def _sandbox_cfg(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    return cfg.get("sandbox", {})


def _proxy_url(sandbox: dict, network: str) -> str | None:
    proxy = sandbox.get("proxy", {})
    host = proxy.get(f"{network}_host")
    port = proxy.get("port", 3128)
    return f"http://{host}:{port}" if host else None


def _base_env(sandbox: dict, network: str) -> dict[str, str]:
    env = {
        "HOME": "/home/econ",
        "XDG_CONFIG_HOME": "/home/econ/.config",
        "XDG_DATA_HOME": "/home/econ/.local/share",
        "XDG_CACHE_HOME": "/home/econ/.cache",
    }
    for key in sandbox.get("env", {}).get("allow", []):
        if key in os.environ:
            env[key] = os.environ[key]
    proxy = _proxy_url(sandbox, network)
    if proxy:
        env.update(
            {
                "HTTP_PROXY": proxy,
                "HTTPS_PROXY": proxy,
                "http_proxy": proxy,
                "https_proxy": proxy,
                "NO_PROXY": "127.0.0.1,localhost",
            }
        )
    return env


def _mounts(ws: Workspace) -> list[str]:
    mounts = [
        f"{ws.inbox}:/workspace/in:ro",
        f"{ws.outbox}:/workspace/out:rw",
        f"{ws.home}:/home/econ:rw",
    ]
    agents_dir = config.ROOT / ".opencode" / "agents"
    if agents_dir.exists():
        mounts.append(f"{agents_dir}:/workspace/.opencode/agents:ro")
    project_config = config.ROOT / "opencode.jsonc"
    if project_config.exists():
        mounts.append(f"{project_config}:/workspace/opencode.jsonc:ro")
    if OPENCODE_BIN.exists():
        mounts.append(f"{OPENCODE_BIN}:/usr/local/bin/opencode:ro")
    if AUTH_FILE.exists():
        mounts.append(
            f"{AUTH_FILE}:/home/econ/.local/share/opencode/auth.json:ro"
        )
    return mounts


def _write_audit(
    ws: Workspace,
    *,
    argv: list[str],
    image: str | None,
    network: str,
    env_keys: list[str],
    limits: dict,
    exit_code: int,
    duration_s: float,
    timed_out: bool,
    stdout: Path,
    stderr: Path,
    extra: dict | None = None,
) -> Path:
    audit = {
        "invocation_id": ws.invocation_id,
        "run_id": ws.run_id,
        "role": ws.role,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "argv": argv,
        "image": image,
        "network": network,
        "env_keys": env_keys,
        "limits": limits,
        "exit_code": exit_code,
        "duration_s": round(duration_s, 3),
        "timed_out": timed_out,
        "stdout_sha256": _sha(stdout) if stdout.exists() else None,
        "stderr_sha256": _sha(stderr) if stderr.exists() else None,
        "workspace": ws.audit(),
        **(extra or {}),
    }
    path = ws.logs / "invocation.json"
    path.write_text(json.dumps(audit, indent=2))
    return path


def docker_command(
    ws: Workspace,
    argv: list[str],
    *,
    network: str = "offline",
    image: str | None = None,
    sandbox: dict | None = None,
) -> tuple[list[str], str, dict[str, str]]:
    sandbox = sandbox or _sandbox_cfg()
    image = image or sandbox.get("image", "econ-agent:latest")
    limits = sandbox.get("limits", {})
    net_name = sandbox.get("networks", {}).get(network, "none")
    env = _base_env(sandbox, network)
    name = f"econ-{ws.run_id[:8]}-{ws.invocation_id}"[:63]
    cmd = [
        "docker",
        "run",
        "--rm",
        "--init",
        "--name",
        name,
        "--user",
        str(sandbox.get("user", "1000:1000")),
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=256m",
        "--cap-drop=ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        str(limits.get("pids", 256)),
        "--memory",
        str(limits.get("memory", "4g")),
        "--cpus",
        str(limits.get("cpus", 2)),
        "--network",
        net_name,
        "--workdir",
        "/workspace",
    ]
    for mount in _mounts(ws):
        cmd += ["-v", mount]
    for key, value in env.items():
        cmd += ["-e", f"{key}={value}"]
    cmd += [image, *argv]
    return cmd, name, env


def run_in_sandbox(
    ws: Workspace,
    argv: list[str],
    *,
    network: str = "offline",
    timeout_s: int = 900,
    image: str | None = None,
    extra_audit: dict | None = None,
) -> InvocationResult:
    sandbox = _sandbox_cfg()
    image = image or sandbox.get("image", "econ-agent:latest")
    limits = sandbox.get("limits", {})
    stdout_path = ws.logs / "stdout.log"
    stderr_path = ws.logs / "stderr.log"

    if not docker_available():
        return _run_bwrap(ws, argv, timeout_s, stdout_path, stderr_path, extra_audit)

    cmd, name, env = docker_command(
        ws, argv, network=network, image=image, sandbox=sandbox
    )
    net_name = sandbox.get("networks", {}).get(network, "none")

    start = time.time()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s, check=False
        )
        out, err, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        err = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        code = 124
        subprocess.run(
            ["docker", "kill", name], capture_output=True, text=True, check=False
        )
    duration = time.time() - start
    stdout_path.write_text(out)
    stderr_path.write_text(err)
    audit_path = _write_audit(
        ws,
        argv=argv,
        image=image,
        network=network,
        env_keys=sorted(env),
        limits=limits,
        exit_code=code,
        duration_s=duration,
        timed_out=timed_out,
        stdout=stdout_path,
        stderr=stderr_path,
        extra=extra_audit,
    )
    return InvocationResult(
        workspace=ws,
        exit_code=code,
        duration_s=duration,
        timed_out=timed_out,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        audit_path=audit_path,
    )


def _run_bwrap(
    ws: Workspace,
    argv: list[str],
    timeout_s: int,
    stdout_path: Path,
    stderr_path: Path,
    extra_audit: dict | None,
) -> InvocationResult:
    """Filesystem/process-only fallback. No network and no model calls."""
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise RuntimeError("neither Docker nor bwrap is available")
    cmd = [
        bwrap,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind",
        "/lib",
        "/lib",
        "--ro-bind",
        "/lib64",
        "/lib64",
        "--ro-bind",
        "/bin",
        "/bin",
        "--ro-bind",
        "/sbin",
        "/sbin",
        "--ro-bind",
        "/etc",
        "/etc",
        "--bind",
        str(ws.inbox),
        "/workspace/in",
        "--bind",
        str(ws.outbox),
        "/workspace/out",
        "--tmpfs",
        "/tmp",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--chdir",
        "/workspace",
        "--setenv",
        "HOME",
        "/tmp",
        "--setenv",
        "PATH",
        "/usr/local/bin:/usr/bin:/bin",
        *argv,
    ]
    start = time.time()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s, check=False
        )
        out, err, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        err = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        code = 124
    duration = time.time() - start
    stdout_path.write_text(out)
    stderr_path.write_text(err)
    audit_path = _write_audit(
        ws,
        argv=argv,
        image=None,
        network="none-bwrap",
        env_keys=["HOME", "PATH"],
        limits={"timeout_s": timeout_s},
        exit_code=code,
        duration_s=duration,
        timed_out=timed_out,
        stdout=stdout_path,
        stderr=stderr_path,
        extra={"backend": "bwrap", **(extra_audit or {})},
    )
    return InvocationResult(
        workspace=ws,
        exit_code=code,
        duration_s=duration,
        timed_out=timed_out,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        audit_path=audit_path,
    )


def run_agent(
    role: str,
    run_id: str,
    inputs: dict[str, str | Path] | None = None,
    packet: str | None = None,
    network: str | None = None,
) -> InvocationResult:
    cfg = load_config()
    specs = {s.name: s for s in list_agents(cfg)}
    if role not in specs:
        raise ValueError(f"unknown agent role: {role}")
    spec: AgentSpec = specs[role]
    ws = project_workspace(run_id, role, inputs=inputs, packet=packet)
    argv = agent_argv(spec, brief_message())
    return run_in_sandbox(
        ws,
        argv,
        network=network or spec.sandbox,
        timeout_s=spec.timeout_s,
        extra_audit={"agent_id": spec.agent_id, "model": spec.selector},
    )


def build_image(tag: str = "econ-agent:latest") -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "docker",
            "build",
            "-t",
            tag,
            "-f",
            str(config.ROOT / "sandbox" / "Dockerfile"),
            str(config.ROOT),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def setup_networks(cfg: dict | None = None) -> subprocess.CompletedProcess:
    cfg = cfg or load_config()
    sb = cfg.get("sandbox", {})
    nets = sb.get("networks", {})
    proxy = sb.get("proxy", {})
    script = config.ROOT / "sandbox" / "setup.sh"
    env = os.environ.copy()
    env["OFFLINE_NETWORK"] = nets.get("offline", "econ-internal")
    env["DATA_NETWORK"] = nets.get("data", "econ-data-internal")
    env["EGRESS_NETWORK"] = "econ-egress"
    env["PROXY_OFFLINE_HOSTS"] = ",".join(proxy.get("offline_hosts", []))
    env["PROXY_DATA_HOSTS"] = ",".join(proxy.get("data_hosts", []))
    env["PROXY_PORT"] = str(proxy.get("port", 3128))
    return subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
