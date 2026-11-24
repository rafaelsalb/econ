# Data layer

## Schema

`data/curated/observations.parquet`:

| Column | Meaning |
|---|---|
| `series_id` | Catalog key |
| `ref_date` | First day of the reference period (month/quarter) or the observation date for daily series |
| `period_end` | Last day of the reference period (equal to `ref_date` for daily series) |
| `release_date` | `period_end + release_lag_days` (or `ref_date + lag` for daily series) |
| `vintage_date` | Date the snapshot was pulled |
| `value` | Observation |
| `source` | `sgs`, `sidra`, `focus`, `focus_annual` |
| `unit`, `freq`, `sa_flag` | Metadata |
| `extra` | Reference year for annual Focus expectations; empty otherwise |

`ref_date` is the period start, not the release date. A monthly value for
January 2019 has `ref_date = 2019-01-01`, `period_end = 2019-01-31`, and
`release_date = 2019-02-10` for IPCA.

## Series

| ID | Source | Code | Freq | Release lag | Role |
|---|---|---|---|---|---|
| `ipca_m` | BCB SGS | 433 | M | 10 days | Target, NKPC |
| `ipca_12m` | BCB SGS | 13522 | M | 10 days | Cross-check |
| `selic_target` | BCB SGS | 432 | D | 0 | Target, policy rate |
| `ibc_br` | BCB SGS | 24364 | M | 20 days | Activity, output gap |
| `fx_usdbrl` | BCB SGS | 3695 | M | 1 day | FX pass-through |
| `gdp_qq` | IBGE SIDRA | 5932/6564, class 11255[90707] | Q | 60 days | Target |
| `gdp_level` | IBGE SIDRA | 6612/9318, class 11255[90707] | Q | 60 days | Cross-check |
| `focus_ipca_12m` | BCB Focus | `ExpectativasMercadoInflacao12Meses` | D | 0 | Expectations, benchmark |
| `focus_ipca_annual` | BCB Focus | `ExpectativasMercadoAnuais` | D | 0 | Focus path |
| `focus_gdp_annual` | BCB Focus | `ExpectativasMercadoAnuais` | D | 0 | Focus path |
| `focus_selic_annual` | BCB Focus | `ExpectativasMercadoAnuais` | D | 0 | Focus path |
| `m2` | BCB SGS | 27810 | M | 30 days | Monetarist money stock |
| `credit_total` | BCB SGS | 2064 | M | 30 days | Monetarist credit stock |
| `debt_gdp` | BCB SGS | 13762 | M | 30 days | FTPL gross debt |
| `primary_balance_12m` | BCB SGS | 5793 | M | 30 days | FTPL primary balance |
| `net_debt_gdp` | BCB SGS | 4513 | M | 30 days | Fiscal cross-check |
| `gdp_nominal` | IBGE SIDRA | 1846/585, class 11255[90707] | Q | 60 days | SFC nominal GDP |
| `consumption_nominal` | IBGE SIDRA | 1846/585, class 11255[93404] | Q | 60 days | SFC consumption |
| `govt_consumption_nominal` | IBGE SIDRA | 1846/585, class 11255[93405] | Q | 60 days | SFC government |
| `investment_nominal` | IBGE SIDRA | 1846/585, class 11255[93406] | Q | 60 days | SFC investment |
| `exports_nominal` | IBGE SIDRA | 1846/585, class 11255[93407] | Q | 60 days | SFC exports |
| `imports_nominal` | IBGE SIDRA | 1846/585, class 11255[93408] | Q | 60 days | SFC imports |
| `taxes_nominal` | IBGE SIDRA | 1846/585, class 11255[90706] | Q | 60 days | SFC taxes |

SIDRA quarterly periods use `YYYYQQ` (202401 = 2024Q1), not `YYYYMM`. The
adapter maps quarter codes to the first month of the quarter. The SIDRA range
end is clamped to the latest period advertised in the aggregate metadata; asking
for a future quarter returns HTTP 500.

Focus annual series contain multiple reference years per survey date. They are
stored with `extra = DataReferencia` and deduplicated on
`(series_id, ref_date, extra)`.

## Pseudo-vintages

At forecast origin `t`:

```
visible = observations[observations.release_date <= t]
```

This removes publication-timing look-ahead. It does not remove revision
look-ahead, because the public APIs return the current (final) vintage for most
series. Where a real-time archive exists, it should replace the pseudo-vintage;
the catalog is the place to add it.

Daily series are visible through `t`. Monthly series whose release date falls
after `t` are excluded, which is why at the last business day of month `M` the
latest IPCA and IBC-Br observations are for `M-1`.

## Leakage rules

1. Models never see `release_date > origin`. The `Panel` class is the only
   sanctioned access path.
2. Outcome data are joined only in `evaluate.realized_table`, never in a model.
3. Focus expectations are used as of the origin only.
4. `econ check` runs the release-date leak test at four representative origins.
5. `tests/test_data.py` asserts the boundary for every sampled origin.

## Validation purge

Backtests purge any forecast whose `ref_date` is after the requested end date.
For the 2010-01..2019-12 validation window this drops the 2020 targets that
would otherwise be scored by late-2019 origins: 12/120 h=12 cells and 6/120 h=6
cells. The lockbox is defined by the *outcome* date, not only the origin date, so
this purge is required to keep 2020-01..2026-10 sealed.

`econ check` asserts that the latest qualifying run has `embargo_until` equal to
the validation end and `max(ref_date) <= 2019-12-31`.

## Sandbox data access

Agent roles receive a projected `in/` directory built by `econ.sandbox`. The
projection contains only the files explicitly passed by the driver: the card,
the packet, diagnostics, and optionally a code snapshot. `eval/`, the registry,
the raw data, and the lockbox are not mounted. The librarian's `data` profile is
the only role with a network allowlist, and that allowlist is limited to the
BCB/IBGE hosts.

## Known issues

- No revision history: final-vintage values are used for the historical
  pseudo-vintages. This biases real-time evaluation in favour of models that
  benefit from revised data.
- Focus history starts in 2000 for annual expectations and 2001-11 for the
  12-month series. Earlier origins are not supported for survey-based models.
- The Selic target series is a daily step function filled across weekends; the
  monthly panel takes the last value in the month.
- SIDRA GDP is quarterly and released with a lag; at some origins the latest
  published quarter is two quarters old.
- The GDP chain-linked level is an index in 1995 prices, not a seasonally
  adjusted level; the model uses q/q growth, not the level.
- Fiscal series (`debt_gdp`, `primary_balance_12m`) have a ~30-day release lag,
  so the FTPL model starts from the latest available fiscal month rather than
  assuming M-1.
- The SFC uses quarterly national accounts; its effective validation sample
  starts in 2012 because the behavioral system needs 20 quarters.
- M2 has a null observation at the start of the SGS series; the adapter skips it.

## Adding a series

1. Add an entry to `catalog.yaml` with `source`, `freq`, `unit`, `start`,
   `release_lag_days`, and the source-specific fields.
2. Implement the adapter in `src/econ/sources.py` if the source is new.
3. Run `econ ingest`. The manifest records rows, min/max dates, and the new hash.
4. Add a leak test or a panel accessor if the series has a special frequency.
