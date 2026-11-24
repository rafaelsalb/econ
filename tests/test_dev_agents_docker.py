from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import yaml

from econ.agents import (
    check_dev_all,
    dev_agents,
    load_dev_config,
    step_budget_problems,
    validate_dev_variants,
)
from econ.dev.docker import DockerRunner
from econ.dev.policy import DevPolicy, load_policy
from econ.dev.runner import OpencodeRunner, parse_opencode_events

from dev_support import make_repo


def test_dev_roster_is_rendered_and_complete():
    specs = {spec.name: spec for spec in dev_agents(load_dev_config())}
    assert {
        "lead",
        "pm",
        "architect",
        "implementer",
        "reviewer",
        "reviewer_alt",
        "verifier",
        "science_guard",
        "scribe",
        "triage",
        "reproducer",
    } <= set(specs)
    assert specs["lead"].mode == "primary"
    assert specs["lead"].hidden is False
    assert specs["pm"].mode == "primary"
    assert specs["pm"].hidden is False
    assert specs["implementer"].mode == "subagent"
    assert check_dev_all() == []


def test_dev_step_budgets_stay_within_policy_ceiling():
    policy = load_policy(Path(__file__).resolve().parent.parent)
    problems = step_budget_problems(
        dev_agents(load_dev_config()), policy.budget.max_agent_steps
    )
    assert problems == []


def test_step_budget_problems_flags_over_ceiling():
    specs = dev_agents(load_dev_config())
    pm = next(spec for spec in specs if spec.name == "pm")
    problems = step_budget_problems([replace(pm, steps=61)], 60)
    assert problems == ["pm: steps 61 exceeds budget.max_agent_steps 60"]


def test_pm_can_ask_questions_but_cannot_edit_source():
    from econ.agents import render_dev_all

    rendered = {
        path.name: text for path, text in render_dev_all().items()
    }
    front = yaml.safe_load(rendered["dev-pm.md"].split("---")[1])
    rules = front["permissions"]
    question_effects = [
        rule["effect"] for rule in rules if rule["action"] == "question"
    ]
    assert question_effects[-1] == "allow"
    edit_allows = {
        rule["resource"]
        for rule in rules
        if rule["action"] == "edit" and rule["effect"] == "allow"
    }
    assert ".dev/**" in edit_allows
    assert "tasks/proposed/**" in edit_allows
    assert "src/**" not in edit_allows
    assert "tasks/ready/**" not in edit_allows


def test_implementer_cannot_edit_protected_paths():
    rendered = {
        path.name: text for path, text in __import__("econ.agents", fromlist=["render_dev_all"]).render_dev_all().items()
    }
    text = rendered["dev-implementer.md"]
    front = yaml.safe_load(text.split("---")[1])
    denies = {
        (rule["action"], rule["resource"])
        for rule in front["permissions"]
        if rule["effect"] == "deny"
    }
    assert ("edit", "specs/**") in denies
    assert ("edit", "src/econ/evaluate.py") in denies
    assert ("edit", "config/dev_policy.yaml") in denies


def test_dev_variants_resolve_or_catalog_is_missing():
    problems = validate_dev_variants()
    assert not problems or all("catalog cache unavailable" in p for p in problems)


def test_reviewer_models_diverge_and_match_policy():
    specs = {spec.name: spec for spec in dev_agents(load_dev_config())}
    # Which model each role uses is configuration, not code: change
    # config/dev_agents.yaml, re-render, and this test keeps enforcing only
    # the relationships that are design rules.
    assert specs["reviewer"].model != specs["reviewer_alt"].model
    policy = load_policy(Path(__file__).resolve().parent.parent)
    assert policy.auto_merge.second_reviewer_model == specs["reviewer_alt"].model


def test_implementer_and_verifier_are_different_families():
    # The verifier is the real second opinion for risk 0/1; it must not share
    # the implementer's model family or it can inherit the same blind spots.
    specs = {spec.name: spec for spec in dev_agents(load_dev_config())}
    assert specs["implementer"].model != specs["verifier"].model


def test_reviewer_model_problems_flags_pin_drift():
    from econ.dev.policy import DevPolicy, reviewer_model_problems

    cfg = {
        "defaults": {"model": "opencode-go/deepseek-v4.1-flash"},
        "agents": {
            "reviewer": {"model": "opencode-go/deepseek-v4.1-flash"},
            "reviewer_alt": {"model": "opencode-go/gpt-6-luna"},
        },
    }
    policy = DevPolicy()
    policy.auto_merge.second_reviewer_model = "opencode-go/qwen3.8-max"
    assert any("second_reviewer_model" in problem for problem in reviewer_model_problems(cfg, policy))
    policy.auto_merge.second_reviewer_model = "opencode-go/gpt-6-luna"
    assert reviewer_model_problems(cfg, policy) == []
    cfg["agents"]["reviewer"]["model"] = "opencode-go/gpt-6-luna"
    assert any("different" in problem for problem in reviewer_model_problems(cfg, policy))


def test_opencode_argv_is_archived_and_auto():
    runner = OpencodeRunner(__import__("pathlib").Path("."))
    argv = runner.command("implementer", "do it")
    assert argv[:2] == ["opencode", "run"]
    assert "--archived" in argv
    assert "--auto" in argv
    assert "--agent" in argv and "dev-implementer" in argv
    assert "--format" in argv and "json" in argv


def test_opencode_runner_sets_pwd_to_the_worktree(tmp_path, monkeypatch):
    from pathlib import Path

    repo = make_repo(tmp_path / "repo")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    runner = OpencodeRunner(repo)
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["env"] = kwargs.get("env", {})
        captured["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = runner.run("lead", worktree, "hello")
    assert result.exit_code == 0
    assert captured["cwd"] == worktree
    assert captured["env"]["PWD"] == str(worktree.resolve())


def test_parse_opencode_events():
    lines = [
        json.dumps({"type": "text", "part": {"text": "hello"}}),
        json.dumps({"type": "step_finish", "cost": 0.01, "tokens": {"input": 3, "output": 4}}),
        json.dumps({"type": "step_finish", "cost": 0.02, "tokens": {"input": 1, "output": 2}}),
    ]
    text, cost, tokens, steps = parse_opencode_events("\n".join(lines))
    assert text == "hello"
    assert cost == 0.03
    assert tokens == 10
    assert steps == 2


def test_docker_command_is_hardened_and_mounts_worktree(tmp_path):
    repo = make_repo(tmp_path / "repo")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    runner = DockerRunner(repo, DevPolicy())
    cmd = runner.command("implementer", worktree, "do it")
    joined = " ".join(cmd)
    assert "--read-only" in cmd
    assert "--cap-drop=ALL" in joined
    assert "--security-opt no-new-privileges" in joined
    assert "--network econ-internal" in joined
    assert f"{worktree}:/workspace:rw" in joined
    assert "docker.sock" not in joined
    assert "opencode" in cmd and "run" in cmd
    assert "dev-implementer" in cmd


def test_docker_command_mounts_linked_worktree_metadata(tmp_path):
    from econ.dev.workspace import Worktree

    repo = make_repo(tmp_path / "repo")
    worktree = Worktree.create(repo, "DOCKER1", base="main")
    try:
        cmd = DockerRunner(repo, DevPolicy()).command(
            "reviewer", worktree.path, "review"
        )
        joined = " ".join(cmd)
        assert f"{repo / '.git'}:{repo / '.git'}:rw" in joined
        assert f"{worktree.path}:{worktree.path}:rw" in joined
    finally:
        worktree.remove()
