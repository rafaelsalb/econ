# Development tasks

A task is a frozen YAML contract. Put runnable tasks in `ready/`; the scheduler
only picks those. `proposed/` holds issues that have not been promoted yet.

Required fields:

```yaml
id: DEV-0001
title: ...
status: proposed        # proposed | ready | active | done | escalated | failed | shadow
risk: 1                 # 0 docs, 1 tests/refactor, 2 behavior, 3 protected/science
priority: 50
created: 2026-11-24
goal: |
  What must be true when this is done.
acceptance:
  - python -m pytest tests/test_example.py -q
scope:
  allow: ["src/econ/example.py", "tests/test_example.py"]
  deny: ["specs/**", "registry/**"]
limits:
  max_review_rounds: 2
  max_usd: 5
  max_changed_files: 10
  max_diff_lines: 400
```

Limits are hard gates. `max_diff_lines` counts added + deleted lines for the
whole branch diff, including tests and templates. Leave headroom for at least
one review-fix cycle; for risk 2, prefer the policy auto-merge cap (400) or
split the task. `max_changed_files` should be above the number of entries in
`scope.allow`. `econ dev validate` warns when a risk-2 line cap is below the
policy cap or the file cap has no headroom.

Rules:

- Acceptance criteria are executable commands, never prose. Shell metacharacters
  are rejected so an imported issue cannot smuggle a second command.
- `scope.allow` must name the paths. `**` is rejected.
- If the change needs a protected path, set `risk: 3`; the scheduler escalates it
  for human sign-off instead of implementing it autonomously.
- A behavior change needs a test that fails on the base commit and passes on the
  patch. The controller enforces this.
- `demo` is only for the deterministic fake runner used by tests, smoke runs, and
  canaries. Real agents ignore it.

## Agent step budgets

`steps` in `config/dev_agents.yaml` is a **per-turn** cap on model steps, not a
session budget. On the final step OpenCode removes tools and asks the agent to
summarize. The `question` tool does not reset the allowance; a new user prompt
does. Keep every dev agent at or below `budget.max_agent_steps` in
`config/dev_policy.yaml`; `econ dev agents check` enforces the ceiling. Each task
records `runs/dev/tasks/<id>/steps.json`, and the dashboard shows the highest
utilization plus any step-limited runs.

Authoring in the interactive CLI:

```text
/dev/propose Fix the percent-sign formatting bug in labels
```

`dev-pm` writes to `tasks/proposed/`. Promotion to the runnable queue is a
separate human step:

```bash
econ dev promote DEV-0001
econ dev validate DEV-0001
```

Commands:

```bash
econ dev validate --all
econ dev list
econ dev promote DEV-0001
econ dev run --task DEV-0001
econ dev run --task DEV-0001 --shadow
econ dev daemon --once
```
