from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from econ.agents import (
    agent_argv,
    agents,
    dev_agents,
    load_config,
    load_dev_config,
    validate_runtime_config,
)
from econ.claude_cli import (
    ClaudeProtocolError,
    PermissionMappingError,
    parse_claude_result,
    permission_policy,
)
from econ.dev.claude import ClaudeRunner
from econ.dev.docker import DockerRunner
from econ.dev.policy import DevPolicy
from econ.dev.runner import OpencodeRunner, RoutedRunner, runner_for


def _claude_specs() -> dict:
    return {
        spec.name: replace(
            spec,
            runtime="claude",
            claude_model="haiku",
            claude_effort="high",
        )
        for spec in dev_agents(load_dev_config())
    }


def test_parse_claude_result_success():
    payload = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "num_turns": 4,
        "total_cost_usd": 0.125,
        "usage": {"input_tokens": 100, "output_tokens": 25},
        "result": "done",
        "permission_denials": [],
    }
    parsed = parse_claude_result(json.dumps(payload))
    assert parsed.text == "done"
    assert parsed.cost_usd == 0.125
    assert parsed.tokens == 125
    assert parsed.steps == 4
    assert parsed.subtype == "success"
    assert parsed.is_error is False


def test_parse_claude_result_stream_and_max_turns():
    lines = [
        json.dumps({"type": "system", "subtype": "init"}),
        json.dumps(
            {
                "type": "result",
                "subtype": "error_max_turns",
                "is_error": True,
                "num_turns": 60,
                "total_cost_usd": 0.5,
                "usage": {"input_tokens": 10, "output_tokens": 2},
                "result": "",
                "errors": ["max turns reached"],
                "permission_denials": [{"tool_name": "Bash"}],
            }
        ),
    ]
    parsed = parse_claude_result("\n".join(lines))
    assert parsed.subtype == "error_max_turns"
    assert parsed.is_error is True
    assert parsed.steps == 60
    assert parsed.denials == [{"tool_name": "Bash"}]


def test_parse_claude_result_rejects_non_result():
    with pytest.raises(ClaudeProtocolError):
        parse_claude_result("not json")
    with pytest.raises(ClaudeProtocolError):
        parse_claude_result(json.dumps({"type": "system"}))


def test_permission_policy_is_fail_closed_on_read_allowlist(tmp_path):
    with pytest.raises(PermissionMappingError, match="read allowlist"):
        permission_policy(
            edit=["out/**"],
            shell=[],
            deny=[],
            root=tmp_path,
            read=["in/**"],
        )


def test_permission_policy_maps_paths_commands_and_secrets(tmp_path):
    translated = permission_policy(
        edit=["src/**", "Makefile"],
        shell=["python -m pytest *", "git status *"],
        deny=[{"action": "edit", "resource": "specs/**", "effect": "deny"}],
        root=tmp_path,
        read=["**"],
    )
    allow = translated["settings"]["permissions"]["allow"]
    deny = translated["settings"]["permissions"]["deny"]
    root = tmp_path.resolve()
    assert f"Edit(//{root}/src/**)" in allow
    assert f"Edit(//{root}/Makefile)" in allow
    assert "Bash(python -m pytest *)" in allow
    assert f"Edit(//{root}/specs/**)" in deny
    assert "Read(~/.claude/**)" in deny
    assert "Bash(rm *)" in deny
    assert f"Read(//{root}/.git/**)" in deny
    assert translated["tools"] == ["Read", "Grep", "Glob", "Edit", "Write", "Bash"]
    assert "WebFetch" not in translated["tools"]


def test_permission_policy_rejects_unknown_deny_action(tmp_path):
    with pytest.raises(PermissionMappingError, match="unsupported deny action"):
        permission_policy(
            edit=[],
            shell=[],
            deny=[{"action": "execute", "resource": "*", "effect": "deny"}],
            root=tmp_path,
        )


def test_claude_command_is_restricted_and_scoped(tmp_path):
    repo = tmp_path / "repo"
    worktree = tmp_path / "worktree"
    repo.mkdir()
    worktree.mkdir()
    runner = ClaudeRunner(repo, specs=_claude_specs())
    argv = runner.command("implementer", worktree, "do it")
    joined = " ".join(argv)
    assert argv[0] == "claude"
    assert "-p" in argv
    assert "json" in argv
    assert "--restricted" in argv
    assert "--permission-mode" in argv and "dontAsk" in argv
    assert "--permission-prompts" in argv and "none" in argv
    assert "--no-session-persistence" in argv
    assert "--strict-mcp-config" in argv
    assert "--dangerously-skip-permissions" not in argv
    assert "--max-turns" in argv and "60" in argv
    assert "--effort" in argv and "high" in argv
    assert "--append-system-prompt" in argv
    policy = runner.policy("implementer", worktree)
    allow = policy["settings"]["permissions"]["allow"]
    deny = policy["settings"]["permissions"]["deny"]
    root = worktree.resolve()
    assert f"Edit(//{root}/src/**)" in allow
    assert "Bash(python -m pytest *)" in allow
    assert f"Edit(//{root}/config/dev_policy.yaml)" in deny
    assert f"Edit(//{root}/.claude/**)" in deny
    assert "Read(~/.claude/**)" in deny
    assert "WebFetch" not in policy["tools"]


def test_claude_runner_writes_artifact_and_records_usage(tmp_path):
    repo = tmp_path / "repo"
    worktree = tmp_path / "worktree"
    repo.mkdir()
    worktree.mkdir()
    script = tmp_path / "fake-claude"
    script.write_text(
        "#!/bin/sh\n"
        "mkdir -p .dev/out\n"
        "printf '%s\\n' '{\"role\":\"implementer\",\"summary\":\"ok\","
        "\"files\":[],\"tests_added\":[],\"commands\":[],"
        "\"known_limitations\":[]}' > .dev/out/implementer.json\n"
        "printf '%s\\n' '{\"type\":\"result\",\"subtype\":\"success\","
        "\"is_error\":false,\"num_turns\":3,\"total_cost_usd\":0.01,"
        "\"usage\":{\"input_tokens\":10,\"output_tokens\":5},"
        "\"result\":\"done\",\"permission_denials\":[]}'\n"
    )
    script.chmod(0o755)
    runner = ClaudeRunner(repo, specs=_claude_specs(), executable=str(script))
    result = runner.run("implementer", worktree, "do it")
    assert result.exit_code == 0
    assert result.error == ""
    assert result.steps == 3
    assert result.cost_usd == 0.01
    assert result.tokens == 15
    assert result.text == "done"
    assert (worktree / ".dev" / "out" / "implementer.json").exists()
    assert "permissions" in result.request["settings"]
    assert result.request["runner"] == "claude"
    # The effective settings live outside the worktree so the agent cannot
    # rewrite its own permission policy and have Claude reload it.
    assert not (worktree / ".dev" / "claude" / "implementer-settings.json").exists()


def test_claude_runner_fails_closed_on_max_turns(tmp_path):
    repo = tmp_path / "repo"
    worktree = tmp_path / "worktree"
    repo.mkdir()
    worktree.mkdir()
    script = tmp_path / "fake-claude"
    script.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' '{\"type\":\"result\",\"subtype\":\"error_max_turns\","
        "\"is_error\":true,\"num_turns\":60,\"total_cost_usd\":0.2,"
        "\"usage\":{},\"result\":\"\",\"permission_denials\":[]}'\n"
    )
    script.chmod(0o755)
    runner = ClaudeRunner(repo, specs=_claude_specs(), executable=str(script))
    result = runner.run("implementer", worktree, "do it")
    assert result.exit_code == 1
    assert "error_max_turns" in result.error


def test_runtime_config_requires_a_claude_model():
    cfg = {
        "defaults": {"model": "opencode-go/deepseek-v4.1-flash"},
        "agents": {"implementer": {"runtime": "claude"}},
    }
    assert any(
        "requires claude_model" in problem
        for problem in validate_runtime_config(cfg)
    )


def test_runtime_config_rejects_headless_question_role():
    cfg = {
        "defaults": {
            "model": "opencode-go/deepseek-v4.1-flash",
            "claude_model": "haiku",
        },
        "agents": {
            "pm": {
                "runtime": "claude",
                "permissions": {"question": "allow"},
            }
        },
    }
    assert any(
        "question tool" in problem for problem in validate_runtime_config(cfg)
    )


def test_runner_for_auto_routes_by_role(tmp_path):
    specs = _claude_specs()
    specs["reviewer"] = replace(specs["reviewer"], runtime="opencode")
    repo = tmp_path / "repo"
    repo.mkdir()
    runner = runner_for(repo, "auto", specs=specs, cfg=load_dev_config())
    assert isinstance(runner, RoutedRunner)
    assert runner.runtime_for("implementer") == "claude"
    assert runner.runtime_for("reviewer") == "opencode"


def test_runner_for_forced_claude_rejects_missing_models(tmp_path):
    specs = _claude_specs()
    specs["implementer"] = replace(specs["implementer"], claude_model=None)
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError, match="without claude_model"):
        runner_for(repo, "claude", specs=specs, cfg=load_dev_config())


def test_runner_for_forced_runtime_rewrites_specs(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    forced = runner_for(
        repo, "opencode", specs=_claude_specs(), cfg=load_dev_config()
    )
    assert isinstance(forced, OpencodeRunner)
    assert {spec.runtime for spec in forced.specs.values()} == {"opencode"}
    claude = runner_for(
        repo, "claude", specs=_claude_specs(), cfg=load_dev_config()
    )
    assert isinstance(claude, ClaudeRunner)
    assert {spec.runtime for spec in claude.specs.values()} == {"claude"}


def test_docker_command_is_runtime_aware_for_claude(tmp_path):
    repo = tmp_path / "repo"
    worktree = tmp_path / "worktree"
    repo.mkdir()
    worktree.mkdir()
    fake_claude = tmp_path / "claude"
    fake_claude.write_text("#!/bin/sh\n")
    runner = DockerRunner(
        repo,
        DevPolicy(),
        specs=_claude_specs(),
        claude_bin=fake_claude,
        claude_auth=tmp_path / "missing-auth",
    )
    cmd = runner.command("implementer", worktree, "do it")
    joined = " ".join(cmd)
    assert "--read-only" in cmd
    assert "--cap-drop=ALL" in joined
    assert f"{worktree}:/workspace:rw" in joined
    assert f"{fake_claude}:/usr/local/bin/claude:ro" in joined
    assert "claude" in cmd
    assert "--agent" not in cmd
    assert "/workspace/.dev/claude/implementer-settings.json" in joined
    assert f"{worktree / '.dev' / 'claude'}:/workspace/.dev/claude:ro" in joined
    assert "--restricted" in cmd
    assert "--settings" in cmd
    assert "CLAUDE_CONFIG_DIR=/home/econ/.claude" in joined
    assert (worktree / ".dev" / "claude" / "implementer-settings.json").exists()


def test_research_claude_argv_uses_sandbox_settings(tmp_path):
    spec = next(spec for spec in agents(load_config()) if spec.name == "theorist")
    spec = replace(
        spec, runtime="claude", claude_model="haiku", claude_effort="high"
    )
    settings = tmp_path / "settings.json"
    argv = agent_argv(spec, "hello", settings_path=settings)
    assert argv[0] == "claude"
    assert "-p" in argv
    assert "--restricted" in argv
    assert "--settings" in argv and str(settings) in argv
    assert "--max-turns" in argv
    assert "--effort" in argv and "high" in argv
    assert "Bash" not in " ".join(
        argv[argv.index("--tools") + 1].split(",")
    )  # theorist has shell: []
