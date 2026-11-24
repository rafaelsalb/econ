from __future__ import annotations

import json
import os
from pathlib import Path

from econ.dev.models import Task
from econ.dev.policy import DevPolicy
from econ.dev.sync import GitHubClient, sync_pull, sync_push, task_from_issue
from econ.dev.tasks import TaskStore

from dev_support import make_repo


def _fake_gh(tmp_path: Path, issues: list[dict]) -> tuple[Path, Path]:
    list_file = tmp_path / "issues.json"
    log_file = tmp_path / "gh.log"
    list_file.write_text(json.dumps(issues))
    script = tmp_path / "gh"
    script.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "issue" ] && [ "$2" = "list" ]; then cat "$GH_LIST"; exit 0; fi\n'
        'if [ "$1" = "issue" ] && [ "$2" = "comment" ]; then echo "COMMENT $3 $5" >> "$GH_LOG"; exit 0; fi\n'
        'if [ "$1" = "issue" ] && [ "$2" = "close" ]; then echo "CLOSE $3" >> "$GH_LOG"; exit 0; fi\n'
        "exit 0\n"
    )
    script.chmod(0o755)
    os.environ["GH_LIST"] = str(list_file)
    os.environ["GH_LOG"] = str(log_file)
    return script, log_file


def _issue(number: int = 7, *, author: str = "alice") -> dict:
    body = """Here is the task.

```yaml
id: DEV-0007
title: Add a GitHub-imported feature
status: proposed
risk: 1
created: 2026-11-24
goal: Add a feature from an issue.
acceptance:
  - python -m pytest tests/test_issue.py -q
scope:
  allow:
    - src/econ/issue_feature.py
    - tests/test_issue.py
```
"""
    return {
        "number": number,
        "title": "Add a feature",
        "body": body,
        "labels": [{"name": "dev:ready"}, {"name": "risk:1"}],
        "author": {"login": author},
        "url": f"https://github.com/example/repo/issues/{number}",
    }


def test_task_from_issue_parses_fenced_yaml():
    policy = DevPolicy()
    task = task_from_issue(_issue(), policy)
    assert task.id == "DEV-0007"
    assert task.source.kind == "github"
    assert task.source.number == 7
    assert task.risk == 1


def test_sync_pull_imports_and_promotes_trusted_author(tmp_path):
    repo = make_repo(tmp_path / "repo")
    script, _ = _fake_gh(tmp_path, [_issue(author="alice")])
    policy = DevPolicy()
    policy.github.auto_promote = True
    policy.github.trusted_authors = ["alice"]
    store = TaskStore(repo)
    result = sync_pull(repo, policy, store, client=GitHubClient(repo, str(script)))
    assert result["imported"] == ["DEV-0007"]
    assert result["promoted"] == ["DEV-0007"]
    assert (repo / "tasks" / "ready" / "DEV-0007.yaml").exists()

    again = sync_pull(repo, policy, store, client=GitHubClient(repo, str(script)))
    assert again["imported"] == []
    assert again["skipped"][0]["reason"] == "already imported"


def test_sync_pull_keeps_untrusted_issue_proposed(tmp_path):
    repo = make_repo(tmp_path / "repo")
    script, _ = _fake_gh(tmp_path, [_issue(author="mallory")])
    policy = DevPolicy()
    policy.github.auto_promote = True
    policy.github.trusted_authors = ["alice"]
    store = TaskStore(repo)
    result = sync_pull(repo, policy, store, client=GitHubClient(repo, str(script)))
    assert result["imported"] == ["DEV-0007"]
    assert result["promoted"] == []
    assert (repo / "tasks" / "proposed" / "DEV-0007.yaml").exists()


def test_sync_push_comments_and_closes_done_issue(tmp_path):
    repo = make_repo(tmp_path / "repo")
    script, log = _fake_gh(tmp_path, [])
    policy = DevPolicy()
    store = TaskStore(repo)
    task = Task.model_validate(
        {
            "id": "DEV-0007",
            "title": "issue task",
            "status": "done",
            "risk": 1,
            "created": "2026-11-24",
            "goal": "done",
            "acceptance": ["python -m pytest -q"],
            "scope": {"allow": ["src/econ/feature.py"]},
            "source": {"kind": "github", "number": 7, "author": "alice"},
        }
    )
    store.save(task, status="done")
    result = sync_push(repo, policy, store, client=GitHubClient(repo, str(script)))
    assert result["updated"] == ["DEV-0007"]
    text = log.read_text()
    assert "COMMENT 7" in text
    assert "CLOSE 7" in text


def test_issue_without_yaml_is_rejected():
    policy = DevPolicy()
    try:
        task_from_issue({"number": 1, "title": "x", "body": "please do a thing"}, policy)
    except Exception as exc:  # noqa: BLE001
        assert "YAML task contract" in str(exc)
    else:
        raise AssertionError("expected rejection")
