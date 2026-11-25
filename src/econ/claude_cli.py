from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

CLAUDE_EFFORTS: tuple[str, ...] = ("low", "medium", "high", "xhigh", "max")

# Deny rules that must hold for every role. They are scoped so the tool stays
# available where a role legitimately needs it: a bare tool deny would remove
# the tool entirely.
SECRET_READ_DENIES: tuple[str, ...] = (
    "Read(**/.env)",
    "Read(**/.env.*)",
    "Read(*.env)",
    "Read(*.env.*)",
    "Read(~/.ssh/**)",
    "Read(~/.config/econ/**)",
    "Read(~/.claude/**)",
    "Read(~/.claude.json)",
    "Read(~/.config/anthropic/**)",
    "Read(~/.local/share/opencode/**)",
)

DANGEROUS_SHELL_DENIES: tuple[str, ...] = (
    "Bash(git push *)",
    "Bash(git reset --hard *)",
    "Bash(git clean *)",
    "Bash(git commit *)",
    "Bash(rm *)",
    "Bash(sudo *)",
    "Bash(su *)",
    "Bash(docker *)",
    "Bash(podman *)",
    "Bash(pip install *)",
    "Bash(uv *)",
    "Bash(curl *)",
    "Bash(wget *)",
    "Bash(ssh *)",
    "Bash(scp *)",
    "Bash(chmod *)",
    "Bash(chown *)",
)

# Whole tools that pipeline roles never get. Scoped command and path rules
# belong in permissions.deny; --disallowedTools removes the whole tool.
DISALLOWED_TOOLS: tuple[str, ...] = (
    "WebFetch",
    "WebSearch",
    "Agent",
    "Skill",
    "AskUserQuestion",
)


class ClaudeProtocolError(RuntimeError):
    pass


class PermissionMappingError(ValueError):
    pass


@dataclass
class ClaudeResult:
    text: str
    cost_usd: float
    tokens: int
    steps: int
    subtype: str | None = None
    is_error: bool = False
    denials: list[dict] = field(default_factory=list)


def _usage_tokens(event: dict) -> int:
    usage = event.get("usage") or {}
    if not isinstance(usage, dict):
        return 0
    total = 0
    for key in ("input_tokens", "output_tokens"):
        value = usage.get(key)
        if isinstance(value, int):
            total += value
    return total


def parse_claude_result(stdout: str) -> ClaudeResult:
    """Parse the final result object from `claude -p --output-format json`.

    The CLI normally emits one JSON object. We also accept a line-delimited
    stream because a future version or a wrapper may keep stream-json-like
    framing, and take the last result message.
    """
    payload = None
    text = stdout.strip()
    if text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            for line in text.splitlines():
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict) and event.get("type") == "result":
                    payload = event
    if payload is None:
        raise ClaudeProtocolError(
            "claude did not emit a JSON result object: " + (stdout[-800:] or "(empty)")
        )
    if payload.get("type") not in {None, "result"}:
        raise ClaudeProtocolError(
            f"claude emitted unexpected JSON type: {payload.get('type')!r}"
        )
    result_text = payload.get("result")
    if not isinstance(result_text, str):
        result_text = ""
    cost = payload.get("total_cost_usd", 0.0)
    if not isinstance(cost, (int, float)):
        cost = 0.0
    steps = payload.get("num_turns", 0)
    if not isinstance(steps, int):
        steps = 0
    denials = payload.get("permission_denials") or []
    if not isinstance(denials, list):
        denials = []
    denials = [item for item in denials if isinstance(item, dict)]
    subtype = payload.get("subtype")
    return ClaudeResult(
        text=result_text,
        cost_usd=float(cost),
        tokens=_usage_tokens(payload),
        steps=steps,
        subtype=subtype if isinstance(subtype, str) else None,
        is_error=bool(payload.get("is_error")),
        denials=denials,
    )


def _scoped(pattern: str, root: str | Path) -> str:
    value = pattern.strip()
    if value in {"", "."}:
        value = "**"
    if value.startswith("//") or value.startswith("~/"):
        return value
    if value.startswith("/"):
        # A single leading slash anchors at the settings source in Claude.
        # Our generated settings are not project settings, so make the anchor
        # explicit instead of relying on that rule.
        value = value.lstrip("/")
    if value.startswith("./"):
        value = value[2:]
    root_text = str(root).rstrip("/")
    return f"//{root_text}/{value}" if root_text else f"//{value}"


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def permission_policy(
    *,
    edit: list[str],
    shell: list[str],
    deny: list[dict],
    root: str | Path,
    read: list[str] | None = None,
    extra_read_denies: tuple[str, ...] = (),
    extra_edit_denies: tuple[str, ...] = (),
    extra_shell_denies: tuple[str, ...] = (),
    allow_read_allowlist: bool = False,
) -> dict:
    """Translate OpenCode-style permission intent into a Claude policy.

    The mapping is intentionally fail-closed. Claude cannot enforce a read
    allowlist the way OpenCode can, so a narrow read pattern is rejected
    unless the caller runs inside a workspace projection that physically
    limits what is visible.
    """
    read = list(read or [])
    if read and set(read) != {"**"} and not allow_read_allowlist:
        raise PermissionMappingError(
            "Claude cannot enforce a read allowlist outside a sandbox mount; "
            f"refusing to translate read={read!r}"
        )

    allows: list[str] = []
    for pattern in edit:
        allows.append(f"Edit({_scoped(pattern, root)})")
    for pattern in shell:
        allows.append(f"Bash({pattern})")

    denies: list[str] = [*SECRET_READ_DENIES]
    denies += [f"Read({_scoped('.git/**', root)})"]
    denies += [f"Edit({_scoped('.git/**', root)})"]
    denies += [f"Edit({_scoped('**/.git/**', root)})"]
    denies += [
        f"Edit({_scoped('.claude/**', root)})",
        f"Edit({_scoped('.mcp.json', root)})",
    ]
    denies += list(DANGEROUS_SHELL_DENIES)
    denies += list(extra_read_denies)
    denies += list(extra_edit_denies)
    denies += list(extra_shell_denies)

    unsupported: list[str] = []
    for entry in deny:
        if not isinstance(entry, dict):
            continue
        action = entry.get("action")
        resource = entry.get("resource")
        effect = entry.get("effect", "deny")
        if effect != "deny":
            unsupported.append(f"unsupported deny effect: {entry!r}")
            continue
        if not isinstance(resource, str):
            unsupported.append(f"unsupported deny resource: {entry!r}")
            continue
        if action == "read":
            denies.append(f"Read({_scoped(resource, root)})")
        elif action == "edit":
            denies.append(f"Edit({_scoped(resource, root)})")
        elif action == "shell":
            denies.append(f"Bash({resource})")
        else:
            unsupported.append(f"unsupported deny action: {action!r}")
    if unsupported:
        raise PermissionMappingError(
            "cannot translate permissions to Claude: " + "; ".join(unsupported)
        )

    tools = ["Read", "Grep", "Glob"]
    if edit:
        tools += ["Edit", "Write"]
    if shell:
        tools.append("Bash")

    settings = {
        "permissions": {
            "defaultMode": "dontAsk",
            "allow": _dedupe(allows),
            "deny": _dedupe(denies),
            "blockReadsOutsideWorkingDirectories": True,
            "disableBypassPermissionsMode": "disable",
            "disableAutoMode": "disable",
            "denyInsteadOfPrompting": True,
        }
    }
    return {
        "settings": settings,
        "tools": _dedupe(tools),
        "disallowed_tools": list(DISALLOWED_TOOLS),
        "unsupported": [],
    }


def claude_command(
    spec,
    system_prompt: str,
    user_prompt: str,
    settings_path: str | Path,
    *,
    cwd: str | Path,
    model_override: str | None = None,
    max_budget_usd: float | None = None,
    policy: dict | None = None,
) -> list[str]:
    model = model_override or getattr(spec, "claude_model", None)
    if not model:
        raise ValueError(f"{spec.name}: no Claude model configured")
    if "/" in model:
        raise ValueError(
            f"{spec.name}: {model!r} looks like an OpenCode selector, not a Claude model"
        )
    effort = getattr(spec, "claude_effort", None)
    if effort is not None and effort not in CLAUDE_EFFORTS:
        raise ValueError(
            f"{spec.name}: unsupported Claude effort {effort!r}; "
            f"choose one of {', '.join(CLAUDE_EFFORTS)}"
        )
    if policy is None:
        raise ValueError("claude_command requires a translated permission policy")
    argv = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--model",
        model,
        "--max-turns",
        str(getattr(spec, "steps", 12)),
        "--permission-mode",
        "dontAsk",
        "--permission-prompts",
        "none",
        "--restricted",
        "--no-session-persistence",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--tools",
        ",".join(policy["tools"]),
        "--disallowedTools",
        ",".join(policy["disallowed_tools"]),
        "--settings",
        str(settings_path),
        "--append-system-prompt",
        system_prompt,
    ]
    if effort:
        argv.extend(["--effort", effort])
    if max_budget_usd is not None and max_budget_usd > 0:
        argv.extend(["--max-budget-usd", f"{max_budget_usd:.2f}"])
    argv.append(user_prompt)
    return argv
