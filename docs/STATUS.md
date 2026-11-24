# Implementation status

Status as of 2026-11-24. All four phases are complete. No school model passed
its pre-registered validation gate; the one-time lockbox is sealed; the final
report is reproducible from the registry and the evaluator.

## Phase overview

| Phase | State | Evidence |
|---|---|---|
| 0 — data, benchmarks, registry, evaluator | Complete | 120 origins, 14,820 benchmark forecasts, 0 failures |
| 1 — New Keynesian critic loop | Complete, `REJECTED` | run `3f0d230adab02ce7` |
| 2 — Monetarist, Fiscal/FTPL, PK-SFC | Complete, all `REJECTED` with reasons | runs `8ab354e552e0c374`, `08a33e57b8676d20`, `893c058bf19467b9` |
| 3 — ensembles, fan, disagreement, lockbox | Complete | lockbox run `db620d60530fb7f6`; `reports/final_report.md` |

Data snapshot: 118,723 observations, hash `14b49d7a27ffc32f5b329420c1b05c08a4b37215bf3b644d6da8e29f982f8ca8`.
Validation targets are purged at 2019-12-31; the lockbox 2020-01..2026-10 is
opened exactly once and recorded in `registry/lockbox.json`.

## Phase 0 — complete

| Gate | Evidence |
|---|---|
| Data layer | 23 series including money, credit, fiscal and national-accounts blocks |
| Benchmarks B0–B5 | RW, seasonal naive, AR, BVAR, IBC-Br bridge, Focus consensus |
| ≥120 origins | run `735d478fe2e4eeea`: 120 origins, 14,820 forecasts, 0 failures |
| Purge | `max_ref_date = 2019-12-31`; `econ check` enforces it |
| Leak test | 4 origins, 0 release-date violations |
| Reproducibility | forced re-run reproduced `735d478fe2e4eeea` twice |
| Focus comparison | present for IPCA and Selic |

## Phase 1 — New Keynesian, rejected

| Item | Evidence |
|---|---|
| Card v1.0.1 | `specs/new_keynesian.yaml`, sha256 `bdaebdd44087...` |
| Terminal | **`REJECTED`**, R1, run `3f0d230adab02ce7`, 3 high / 3 medium |
| Core metrics | IPCA 12m h=6 Theil 0.516; h=12 Theil 0.463; Selic h=12 0.935 |
| High defects | gap t=1.15; FX pass-through negative; IPCA h=6 Focus ratio 1.114 (p=0.029) |
| Review | `runs/loop/new_keynesian/external_review.md` |
| Advisory | `runs/loop/new_keynesian/advisory_live_v1.0.1/` |

The external review overturned the first `PASS_WITH_LIMITATIONS`. The corrected
gate now evaluates the card's machine-readable refutation tests, purges 2020
targets, uses a 2005 sample, compares against Focus, and excludes satellite GDP.
The review's zero-mean HP argument is not itself proof of post-origin leakage;
the actual defect was the "one-sided" description and endpoint bias.

## Phase 2 — the other schools, all rejected

### Data added

| Block | Series |
|---|---|
| Money | M2 (`27810`), credit stock (`2064`) |
| Fiscal | gross debt/GDP (`13762`), primary balance 12m (`5793`), net debt (`4513`) |
| National accounts | nominal GDP, household/government consumption, investment, exports, imports, taxes (SIDRA 1846) |

### Terminal states

| Model | Run | Rows / failures | Terminal | Main refutations |
|---|---|---:|---|---|
| Monetarist | `8ab354e552e0c374` | 8,550 / 0 | `REJECTED` | P-star gap sign negative; money/credit channel fails |
| Fiscal/FTPL | `08a33e57b8676d20` | 8,550 / 0 | `REJECTED` | fiscal reaction positive (Ricardian); debt-inflation and primary-inflation signs wrong |
| PK-SFC | `893c058bf19467b9` | 8,000 / 22 | `REJECTED` | consumption real-rate sign positive; deflator persistence negative; other behavioral signs |

The SFC's 22 failures are 2010–2011 origins with fewer than 20 usable quarters;
its effective validation sample is 2012–2019. The FTPL is fully populated after
the data-lag fix.

### Validation mean ranks

| Model | Mean rank |
|---|---:|
| Focus consensus | 1.20 |
| New Keynesian | 1.67 (3 cells) |
| AR | 4.00 |
| IBC-Br bridge | 4.50 |
| BVAR | 5.20 |
| Monetarist | 5.33 |
| Seasonal naive | 6.20 |
| PK-SFC | 6.25 (4 cells) |
| Random walk | 6.60 |
| Fiscal/FTPL | 9.00 |

Full detail: `eval/scoreboard.csv`, `eval/episodes.csv`, per-school
`runs/loop/<model>/round-1/defects.json`.

## Phase 3 — synthesis, ensembles and lockbox

### Validation ensembles

| Ensemble | IPCA h=6 Theil | IPCA h=12 Theil | Selic h=12 Theil |
|---|---:|---:|---:|
| Combined performance | 0.542 | 0.510 | 0.867 |
| Combined equal | 0.577 | 0.648 | 0.842 |
| School performance | 0.583 | 0.536 | 0.901 |
| School equal | 0.636 | 0.874 | 0.991 |

The combined performance ensemble is the best ensemble on inflation; it still
does not beat Focus on validation. GDP h=4: school performance Theil 0.746,
combined performance 0.772. The fan chart is `reports/fan_chart.png`; the
dispersion series is `reports/disagreement.csv`; weights are frozen in
`eval/ensemble_weights.json`.

### One-time lockbox (2020-01..2026-10)

Opened 2026-11-24, run `db620d60530fb7f6`, 82 origins, 17,430 forecasts, 0
failures. Sealed in `registry/lockbox.json`. Report:
`reports/lockbox_report.md`.

Notable lockbox findings:

- The **combined performance ensemble** beats Focus on IPCA h=12 (Theil 0.507,
  Focus ratio 0.857) and Selic h=12 (0.776, Focus ratio 0.972).
- The **Monetarist** model beats Focus on IPCA h=12 (Theil 0.446, Focus ratio
  0.754); the **AR benchmark** also beats Focus at h=12 (0.437, 0.738).
- The **New Keynesian** does not (h=12 Theil 0.695, Focus ratio 1.173).
- The 2020–2026 window includes COVID and the inflation surge; the lockbox is a
  single reading, not a selection device. It does not reverse the validation
  rejections.

Final cross-phase report: `reports/final_report.md`.

## Agent sandbox — live advisory, text-only

The roster is `config/agents.yaml`; every role defaults to
`opencode-go/deepseek-v4.1-flash#max`. Docker + internal network + CONNECT
allowlist + projected workspace; bwrap fallback for filesystem/process isolation.

Both live critics ran against card v1.0.1 on 2026-11-24 and agreed with the
mechanical `REJECTED`. They hit the old 8-step budget before writing
`result.json`; their full text is preserved in
`runs/loop/new_keynesian/advisory_live_v1.0.1/`. The step budget is now 12.
They caught two advisory-packet defects, fixed immediately: the gate file
ignored the Focus loss at IPCA h=6, and it included satellite GDP. The remaining
advisory findings (gate-label naming, `abs_ge` semantics, AR(p) vs AR(1),
bridge sample, Taylor sample start, two-origin stability, untested Taylor
principle) are documented as v1.1 follow-ups.

Credentialing: `OPENCODE_API_KEY` or `--api-key-file` takes precedence over the
stale stored account. The key is never copied into the workspace, image or audit.

## Development automation — phases 0–4 complete

The development team is a deterministic controller in `src/econ/dev/` with a
separate `dev-*` agent roster, task contracts, and a policy boundary. The
research agents remain advisory and sandboxed; the research sandbox mounts only
`econ-*.md`.

Evidence:

| Phase | Deliverable | Evidence |
|---|---|---|
| 0 | Baseline, CI, protected paths, gate | `make gate` passes; `.github/workflows/ci.yml`; `.github/CODEOWNERS` |
| 1 | Dev roster, prompts, commands, task schema, canaries | `config/dev_agents.yaml`; 3/3 canaries pass; `econ dev validate --all` |
| 2 | Worktree pipeline, blind review, verifier, gates, shadow mode | fake end-to-end merge; `runs/dev/` artifacts; 104 tests |
| 3 | Scheduler, budgets, pause/lock, GitHub sync, dashboard, maintenance, release | `econ dev daemon --once`; `econ dev sync --pull`; dashboard files |
| 4 | Parallel execution, Docker executor, scheduled workflows, release bot | two-task parallel test; `econ-agent:latest` rebuilt with git; 4 workflows; `v0.2.0` release |

The pipeline enforces red-green tests, scope, secrets, dependency sign-off,
lockbox hashes, registry append-only, and a risk-tiered merge policy. Risk 3
changes (`specs/`, data, gates, lockbox, sandbox) are always escalated.

## Deviations from the plan

1. **The first New Keynesian PASS was withdrawn** after the external review.
2. **All four schools are rejected.** The ensemble and lockbox are diagnostics,
   not a rescue.
3. **The SFC is SFC-lite**: expenditure identity, behavioral components, debt
   identity; no full transaction-flow matrix. Its effective sample is 2012–2019.
4. **FTPL debt identity** uses the 12-month primary balance divided by 12.
5. **GDP is a satellite** for NK/Monetarist/FTPL; the SFC GDP is part of its
   own identity.
6. **Validation is purged** at 2019-12-31; the lockbox is opened exactly once.
7. **The loop is deterministic; LLM agents are advisory.**

## Reproducibility

A run id is `sha256(models, config, seed, data_hash, code_hash, spec_hashes)[:16]`.
The manifests in `runs/<run_id>/manifest.json` and `registry/runs.jsonl` record
the data and code hashes, failures and row counts. The curated parquet hash is
in `data/curated/manifest.json`. Re-running the same command on the same data
and code reproduces the id.

Tests: **70 passed**. `econ agents check` and `econ check` pass.

## Next

- v1.1 New Keynesian card: real-time gap, lower/estimated `r*`, FX only if
  identified, shock-based Taylor-principle test, episode-level value added.
- v1.1 Monetarist: pre-register a two-regime P-star (or drop the sign
  restriction) because the lockbox performance is strong but the validation
  refutation stands.
- Real-time vintages and density forecasts (registry quantiles are ready).
- Do not reopen the lockbox.
