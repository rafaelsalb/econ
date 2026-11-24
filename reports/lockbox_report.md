# Lockbox report — 2020-01 to 2026-10

Opened: 2026-11-24T01:12:23 · run `db620d60530fb7f6`
Data hash: `14b49d7a27ffc32f5b329420c1b05c08a4b37215bf3b644d6da8e29f982f8ca8` · code hash: `78c695a959fef6b48ada93dd76f6ffe3fed73667aaad7296722bf31dca782b6f`
Models: new_keynesian, monetarist, fiscal_ftpl, pk_sfc, random_walk, seasonal_naive, ar, bvar, ibc_bridge, focus_consensus

This is the single lockbox evaluation. The weights were fitted on the
2010–2019 validation window and frozen before this run.

## School terminal states (validation)

| model | status | reason |
|---|---|---|
| new_keynesian | REJECTED | high-severity defects remain |
| monetarist | REJECTED | high-severity defects remain |
| fiscal_ftpl | REJECTED | high-severity defects remain |
| pk_sfc | REJECTED | high-severity defects remain |

## Lockbox scoreboard (primary cells)

| model_id        | target   |   horizon |   n |   rmse |   theil_u |   mz_slope_p |   focus_ratio |   rank |
|:----------------|:---------|----------:|----:|-------:|----------:|-------------:|--------------:|-------:|
| monetarist      | gdp_qq   |         1 |  75 |  2.624 |     0.647 |        0.221 |         0.908 |      1 |
| fiscal_ftpl     | gdp_qq   |         1 |  75 |  2.681 |     0.661 |        0.057 |         0.928 |      2 |
| ibc_bridge      | gdp_qq   |         1 |  75 |  2.72  |     0.671 |        0     |         0.942 |      3 |
| bvar            | gdp_qq   |         1 |  75 |  2.721 |     0.671 |        0     |         0.942 |      4 |
| ar              | gdp_qq   |         1 |  75 |  2.731 |     0.674 |        0     |         0.946 |      5 |
| pk_sfc          | gdp_qq   |         1 |  75 |  2.758 |     0.68  |        0.013 |         0.955 |      6 |
| focus_consensus | gdp_qq   |         1 |  75 |  2.888 |     0.713 |        0     |       nan     |      7 |
| seasonal_naive  | gdp_qq   |         1 |  75 |  3.56  |     0.878 |        0     |         1.233 |      8 |
| random_walk     | gdp_qq   |         1 |  75 |  4.054 |     1     |        0     |         1.403 |      9 |
| new_keynesian   | gdp_qq   |         1 |  75 |  4.672 |     1.153 |        0     |         1.618 |     10 |
| ibc_bridge      | gdp_qq   |         4 |  66 |  0.542 |     0.193 |        0.027 |         0.846 |      1 |
| monetarist      | gdp_qq   |         4 |  66 |  0.543 |     0.193 |        0.162 |         0.847 |      2 |
| ar              | gdp_qq   |         4 |  66 |  0.572 |     0.204 |        0.002 |         0.893 |      3 |
| focus_consensus | gdp_qq   |         4 |  66 |  0.641 |     0.228 |        0.048 |       nan     |      4 |
| fiscal_ftpl     | gdp_qq   |         4 |  66 |  0.649 |     0.231 |        0     |         1.012 |      5 |
| bvar            | gdp_qq   |         4 |  66 |  0.652 |     0.232 |        0     |         1.018 |      6 |
| pk_sfc          | gdp_qq   |         4 |  66 |  1.338 |     0.476 |        0     |         2.088 |      7 |
| new_keynesian   | gdp_qq   |         4 |  66 |  2.606 |     0.927 |        0     |         4.067 |      8 |
| random_walk     | gdp_qq   |         4 |  66 |  2.811 |     1     |        0     |         4.386 |      9 |
| seasonal_naive  | gdp_qq   |         4 |  66 |  2.811 |     1     |        0     |         4.386 |      9 |
| monetarist      | ipca_12m |         6 |  76 |  1.839 |     0.551 |        0.652 |         0.946 |      1 |
| bvar            | ipca_12m |         6 |  76 |  1.84  |     0.552 |        0.636 |         0.947 |      2 |
| pk_sfc          | ipca_12m |         6 |  76 |  1.866 |     0.559 |        0.873 |         0.96  |      3 |
| ar              | ipca_12m |         6 |  76 |  1.874 |     0.562 |        0.38  |         0.964 |      4 |
| focus_consensus | ipca_12m |         6 |  76 |  1.943 |     0.583 |        0.836 |       nan     |      5 |
| fiscal_ftpl     | ipca_12m |         6 |  76 |  2.238 |     0.671 |        0.35  |         1.152 |      6 |
| new_keynesian   | ipca_12m |         6 |  76 |  2.405 |     0.721 |        0.034 |         1.238 |      7 |
| seasonal_naive  | ipca_12m |         6 |  76 |  2.449 |     0.734 |        0.037 |         1.26  |      8 |
| random_walk     | ipca_12m |         6 |  76 |  3.336 |     1     |        0     |         1.717 |      9 |
| ar              | ipca_12m |        12 |  70 |  2.486 |     0.437 |        0.164 |         0.738 |      1 |
| monetarist      | ipca_12m |        12 |  70 |  2.54  |     0.446 |        0.022 |         0.754 |      2 |
| bvar            | ipca_12m |        12 |  70 |  2.547 |     0.448 |        0.009 |         0.756 |      3 |
| pk_sfc          | ipca_12m |        12 |  70 |  2.577 |     0.453 |        0     |         0.765 |      4 |
| focus_consensus | ipca_12m |        12 |  70 |  3.369 |     0.592 |        0     |       nan     |      5 |
| seasonal_naive  | ipca_12m |        12 |  70 |  3.879 |     0.682 |        0     |         1.151 |      6 |
| new_keynesian   | ipca_12m |        12 |  70 |  3.952 |     0.695 |        0     |         1.173 |      7 |
| fiscal_ftpl     | ipca_12m |        12 |  70 |  4.273 |     0.751 |        0.282 |         1.268 |      8 |
| random_walk     | ipca_12m |        12 |  70 |  5.689 |     1     |        0     |         1.688 |      9 |
| ar              | selic    |        12 |  70 |  2.876 |     0.686 |        0.126 |         0.859 |      1 |
| focus_consensus | selic    |        12 |  70 |  3.347 |     0.798 |        0.154 |       nan     |      2 |
| bvar            | selic    |        12 |  70 |  3.565 |     0.85  |        0.466 |         1.065 |      3 |
| monetarist      | selic    |        12 |  70 |  3.659 |     0.872 |        0.834 |         1.093 |      4 |
| pk_sfc          | selic    |        12 |  70 |  4.194 |     1     |        0.012 |         1.253 |      5 |
| random_walk     | selic    |        12 |  70 |  4.194 |     1     |        0.012 |         1.253 |      5 |
| seasonal_naive  | selic    |        12 |  70 |  4.194 |     1     |        0.012 |         1.253 |      5 |
| new_keynesian   | selic    |        12 |  70 |  5.65  |     1.347 |        0     |         1.688 |      8 |
| fiscal_ftpl     | selic    |        12 |  70 |  6.191 |     1.476 |        0     |         1.85  |      9 |

## Ensemble scoreboard

| model_id                | target   |   horizon |   n |   rmse |   theil_u |   mz_slope_p |   focus_ratio |
|:------------------------|:---------|----------:|----:|-------:|----------:|-------------:|--------------:|
| ensemble_school_perf    | gdp_qq   |         0 |  78 |  1.154 |     0.284 |        0.551 |         0.433 |
| ensemble_school_equal   | gdp_qq   |         0 |  78 |  1.197 |     0.295 |        0.319 |         0.45  |
| ensemble_combined_perf  | gdp_qq   |         0 |  78 |  1.564 |     0.385 |        0.01  |         0.587 |
| ensemble_combined_equal | gdp_qq   |         0 |  78 |  1.893 |     0.466 |        0     |         0.711 |
| ensemble_combined_perf  | gdp_qq   |         1 |  75 |  2.848 |     0.703 |        0     |         0.986 |
| ensemble_combined_equal | gdp_qq   |         1 |  75 |  2.857 |     0.705 |        0     |         0.989 |
| ensemble_school_perf    | gdp_qq   |         1 |  75 |  3.041 |     0.75  |        0     |         1.053 |
| ensemble_school_equal   | gdp_qq   |         1 |  75 |  3.048 |     0.752 |        0     |         1.055 |
| ensemble_combined_equal | gdp_qq   |         2 |  72 |  1.948 |     0.577 |        0.002 |         0.975 |
| ensemble_combined_perf  | gdp_qq   |         2 |  72 |  1.952 |     0.579 |        0.002 |         0.978 |
| ensemble_school_equal   | gdp_qq   |         2 |  72 |  2.112 |     0.626 |        0     |         1.058 |
| ensemble_school_perf    | gdp_qq   |         2 |  72 |  2.169 |     0.643 |        0     |         1.086 |
| ensemble_combined_perf  | gdp_qq   |         3 |  69 |  0.973 |     0.353 |        0.001 |         0.985 |
| ensemble_combined_equal | gdp_qq   |         3 |  69 |  0.975 |     0.354 |        0     |         0.986 |
| ensemble_school_equal   | gdp_qq   |         3 |  69 |  1.067 |     0.387 |        0     |         1.08  |
| ensemble_school_perf    | gdp_qq   |         3 |  69 |  1.146 |     0.416 |        0     |         1.159 |
| ensemble_combined_perf  | gdp_qq   |         4 |  66 |  0.834 |     0.297 |        0     |         1.302 |
| ensemble_combined_equal | gdp_qq   |         4 |  66 |  0.855 |     0.304 |        0     |         1.335 |
| ensemble_school_equal   | gdp_qq   |         4 |  66 |  1.007 |     0.358 |        0     |         1.571 |
| ensemble_school_perf    | gdp_qq   |         4 |  66 |  1.142 |     0.406 |        0     |         1.783 |
| ensemble_combined_perf  | ipca_12m |         3 |  79 |  1.226 |     0.663 |        0.814 |         1.022 |
| ensemble_combined_equal | ipca_12m |         3 |  79 |  1.236 |     0.669 |        0.749 |         1.03  |
| ensemble_school_equal   | ipca_12m |         3 |  79 |  1.272 |     0.688 |        0.903 |         1.061 |
| ensemble_school_perf    | ipca_12m |         3 |  79 |  1.274 |     0.689 |        0.807 |         1.062 |
| ensemble_combined_perf  | ipca_12m |         6 |  76 |  1.879 |     0.563 |        0.466 |         0.967 |
| ensemble_combined_equal | ipca_12m |         6 |  76 |  1.893 |     0.567 |        0.347 |         0.974 |
| ensemble_school_equal   | ipca_12m |         6 |  76 |  1.941 |     0.582 |        0.483 |         0.999 |
| ensemble_school_perf    | ipca_12m |         6 |  76 |  1.971 |     0.591 |        0.361 |         1.014 |
| ensemble_combined_equal | ipca_12m |        12 |  70 |  2.886 |     0.507 |        0.003 |         0.857 |
| ensemble_combined_perf  | ipca_12m |        12 |  70 |  2.9   |     0.51  |        0     |         0.861 |
| ensemble_school_equal   | ipca_12m |        12 |  70 |  2.949 |     0.518 |        0.05  |         0.875 |
| ensemble_school_perf    | ipca_12m |        12 |  70 |  3.038 |     0.534 |        0     |         0.902 |
| ensemble_combined_perf  | ipca_m   |         0 |  82 |  0.35  |     0.803 |        0.51  |         1.015 |
| ensemble_combined_equal | ipca_m   |         0 |  82 |  0.35  |     0.803 |        0.353 |         1.015 |
| ensemble_school_perf    | ipca_m   |         0 |  82 |  0.358 |     0.822 |        0.372 |         1.04  |
| ensemble_school_equal   | ipca_m   |         0 |  82 |  0.361 |     0.829 |        0.219 |         1.049 |
| ensemble_combined_equal | ipca_m   |         1 |  81 |  0.38  |     0.805 |        0.443 |         0.99  |
| ensemble_combined_perf  | ipca_m   |         1 |  81 |  0.381 |     0.806 |        0.301 |         0.992 |
| ensemble_school_perf    | ipca_m   |         1 |  81 |  0.395 |     0.837 |        0.415 |         1.03  |
| ensemble_school_equal   | ipca_m   |         1 |  81 |  0.395 |     0.838 |        0.326 |         1.031 |
| ensemble_combined_equal | ipca_m   |         2 |  80 |  0.415 |     0.748 |        0.532 |         1.007 |
| ensemble_combined_perf  | ipca_m   |         2 |  80 |  0.415 |     0.748 |        0.623 |         1.007 |
| ensemble_school_equal   | ipca_m   |         2 |  80 |  0.428 |     0.773 |        0.215 |         1.04  |
| ensemble_school_perf    | ipca_m   |         2 |  80 |  0.429 |     0.773 |        0.175 |         1.041 |
| ensemble_combined_perf  | ipca_m   |         3 |  79 |  0.427 |     0.705 |        0.389 |         0.975 |
| ensemble_combined_equal | ipca_m   |         3 |  79 |  0.428 |     0.707 |        0.348 |         0.978 |
| ensemble_school_equal   | ipca_m   |         3 |  79 |  0.436 |     0.719 |        0.139 |         0.995 |
| ensemble_school_perf    | ipca_m   |         3 |  79 |  0.437 |     0.721 |        0.093 |         0.997 |
| ensemble_combined_perf  | ipca_m   |         4 |  78 |  0.425 |     0.696 |        0.324 |         0.944 |
| ensemble_combined_equal | ipca_m   |         4 |  78 |  0.427 |     0.699 |        0.32  |         0.948 |
| ensemble_school_equal   | ipca_m   |         4 |  78 |  0.437 |     0.716 |        0.041 |         0.971 |
| ensemble_school_perf    | ipca_m   |         4 |  78 |  0.438 |     0.717 |        0.015 |         0.972 |
| ensemble_combined_perf  | ipca_m   |         5 |  77 |  0.423 |     0.675 |        0.123 |         0.932 |
| ensemble_combined_equal | ipca_m   |         5 |  77 |  0.425 |     0.678 |        0.15  |         0.937 |
| ensemble_school_equal   | ipca_m   |         5 |  77 |  0.436 |     0.695 |        0.004 |         0.96  |
| ensemble_school_perf    | ipca_m   |         5 |  77 |  0.437 |     0.696 |        0     |         0.962 |
| ensemble_combined_equal | ipca_m   |         6 |  76 |  0.424 |     0.707 |        0.239 |         0.917 |
| ensemble_combined_perf  | ipca_m   |         6 |  76 |  0.424 |     0.707 |        0.149 |         0.917 |
| ensemble_school_equal   | ipca_m   |         6 |  76 |  0.441 |     0.736 |        0.009 |         0.955 |
| ensemble_school_perf    | ipca_m   |         6 |  76 |  0.443 |     0.739 |        0     |         0.958 |
| ensemble_combined_perf  | ipca_m   |         7 |  75 |  0.425 |     0.705 |        0.131 |         0.916 |
| ensemble_combined_equal | ipca_m   |         7 |  75 |  0.425 |     0.705 |        0.237 |         0.916 |
| ensemble_school_equal   | ipca_m   |         7 |  75 |  0.442 |     0.732 |        0.051 |         0.951 |
| ensemble_school_perf    | ipca_m   |         7 |  75 |  0.443 |     0.733 |        0     |         0.953 |
| ensemble_combined_equal | ipca_m   |         8 |  74 |  0.422 |     0.727 |        0.434 |         0.902 |
| ensemble_combined_perf  | ipca_m   |         8 |  74 |  0.423 |     0.728 |        0.257 |         0.903 |
| ensemble_school_perf    | ipca_m   |         8 |  74 |  0.437 |     0.753 |        0     |         0.934 |
| ensemble_school_equal   | ipca_m   |         8 |  74 |  0.439 |     0.756 |        0.236 |         0.937 |
| ensemble_combined_equal | ipca_m   |         9 |  73 |  0.418 |     0.742 |        0.612 |         0.895 |
| ensemble_combined_perf  | ipca_m   |         9 |  73 |  0.419 |     0.744 |        0.442 |         0.898 |
| ensemble_school_perf    | ipca_m   |         9 |  73 |  0.43  |     0.764 |        0     |         0.922 |
| ensemble_school_equal   | ipca_m   |         9 |  73 |  0.433 |     0.768 |        0.699 |         0.927 |
| ensemble_combined_equal | ipca_m   |        10 |  72 |  0.42  |     0.739 |        0.473 |         0.903 |
| ensemble_combined_perf  | ipca_m   |        10 |  72 |  0.42  |     0.74  |        0.326 |         0.905 |
| ensemble_school_perf    | ipca_m   |        10 |  72 |  0.433 |     0.763 |        0     |         0.933 |
| ensemble_school_equal   | ipca_m   |        10 |  72 |  0.437 |     0.769 |        0.469 |         0.94  |
| ensemble_combined_equal | ipca_m   |        11 |  71 |  0.412 |     0.805 |        0.652 |         0.891 |
| ensemble_combined_perf  | ipca_m   |        11 |  71 |  0.412 |     0.806 |        0.57  |         0.892 |
| ensemble_school_perf    | ipca_m   |        11 |  71 |  0.428 |     0.837 |        0     |         0.927 |
| ensemble_school_equal   | ipca_m   |        11 |  71 |  0.433 |     0.847 |        0.695 |         0.938 |
| ensemble_school_perf    | ipca_m   |        12 |  70 |  0.415 |     0.73  |        0     |         0.928 |
| ensemble_combined_perf  | ipca_m   |        12 |  70 |  0.417 |     0.733 |        0.044 |         0.932 |
| ensemble_combined_equal | ipca_m   |        12 |  70 |  0.419 |     0.737 |        0.054 |         0.937 |
| ensemble_school_equal   | ipca_m   |        12 |  70 |  0.425 |     0.748 |        0.445 |         0.951 |
| ensemble_combined_perf  | selic    |         3 |  79 |  0.822 |     0.678 |        0.844 |         1.223 |
| ensemble_school_perf    | selic    |         3 |  79 |  0.976 |     0.805 |        0.941 |         1.453 |
| ensemble_combined_equal | selic    |         3 |  79 |  1.067 |     0.88  |        0.028 |         1.587 |
| ensemble_school_equal   | selic    |         3 |  79 |  1.16  |     0.957 |        0.025 |         1.726 |
| ensemble_combined_perf  | selic    |         6 |  76 |  1.681 |     0.728 |        0.652 |         1.145 |
| ensemble_combined_equal | selic    |         6 |  76 |  1.852 |     0.803 |        0.684 |         1.262 |
| ensemble_school_perf    | selic    |         6 |  76 |  1.873 |     0.812 |        0.227 |         1.276 |
| ensemble_school_equal   | selic    |         6 |  76 |  1.979 |     0.858 |        0.856 |         1.348 |
| ensemble_combined_perf  | selic    |        12 |  70 |  3.253 |     0.776 |        0.101 |         0.972 |
| ensemble_combined_equal | selic    |        12 |  70 |  3.345 |     0.797 |        0.172 |         0.999 |
| ensemble_school_perf    | selic    |        12 |  70 |  3.524 |     0.84  |        0     |         1.053 |
| ensemble_school_equal   | selic    |        12 |  70 |  3.693 |     0.881 |        0.026 |         1.103 |

## Caveats

- All four school models were `REJECTED` on the validation window. The
  lockbox is a final out-of-sample reading of those rejected models and
  of the benchmark/ensemble comparators, not a rescue.
- The SFC and FTPL models have shorter effective samples; their lockbox
  rows reflect only the origins where they produced forecasts.
- The lockbox is now sealed in `registry/lockbox.json`. Do not reuse it
  for model selection or another report.
