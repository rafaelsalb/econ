from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

from econ import config
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
