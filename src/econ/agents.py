from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import config

AGENTS_FILE = config.ROOT / "config" / "agents.yaml"
RENDER_DIR = config.ROOT / ".opencode" / "agents"
DEFAULT_AGENT_PREFIX = "econ-"


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

    @property
    def agent_id(self) -> str:
        return f"{DEFAULT_AGENT_PREFIX}{self.name}"

    @property
    def selector(self) -> str:
        return f"{self.model}#{self.variant}" if self.variant else self.model


def load_config(path: Path | None = None) -> dict:
    path = path or AGENTS_FILE
    if not path.exists():
        raise FileNotFoundError(f"agent config not found: {path}")
    return yaml.safe_load(path.read_text())


def agents(cfg: dict | None = None) -> list[AgentSpec]:
    cfg = cfg or load_config()
    defaults = cfg.get("defaults", {})
    out = []
    for name, raw in cfg.get("agents", {}).items():
        model = raw.get("model", defaults.get("model"))
        if not model or "#" in model:
            raise ValueError(f"{name}: model must be provider/model without #variant")
        variant = raw.get("variant", defaults.get("variant"))
        out.append(
            AgentSpec(
                name=name,
                description=raw.get("description", ""),
                prompt_path=config.ROOT / raw["prompt"],
                model=model,
                variant=variant,
                steps=int(raw.get("steps", defaults.get("steps", 12))),
                sandbox=raw.get("sandbox", defaults.get("sandbox", "offline")),
                timeout_s=int(raw.get("timeout_s", defaults.get("timeout_s", 900))),
            )
        )
    return out


def _permissions(raw: dict) -> list[dict]:
    perms = [{"action": "*", "resource": "*", "effect": "deny"}]
    p = raw.get("permissions", {})
    for path in p.get("read", []):
        perms.append({"action": "read", "resource": path, "effect": "allow"})
    for path in p.get("edit", []):
        perms.append({"action": "edit", "resource": path, "effect": "allow"})
    for cmd in p.get("shell", []):
        perms.append({"action": "shell", "resource": cmd, "effect": "allow"})
    for action in [
        "external_directory",
        "webfetch",
        "websearch",
        "question",
        "skill",
        "subagent",
    ]:
        perms.append({"action": action, "resource": "*", "effect": "deny"})
    return perms


def render_agent(spec: AgentSpec, raw: dict) -> str:
    body = spec.prompt_path.read_text().strip()
    front = {
        "description": spec.description,
        "mode": "all",
        "model": spec.selector,
        "hidden": True,
        "steps": spec.steps,
        "permissions": _permissions(raw),
    }
    return (
        "---\n"
        + yaml.safe_dump(front, sort_keys=False, default_flow_style=False).strip()
        + "\n---\n\n"
        + body
        + "\n"
    )


def render_all(cfg: dict | None = None) -> dict[Path, str]:
    cfg = cfg or load_config()
    raw_agents = cfg.get("agents", {})
    out = {}
    for spec in agents(cfg):
        path = RENDER_DIR / f"{spec.agent_id}.md"
        out[path] = render_agent(spec, raw_agents[spec.name])
    return out


def write_all() -> list[Path]:
    rendered = render_all()
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for path, text in rendered.items():
        path.write_text(text)
        written.append(path)
    return written


def check_all() -> list[str]:
    problems = []
    rendered = render_all()
    for path, text in rendered.items():
        if not path.exists():
            problems.append(f"missing generated agent: {path}")
        elif path.read_text() != text:
            problems.append(f"stale generated agent: {path}")
    extra = set(RENDER_DIR.glob("econ-*.md")) - set(rendered)
    for path in sorted(extra):
        problems.append(f"unexpected agent file: {path}")
    return problems


def _model_catalog() -> dict:
    path = Path.home() / ".cache" / "opencode" / "models.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def validate_variants(cfg: dict | None = None) -> list[str]:
    cfg = cfg or load_config()
    cache = _model_catalog()
    if not cache:
        return ["model catalog cache unavailable; variant check skipped"]
    problems = []
    for spec in agents(cfg):
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


def agent_argv(spec: AgentSpec, message: str) -> list[str]:
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


def brief_message() -> str:
    return (
        "Read /workspace/in/packet.md and the files it names. "
        "Write the required JSON artifact to /workspace/out/result.json. "
        "Do not access anything outside /workspace."
    )
