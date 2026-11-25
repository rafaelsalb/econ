from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import config
from .claude_cli import CLAUDE_EFFORTS, claude_command, permission_policy

AGENTS_FILE = config.ROOT / "config" / "agents.yaml"
DEV_AGENTS_FILE = config.ROOT / "config" / "dev_agents.yaml"
RENDER_DIR = config.ROOT / ".opencode" / "agents"
DEFAULT_AGENT_PREFIX = "econ-"
DEV_AGENT_PREFIX = "dev-"

# Deny rules applied after allows. The last matching permission rule wins, so
# these are the backstop even when an agent has a broad read/edit pattern.
_SECRET_DENIES: tuple[dict, ...] = (
    {"action": "read", "resource": "**/.env", "effect": "deny"},
    {"action": "read", "resource": "**/.env.*", "effect": "deny"},
    {"action": "read", "resource": "*.env", "effect": "deny"},
    {"action": "read", "resource": "*.env.*", "effect": "deny"},
    {"action": "read", "resource": "~/.ssh/**", "effect": "deny"},
    {"action": "read", "resource": "~/.config/econ/**", "effect": "deny"},
    {"action": "read", "resource": "~/.local/share/opencode/**", "effect": "deny"},
)

_DANGEROUS_SHELL: tuple[dict, ...] = (
    {"action": "shell", "resource": "git push *", "effect": "deny"},
    {"action": "shell", "resource": "git reset --hard *", "effect": "deny"},
    {"action": "shell", "resource": "git clean *", "effect": "deny"},
    {"action": "shell", "resource": "rm *", "effect": "deny"},
    {"action": "shell", "resource": "sudo *", "effect": "deny"},
    {"action": "shell", "resource": "su *", "effect": "deny"},
    {"action": "shell", "resource": "docker *", "effect": "deny"},
    {"action": "shell", "resource": "podman *", "effect": "deny"},
    {"action": "shell", "resource": "pip install *", "effect": "deny"},
    {"action": "shell", "resource": "uv *", "effect": "deny"},
    {"action": "shell", "resource": "curl *", "effect": "deny"},
    {"action": "shell", "resource": "wget *", "effect": "deny"},
    {"action": "shell", "resource": "ssh *", "effect": "deny"},
    {"action": "shell", "resource": "scp *", "effect": "deny"},
    {"action": "shell", "resource": "chmod *", "effect": "deny"},
    {"action": "shell", "resource": "chown *", "effect": "deny"},
)

_GENERIC_DENIES: tuple[dict, ...] = (
    {"action": "external_directory", "resource": "*", "effect": "deny"},
    {"action": "webfetch", "resource": "*", "effect": "deny"},
    {"action": "websearch", "resource": "*", "effect": "deny"},
    {"action": "question", "resource": "*", "effect": "deny"},
    {"action": "skill", "resource": "*", "effect": "deny"},
    {"action": "execute", "resource": "*", "effect": "deny"},
    {"action": "generate_image", "resource": "*", "effect": "deny"},
    {"action": "edit", "resource": ".git/**", "effect": "deny"},
    {"action": "edit", "resource": "**/.git/**", "effect": "deny"},
)


@dataclass(frozen=True)
class AgentSpec:
    name: str
    description: str
    prompt_path: Path
    model: str
    variant: str | None
    steps: int
    sandbox: str
    timeout_s: int
    runtime: str = "opencode"
    claude_model: str | None = None
    claude_effort: str | None = None
    prefix: str = DEFAULT_AGENT_PREFIX
    mode: str = "all"
    hidden: bool = True

    @property
    def agent_id(self) -> str:
        return f"{self.prefix}{self.name}"

    @property
    def selector(self) -> str:
        return f"{self.model}#{self.variant}" if self.variant else self.model

    @property
    def claude_selector(self) -> str:
        if not self.claude_model:
            raise ValueError(f"{self.name}: no Claude model configured")
        return self.claude_model


def load_config(path: Path | None = None) -> dict:
    path = path or AGENTS_FILE
    if not path.exists():
        raise FileNotFoundError(f"agent config not found: {path}")
    return yaml.safe_load(path.read_text())


def load_dev_config(path: Path | None = None) -> dict:
    return load_config(path or DEV_AGENTS_FILE)


def agents(
    cfg: dict | None = None,
    *,
    prefix: str = DEFAULT_AGENT_PREFIX,
    root: Path | None = None,
) -> list[AgentSpec]:
    cfg = cfg or load_config()
    root = root or config.ROOT
    defaults = cfg.get("defaults", {})
    out = []
    for name, raw in cfg.get("agents", {}).items():
        if raw.get("disabled"):
            continue
        model = raw.get("model", defaults.get("model"))
        if not model or "#" in model:
            raise ValueError(f"{name}: model must be provider/model without #variant")
        variant = raw.get("variant", defaults.get("variant"))
        runtime = raw.get("runtime", defaults.get("runtime", "opencode"))
        if runtime not in {"opencode", "claude"}:
            raise ValueError(f"{name}: runtime must be opencode or claude, got {runtime!r}")
        claude_model = raw.get("claude_model", defaults.get("claude_model"))
        claude_effort = raw.get("claude_effort", defaults.get("claude_effort"))
        if runtime == "claude":
            if not claude_model:
                raise ValueError(f"{name}: runtime claude requires claude_model")
            if claude_effort is not None and claude_effort not in CLAUDE_EFFORTS:
                raise ValueError(
                    f"{name}: claude_effort must be one of {', '.join(CLAUDE_EFFORTS)}"
                )
        out.append(
            AgentSpec(
                name=name,
                description=raw.get("description", ""),
                prompt_path=root / raw["prompt"],
                model=model,
                variant=variant,
                steps=int(raw.get("steps", defaults.get("steps", 12))),
                sandbox=raw.get("sandbox", defaults.get("sandbox", "offline")),
                timeout_s=int(raw.get("timeout_s", defaults.get("timeout_s", 900))),
                runtime=runtime,
                claude_model=claude_model,
                claude_effort=claude_effort,
                prefix=prefix,
                mode=raw.get("mode", defaults.get("mode", "all")),
                hidden=bool(raw.get("hidden", defaults.get("hidden", True))),
            )
        )
    return out


def dev_agents(cfg: dict | None = None, *, root: Path | None = None) -> list[AgentSpec]:
    return agents(cfg or load_dev_config(), prefix=DEV_AGENT_PREFIX, root=root)


def step_budget_problems(specs: list[AgentSpec], ceiling: int) -> list[str]:
    """Report agents whose per-turn step cap exceeds the policy ceiling.

    The per-turn cap is a safety and cost control, not a suggestion. Keeping it
    inside ``budget.max_agent_steps`` makes an increase a deliberate policy
    change instead of a silent roster edit.
    """
    problems = []
    for spec in specs:
        if spec.steps > ceiling:
            problems.append(
                f"{spec.name}: steps {spec.steps} exceeds "
                f"budget.max_agent_steps {ceiling}"
            )
    return problems


def _merged_permissions(raw: dict, defaults: dict | None = None) -> dict:
    defaults = defaults or {}
    base_permissions = defaults.get("permissions", {})
    own_permissions = raw.get("permissions", {})
    p = {
        key: list(
            dict.fromkeys(
                [*base_permissions.get(key, []), *own_permissions.get(key, [])]
            )
        )
        for key in {"read", "edit", "shell", "subagents"}
    }
    p["deny"] = [*base_permissions.get("deny", []), *own_permissions.get("deny", [])]
    p["question"] = own_permissions.get(
        "question", base_permissions.get("question")
    )
    return p


def agent_permissions(cfg: dict, name: str) -> dict:
    defaults = cfg.get("defaults") or {}
    raw = (cfg.get("agents") or {}).get(name) or {}
    return _merged_permissions(raw, defaults)


def validate_runtime_config(cfg: dict) -> list[str]:
    """Validate the runtime half of the roster without touching model catalogs."""
    problems: list[str] = []
    defaults = cfg.get("defaults") or {}
    default_runtime = defaults.get("runtime", "opencode")
    for name, raw in (cfg.get("agents") or {}).items():
        if raw.get("disabled"):
            continue
        runtime = raw.get("runtime", default_runtime)
        if runtime not in {"opencode", "claude"}:
            problems.append(f"{name}: unknown runtime {runtime!r}")
            continue
        if runtime == "claude":
            model = raw.get("claude_model", defaults.get("claude_model"))
            effort = raw.get("claude_effort", defaults.get("claude_effort"))
            if not model:
                problems.append(f"{name}: runtime claude requires claude_model")
            if effort is not None and effort not in CLAUDE_EFFORTS:
                problems.append(
                    f"{name}: claude_effort must be one of "
                    f"{', '.join(CLAUDE_EFFORTS)}"
                )
            perms = _merged_permissions(raw, defaults)
            if perms.get("question") == "allow":
                problems.append(
                    f"{name}: runtime claude is headless and cannot use the "
                    "question tool; keep this role on opencode or add an "
                    "interactive Claude runner"
                )
    return problems


def _permissions(raw: dict, defaults: dict | None = None) -> list[dict]:
    defaults = defaults or {}
    perms: list[dict] = [{"action": "*", "resource": "*", "effect": "deny"}]
    p = _merged_permissions(raw, defaults)
    for path in p["read"]:
        perms.append({"action": "read", "resource": path, "effect": "allow"})
    for path in p["edit"]:
        perms.append({"action": "edit", "resource": path, "effect": "allow"})
    for cmd in p["shell"]:
        perms.append({"action": "shell", "resource": cmd, "effect": "allow"})

    subagents = p.get("subagents", [])
    if subagents:
        for agent_id in subagents:
            perms.append(
                {"action": "subagent", "resource": agent_id, "effect": "allow"}
            )
        perms.append({"action": "subagent", "resource": "*", "effect": "deny"})
    else:
        perms.append({"action": "subagent", "resource": "*", "effect": "deny"})

    perms.extend(_GENERIC_DENIES)
    question_mode = p.get("question")
    if question_mode == "allow":
        # The question tool is denied for the rest of the roster; the intake
        # agent is the explicit exception so it can interview the human.
        perms.append({"action": "question", "resource": "*", "effect": "allow"})
    perms.extend(_SECRET_DENIES)
    perms.extend(_DANGEROUS_SHELL)
    perms.extend(p.get("deny", []))
    return perms


def render_agent(spec: AgentSpec, raw: dict, defaults: dict | None = None) -> str:
    body = spec.prompt_path.read_text().strip()
    front: dict = {
        "description": spec.description,
        "mode": spec.mode,
        "model": spec.selector,
        "hidden": spec.hidden,
        "steps": spec.steps,
        "permissions": _permissions(raw, defaults),
    }
    if raw.get("color"):
        front["color"] = raw["color"]
    return (
        "---\n"
        + yaml.safe_dump(front, sort_keys=False, default_flow_style=False).strip()
        + "\n---\n\n"
        + body
        + "\n"
    )


def render_all(
    cfg: dict | None = None,
    *,
    render_dir: Path | None = None,
    prefix: str = DEFAULT_AGENT_PREFIX,
    root: Path | None = None,
) -> dict[Path, str]:
    cfg = cfg or load_config()
    root = root or config.ROOT
    render_dir = render_dir or (root / ".opencode" / "agents")
    raw_agents = cfg.get("agents", {})
    defaults = cfg.get("defaults", {})
    out = {}
    for spec in agents(cfg, prefix=prefix, root=root):
        path = render_dir / f"{spec.agent_id}.md"
        out[path] = render_agent(spec, raw_agents[spec.name], defaults)
    return out


def write_all(
    cfg: dict | None = None,
    *,
    render_dir: Path | None = None,
    prefix: str = DEFAULT_AGENT_PREFIX,
    root: Path | None = None,
) -> list[Path]:
    rendered = render_all(cfg, render_dir=render_dir, prefix=prefix, root=root)
    target = render_dir or ((root or config.ROOT) / ".opencode" / "agents")
    target.mkdir(parents=True, exist_ok=True)
    written = []
    for path, text in rendered.items():
        path.write_text(text)
        written.append(path)
    return written


def check_all(
    cfg: dict | None = None,
    *,
    render_dir: Path | None = None,
    prefix: str = DEFAULT_AGENT_PREFIX,
    root: Path | None = None,
) -> list[str]:
    problems = []
    rendered = render_all(cfg, render_dir=render_dir, prefix=prefix, root=root)
    for path, text in rendered.items():
        if not path.exists():
            problems.append(f"missing generated agent: {path}")
        elif path.read_text() != text:
            problems.append(f"stale generated agent: {path}")
    target = render_dir or ((root or config.ROOT) / ".opencode" / "agents")
    extra = set(target.glob(f"{prefix}*.md")) - set(rendered)
    for path in sorted(extra):
        problems.append(f"unexpected agent file: {path}")
    return problems


def render_dev_all(cfg: dict | None = None, *, root: Path | None = None) -> dict[Path, str]:
    return render_all(
        cfg or load_dev_config(),
        render_dir=(root or config.ROOT) / ".opencode" / "agents",
        prefix=DEV_AGENT_PREFIX,
        root=root,
    )


def write_dev_all(cfg: dict | None = None, *, root: Path | None = None) -> list[Path]:
    return write_all(
        cfg or load_dev_config(),
        render_dir=(root or config.ROOT) / ".opencode" / "agents",
        prefix=DEV_AGENT_PREFIX,
        root=root,
    )


def check_dev_all(cfg: dict | None = None, *, root: Path | None = None) -> list[str]:
    return check_all(
        cfg or load_dev_config(),
        render_dir=(root or config.ROOT) / ".opencode" / "agents",
        prefix=DEV_AGENT_PREFIX,
        root=root,
    )


def _model_catalog() -> dict:
    path = Path.home() / ".cache" / "opencode" / "models.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _validate_variants(cfg: dict, *, root: Path | None = None) -> list[str]:
    cache = _model_catalog()
    if not cache:
        return ["model catalog cache unavailable; variant check skipped"]
    problems = []
    for spec in agents(cfg, root=root):
        provider, model = spec.model.split("/", 1)
        entry = cache.get(provider, {}).get("models", {}).get(model)
        if not entry:
            problems.append(f"{spec.name}: {spec.model} not in the local catalog")
            continue
        efforts = [
            v
            for opt in entry.get("reasoning_options", [])
            if opt.get("type") == "effort"
            for v in opt.get("values", [])
        ]
        if spec.variant and efforts and spec.variant not in efforts:
            problems.append(
                f"{spec.name}: variant {spec.variant} not available; choices={efforts}"
            )
    return problems


def validate_variants(cfg: dict | None = None, *, root: Path | None = None) -> list[str]:
    return _validate_variants(cfg or load_config(), root=root)


def validate_dev_variants(cfg: dict | None = None, *, root: Path | None = None) -> list[str]:
    return _validate_variants(cfg or load_dev_config(), root=root)


def opencode_argv(spec: AgentSpec, message: str) -> list[str]:
    return [
        "opencode",
        "run",
        "--agent",
        spec.agent_id,
        "--model",
        spec.selector,
        "--format",
        "json",
        message,
    ]


def claude_argv(
    spec: AgentSpec,
    message: str,
    *,
    settings_path: Path,
    cfg: dict | None = None,
    cwd: Path = Path("/workspace"),
) -> list[str]:
    cfg = cfg or load_config()
    perms = agent_permissions(cfg, spec.name)
    policy = permission_policy(
        edit=perms["edit"],
        shell=perms["shell"],
        deny=perms["deny"],
        root=cwd,
        read=perms["read"],
        allow_read_allowlist=True,
    )
    system_prompt = spec.prompt_path.read_text().strip()
    return claude_command(
        spec,
        system_prompt,
        message,
        settings_path,
        cwd=cwd,
        policy=policy,
    )


def agent_argv(
    spec: AgentSpec,
    message: str,
    *,
    settings_path: Path | None = None,
    cfg: dict | None = None,
) -> list[str]:
    if spec.runtime == "opencode":
        return opencode_argv(spec, message)
    if spec.runtime == "claude":
        if settings_path is None:
            raise ValueError(
                f"{spec.name}: Claude runs require a generated settings path"
            )
        return claude_argv(
            spec,
            message,
            settings_path=settings_path,
            cfg=cfg,
        )
    raise ValueError(f"{spec.name}: unknown runtime {spec.runtime!r}")


def brief_message() -> str:
    return (
        "Read /workspace/in/packet.md and the files it names. "
        "Write the required JSON artifact to /workspace/out/result.json. "
        "Do not access anything outside /workspace."
    )
