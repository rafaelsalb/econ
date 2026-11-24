from __future__ import annotations

import os

import yaml

from econ.agents import (
    agent_argv,
    agents,
    check_all,
    load_config,
    render_all,
    validate_variants,
)
from econ.cli import _load_api_key
from econ.diagnostics import Defect
from econ.loop import _modeler_view


def test_all_roles_present():
    names = {a.name for a in agents(load_config())}
    assert names == {
        "theorist",
        "modeler",
        "critic_fidelity",
        "critic_adequacy",
        "librarian",
    }


def test_default_model_and_max_variant():
    for spec in agents(load_config()):
        assert spec.model == "opencode-go/deepseek-v4.1-flash"
        assert spec.variant == "max"
        assert spec.selector.endswith("#max")


def test_render_is_deterministic():
    first = render_all()
    second = render_all()
    assert first == second


def test_generated_files_are_current():
    assert check_all() == []


def test_permissions_are_deny_by_default():
    rendered = render_all()
    theorist = next(text for path, text in rendered.items() if "theorist" in path.name)
    front = yaml.safe_load(theorist.split("---")[1])
    perms = front["permissions"]
    assert perms[0] == {"action": "*", "resource": "*", "effect": "deny"}
    assert any(
        p["action"] == "read" and p["resource"] == "in/**" and p["effect"] == "allow"
        for p in perms
    )
    assert any(
        p["action"] == "edit" and p["resource"] == "out/**" and p["effect"] == "allow"
        for p in perms
    )
    assert not any(
        p["action"] == "shell" and p["effect"] == "allow" for p in perms
    )
    assert front["mode"] == "all"
    assert front["hidden"] is True


def test_modeler_has_limited_shell():
    rendered = render_all()
    modeler = next(text for path, text in rendered.items() if "modeler" in path.name)
    front = yaml.safe_load(modeler.split("---")[1])
    shell_allows = [
        p["resource"]
        for p in front["permissions"]
        if p["action"] == "shell" and p["effect"] == "allow"
    ]
    assert shell_allows == ["python -m pytest *", "python -m econ.models.*"]


def test_agent_argv():
    spec = agents(load_config())[0]
    argv = agent_argv(spec, "hello")
    assert argv[:2] == ["opencode", "run"]
    assert "--agent" in argv and f"econ-{spec.name}" in argv
    assert "--model" in argv and spec.selector in argv
    assert "--format" in argv and "json" in argv


def test_variants_resolve():
    assert validate_variants() == []


def test_modeler_packet_redacts_scores():
    d = [
        Defect(
            "D5",
            "medium",
            "gdp_qq h=1 loses to random walk (Theil U=1.164)",
            {"target": "gdp_qq", "horizon": 1, "theil_u": 1.164},
        )
    ]
    view = _modeler_view(d)[0]
    assert view["evidence"] == {"target": "gdp_qq", "horizon": 1, "gate": "fail"}
    assert "1.164" not in view["message"]


def test_api_key_file_sets_env(tmp_path, monkeypatch):
    key = tmp_path / "opencode.key"
    key.write_text("dummy-key\n")
    key.chmod(0o600)
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    _load_api_key(str(key))
    assert os.environ["OPENCODE_API_KEY"] == "dummy-key"
