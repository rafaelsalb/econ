# Brazil macro model hub — monthly report

Origin: **2026-10-30** · data vintage: pseudo-real-time (release dates, no revision history)

## Latest forecasts

### IPCA 12-month accumulated (%)

| model_id        |    3 |    6 |    12 |
|:----------------|-----:|-----:|------:|
| ar              | 6.11 | 5.36 |  6.39 |
| bvar            | 5.84 | 4.92 |  5.74 |
| fiscal_ftpl     | 5.28 | 3.4  |  0.06 |
| focus_consensus | 5.28 | 4.15 |  4.8  |
| monetarist      | 5.84 | 4.91 |  5.73 |
| new_keynesian   | 5.65 | 4.66 |  5.46 |
| pk_sfc          | 5.52 | 4.61 |  5.66 |
| random_walk     | 7.05 | 7.27 | 10.3  |
| seasonal_naive  | 4.58 | 4.58 |  4.58 |

### GDP q/q (%)

| model_id        |     0 |     1 |     2 |     3 |     4 |
|:----------------|------:|------:|------:|------:|------:|
| ar              |  0.58 |  0.58 |  0.58 |  0.58 |  0.58 |
| bvar            |  0.69 |  0.67 |  0.61 |  0.58 |  0.58 |
| fiscal_ftpl     |  0.06 |  0.26 |  0.24 |  0.22 |  0.17 |
| focus_consensus |  0.44 |  0.3  |  0.3  |  0.3  |  0.3  |
| ibc_bridge      |  0.23 |  0.54 |  0.55 |  0.55 |  0.55 |
| monetarist      |  0.1  |  0.43 |  0.53 |  0.54 |  0.54 |
| new_keynesian   |  0.87 |  1.38 |  1    |  0.85 |  0.79 |
| pk_sfc          | -2.01 | -1.36 | -0.88 | -0.6  | -0.44 |
| random_walk     |  0.5  |  0.5  |  0.5  |  0.5  |  0.5  |
| seasonal_naive  |  0.2  |  1.1  |  0.5  |  0.5  |  0.5  |

### Selic target (%)

| model_id        |     3 |     6 |    12 |
|:----------------|------:|------:|------:|
| ar              | 13.48 | 13.27 | 12.92 |
| bvar            | 12.78 | 12.25 | 11.66 |
| fiscal_ftpl     | 13.96 | 14.17 | 15.27 |
| focus_consensus | 13.42 | 13.17 | 12.67 |
| monetarist      | 12.62 | 12.07 | 11.48 |
| new_keynesian   | 13.35 | 13.13 | 12.8  |
| pk_sfc          | 13.75 | 13.75 | 13.75 |
| random_walk     | 13.75 | 13.75 | 13.75 |
| seasonal_naive  | 13.75 | 13.75 | 13.75 |

## Validation scoreboard (primary cells)

| model_id        | target   |   horizon |   n |   rmse |   theil_u |    dm_p |   mz_slope_p |   rank |
|:----------------|:---------|----------:|----:|-------:|----------:|--------:|-------------:|-------:|
| focus_consensus | gdp_qq   |         1 | 117 |  0.849 |     0.741 |   0.001 |        0.187 |      1 |
| monetarist      | gdp_qq   |         1 | 117 |  1.003 |     0.875 |   0.139 |        0.961 |      2 |
| ar              | gdp_qq   |         1 | 117 |  1.067 |     0.931 |   0.425 |        0.933 |      3 |
| ibc_bridge      | gdp_qq   |         1 | 117 |  1.078 |     0.94  |   0.498 |        0.545 |      4 |
| bvar            | gdp_qq   |         1 | 117 |  1.095 |     0.956 |   0.626 |        0.791 |      5 |
| random_walk     | gdp_qq   |         1 | 117 |  1.146 |     1     | nan     |        0     |      6 |
| seasonal_naive  | gdp_qq   |         1 | 117 |  1.252 |     1.093 |   0.324 |        0     |      7 |
| new_keynesian   | gdp_qq   |         1 | 117 |  1.303 |     1.136 |   0.199 |        0     |      8 |
| fiscal_ftpl     | gdp_qq   |         1 | 117 |  1.399 |     1.221 |   0.048 |        0     |      9 |
| pk_sfc          | gdp_qq   |         1 |  95 |  1.815 |     1.55  |   0     |        0     |     10 |
| focus_consensus | gdp_qq   |         4 | 108 |  1.03  |     0.773 |   0.017 |        0.442 |      1 |
| pk_sfc          | gdp_qq   |         4 |  86 |  1.078 |     0.811 |   0.117 |        0.422 |      2 |
| ar              | gdp_qq   |         4 | 108 |  1.163 |     0.873 |   0.257 |        0.092 |      3 |
| monetarist      | gdp_qq   |         4 | 108 |  1.178 |     0.884 |   0.304 |        0.128 |      4 |
| ibc_bridge      | gdp_qq   |         4 | 108 |  1.185 |     0.889 |   0.328 |        0.115 |      5 |
| bvar            | gdp_qq   |         4 | 108 |  1.202 |     0.902 |   0.391 |        0.02  |      6 |
| new_keynesian   | gdp_qq   |         4 | 108 |  1.246 |     0.935 |   0.574 |        0     |      7 |
| random_walk     | gdp_qq   |         4 | 108 |  1.333 |     1     | nan     |        0     |      8 |
| seasonal_naive  | gdp_qq   |         4 | 108 |  1.333 |     1     | nan     |        0     |      8 |
| fiscal_ftpl     | gdp_qq   |         4 | 108 |  5.013 |     3.761 |   0.003 |        0     |     10 |
| focus_consensus | ipca_12m |         6 | 114 |  1.105 |     0.463 |   0     |        0.067 |      1 |
| new_keynesian   | ipca_12m |         6 | 114 |  1.231 |     0.516 |   0     |        0.849 |      2 |
| bvar            | ipca_12m |         6 | 114 |  1.474 |     0.618 |   0     |        0.95  |      3 |
| monetarist      | ipca_12m |         6 | 114 |  1.486 |     0.623 |   0     |        0.864 |      4 |
| ar              | ipca_12m |         6 | 114 |  1.503 |     0.63  |   0     |        0.429 |      5 |
| seasonal_naive  | ipca_12m |         6 | 114 |  1.608 |     0.674 |   0.028 |        0.069 |      6 |
| pk_sfc          | ipca_12m |         6 |  92 |  1.629 |     0.688 |   0.003 |        0.168 |      7 |
| random_walk     | ipca_12m |         6 | 114 |  2.386 |     1     | nan     |        0     |      8 |
| fiscal_ftpl     | ipca_12m |         6 | 114 |  2.506 |     1.05  |   0.702 |        0     |      9 |
| new_keynesian   | ipca_12m |        12 | 108 |  1.802 |     0.463 |   0     |        0.53  |      1 |
| focus_consensus | ipca_12m |        12 | 108 |  1.813 |     0.466 |   0     |        0.148 |      2 |
| ar              | ipca_12m |        12 | 108 |  2.136 |     0.549 |   0     |        0.845 |      3 |
| bvar            | ipca_12m |        12 | 108 |  2.201 |     0.566 |   0     |        0.118 |      4 |
| monetarist      | ipca_12m |        12 | 108 |  2.206 |     0.567 |   0     |        0.109 |      5 |
| pk_sfc          | ipca_12m |        12 |  86 |  2.506 |     0.639 |   0.012 |        0     |      6 |
| seasonal_naive  | ipca_12m |        12 | 108 |  2.536 |     0.652 |   0.01  |        0.004 |      7 |
| random_walk     | ipca_12m |        12 | 108 |  3.891 |     1     | nan     |        0     |      8 |
| fiscal_ftpl     | ipca_12m |        12 | 108 |  8.543 |     2.196 |   0.028 |        0     |      9 |
| focus_consensus | selic    |        12 | 108 |  2.021 |     0.704 |   0.084 |        0.826 |      1 |
| new_keynesian   | selic    |        12 | 108 |  2.685 |     0.935 |   0.721 |        0.498 |      2 |
| random_walk     | selic    |        12 | 108 |  2.87  |     1     | nan     |        0.059 |      3 |
| seasonal_naive  | selic    |        12 | 108 |  2.87  |     1     | nan     |        0.059 |      3 |
| pk_sfc          | selic    |        12 |  86 |  2.891 |     1     | nan     |        0.122 |      5 |
| ar              | selic    |        12 | 108 |  3.142 |     1.095 |   0.532 |        0.742 |      6 |
| monetarist      | selic    |        12 | 108 |  3.794 |     1.322 |   0.182 |        0.725 |      7 |
| bvar            | selic    |        12 | 108 |  3.993 |     1.391 |   0.123 |        0.91  |      8 |
| fiscal_ftpl     | selic    |        12 | 108 |  8.535 |     2.973 |   0.002 |        0     |      9 |

## School model status

- **new_keynesian**: `REJECTED` after 1 rounds (variant R1, run `3f0d230adab02ce7`).
  - Reason: high-severity defects remain.
  - Shown for reference only; this is not a validated school forecast.
- **monetarist**: `REJECTED` after 1 rounds (variant R1, run `8ab354e552e0c374`).
  - Reason: high-severity defects remain.
  - Shown for reference only; this is not a validated school forecast.
- **fiscal_ftpl**: `REJECTED` after 1 rounds (variant R1, run `08a33e57b8676d20`).
  - Reason: high-severity defects remain.
  - Shown for reference only; this is not a validated school forecast.
- **pk_sfc**: `REJECTED` after 1 rounds (variant R1, run `893c058bf19467b9`).
  - Reason: high-severity defects remain.
  - Shown for reference only; this is not a validated school forecast.

All four school models are rejected; see `reports/final_report.md` for the cross-school ensemble, disagreement and lockbox.

## Data and method notes

- Vintage: observations are filtered by `release_date <= origin`; revision history is not available for most series, so this is pseudo-real-time.
- Evaluation: final-vintage outcomes, joined only in the evaluator.
- Lockbox 2020-01..2026-10 is sealed for model selection; see the one-time lockbox report.
- The 12-month IPCA forecast is derived by compounding the monthly path.
- New Keynesian R1 is the terminal variant; the Phase 2 schools are Monetarist, Fiscal/FTPL and PK-SFC.
