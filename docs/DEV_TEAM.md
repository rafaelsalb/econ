# Multi-agent development team

The development team is a deterministic pipeline, not a free-form agent swarm.
Agents produce typed role artifacts; a Python controller owns state, gates,
budgets, and merging. This mirrors the research loop: the driver is
deterministic, the LLM is advisory.

## Why this shape

A multi-agent system fails when agents negotiate with each other. It works when:

- each role has a narrow input packet and a typed output artifact;
- a fresh session gives reviewers no shared context with the implementer;
- tests, policy checks, and protected paths decide whether work advances;
- the scheduler, not an agent, merges;
- every action is recorded under `runs/dev/`.

The controller lives in `src/econ/dev/`. The agent definitions live in
`config/dev_agents.yaml` and `config/prompts/dev/`; rendered files in
`.opencode/agents/dev-*.md` are generated and must not be hand-edited.

## Roster

| Agent | Mode | Job |
|---|---|---|
| `dev-pm` | primary | Interview the human, draft a proposed contract, validate it, hand off; never edits code or merges |
| `dev-lead` | primary | Plan, set risk, dispatch for risk ≥ 2; never edits code |
| `dev-architect` | subagent | Design, interface and test plan for risk ≥ 2 |
| `dev-implementer` | subagent | Smallest patch plus a red-green test, on Claude Haiku at `xhigh` |
| `dev-reviewer` | subagent | Blind diff review on `deepseek-v4.1-flash#max`, risk ≥ 2 only |
| `dev-reviewer_alt` | subagent | Independent second review for risk 2 on `gpt-6-luna#xhigh` |
| `dev-verifier` | subagent | Applies the patch to a clean worktree and runs acceptance, on `deepseek-v4.1-flash#max` |
| `dev-science_guard` | subagent | Protected paths, purge, lockbox, registry, determinism; risk ≥ 2 only |
| `dev-scribe` | subagent | Docs only, after approval |
| `dev-triage` | subagent | Turns a GitHub issue into a task contract |
| `dev-reproducer` | subagent | Turns a bug contract into a failing test before any fix |

Role routing is by risk tier: risk 0/1 runs intake → reproducer (bug-sourced
contracts only) → implementer → verifier → gates; the lead, architect,
reviewers, and science guard are risk ≥ 2 controls. The gates and the blind
clean-tree verification run for every tier.

The canary suite grows from real failures: a failed run or a budget-exhausted
escalation writes a *proposed* canary under `dev/evals/canary/proposed/`;
a human curates the demo fixture and promotes it with `econ dev canary
--promote`. Nothing runs from `proposed/` until then.

## Model and runtime configuration

Runtime, models and reasoning effort live only in `config/dev_agents.yaml`
(per-agent `runtime`, `model`/`variant`, `claude_model`/`claude_effort`; the
`defaults` block is the fallback). To change one:

1. Edit `runtime` and the model/effort for the role.
2. Run `econ dev agents render` then `econ dev agents check`.
3. `econ dev agents list` prints the resolved runtime and selector for every
   role.

`runtime: opencode` uses `opencode run`; `runtime: claude` uses the Claude Code
CLI (`claude -p`). The two model namespaces are deliberately separate: an
OpenCode selector is never silently translated into a Claude model, and a
Claude role without `claude_model` fails validation. `econ dev run --runner
{auto,opencode,claude}` overrides the per-role choice for one run.

The Claude runner is not a full OpenCode permission clone. It translates the
config intent into a generated `--settings` policy with `dontAsk` default-deny,
`--restricted`, no project/user settings, no MCP, no skills, and a tools
allowlist. Scoped Edit/Bash allows come from the role's `edit`/`shell` lists;
secret files and dangerous commands are denied. A read allowlist cannot be
expressed in Claude, so a local role with a narrow `read` pattern is refused
rather than silently widened; the research sandbox relies on its mounts
instead. The Docker executor remains the real OS boundary. The generated
settings file is kept outside the worktree (or mounted read-only in Docker) so
an agent cannot rewrite its own policy and have Claude reload it.

Runtime smoke checks on 2026-11-24 used Haiku at `high`: a live Claude write to
`.dev/out` succeeded, a write to `specs/evil.txt` was denied with a
`permission_denials` record, and a fake-Claude Docker run wrote the artifact
without leaking the settings file into the worktree. The research sandbox was
exercised with the same fake-Claude path through the read-only inbox settings
mount.

`econ dev agents check` also enforces the cross-file reviewer relationship:
`auto_merge.second_reviewer_runtime` and `second_reviewer_model` in
`config/dev_policy.yaml` must match `reviewer_alt`, and `reviewer_alt` must use
a different runtime/model identity from `reviewer`. The test suite asserts
those relationships, not specific model IDs, so a model or runtime swap is a
configuration edit, not a code change.

Current pins: implementer Claude Haiku at `xhigh` through the Claude runner
(the OpenCode selector remains `gpt-6-luna#xhigh` for interactive sessions);
verifier `deepseek-v4.1-flash#max` on OpenCode (different family from the
implementer, so a blind check is not a shared blind spot); reviewer_alt
`gpt-6-luna#xhigh` on OpenCode, the second family against the `deepseek`
reviewer; everything else `deepseek-v4.1-flash#max` except triage and scribe on
`glm-5.3-flash`. The roster default for a Claude role is Haiku at `high`; raise
effort only within the review budget and keep the second reviewer on a
genuinely different runtime/model.

Research agents (`econ-*`) remain advisory and sandboxed. They are not part of
this roster. The research sandbox mounts only `econ-*.md`, so development agents
are not visible inside it. Research roles also accept `runtime: claude` in
`config/agents.yaml`; the sandbox mounts the Claude binary/credential instead
of OpenCode and passes a generated read-only settings file. The mechanical
evaluator remains the authority in either case.

## The human front door

In the interactive OpenCode CLI, select `dev-pm` and run:

```text
/dev/propose Fix the percent-sign formatting bug in labels
```

`dev-pm` interviews you, inspects the relevant code, shows a compact task card,
and writes a validated contract to `tasks/proposed/` only after confirmation.
It cannot edit source, move a task to `ready/`, or run the controller.

The handoff is explicit:

```bash
econ dev promote DEV-0002          # validate, move proposed → ready
econ dev run --task DEV-0002 --shadow
econ dev run --task DEV-0002
```

`econ dev promote` is the human promotion step. It is deliberately separate from
agent authoring, so no model can silently queue a runnable task.

One exception, stated honestly: with `github.auto_promote: true` (owner
decision, 2026-11-24), the scheduler imports labeled issues each tick and
promotes complete contracts from trusted authors straight into `ready/`
without a human click. Local and `dev-pm` contracts always need `econ dev
promote`; trusted GitHub intake does not. Turn the flag off in
`config/dev_policy.yaml` if that is not what you want.

## What this system is, and is not

The development team automates **engineering chores under policy**: tests,
refactors, tooling, CI, docs, and small behavior changes in non-protected
code, with gates as the authority and agents advisory. It does not do
research. Model revisions go through each card's pre-registered revision
ladder and the critic loop; specs, the validation window, the lockbox, the
registry, and ensemble selection are risk 3 and human-gated. No development
agent can alter a scientific verdict, and no dev-agent path reaches the
lockbox or the registry history. The ceiling is deliberate: a disciplined
junior engineer with perfect auditability, not a co-researcher.

## Task contract

A runnable task is a YAML contract under `tasks/ready/`:

```yaml
id: DEV-0001
title: ...
status: ready
risk: 1
priority: 50
created: 2026-11-24
goal: |
  Observable behavior that must be true.
acceptance:
  - python -m pytest tests/test_example.py -q
scope:
  allow: ["src/econ/example.py", "tests/test_example.py"]
  deny: ["specs/**", "data/**", "registry/**", "eval/**"]
limits: {max_review_rounds: 2, max_usd: 5, max_changed_files: 10, max_diff_lines: 400}
```

Acceptance commands are parsed and executed without a shell. Shell
metacharacters are rejected, so an imported issue cannot smuggle a second
command. `scope.allow` must name explicit paths; `**` is rejected. A task that
needs a protected path is risk 3.

Risk tiers: 0 docs, 1 tests/refactor, 2 behavior, 3 protected/science. The
protected set includes the referee itself — `src/econ/dev/**`,
`.github/workflows/**`, `tests/dev_support.py`, `tasks/templates/task.yaml`,
`dev/evals/canary/**` — so the pipeline cannot silently rewrite the controller,
the CI that verifies auto-merges, or the canaries that calibrate it.

## State machine

```
READY → PLAN → IMPLEMENT → REVIEW → VERIFY → POST-GATES → INTEGRITY → MERGE → DONE
                    ↑          │        │
                    └─ changes ┘        └─ blocked → ESCALATED
```

- Each task gets a branch and worktree from a frozen base commit.
- The implementer commits through the controller, not its own git commands.
- The reviewer sees the diff and test evidence, not the implementer's rationale.
- The verifier runs in a *fresh* worktree at the patch commit.
- The controller applies deterministic gates; a green agent opinion is not
  enough.
- Merge is a serial queue. The branch is rebased onto `main` and the full gate
  is rerun before a fast-forward merge.
- Max two review rounds plus one mechanical repair attempt; then a human gets
  an escalation. A pre-gate failure (size, acceptance, full tests) is a repair,
  not a review, so it does not consume the second review round. The bound is
  `budget.max_repair_rounds` (default 1) in `config/dev_policy.yaml`.
- Size limits are hard gates. `max_diff_lines` counts added + deleted lines for
  the whole branch diff, including tests and templates. Leave headroom for one
  review fix, and split the task rather than tightening the budget below the
  natural size of the change.

## Gates

| Gate | What it proves |
|---|---|
| `patch` / `patch_apply` | non-empty and applies to a clean base |
| `scope` | every changed file is explicitly allowed |
| `protected` | no protected path is touched: science contract or merge authority |
| `critical_paths` | merge-critical blast radius forces human sign-off regardless of diff size |
| `dependencies` | dependency changes need human sign-off |
| `secrets` | no key-like strings in the diff |
| `size` | task and policy limits |
| `tests_present` | behavior changes include tests |
| `acceptance` | the task's commands pass |
| `full_tests` | no regression in the suite |
| `red_green` | new tests fail on the base commit |
| `coverage_delta` | changed sources do not lose test coverage (pytest-cov, risk 2) |
| `econ_check` | vintage/purge/registry gates still pass |
| `agents_check` | generated research roster is current |
| `dev_agents_check` | generated development roster is current |
| `dev_validate` | every task contract in the worktree is valid |
| `lockbox` | one-time ledger unchanged |
| `registry_append_only` | no historical registry mutation |

`red_green` is the anti-reward-hacking gate: a new test that already passes on
the base commit proves nothing.

## Autonomy policy

`config/dev_policy.yaml`:

- risk 0/1: auto-merge after gates and blind verification; no lead, no
  reviewers — the deterministic gates are the authority;
- risk 2: two independent approvals on different models, no critical path,
  no coverage drop on changed sources; the ≤12-file / ≤400-line caps are a
  secondary guard, not the blast-radius rule;
- risk 3: always escalated for human sign-off; never auto-merged.

The controller enforces this from structured gate results, not from prose.

## Commands

```bash
econ dev validate --all --canaries
econ dev list
econ dev promote DEV-0001                  # human promotion: proposed → ready
econ dev run --task DEV-0001 --fake        # deterministic local pipeline
econ dev run --task DEV-0001               # configured runtime (opencode/claude)
econ dev run --task DEV-0001 --runner claude  # force Claude for this run
econ dev run --task DEV-0001 --shadow      # run everything, never merge
econ dev daemon --once --max-parallel 2    # one scheduler tick
econ dev daemon --max-parallel 2           # continuous scheduler
econ dev pause --reason "review queue"     # stop picking new work
econ dev resume
econ dev status
econ dev report --write                    # reports/dev_dashboard.{md,html}
econ dev report --digest --days 1
econ dev sync --pull --promote             # GitHub issues → task contracts
econ dev sync --push                       # status back to issues
econ dev canary --run --fake               # held-out pipeline evaluation
econ dev canary --promote CANARY-004        # human step: curate, then promote
econ dev smoke --fake                      # one end-to-end fake-agent run
econ dev maintenance --create-issue        # nightly deterministic gate
econ dev release --bump patch --dry-run
econ dev doctor
```

`make gate` runs tests, `econ check`, research and development roster drift, and
`dev validate --all`. CI runs the same command.

## Worktrees, container executor, and budgets

- Local executor: `git worktree` per task under a sibling
  `.<repo>-worktrees/` directory. Worktrees are deliberately outside the
  checkout so OpenCode cannot resolve the project root back to `main`.
- Local agents run with a private OpenCode server (`--standalone`) so the
  project root is pinned to the worktree, not the main checkout. Without it a
  shared server can resolve edits back to `main`.
- Docker executor: `econ dev run --task ... --executor docker` uses
  `econ-agent:latest`, mounts only the worktree read-write, uses the worktree's
  committed agents/config, drops all capabilities, uses the internal proxy
  network, and keeps the worktree home in `.dev/home`.
- Budgets: per-task `limits.max_usd`, daily `budget.daily_usd`, and a hard stop
  in `_record_agent`. The ledger is `runs/dev/budget.json`.
- Scheduler locks: `runs/dev/.daemon.lock`, merge lock
  `runs/dev/.merge.lock`, pause switch `runs/dev/PAUSED`.

## Artifacts

```
runs/dev/tasks/<task-id>/
  task.yaml / task.sha256
  state.json
  events.jsonl
  packets/latest.md
  out/{lead,architect,implementer,review-*,verifier,science_guard}.json
  patch.diff
  test-report.json
  gates-pre.json / gates-post.json / gates-merge.json
  cost.json
  decision.json
  error.json            # on failure
runs/dev/index.jsonl    # append-only outcome ledger for metrics
runs/dev/canaries/      # held-out canary results (latest.json, index.jsonl)
reports/dev_canaries.md # human-readable canary evidence
reports/dev_dashboard.{md,html}
```

`runs/` is gitignored. The dashboard and task files are the durable record.

## GitHub intake

Issues labeled `dev:ready` may contain a fenced YAML task contract. `sync
--pull` imports it as `proposed`; with `github.auto_promote: true` and an author
in `trusted_authors`, it goes straight to `ready`. The issue body is untrusted
data: only the YAML contract fields are used, and shell metacharacters are
rejected. `sync --push` comments status back and closes the issue on `done`.

## Scheduled automation

- `.github/workflows/dev-daemon.yml` runs a scheduler tick every six hours and
  on `dev:ready` labels; it imports issues, runs up to two workers, and commits
  the dashboard and task state.
- `.github/workflows/dev-maintenance.yml` runs the deterministic gate daily and
  opens an issue on failure. It never generates a ready task automatically.
- `.github/workflows/release.yml` is manual and deterministic; it bumps the
  version, updates `CHANGELOG.md`, runs the gate, commits, and tags.

Required repository secret: `OPENCODE_API_KEY`. The daemon workflow also uses
the default `GITHUB_TOKEN` with `contents: write` and `issues: write`.

## What is deliberately not automated

- Changing `specs/`, validation gates, data semantics, the lockbox, or the
  sandbox boundary. A risk 3 task is escalated.
- Reopening the lockbox or rewriting `registry/`.
- Release pushes without a human workflow dispatch.
- Accepting a task whose acceptance criteria are prose.

Those are the rules of the game; automating them away would invalidate the
research claims.
