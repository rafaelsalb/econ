from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

from dataclasses import replace

from econ import config
from econ.agents import agents, load_config
from econ.sandbox import docker_command, project_workspace


def test_projection_rejects_paths_outside_repo():
    with pytest.raises(ValueError):
        project_workspace("t", "escape", inputs={"x": "../outside"})


def test_projection_is_minimal_and_read_only_view():
    ws = project_workspace(
        "t",
        "minimal",
        inputs={"spec.yaml": "specs/new_keynesian.yaml"},
        packet="hello",
    )
    try:
        assert (ws.inbox / "spec.yaml").exists()
        assert (ws.inbox / "packet.md").read_text() == "hello"
        assert not (ws.inbox / "eval").exists()
        assert not (ws.inbox / "registry").exists()
        assert list(ws.outbox.iterdir()) == []
        # The workspace projection physically excludes the lockbox and scores.
        assert not any(p.name == "scoreboard.csv" for p in ws.inbox.rglob("*"))
    finally:
        shutil.rmtree(ws.root, ignore_errors=True)


def test_docker_command_is_hardened():
    ws = project_workspace("t", "hardening")
    try:
        cmd, name, env = docker_command(
            ws, ["python", "-c", "print(1)"], network="offline"
        )
        joined = " ".join(cmd)
        assert "--read-only" in cmd
        assert "--cap-drop=ALL" in cmd
        assert "--security-opt no-new-privileges" in joined
        assert "--pids-limit 256" in joined
        assert "--memory 4g" in joined
        assert "--cpus 2" in joined
        assert "--network econ-internal" in joined
        assert f"{ws.inbox}:/workspace/in:ro" in joined
        assert f"{ws.outbox}:/workspace/out:rw" in joined
        assert "docker.sock" not in joined
        assert env["HTTPS_PROXY"].startswith("http://econ-proxy")
        assert env["NO_PROXY"] == "127.0.0.1,localhost"
    finally:
        shutil.rmtree(ws.root, ignore_errors=True)


def test_data_role_uses_data_network():
    ws = project_workspace("t", "data")
    try:
        cmd, _, env = docker_command(ws, ["true"], network="data")
        joined = " ".join(cmd)
        assert "--network econ-data-internal" in joined
        assert env["HTTPS_PROXY"].startswith("http://econ-data-proxy")
    finally:
        shutil.rmtree(ws.root, ignore_errors=True)


def test_claude_mounts_binary_and_ignores_opencode_roster(tmp_path, monkeypatch):
    import econ.sandbox as sandbox

    fake = tmp_path / "claude"
    fake.write_text("#!/bin/sh\n")
    real_which = sandbox.shutil.which
    monkeypatch.setattr(
        sandbox.shutil,
        "which",
        lambda name: str(fake) if name == "claude" else real_which(name),
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    spec = replace(
        next(spec for spec in agents(load_config()) if spec.name == "theorist"),
        runtime="claude",
        claude_model="haiku",
        claude_effort="high",
    )
    ws = project_workspace("t", "claude-mount")
    try:
        cmd, _, env = docker_command(
            ws, ["claude", "--version"], network="offline", spec=spec
        )
        joined = " ".join(cmd)
        assert f"{fake}:/usr/local/bin/claude:ro" in joined
        assert "/workspace/.opencode/agents" not in joined
        assert env["CLAUDE_CONFIG_DIR"] == "/home/econ/.claude"
        assert env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
    finally:
        shutil.rmtree(ws.root, ignore_errors=True)


def test_proxy_allowlist(monkeypatch):
    monkeypatch.setenv("ALLOW_HOSTS", "opencode.ai,models.dev")
    path = config.ROOT / "sandbox" / "proxy.py"
    spec = importlib.util.spec_from_file_location("econ_proxy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.allowed("opencode.ai")
    assert module.allowed("models.opencode.ai")
    assert module.allowed("models.dev")
    assert not module.allowed("example.com")
    assert not module.allowed("evilopencode.ai")
