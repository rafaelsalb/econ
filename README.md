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
controller runs tasks through plan → implement → blind review → independent
verify → integrity gates → merge. Agents cannot merge, touch the lockbox, or
change the rules of the game. Risk 3 changes are always escalated.

In the interactive CLI, select `dev-pm` and run `/dev/propose ...` to interview
and draft a contract. Promotion is an explicit human step:

```bash
econ dev promote DEV-0001
```

```bash
econ dev validate --all --canaries
econ dev smoke --fake                 # full pipeline, no model credits
econ dev run --task DEV-0001 --fake   # one task end to end
econ dev daemon --once --max-parallel 2
econ dev report --write               # reports/dev_dashboard.html
```

The roster is `config/dev_agents.yaml`; tasks are YAML contracts in
`tasks/`; the policy and protected paths are in `config/dev_policy.yaml`.
The full operating manual is `docs/DEV_TEAM.md`.

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
