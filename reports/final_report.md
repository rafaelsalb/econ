# Brazil macro model hub — final report

Generated: 2026-11-24T01:16:31

## Phase status

| Phase | State |
|---|---|
| 0 — data, benchmarks, registry, evaluator | Complete |
| 1 — New Keynesian, critic loop | Complete, `REJECTED` |
| 2 — Monetarist, FTPL, SFC | Complete, all `REJECTED` with reasons |
| 3 — ensembles, fan, lockbox | Complete |

## School terminal states

| model | status | reason |
|---|---|---|
| new_keynesian | REJECTED | high-severity defects remain |
| monetarist | REJECTED | high-severity defects remain |
| fiscal_ftpl | REJECTED | high-severity defects remain |
| pk_sfc | REJECTED | high-severity defects remain |

## Validation scoreboard (primary cells)

| model_id        | target   |   horizon |   n |   rmse |   theil_u |   focus_ratio | satellite   |
|:----------------|:---------|----------:|----:|-------:|----------:|--------------:|:------------|
| focus_consensus | gdp_qq   |         1 | 117 |  0.849 |     0.741 |       nan     | False       |
| monetarist      | gdp_qq   |         1 | 117 |  1.003 |     0.875 |         1.181 | True        |
| ar              | gdp_qq   |         1 | 117 |  1.067 |     0.931 |         1.257 | False       |
| ibc_bridge      | gdp_qq   |         1 | 117 |  1.078 |     0.94  |         1.269 | False       |
| bvar            | gdp_qq   |         1 | 117 |  1.095 |     0.956 |         1.29  | False       |
| random_walk     | gdp_qq   |         1 | 117 |  1.146 |     1     |         1.35  | False       |
| seasonal_naive  | gdp_qq   |         1 | 117 |  1.252 |     1.093 |         1.475 | False       |
| new_keynesian   | gdp_qq   |         1 | 117 |  1.303 |     1.136 |         1.534 | True        |
| fiscal_ftpl     | gdp_qq   |         1 | 117 |  1.399 |     1.221 |         1.648 | True        |
| pk_sfc          | gdp_qq   |         1 |  95 |  1.815 |     1.55  |         2.072 | False       |
| focus_consensus | gdp_qq   |         4 | 108 |  1.03  |     0.773 |       nan     | False       |
| pk_sfc          | gdp_qq   |         4 |  86 |  1.078 |     0.811 |         1.076 | False       |
| ar              | gdp_qq   |         4 | 108 |  1.163 |     0.873 |         1.13  | False       |
| monetarist      | gdp_qq   |         4 | 108 |  1.178 |     0.884 |         1.144 | True        |
| ibc_bridge      | gdp_qq   |         4 | 108 |  1.185 |     0.889 |         1.15  | False       |
| bvar            | gdp_qq   |         4 | 108 |  1.202 |     0.902 |         1.167 | False       |
| new_keynesian   | gdp_qq   |         4 | 108 |  1.246 |     0.935 |         1.21  | True        |
| random_walk     | gdp_qq   |         4 | 108 |  1.333 |     1     |         1.294 | False       |
| seasonal_naive  | gdp_qq   |         4 | 108 |  1.333 |     1     |         1.294 | False       |
| fiscal_ftpl     | gdp_qq   |         4 | 108 |  5.013 |     3.761 |         4.868 | True        |
| focus_consensus | ipca_12m |         6 | 114 |  1.105 |     0.463 |       nan     | False       |
| new_keynesian   | ipca_12m |         6 | 114 |  1.231 |     0.516 |         1.114 | False       |
| bvar            | ipca_12m |         6 | 114 |  1.474 |     0.618 |         1.334 | False       |
| monetarist      | ipca_12m |         6 | 114 |  1.486 |     0.623 |         1.345 | False       |
| ar              | ipca_12m |         6 | 114 |  1.503 |     0.63  |         1.361 | False       |
| seasonal_naive  | ipca_12m |         6 | 114 |  1.608 |     0.674 |         1.455 | False       |
| pk_sfc          | ipca_12m |         6 |  92 |  1.629 |     0.688 |         1.434 | False       |
| random_walk     | ipca_12m |         6 | 114 |  2.386 |     1     |         2.16  | False       |
| fiscal_ftpl     | ipca_12m |         6 | 114 |  2.506 |     1.05  |         2.269 | False       |
| new_keynesian   | ipca_12m |        12 | 108 |  1.802 |     0.463 |         0.994 | False       |
| focus_consensus | ipca_12m |        12 | 108 |  1.813 |     0.466 |       nan     | False       |
| ar              | ipca_12m |        12 | 108 |  2.136 |     0.549 |         1.179 | False       |
| bvar            | ipca_12m |        12 | 108 |  2.201 |     0.566 |         1.214 | False       |
| monetarist      | ipca_12m |        12 | 108 |  2.206 |     0.567 |         1.217 | False       |
| pk_sfc          | ipca_12m |        12 |  86 |  2.506 |     0.639 |         1.316 | False       |
| seasonal_naive  | ipca_12m |        12 | 108 |  2.536 |     0.652 |         1.399 | False       |
| random_walk     | ipca_12m |        12 | 108 |  3.891 |     1     |         2.146 | False       |
| fiscal_ftpl     | ipca_12m |        12 | 108 |  8.543 |     2.196 |         4.713 | False       |
| focus_consensus | selic    |        12 | 108 |  2.021 |     0.704 |       nan     | False       |
| new_keynesian   | selic    |        12 | 108 |  2.685 |     0.935 |         1.328 | False       |
| random_walk     | selic    |        12 | 108 |  2.87  |     1     |         1.42  | False       |
| seasonal_naive  | selic    |        12 | 108 |  2.87  |     1     |         1.42  | False       |
| pk_sfc          | selic    |        12 |  86 |  2.891 |     1     |         1.507 | True        |
| ar              | selic    |        12 | 108 |  3.142 |     1.095 |         1.554 | False       |
| monetarist      | selic    |        12 | 108 |  3.794 |     1.322 |         1.877 | False       |
| bvar            | selic    |        12 | 108 |  3.993 |     1.391 |         1.976 | False       |
| fiscal_ftpl     | selic    |        12 | 108 |  8.535 |     2.973 |         4.223 | False       |

## Ensemble

| model_id                | target   |   horizon |   n |   rmse |   theil_u |   focus_ratio |
|:------------------------|:---------|----------:|----:|-------:|----------:|--------------:|
| ensemble_school_perf    | gdp_qq   |         0 | 120 |  0.676 |     0.583 |         0.823 |
| ensemble_combined_perf  | gdp_qq   |         0 | 120 |  0.696 |     0.6   |         0.847 |
| ensemble_school_equal   | gdp_qq   |         0 | 120 |  0.707 |     0.609 |         0.86  |
| ensemble_combined_equal | gdp_qq   |         0 | 120 |  0.721 |     0.621 |         0.876 |
| ensemble_school_equal   | gdp_qq   |         1 | 117 |  0.881 |     0.769 |         1.038 |
| ensemble_combined_equal | gdp_qq   |         1 | 117 |  0.891 |     0.777 |         1.049 |
| ensemble_combined_perf  | gdp_qq   |         1 | 117 |  0.914 |     0.797 |         1.076 |
| ensemble_school_perf    | gdp_qq   |         1 | 117 |  0.932 |     0.813 |         1.098 |
| ensemble_combined_perf  | gdp_qq   |         2 | 114 |  0.969 |     0.847 |         1.063 |
| ensemble_school_perf    | gdp_qq   |         2 | 114 |  1.01  |     0.883 |         1.108 |
| ensemble_combined_equal | gdp_qq   |         2 | 114 |  1.025 |     0.896 |         1.125 |
| ensemble_school_equal   | gdp_qq   |         2 | 114 |  1.226 |     1.072 |         1.345 |
| ensemble_combined_perf  | gdp_qq   |         3 | 111 |  1.013 |     0.785 |         1.047 |
| ensemble_school_perf    | gdp_qq   |         3 | 111 |  1.016 |     0.788 |         1.05  |
| ensemble_combined_equal | gdp_qq   |         3 | 111 |  1.159 |     0.898 |         1.198 |
| ensemble_school_equal   | gdp_qq   |         3 | 111 |  1.654 |     1.282 |         1.709 |
| ensemble_school_perf    | gdp_qq   |         4 | 108 |  0.994 |     0.746 |         0.965 |
| ensemble_combined_perf  | gdp_qq   |         4 | 108 |  1.029 |     0.772 |         0.999 |
| ensemble_combined_equal | gdp_qq   |         4 | 108 |  1.265 |     0.949 |         1.228 |
| ensemble_school_equal   | gdp_qq   |         4 | 108 |  1.909 |     1.432 |         1.854 |
| ensemble_combined_perf  | ipca_12m |         3 | 117 |  0.846 |     0.669 |         1.126 |
| ensemble_combined_equal | ipca_12m |         3 | 117 |  0.864 |     0.684 |         1.15  |
| ensemble_school_perf    | ipca_12m |         3 | 117 |  0.924 |     0.731 |         1.23  |
| ensemble_school_equal   | ipca_12m |         3 | 117 |  0.941 |     0.745 |         1.253 |
| ensemble_combined_perf  | ipca_12m |         6 | 114 |  1.293 |     0.542 |         1.171 |
| ensemble_combined_equal | ipca_12m |         6 | 114 |  1.377 |     0.577 |         1.247 |
| ensemble_school_perf    | ipca_12m |         6 | 114 |  1.391 |     0.583 |         1.259 |
| ensemble_school_equal   | ipca_12m |         6 | 114 |  1.517 |     0.636 |         1.373 |
| ensemble_combined_perf  | ipca_12m |        12 | 108 |  1.982 |     0.51  |         1.094 |
| ensemble_school_perf    | ipca_12m |        12 | 108 |  2.084 |     0.536 |         1.15  |
| ensemble_combined_equal | ipca_12m |        12 | 108 |  2.52  |     0.648 |         1.39  |
| ensemble_school_equal   | ipca_12m |        12 | 108 |  3.4   |     0.874 |         1.876 |
| ensemble_combined_perf  | ipca_m   |         0 | 120 |  0.246 |     0.884 |         0.978 |
| ensemble_combined_equal | ipca_m   |         0 | 120 |  0.249 |     0.896 |         0.992 |
| ensemble_school_perf    | ipca_m   |         0 | 120 |  0.262 |     0.942 |         1.042 |
| ensemble_school_equal   | ipca_m   |         0 | 120 |  0.265 |     0.955 |         1.056 |
| ensemble_combined_perf  | ipca_m   |         1 | 119 |  0.289 |     0.789 |         1.073 |
| ensemble_combined_equal | ipca_m   |         1 | 119 |  0.291 |     0.794 |         1.08  |
| ensemble_school_perf    | ipca_m   |         1 | 119 |  0.301 |     0.821 |         1.117 |
| ensemble_school_equal   | ipca_m   |         1 | 119 |  0.302 |     0.824 |         1.121 |
| ensemble_combined_perf  | ipca_m   |         2 | 118 |  0.298 |     0.769 |         1.052 |
| ensemble_combined_equal | ipca_m   |         2 | 118 |  0.299 |     0.772 |         1.056 |
| ensemble_school_perf    | ipca_m   |         2 | 118 |  0.309 |     0.797 |         1.09  |
| ensemble_school_equal   | ipca_m   |         2 | 118 |  0.31  |     0.802 |         1.097 |
| ensemble_combined_perf  | ipca_m   |         3 | 117 |  0.307 |     0.726 |         1.053 |
| ensemble_combined_equal | ipca_m   |         3 | 117 |  0.309 |     0.733 |         1.063 |
| ensemble_school_perf    | ipca_m   |         3 | 117 |  0.316 |     0.749 |         1.086 |
| ensemble_school_equal   | ipca_m   |         3 | 117 |  0.322 |     0.762 |         1.104 |
| ensemble_combined_perf  | ipca_m   |         4 | 116 |  0.313 |     0.684 |         1.049 |
| ensemble_combined_equal | ipca_m   |         4 | 116 |  0.32  |     0.699 |         1.072 |
| ensemble_school_perf    | ipca_m   |         4 | 116 |  0.32  |     0.7   |         1.072 |
| ensemble_school_equal   | ipca_m   |         4 | 116 |  0.334 |     0.73  |         1.12  |
| ensemble_combined_perf  | ipca_m   |         5 | 115 |  0.315 |     0.689 |         1.021 |
| ensemble_school_perf    | ipca_m   |         5 | 115 |  0.321 |     0.702 |         1.041 |
| ensemble_combined_equal | ipca_m   |         5 | 115 |  0.323 |     0.707 |         1.049 |
| ensemble_school_equal   | ipca_m   |         5 | 115 |  0.346 |     0.755 |         1.121 |
| ensemble_combined_perf  | ipca_m   |         6 | 114 |  0.314 |     0.693 |         1.004 |
| ensemble_school_perf    | ipca_m   |         6 | 114 |  0.321 |     0.708 |         1.025 |
| ensemble_combined_equal | ipca_m   |         6 | 114 |  0.325 |     0.717 |         1.039 |
| ensemble_school_equal   | ipca_m   |         6 | 114 |  0.359 |     0.792 |         1.147 |
| ensemble_combined_perf  | ipca_m   |         7 | 113 |  0.313 |     0.735 |         0.998 |
| ensemble_school_perf    | ipca_m   |         7 | 113 |  0.324 |     0.761 |         1.033 |
| ensemble_combined_equal | ipca_m   |         7 | 113 |  0.331 |     0.778 |         1.056 |
| ensemble_school_equal   | ipca_m   |         7 | 113 |  0.386 |     0.907 |         1.232 |
| ensemble_combined_perf  | ipca_m   |         8 | 112 |  0.308 |     0.805 |         0.99  |
| ensemble_school_perf    | ipca_m   |         8 | 112 |  0.325 |     0.849 |         1.043 |
| ensemble_combined_equal | ipca_m   |         8 | 112 |  0.334 |     0.874 |         1.074 |
| ensemble_school_equal   | ipca_m   |         8 | 112 |  0.41  |     1.071 |         1.317 |
| ensemble_combined_perf  | ipca_m   |         9 | 111 |  0.308 |     0.834 |         0.991 |
| ensemble_school_perf    | ipca_m   |         9 | 111 |  0.328 |     0.886 |         1.053 |
| ensemble_combined_equal | ipca_m   |         9 | 111 |  0.346 |     0.937 |         1.113 |
| ensemble_school_equal   | ipca_m   |         9 | 111 |  0.438 |     1.185 |         1.408 |
| ensemble_combined_perf  | ipca_m   |        10 | 110 |  0.31  |     0.831 |         0.995 |
| ensemble_school_perf    | ipca_m   |        10 | 110 |  0.328 |     0.879 |         1.052 |
| ensemble_combined_equal | ipca_m   |        10 | 110 |  0.359 |     0.965 |         1.155 |
| ensemble_school_equal   | ipca_m   |        10 | 110 |  0.463 |     1.243 |         1.488 |
| ensemble_combined_perf  | ipca_m   |        11 | 109 |  0.312 |     0.812 |         1.006 |
| ensemble_school_perf    | ipca_m   |        11 | 109 |  0.328 |     0.853 |         1.056 |
| ensemble_combined_equal | ipca_m   |        11 | 109 |  0.375 |     0.976 |         1.209 |
| ensemble_school_equal   | ipca_m   |        11 | 109 |  0.492 |     1.279 |         1.584 |
| ensemble_combined_perf  | ipca_m   |        12 | 108 |  0.317 |     0.804 |         1.012 |
| ensemble_school_perf    | ipca_m   |        12 | 108 |  0.33  |     0.838 |         1.055 |
| ensemble_combined_equal | ipca_m   |        12 | 108 |  0.387 |     0.982 |         1.237 |
| ensemble_school_equal   | ipca_m   |        12 | 108 |  0.512 |     1.3   |         1.637 |
| ensemble_combined_perf  | selic    |         3 | 117 |  0.66  |     0.76  |         1.304 |
| ensemble_school_perf    | selic    |         3 | 117 |  0.867 |     0.999 |         1.713 |
| ensemble_combined_equal | selic    |         3 | 117 |  0.913 |     1.052 |         1.804 |
| ensemble_school_equal   | selic    |         3 | 117 |  1.06  |     1.221 |         2.094 |
| ensemble_combined_perf  | selic    |         6 | 114 |  1.34  |     0.829 |         1.306 |
| ensemble_combined_equal | selic    |         6 | 114 |  1.535 |     0.949 |         1.496 |
| ensemble_school_perf    | selic    |         6 | 114 |  1.573 |     0.973 |         1.533 |
| ensemble_school_equal   | selic    |         6 | 114 |  2.066 |     1.278 |         2.013 |
| ensemble_combined_equal | selic    |        12 | 108 |  2.417 |     0.842 |         1.196 |
| ensemble_combined_perf  | selic    |        12 | 108 |  2.489 |     0.867 |         1.231 |
| ensemble_school_perf    | selic    |        12 | 108 |  2.585 |     0.901 |         1.279 |
| ensemble_school_equal   | selic    |        12 | 108 |  2.845 |     0.991 |         1.408 |

## Lockbox

Opened once at 2026-11-24T01:12:23 · run `db620d60530fb7f6` · data hash `14b49d7a27ffc32f5b329420c1b05c08a4b37215bf3b644d6da8e29f982f8ca8`.

| model_id        | target   |   horizon |   n |   rmse |   theil_u |   focus_ratio |
|:----------------|:---------|----------:|----:|-------:|----------:|--------------:|
| monetarist      | gdp_qq   |         1 |  75 |  2.624 |     0.647 |         0.908 |
| fiscal_ftpl     | gdp_qq   |         1 |  75 |  2.681 |     0.661 |         0.928 |
| ibc_bridge      | gdp_qq   |         1 |  75 |  2.72  |     0.671 |         0.942 |
| bvar            | gdp_qq   |         1 |  75 |  2.721 |     0.671 |         0.942 |
| ar              | gdp_qq   |         1 |  75 |  2.731 |     0.674 |         0.946 |
| pk_sfc          | gdp_qq   |         1 |  75 |  2.758 |     0.68  |         0.955 |
| focus_consensus | gdp_qq   |         1 |  75 |  2.888 |     0.713 |       nan     |
| seasonal_naive  | gdp_qq   |         1 |  75 |  3.56  |     0.878 |         1.233 |
| random_walk     | gdp_qq   |         1 |  75 |  4.054 |     1     |         1.403 |
| new_keynesian   | gdp_qq   |         1 |  75 |  4.672 |     1.153 |         1.618 |
| ibc_bridge      | gdp_qq   |         4 |  66 |  0.542 |     0.193 |         0.846 |
| monetarist      | gdp_qq   |         4 |  66 |  0.543 |     0.193 |         0.847 |
| ar              | gdp_qq   |         4 |  66 |  0.572 |     0.204 |         0.893 |
| focus_consensus | gdp_qq   |         4 |  66 |  0.641 |     0.228 |       nan     |
| fiscal_ftpl     | gdp_qq   |         4 |  66 |  0.649 |     0.231 |         1.012 |
| bvar            | gdp_qq   |         4 |  66 |  0.652 |     0.232 |         1.018 |
| pk_sfc          | gdp_qq   |         4 |  66 |  1.338 |     0.476 |         2.088 |
| new_keynesian   | gdp_qq   |         4 |  66 |  2.606 |     0.927 |         4.067 |
| random_walk     | gdp_qq   |         4 |  66 |  2.811 |     1     |         4.386 |
| seasonal_naive  | gdp_qq   |         4 |  66 |  2.811 |     1     |         4.386 |
| monetarist      | ipca_12m |         6 |  76 |  1.839 |     0.551 |         0.946 |
| bvar            | ipca_12m |         6 |  76 |  1.84  |     0.552 |         0.947 |
| pk_sfc          | ipca_12m |         6 |  76 |  1.866 |     0.559 |         0.96  |
| ar              | ipca_12m |         6 |  76 |  1.874 |     0.562 |         0.964 |
| focus_consensus | ipca_12m |         6 |  76 |  1.943 |     0.583 |       nan     |
| fiscal_ftpl     | ipca_12m |         6 |  76 |  2.238 |     0.671 |         1.152 |
| new_keynesian   | ipca_12m |         6 |  76 |  2.405 |     0.721 |         1.238 |
| seasonal_naive  | ipca_12m |         6 |  76 |  2.449 |     0.734 |         1.26  |
| random_walk     | ipca_12m |         6 |  76 |  3.336 |     1     |         1.717 |
| ar              | ipca_12m |        12 |  70 |  2.486 |     0.437 |         0.738 |
| monetarist      | ipca_12m |        12 |  70 |  2.54  |     0.446 |         0.754 |
| bvar            | ipca_12m |        12 |  70 |  2.547 |     0.448 |         0.756 |
| pk_sfc          | ipca_12m |        12 |  70 |  2.577 |     0.453 |         0.765 |
| focus_consensus | ipca_12m |        12 |  70 |  3.369 |     0.592 |       nan     |
| seasonal_naive  | ipca_12m |        12 |  70 |  3.879 |     0.682 |         1.151 |
| new_keynesian   | ipca_12m |        12 |  70 |  3.952 |     0.695 |         1.173 |
| fiscal_ftpl     | ipca_12m |        12 |  70 |  4.273 |     0.751 |         1.268 |
| random_walk     | ipca_12m |        12 |  70 |  5.689 |     1     |         1.688 |
| ar              | selic    |        12 |  70 |  2.876 |     0.686 |         0.859 |
| focus_consensus | selic    |        12 |  70 |  3.347 |     0.798 |       nan     |
| bvar            | selic    |        12 |  70 |  3.565 |     0.85  |         1.065 |
| monetarist      | selic    |        12 |  70 |  3.659 |     0.872 |         1.093 |
| pk_sfc          | selic    |        12 |  70 |  4.194 |     1     |         1.253 |
| random_walk     | selic    |        12 |  70 |  4.194 |     1     |         1.253 |
| seasonal_naive  | selic    |        12 |  70 |  4.194 |     1     |         1.253 |
| new_keynesian   | selic    |        12 |  70 |  5.65  |     1.347 |         1.688 |
| fiscal_ftpl     | selic    |        12 |  70 |  6.191 |     1.476 |         1.85  |

### Lockbox ensemble

| model_id                | target   |   horizon |   n |   rmse |   theil_u |   focus_ratio |
|:------------------------|:---------|----------:|----:|-------:|----------:|--------------:|
| ensemble_combined_perf  | gdp_qq   |         1 |  75 |  2.848 |     0.703 |         0.986 |
| ensemble_combined_equal | gdp_qq   |         1 |  75 |  2.857 |     0.705 |         0.989 |
| ensemble_school_perf    | gdp_qq   |         1 |  75 |  3.041 |     0.75  |         1.053 |
| ensemble_school_equal   | gdp_qq   |         1 |  75 |  3.048 |     0.752 |         1.055 |
| ensemble_combined_perf  | gdp_qq   |         4 |  66 |  0.834 |     0.297 |         1.302 |
| ensemble_combined_equal | gdp_qq   |         4 |  66 |  0.855 |     0.304 |         1.335 |
| ensemble_school_equal   | gdp_qq   |         4 |  66 |  1.007 |     0.358 |         1.571 |
| ensemble_school_perf    | gdp_qq   |         4 |  66 |  1.142 |     0.406 |         1.783 |
| ensemble_combined_perf  | ipca_12m |         6 |  76 |  1.879 |     0.563 |         0.967 |
| ensemble_combined_equal | ipca_12m |         6 |  76 |  1.893 |     0.567 |         0.974 |
| ensemble_school_equal   | ipca_12m |         6 |  76 |  1.941 |     0.582 |         0.999 |
| ensemble_school_perf    | ipca_12m |         6 |  76 |  1.971 |     0.591 |         1.014 |
| ensemble_combined_equal | ipca_12m |        12 |  70 |  2.886 |     0.507 |         0.857 |
| ensemble_combined_perf  | ipca_12m |        12 |  70 |  2.9   |     0.51  |         0.861 |
| ensemble_school_equal   | ipca_12m |        12 |  70 |  2.949 |     0.518 |         0.875 |
| ensemble_school_perf    | ipca_12m |        12 |  70 |  3.038 |     0.534 |         0.902 |
| ensemble_combined_perf  | selic    |        12 |  70 |  3.253 |     0.776 |         0.972 |
| ensemble_combined_equal | selic    |        12 |  70 |  3.345 |     0.797 |         0.999 |
| ensemble_school_perf    | selic    |        12 |  70 |  3.524 |     0.84  |         1.053 |
| ensemble_school_equal   | selic    |        12 |  70 |  3.693 |     0.881 |         1.103 |

## Interpretation

- The benchmark suite, led by the Focus consensus, remains the strongest
  comparator on the validation window. No school model passed its
  pre-registered gate.
- On the one-time lockbox, the combined ensemble beats Focus on IPCA h=12
  and Selic h=12. The Monetarist and AR models also beat Focus on IPCA
  h=12. This is a combination/benchmark result; it does not reverse the
  validation rejections of the individual schools.
- The New Keynesian model fails on gap significance, FX sign and Focus
  value added; Monetarist fails the P-star channel on validation; FTPL is
  rejected as Ricardian; the SFC-lite fails its behavioral sign restrictions.
- The ensemble is a diagnostic synthesis of rejected models, not a
  validated forecast. The benchmark ensemble is the stronger comparator.
- The lockbox is a one-time reading. It must not be reused for selection.

## Reproducibility

Every run is identified by a hash of models, config, seed, data and code.
The registry is append-only; the model cards and decisions are in `specs/`.
