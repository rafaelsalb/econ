# Brazil Macro Model Hub

A reproducible research system for maintaining several macroeconomic models of
Brazil, scoring their forecasts on a common vintage-aware harness, and running a
critic loop that can revise or reject a model before it reaches the scoreboard.

The scientific core is deliberately boring: a **data layer with release dates**,
a **forecast registry**, and a **deterministic evaluator**. The models, the
critic loop, and the agent sandbox sit on top.

## Status

| Phase | Scope | State |
|---|---|---|
| 0 | Data layer, benchmark suite, registry, evaluator, leak and purge tests | **Complete** |
| 1 | New Keynesian QPM, frozen card, typed critics, loop, terminal decision | **Complete — `REJECTED`** |
| Sandbox | Configurable agent roster, Docker/bwrap, egress allowlist, audit | **Implemented; live critics ran** |
| 2 | Monetarist, Fiscal/FTPL, Post-Keynesian SFC models in parallel | **Complete — all `REJECTED` with reasons** |
| 3 | Ensemble, fan of schools, disagreement, one-time lockbox, final report | **Complete** |
| Dev team | Roster, deterministic pipeline, scheduler, canaries, Docker executor, workflows | **Complete — phases 0–4** |

All four school models were **rejected** on pre-registered validation gates. The
New Keynesian fired gap-significance, FX-sign and Focus value-added refutations;
the Monetarist failed the P-star channel; the FTPL was Ricardian; the SFC-lite
failed behavioral sign restrictions. The decisions are in
`specs/*.decision.json`.

The benchmark registry has **120 monthly validation origins** (2010-01 to
2019-12), **14,820 purged forecasts** with zero failures, led by the Focus
consensus. The Phase 3 ensemble is a diagnostic synthesis. In the one-time
lockbox (2020-01..2026-10), the combined performance ensemble beats Focus on
IPCA h=12 (ratio 0.857) and Selic h=12 (0.972); the Monetarist and AR models
also beat Focus on IPCA h=12, while the New Keynesian does not. The lockbox is
sealed in `registry/lockbox.json`; see `reports/final_report.md`.

## Architecture

```
data layer (vintage-aware, release dates)
    └─ benchmarks (RW, seasonal naive, AR, BVAR, IBC-Br bridge, Focus)
    └─ school models (New Keynesian QPM; Phase 2 adds more)
         └─ forecast registry (append-only, hashed)
              └─ evaluator (RMSE, Theil U, DM, MZ, Focus ratio, episodes)
                   └─ critic loop (typed defects, frozen card, binary gate)
                        └─ terminal decision (PASS / PASS_WITH_LIMITATIONS / REJECTED)
                             └─ optional sandboxed LLM advisory critics
```

The driver is deterministic. The loop applies a pre-registered revision ladder,
computes the gate, and records the terminal state. LLM agents are advisory:
they can add findings, but they cannot grant PASS or write to `src/`.

## Agent sandbox

The roster is defined in **`config/agents.yaml`** and rendered into native
OpenCode agents:

```bash
econ agents render          # writes .opencode/agents/econ-*.md
econ agents check           # fails if the rendered files drift
econ agents list
econ agents validate
```

Every role defaults to **`opencode-go/deepseek-v4.1-flash#max`**. The local
catalog exposes effort levels `low/high/max`; the renderer rejects an
unavailable variant at startup.

The sandbox is a Docker container with a **projected, minimal workspace**:

```
runs/sandbox/<run>/<role>-<id>/
  in/    # read-only: only the files this role may see
  out/   # writable: the role's result.json only
  home/  # writable home for the agent runtime
  logs/  # stdout, stderr, invocation.json (image, mounts, limits, hashes)
```

- Read-only root filesystem, non-root user, `--cap-drop=ALL`,
  `--no-new-privileges`, PID/memory/CPU limits, no Docker socket, no host home.
- `econ-internal` is a Docker `--internal` network with no external route. A
  dual-homed CONNECT proxy is the only bridge and allows only the model hosts
  (or BCB/IBGE for the librarian). TLS is not intercepted.
- `bwrap` is the fallback for filesystem/process isolation when Docker is not
  available; it has no network, so live model calls require Docker.

Smoke and boundary tests:

```bash
econ sandbox build
econ sandbox setup
econ sandbox smoke
```

Verified: `example.com` is blocked by the proxy, direct egress is blocked, the
input mount is read-only, the output mount is writable, `eval/` and the lockbox
are absent, and the container runs the full scientific stack.

**Live critics.** Both sandboxed critics ran against card v1.0.1 on 2026-11-24.
They agreed with the mechanical `REJECTED` and caught two advisory-packet
defects (a too-lenient gate file and satellite GDP leaking into the gate), both
fixed. They hit the old 8-step budget before writing JSON, so their full text is
preserved in `runs/loop/new_keynesian/advisory_live_v1.0.1/`; the budget is now
12 steps. The credential can come from `OPENCODE_API_KEY` or a mode-600 file:

```bash
mkdir -p ~/.config/econ
read -rsp "Paste OpenCode Go key: " KEY
printf '%s' "$KEY" > ~/.config/econ/opencode.key
unset KEY
chmod 600 ~/.config/econ/opencode.key
```

Then pass `--api-key-file ~/.config/econ/opencode.key` to `econ sandbox run` or
`econ loop --agents`. The key is set only in the sandbox process; the audit
records the variable name, never the key.

## Multi-agent development team

Development itself is automated by a second, separate roster. A deterministic
controller runs tasks through propose → implement → blind review → independent
verify → integrity gates → merge. Agents never commit, push, or merge; the
controller and the mechanical gates are the authority. Risk 3 changes always
escalate for human sign-off.

The loop in one line:

```
propose → review → promote → run → gates → merge (or escalate)
```

### Step 0 — one-time setup

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
make gate              # tests + econ check + roster drift + contract validation
econ dev doctor        # local environment: git, gh, opencode, model catalog
```

### Step 1 — propose a task contract

Interactive, with the PM agent:

```text
/dev/propose Fix the percent-sign formatting bug in report labels
```

`dev-pm` interviews you, inspects the relevant code, shows a task card, and
writes `tasks/proposed/DEV-0001.yaml` only after you confirm. It cannot edit
source, promote a contract, or run the controller. The command is defined in
`.opencode/commands/dev/propose.md`; if it does not appear in the picker (for
example right after a checkout that added it), run `/reload` — OpenCode
rebuilds the project's commands and agents.

Headless or hand-written:

```bash
econ dev new --title "Fix label formatting" \
  --goal "Labels render with a literal %; they must show the formatted value." \
  --acceptance "python -m pytest tests/test_labels.py -q" \
  --allow "src/econ/labels.py" --risk 1
cp tasks/templates/task.yaml tasks/proposed/DEV-0002.yaml   # or start from the template
```

A contract is runnable only if the acceptance criteria are executable commands
(no shell metacharacters), `scope.allow` names explicit paths, and the risk is
honest: **0** docs, **1** tests/refactor, **2** behavior change, **3**
protected/science. A task that needs a protected path is risk 3 by
construction and will escalate.

### Step 2 — review and promote

Read the contract the way you would read a PR: an observable goal, a
falsifiable acceptance command, and the smallest scope that can satisfy it.

```bash
econ dev validate tasks/proposed/DEV-0001.yaml   # schema, scope, commands
econ dev promote DEV-0001                        # validate, move to tasks/ready/
```

Promotion is a human step; no agent can do it. (Trusted GitHub issues are the
one exception — see [GitHub intake](#github-intake-optional).)

### Step 3 — dry run

```bash
econ dev run --task DEV-0001 --shadow   # full pipeline, never merges
econ dev run --task DEV-0001 --fake     # deterministic fake agents, no credits
```

Shadow mode gives you the gate evidence, cost, and rounds before anything
touches `main`.

### Step 4 — run it

```bash
econ dev run --task DEV-0001          # one task, auto-merge by policy
econ dev daemon --once --sync         # one scheduler tick
econ dev daemon --sleep 60 --sync     # long-running loop
econ dev pause --reason "review queue"  # kill switch
econ dev resume
```

The daemon selects `tasks/ready/` by priority, risk, and age, enforces file
scope claims (parallel workers never touch the same paths), keeps a daily
budget, and records every run under `runs/dev/tasks/<ID>/`. Bound a run with
`--max-parallel N`, `--daily-budget USD`, `--max-tasks N`; add
`--executor docker` for the container executor.

### Step 5 — watch

```bash
econ dev status                 # queue, active task, budget, lock, last tick
econ dev list                   # every contract and its status
econ dev report --write         # reports/dev_dashboard.{md,html}
econ dev report --digest --days 7
```

Each run directory holds `decision.json`, `gates-pre.json`, `gates-post.json`,
`patch.diff`, `events.jsonl`, and `cost.json`. Statuses: `done`, `shadow`,
`escalated`, `failed`, `awaiting_merge`.

### Step 6 — handle escalations

Escalated contracts move to `tasks/escalated/`; failed runs to
`tasks/failed/`. An escalation means a gate or the policy said "a human
decides":

- risk 3 (specs, data, registry, eval, sandbox, the lockbox, the controller,
  CI, the canary suite);
- a protected or merge-critical path in the diff;
- a dependency change, a coverage drop on changed sources, a size-cap or
  review-policy violation, a rebase conflict, or an exhausted round budget.

Read `decision.json` and the gate reports, then choose: accept the patch
(apply/merge it yourself) or reject it and fix the contract — smaller scope,
better acceptance, or split it. Never loosen a gate to make a task pass.
Re-queue by correcting the contract, setting `status: ready`, and moving it
into `tasks/ready/`.

### Step 7 — change models, prompts, and gates

```bash
econ dev agents list       # resolved model#variant for every role
econ dev agents render     # rewrite .opencode/agents/dev-*.md
econ dev agents check      # drift, reviewer-policy and family-divergence checks
econ dev agents validate   # model/variant resolution against the local catalog
```

Models and reasoning effort live only in `config/dev_agents.yaml`; prompts in
`config/prompts/dev/`; protected paths, auto-merge policy, budgets and gates
in `config/dev_policy.yaml`. Model choice is configuration, not code: the
suite asserts relationships (the second reviewer is a different family, the
policy pin matches the roster), not specific model IDs. After any prompt or
model change run the held-out suite:

```bash
econ dev canary --run --fake
```

A failed or budget-exhausted run writes a *proposed* regression canary to
`dev/evals/canary/proposed/`; curate it and promote it with
`econ dev canary --promote CANARY-004`. Nothing runs from `proposed/` until
then.

### Step 8 — maintain and release

```bash
econ dev maintenance --create-issue   # nightly gate: tests, checks, drift, contracts
econ dev release --bump patch --dry-run
econ dev release --bump patch
```

### GitHub intake (optional)

The issue form asks for goal, executable acceptance, risk, and scope. With
`github.auto_promote: true` and your handle in `trusted_authors`
(`config/dev_policy.yaml`), each daemon tick with `--sync` imports labeled
issues and promotes complete trusted contracts straight to `tasks/ready/`.
`econ dev sync --push` comments progress back and closes merged issues.

### What runs at each risk tier

| Risk | Typical change | Pipeline | Merge |
|---|---|---|---|
| 0 | docs, comments | implementer → verifier → gates | auto |
| 1 | tests, refactors | reproducer first for bug contracts → implementer → verifier → gates | auto |
| 2 | non-protected behavior | lead → architect → implementer → two reviewers on different families → verifier → science guard → gates + coverage delta | auto if no critical path, no coverage drop, ≤12 files / ≤400 lines |
| 3 | specs, data, registry, eval, sandbox, controller, CI, canaries | escalated before a worktree | human only |

Agents never commit, push, or merge — the controller does. The full operating
manual, policy rationale, and escalation artifacts are in
`docs/DEV_TEAM.md`.

## Quickstart

```bash
uv venv --python 3.12
uv pip install -e .
.venv/bin/python -m econ.cli ingest
.venv/bin/python -m econ.cli backtest --models all --start 2010-01-01 --end 2019-12-31
.venv/bin/python -m econ.cli score
.venv/bin/python -m econ.cli loop
.venv/bin/python -m econ.cli report
.venv/bin/python -m econ.cli ensemble
.venv/bin/python -m econ.cli lockbox open      # once only; seals the lockbox
.venv/bin/python -m econ.cli final-report
.venv/bin/python -m econ.cli check
```

With agents:

```bash
econ agents render
econ sandbox build
econ sandbox setup
econ sandbox smoke
econ sandbox run --role critic_fidelity --run-id review \
  --api-key-file ~/.config/econ/opencode.key \
  --input spec.yaml=specs/new_keynesian.yaml \
  --input defects.json=runs/loop/new_keynesian/round-1/defects.json \
  --input diagnostics.json=runs/loop/new_keynesian/round-1/diagnostics.json \
  --input src=src/econ \
  --packet "Review the model and return typed defects."
```

## Commands

| Command | Purpose |
|---|---|
| `econ ingest` | Fetch all catalog series and write curated parquet + manifest |
| `econ backtest` | Run models over monthly origins, purge targets after the window |
| `econ score` | Evaluate the latest run per model; scoreboard, Focus ratio, episodes |
| `econ loop` | Run the deterministic critic loop; `--agents` adds advisory LLM critics |
| `econ report` | Build the monthly report and fan chart |
| `econ check` | Run the Phase 0 / Phase 1 gates, including the purge check |
| `econ spec` | Validate and hash a model card |
| `econ audit --origin` | Print diagnostics for the NK model at an origin |
| `econ panel --origin` | Inspect an as-of data slice |
| `econ ensemble` | Equal/performance ensembles, weights, disagreement, fan chart |
| `econ lockbox open/status` | One-time lockbox evaluation; refuses a second open |
| `econ final-report` | Cross-phase report from the registry and evaluation files |
| `econ agents render/check/list/validate` | Manage the sandboxed research agent roster |
| `econ dev ...` | Development tasks, scheduler, canaries, dashboard, release |
| `econ sandbox build/setup/smoke/run` | Build and run the sandbox |

## What "state of the art" means here

The school supplies the identifying restrictions and the story. The econometrics
supplies the machinery: release-date-aware evaluation, purged out-of-sample
scoring, Diebold-Mariano tests against both the random walk and the Focus
consensus, Mincer-Zarnowitz calibration, density-ready registry columns, and
forecast combination later.

The NK model is a **semi-structural QPM**, not a full DSGE. Its card is explicit
about what is imposed and estimated. The validation record shows where it fails:
the gap channel is weak, the FX channel is wrong-signed, the policy rule implies
an 8% neutral nominal rate, and the inflation forecast is close to a Focus
anchor rather than independent information. That is why the terminal state is
`REJECTED`.

## Repo layout

```
catalog.yaml              series definitions and release lags
config/agents.yaml        single source of truth for the research agent roster
config/dev_agents.yaml    single source of truth for the development roster
config/dev_policy.yaml    protected paths, auto-merge policy, budgets, gates
config/prompts/           research role system prompts
config/prompts/dev/       development role system prompts
.opencode/agents/         rendered native agents (generated)
.opencode/commands/dev/   /dev/task, /dev/review, /dev/verify, ...
tasks/                    development task contracts (proposed/ready/done/...)
dev/evals/canary/         held-out pipeline canaries
src/econ/dev/             deterministic development controller
docs/DEV_TEAM.md          development team operating manual
opencode.jsonc            default model for interactive sessions
sandbox/                  Dockerfile, CONNECT proxy, network setup
data/raw/                 immutable API pulls
data/curated/             observations.parquet + manifest
specs/                    frozen model cards and loop decisions
src/econ/                 package
  sources.py              SGS, SIDRA, Focus adapters
  ingest.py               curation and release dates
  vintage.py              as-of panels (leakage boundary)
  targets.py              targets, 12m compounding, inflation targets
  models/                 benchmarks + new_keynesian
  evaluate.py             metrics, DM, MZ, Focus ratio, episodes
  registry.py             append-only forecasts and provenance
  diagnostics.py          residual/identification/stability checks
  critics.py              typed defects and refutation tests
  loop.py                 critic loop driver and advisory agent hook
  ensemble.py             equal/performance ensembles, disagreement, fan chart
  lockbox.py              one-time lockbox and final report
  agents.py               config renderer and selector validation
  sandbox.py              workspace projection, Docker/bwrap runner, audit
  report.py               monthly report and chart
tests/                    data, models, evaluation, loop gates, sandbox
docs/                     data, method, status notes
```

## Data caveats

Most Brazilian series do not have a public revision history through the APIs
used here. The data layer implements **pseudo-vintages**: observations are
filtered by `release_date`, derived from the reference period plus a publication
lag. This removes publication-timing look-ahead but not revision look-ahead.
Validation targets are purged at the validation end; the lockbox
2020-01..2026-10 is sealed.

## Non-goals

- A full DSGE estimated by Bayesian methods (Phase 2/3 candidate).
- A live trading or policy system.
- Claims of causal identification from the QPM.
- Treating an LLM critic as the gate. The mechanical evaluator decides.
