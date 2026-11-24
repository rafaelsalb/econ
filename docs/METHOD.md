# Method

## Targets and horizons

Origins are the last weekday of each month. Horizons are measured from the
origin month/quarter.

| Target | Definition | Horizons | Primary |
|---|---|---|---|
| `ipca_m` | Monthly IPCA, % m/m | 0..12 | 0, 6, 12 |
| `ipca_12m` | 12-month accumulated IPCA, derived by compounding the monthly path | 3, 6, 12 | 6, 12 |
| `gdp_qq` | GDP q/q, % | 0..4 | 1, 4 |
| `selic` | Selic target, % p.a. | 0, 3, 6, 12 | 12 |

The 12-month inflation rate is never forecast directly. The monthly path is the
object of interest; the aggregate is derived so that accounting errors are
visible.

## Windows

| Window | Period | Use |
|---|---|---|
| Estimation | Expanding from 2005-01 (series-dependent) | Model fitting |
| Validation | 2010-01..2019-12 | Critic loop, model selection |
| Lockbox | 2020-01..2026-10 | Final evaluation only, sealed |

The validation window contains 120 monthly origins. The lockbox is not used by
the loop, the report, or any model-selection decision.

## Benchmarks

| ID | Model | Purpose |
|---|---|---|
| `random_walk` | Last observed value | Minimum bar |
| `seasonal_naive` | Last 12-month seasonal pattern | Seasonality bar |
| `ar` | AR(p) with BIC selection | Univariate bar |
| `bvar` | BVAR with a Minnesota prior (monthly and quarterly systems) | Multivariate bar |
| `ibc_bridge` | GDP bridge on IBC-Br, with an AR(1) monthly path | Activity nowcast bar |
| `focus_consensus` | Focus annual medians, converted to a monthly path | Real-world consensus bar |

The Focus benchmark is the hard bar. It constructs a monthly IPCA path from the
current-year and next-year annual medians, using realised year-to-date inflation
to back out the required rate for the remaining months. GDP and Selic paths are
built from the corresponding annual medians.

## New Keynesian QPM

The full contract is in `specs/new_keynesian.yaml`. The estimated block is:

```
gap_t = a0 + a1 gap_{t-1} + a2 gap_{t-2} + a3 (r_{t-1} - r*) + e_t
pi_t  = c + b1 pi_{t-1} + b2 pi_{t-2} + (1-b1-b2) pi_e_t
          + b4 gap_{t-1} + b5 dfx_{t-1} + e_t
i_t - target_t - r* = rho (i_{t-1} - target_t - r*)
          + g1 (pi12_{t-1} - target_t) + g2 gap_{t-1} + e_t
gdp_qq_t = c0 + c1 ibc_qq_t + c2 ibc_qq_{t-1} + e_t
```

- `gap` is the HP cycle of log IBC-Br, lambda = 129600; it is two-sided within
  the estimation sample and re-estimated at each origin. No post-origin data is
  used, but the endpoint is biased.
- `r` is the ex-ante real Selic: Selic minus the Focus 12-month median.
- `pi_e` is the monthly equivalent of the Focus 12-month median.
- `target` is the CMN annual inflation target; from 2025 the continuous 3.0%
  target applies.
- `r* = 4.0` is calibrated.
- Long-run neutrality (`b1+b2+b3=1`) and the neutral real rate in the Taylor
  rule are imposed, not estimated.
- Estimation is equation-by-equation OLS with Newey-West HAC (12 lags).
- GDP is a satellite bridge; it is not a structural IS curve.

The revision ladder is pre-registered:

| Rung | Change | Target |
|---|---|---|
| R1 | Baseline | — |
| R2 | GDP bridge uses an AR(p) IBC-Br path with BIC selection (max p=3) | GDP |
| R3 | Taylor rule uses the Focus 12m expectation instead of lagged 12m inflation; keeps R2 | Selic |

No new variables, no sample changes, no lockbox access.

## Phase 2 school blocks

**Monetarist.** A money-demand equation, a P-star price gap, and a six-variable
Bayesian VAR in [IPCA, M2 growth, credit growth, IBC-Br growth, Selic, FX
growth]. The school's claim is that money and credit growth carry information
about inflation beyond the gap and the policy rate. The validation P-star gap
coefficient is negative, so the model is rejected; on the one-time lockbox it is
the best single model on IPCA h=12.

**Fiscal/FTPL.** A fiscal reaction function, a debt identity, a
fiscal-augmented inflation equation, an activity equation, and a policy rule
with a debt term. The estimated fiscal reaction is positive (a Ricardian
regime), and the debt and primary-balance inflation coefficients have the wrong
signs; the FTPL mechanism is rejected in this sample.

**Post-Keynesian SFC.** An SFC-lite block: behavioral consumption, investment,
government, export and import equations; the GDP expenditure identity; a
deflator/markup equation; a deflator-to-IPCA bridge; and a government debt
identity. The Selic path is an exogenous scenario. The consumption real-rate
sign and deflator persistence fail; the model is rejected. Its effective
validation sample is 2012–2019 because the quarterly system needs 20 quarters.

The generic gate uses the card's `refutation_tests`, HAC diagnostics, the
accounting identity check, BVAR stability, core-target availability and forecast
sanity. All cards are in `specs/`; terminal decisions are in
`specs/<model>.decision.json`.

## Evaluation

For each `(model, target, horizon)`:

- **RMSE, MAE, bias**
- **Theil U** against the random walk on the common origins
- **Diebold-Mariano** test with Newey-West variance and the
  Harvey-Leybourne-Newbold correction
- **Focus ratio** (model RMSE / Focus RMSE on the common origins) and a
  **Diebold-Mariano test against the Focus consensus**
- **Mincer-Zarnowitz** regression `realized = a + b*forecast` with HAC errors;
  report the slope, the p-value for `b=1`, the intercept, and the p-value for
  `a=0`
- **Directional accuracy** relative to the anchor observed at the origin
- **Episode scorecard** for 2015-16, 2018, 2020-21, 2021-22, 2023-24

The Theil U is computed on the intersection of origins where both the model and
the random walk have forecasts, so models with different sample coverage are not
advantaged.

**Purge.** Every backtest purges targets after the requested end date. For the
validation window 2010-01..2019-12 this drops 12/120 h=12 targets and 6/120 h=6
targets at late origins, so no 2020 outcome enters model selection. `econ check`
asserts the purge and `max_ref_date <= 2019-12-31`.

**Satellite forecasts.** GDP in the NK model is a shared IBC-Br bridge. The rows
carry `notes = "satellite_bridge; shared with ibc_bridge"`, are reported, and are
excluded from the school's gate and mean rank.

## Defect taxonomy

| Code | Class | Blocking? |
|---|---|---|
| D1 | Identification / observability | High if structural, medium if precision |
| D2 | Accounting / dimensional | High |
| D3 | Data contract / leakage | High |
| D4 | Statistical adequacy | Medium/low, recorded as limitation |
| D5 | Forecast adequacy | High for core inflation, medium for auxiliary targets |
| D6 | Reproducibility / non-finite output | High |
| D7 | Economic interpretation / sign | High for sign violations, medium for negligible magnitude |

The critics are falsificationist: they return failure cases, not verdicts.

## Loop protocol

1. Freeze the card and hash it.
2. Run the model on the validation window; write forecasts to the registry.
3. Fit diagnostics at two origins; compare parameter stability.
4. Run the fidelity and adequacy critics blind (packets contain no score table
   for the modeler).
5. Apply the gate:
   - Evaluate the card's machine-readable `refutation_tests`. A failed test is
     high severity and blocks PASS.
   - High-severity defects → revise or reject. If no admissible ladder rung
     targets the blocking defect, the terminal state is `REJECTED`.
   - Core inflation (h=6,12) must have Theil U <= 1.05, MZ p >= 0.05, no
     significant loss to Focus, and a value-added win at one core horizon or
     episode.
   - Auxiliary targets (Selic) follow the same rule; GDP is a satellite and is
     excluded.
   - Medium-only defects → `PASS_WITH_LIMITATIONS`.
6. Record the terminal state in `specs/<model>.decision.json` and
   `runs/loop/<model>/`.
7. Never touch the lockbox.
8. Optionally run the sandboxed advisory critics (`--agents`). They add typed
   findings but cannot grant PASS or write to `src/`.

Terminal states: `PASS`, `PASS_WITH_LIMITATIONS`, `REJECTED`, `UNESTIMABLE`,
`UNRESOLVED`.

## Validation result (New Keynesian, R1, purged)

| Target | h | n | Theil U | MZ p(b=1) | Focus ratio | DM vs Focus p |
|---|---:|---:|---:|---:|---:|---:|
| IPCA 12m | 6 | 114 | 0.516 | 0.849 | 1.114 | 0.029 |
| IPCA 12m | 12 | 108 | 0.463 | 0.530 | 0.994 | 0.954 |
| Selic | 12 | 108 | 0.935 | 0.498 | 1.328 | 0.013 |
| GDP q/q | 1 | 117 | 1.136 | ~0 | 1.534 | ~0 |
| GDP q/q | 4 | 108 | 0.935 | ~0 | 1.210 | 0.010 |

Mean rank across the three school cells: 1.67. Focus: 1.2. GDP is a satellite
and is excluded from the school's rank.

The terminal state is `REJECTED` at R1. Three high-severity defects fired:

1. NKPC output-gap coefficient 0.0073, t = 1.15; the card's refutation test
   requires |t| >= 1.65.
2. FX pass-through coefficient -0.0006; the declared sign is positive.
3. IPCA h=6 is significantly worse than Focus (ratio 1.114, DM p = 0.029).

The R2/R3 ladder was not reached because no rung targets a structural
refutation. The first PASS_WITH_LIMITATIONS was withdrawn after the independent
review in `runs/loop/new_keynesian/external_review.md`.

### All-school mean rank (validation)

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

All four schools are `REJECTED`; the full table is `eval/scoreboard.csv`.

## Phase 3 ensembles and lockbox

Equal and inverse-MSE performance weights are computed per target/horizon on the
validation window and frozen in `eval/ensemble_weights.json`. The ensembles are
combined (all models) and school-only. The disagreement index is the cross-school
standard deviation; the fan chart is `reports/fan_chart.png`.

The one-time lockbox was opened on 2026-11-24 (run `db620d60530fb7f6`, 82
origins, 17,430 forecasts, 0 failures) and sealed in `registry/lockbox.json`.
The combined performance ensemble beats Focus on IPCA h=12 (Focus ratio 0.857)
and Selic h=12 (0.972). The Monetarist and AR models beat Focus on IPCA h=12;
the New Keynesian does not. These are single-reading results and do not reverse
the validation rejections. The lockbox must not be reopened.

## Agent sandbox

`config/agents.yaml` is the single source of truth. `econ agents render` writes
native OpenCode agents under `.opencode/agents/`; every role defaults to
`opencode-go/deepseek-v4.1-flash#max`.

`econ sandbox run` projects a minimal read-only inbox and a writable outbox into
a Docker container with a read-only rootfs, non-root user, dropped capabilities,
PID/memory/CPU limits, and no Docker socket. The container sits on an internal
network whose only route is a CONNECT proxy with a host allowlist. Every
invocation writes `logs/invocation.json` with the image, mounts, limits, exit
code, duration, and stdout/stderr hashes.

Live model calls work with an explicit `OPENCODE_API_KEY` or
`--api-key-file`; the explicit key takes precedence over a stale stored account.
Both critics ran against card v1.0.1 on 2026-11-24 and agreed with the
mechanical `REJECTED`. They hit the old 8-step budget before writing JSON, so
their full text is preserved in
`runs/loop/new_keynesian/advisory_live_v1.0.1/`; the budget is now 12 steps.
The filesystem and network boundaries are verified independently of the
credential.

## Reproducibility

A run is identified by

```
sha256(models, config, seed, data_hash, code_hash, spec_hashes)[:16]
```

The manifest records the data hash, code hash, spec hashes, seed, failures, and
row count. Re-running the same command on the same data and code produces the
same `run_id`. The curated data manifest records the parquet hash.

## Limitations

- Pseudo-vintages remove publication-timing look-ahead but not revision
  look-ahead.
- Validation targets are purged at the window end; the lockbox was opened
  exactly once and is sealed.
- Equation-by-equation OLS ignores simultaneity.
- The HP gap is two-sided within the estimation sample and is re-estimated at
  each origin; endpoint estimates are biased. It is not a true one-sided
  real-time filter.
- The survey expectations are treated as an anchor, not as model-consistent
  expectations; the NKPC's 12-month-ahead term is horizon-mismatched for h < 12.
- The Taylor rule's implied neutral nominal rate is 4.0 (r*) + 4.0 (target) =
  8.0%, well above the post-2016 Selic. This is a known misspecification.
- The GDP block is a shared satellite bridge, not a structural IS curve.
- The QPM is not a DSGE; it is a transparent semi-structural forecasting model.
- The FTPL debt identity uses the 12-month primary balance divided by 12.
- The SFC is SFC-lite, ignores component-specific deflators and uses an
  exogenous Selic; its effective sample is 2012–2019.
- The ensemble is a synthesis of rejected models; its validation score is not a
  PASS, and the lockbox is a single reading.
- Density forecasts are not yet implemented; the registry reserves nullable
  `q05..q95` columns.
- Real-time revision vintages are not available for most series.
