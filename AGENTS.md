# Project instructions

This is a Brazil macro model hub. The scientific core is a release-date-aware
data layer, an append-only forecast registry, and a deterministic evaluator. The
models, critic loop, and agent sandbox sit on top. All four school models are
currently `REJECTED`; the ensemble and lockbox results are diagnostic, not a
rescue.

Read `README.md` for the architecture and `docs/METHOD.md`, `docs/DATA.md`, and
`docs/STATUS.md` for the scientific rules. The development controller is
documented in `tasks/README.md`.

## Commands

- Install only if `.venv/` is missing: `uv venv --python 3.12 && uv pip install -e ".[dev]"`
- All tests: `.venv/bin/python -m pytest -q`
- One test: `.venv/bin/python -m pytest tests/test_registry.py::test_forecast_schema -q`
- Scientific gates: `.venv/bin/python -m econ.cli check`
- Research roster drift: `.venv/bin/python -m econ.cli agents check`
- Full local gate: `make gate` (tests + `econ check` + agent drift + `econ dev` validation)
- Lighter local pair: `make all` (tests + `econ check`). CI runs `make gate PY=python`.

The development controller puts the worktree `src/` on `PYTHONPATH` and the main
`.venv/bin` first on `PATH`. Do not create a second virtualenv inside a worktree.

## Scientific invariants

- Validation is 2010-01..2019-12. The lockbox is 2020-01..2026-10 and is sealed
  in `registry/lockbox.json`. Never run `econ lockbox open`: a second open is
  refused and `--force` would overwrite the one-time ledger. Do not run
  `econ score --lockbox` or use lockbox outcomes for model selection.
- `econ.vintage.Panel` is the only sanctioned data access path. It exposes rows
  with `release_date <= origin`; models must never join realized outcomes.
  `evaluate.realized_table` owns outcome joins.
- Validation targets are purged at the window end (`embargo_until`). No
  `ref_date` after the validation window may reach a forecast.
- Data are **pseudo-vintages**: `release_date = period_end + catalog
  release_lag_days`, not a revision archive. Do not claim real-time or
  revision-aware vintages.
- `specs/*.yaml` model cards and `specs/*.decision.json` are pre-registered
  artifacts. Treat `registry/` as append-only: never modify or delete past run
  directories or `runs.jsonl`.
- A model change goes through the card's pre-registered revision ladder and the
  critic loop, not through a direct code edit by a development agent.
- Protected paths (full list in `config/dev_policy.yaml`): `specs/**`, `data/**`,
  `registry/**`, `eval/**`, `sandbox/**`, `reports/final_report.md`,
  `reports/lockbox_report.md`, `config/dev_policy.yaml`, `config/dev_agents.yaml`,
  the gate modules `src/econ/{evaluate,critics,diagnostics,loop,lockbox,vintage,checks}.py`,
  and the merge authority: `src/econ/dev/**`, `.github/workflows/**`,
  `tests/dev_support.py`, `tasks/templates/task.yaml`, `dev/evals/canary/**`.
  Touching one is risk 3 and requires human sign-off; it is never auto-merged.
  The controller, the CI that independently verifies auto-merges, and the
  canary suite are the referee: they are protected so the system cannot
  silently rewrite the rules that judge it.

## Data and tracked artifacts

- `data/curated/observations.parquet` and `manifest.json` are tracked and are
  the test source of truth. Do not run `econ ingest` unless the task is
  explicitly about data: it calls BCB/IBGE, rewrites the parquet, changes the
  data hash, and changes every run id.
- `data/raw/` files are tracked, but the directory is gitignored for new pulls.
  Do not assume `git add data/raw/...` will stage a new file.
- `econ backtest`, `score`, `ensemble`, `report`, and `loop` mutate tracked
  `registry/`, `eval/`, `reports/`, and/or `specs/`. They are not read-only
  exploration commands. In code and tests, use `run_backtest(..., save=False)`.
- `econ loop` overwrites `specs/<model>.decision.json` and appends registry runs.
  `econ lockbox open` writes the sealed ledger. Do not run either just to see
  what happens.
- `runs/` is gitignored. Docs cite evidence under `runs/loop/...` that exists
  only in a full local checkout.

## Test quirks

- The suite is not fully hermetic: `test_registry` and `test_lockbox` require the
  committed `registry/`, `eval/`, and `reports/` artifacts.
- `test_agents::test_variants_resolve` requires
  `~/.cache/opencode/models.json`; a clean container without that cache fails
  this test.
- `tests/test_agents.py` asserts that rendered roster files are up to date.
  Changing `config/agents.yaml` or a prompt without re-rendering fails the suite.

## Generated rosters

- Research roster: `config/agents.yaml` plus `config/prompts/*.md` renders to
  `.opencode/agents/econ-*.md`.
- Development roster: `config/dev_agents.yaml` plus `config/prompts/dev/*.md`
  renders to `.opencode/agents/dev-*.md`.
- Never hand-edit rendered agents. Edit the config/prompt, run the matching
  `agents render`, then `agents check`. `make agents` covers both rosters.
- Research agents are sandboxed and advisory. The mechanical evaluator, not an
  agent, grants PASS or REJECT.

## Development agent workflow

- A runnable task is a frozen YAML contract in `tasks/ready/`; `tasks/proposed/`
  holds triaged work. The scheduler only picks `ready/`.
- In the interactive CLI, the `dev-pm` agent and `/dev/propose ...` draft a
  contract into `tasks/proposed/`. Promotion is a separate human step:
  `econ dev promote DEV-0001` validates and moves it to `ready/`. Agents never
  promote or run the controller themselves.
- Acceptance criteria must be executable commands (shell metacharacters are
  rejected). `scope.allow` must name explicit paths. Risk: 0 docs, 1
  tests/refactor, 2 behavior, 3 protected/science.
- The controller creates an isolated worktree and records run artifacts under
  `.dev/` (gitignored). Agents write role outputs to `.dev/out/<role>.json` and
  never edit `.git/`, commit, push, or merge.
- Roles: PM interviews and drafts; lead/architect design; reproducer writes a
  failing test; implementer writes the smallest patch plus a red-green test;
  reviewer is blind to the implementer's rationale; verifier applies the patch
  to a clean base and runs acceptance independently; science guard checks
  protected paths, the lockbox, registry append-only, and determinism.
- The deterministic controller (`src/econ/dev/`) decides whether to merge. Risk 3
  is always escalated for human sign-off. See `config/dev_policy.yaml` and
  `tasks/README.md`.

## Style

- Python 3.12, `from __future__ import annotations`, dataclasses or small
  Pydantic models, explicit types.
- Add tests for behavior changes. A new test must fail on the base commit and
  pass on the patch. Never weaken, skip, or over-mock a test to make the suite
  green.
- Do not add dependencies without human sign-off. Do not commit generated data,
  `runs/`, `.venv/`, `.dev/`, or secrets.
