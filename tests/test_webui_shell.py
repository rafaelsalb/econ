from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

import econ.webui.app as webui_app
from econ import cli
from econ.webui import create_console_app


def _snapshot(root: Path) -> dict[str, tuple[bytes | None, int]]:
    return {
        str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None, p.stat().st_mtime_ns)
        for p in root.rglob("*")
    }


def _invoke_console(monkeypatch, *argv: str) -> tuple[tuple, dict]:
    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: calls.append((a, kw)))
    monkeypatch.setattr(sys, "argv", ["econ", "console", *argv])
    cli.main()
    assert len(calls) == 1
    return calls[0]


def test_app_factory_returns_fastapi_and_module_app_exists(tmp_path):
    assert isinstance(create_console_app(), FastAPI)
    assert isinstance(webui_app.app, FastAPI)
    assert create_console_app(tmp_path).state.repo == tmp_path


def test_overview_renders_console_title():
    response = TestClient(create_console_app()).get("/")
    assert response.status_code == 200
    assert "econ console" in response.text
    assert "later contracts" in response.text


def test_healthz_returns_ok_json():
    response = TestClient(create_console_app()).get("/healthz")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"ok": True}


def test_get_does_not_create_or_modify_repo(tmp_path):
    (tmp_path / "keep.txt").write_text("unchanged")
    before = _snapshot(tmp_path)
    client = TestClient(create_console_app(tmp_path))
    assert client.get("/").status_code == 200
    assert client.get("/healthz").status_code == 200
    assert _snapshot(tmp_path) == before


def test_console_command_defaults_to_loopback_8100(monkeypatch):
    args, kwargs = _invoke_console(monkeypatch)
    assert args[0] is webui_app.app
    assert kwargs == {"host": "127.0.0.1", "port": 8100}


def test_console_command_honors_host_and_port(monkeypatch):
    args, kwargs = _invoke_console(monkeypatch, "--host", "0.0.0.0", "--port", "9001")
    assert args[0] is webui_app.app
    assert kwargs == {"host": "0.0.0.0", "port": 9001}


def test_cmd_console_passes_app_host_and_port(monkeypatch):
    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: calls.append((a, kw)))
    cli.cmd_console(SimpleNamespace(host="127.0.0.1", port=8100))
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] is webui_app.app
    assert kwargs == {"host": "127.0.0.1", "port": 8100}
