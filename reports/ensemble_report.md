# Ensemble and disagreement — validation window

Validation end: 2019-12-31. Weights are fitted on this window and frozen.

## Ensemble scoreboard

| model_id                | target   |   horizon |   n |   rmse |   theil_u |   mz_slope_p |   focus_ratio |
|:------------------------|:---------|----------:|----:|-------:|----------:|-------------:|--------------:|
| ensemble_school_perf    | gdp_qq   |         0 | 120 |  0.676 |     0.583 |        0.296 |         0.823 |
| ensemble_combined_perf  | gdp_qq   |         0 | 120 |  0.696 |     0.6   |        0.164 |         0.847 |
| ensemble_school_equal   | gdp_qq   |         0 | 120 |  0.707 |     0.609 |        0.243 |         0.86  |
| ensemble_combined_equal | gdp_qq   |         0 | 120 |  0.721 |     0.621 |        0.161 |         0.876 |
| ensemble_school_equal   | gdp_qq   |         1 | 117 |  0.881 |     0.769 |        0.189 |         1.038 |
| ensemble_combined_equal | gdp_qq   |         1 | 117 |  0.891 |     0.777 |        0.884 |         1.049 |
| ensemble_combined_perf  | gdp_qq   |         1 | 117 |  0.914 |     0.797 |        0.812 |         1.076 |
| ensemble_school_perf    | gdp_qq   |         1 | 117 |  0.932 |     0.813 |        0.811 |         1.098 |
| ensemble_combined_perf  | gdp_qq   |         2 | 114 |  0.969 |     0.847 |        0.478 |         1.063 |
| ensemble_school_perf    | gdp_qq   |         2 | 114 |  1.01  |     0.883 |        0.029 |         1.108 |
| ensemble_combined_equal | gdp_qq   |         2 | 114 |  1.025 |     0.896 |        0.035 |         1.125 |
| ensemble_school_equal   | gdp_qq   |         2 | 114 |  1.226 |     1.072 |        0     |         1.345 |
| ensemble_combined_perf  | gdp_qq   |         3 | 111 |  1.013 |     0.785 |        0.316 |         1.047 |
| ensemble_school_perf    | gdp_qq   |         3 | 111 |  1.016 |     0.788 |        0.047 |         1.05  |
| ensemble_combined_equal | gdp_qq   |         3 | 111 |  1.159 |     0.898 |        0.002 |         1.198 |
| ensemble_school_equal   | gdp_qq   |         3 | 111 |  1.654 |     1.282 |        0     |         1.709 |
| ensemble_school_perf    | gdp_qq   |         4 | 108 |  0.994 |     0.746 |        0.079 |         0.965 |
| ensemble_combined_perf  | gdp_qq   |         4 | 108 |  1.029 |     0.772 |        0.178 |         0.999 |
| ensemble_combined_equal | gdp_qq   |         4 | 108 |  1.265 |     0.949 |        0     |         1.228 |
| ensemble_school_equal   | gdp_qq   |         4 | 108 |  1.909 |     1.432 |        0     |         1.854 |
| ensemble_combined_perf  | ipca_12m |         3 | 117 |  0.846 |     0.669 |        0.654 |         1.126 |
| ensemble_combined_equal | ipca_12m |         3 | 117 |  0.864 |     0.684 |        0.915 |         1.15  |
| ensemble_school_perf    | ipca_12m |         3 | 117 |  0.924 |     0.731 |        0.811 |         1.23  |
| ensemble_school_equal   | ipca_12m |         3 | 117 |  0.941 |     0.745 |        0.903 |         1.253 |
| ensemble_combined_perf  | ipca_12m |         6 | 114 |  1.293 |     0.542 |        0.803 |         1.171 |
| ensemble_combined_equal | ipca_12m |         6 | 114 |  1.377 |     0.577 |        0.533 |         1.247 |
| ensemble_school_perf    | ipca_12m |         6 | 114 |  1.391 |     0.583 |        0.942 |         1.259 |
| ensemble_school_equal   | ipca_12m |         6 | 114 |  1.517 |     0.636 |        0.518 |         1.373 |
| ensemble_combined_perf  | ipca_12m |        12 | 108 |  1.982 |     0.51  |        0.967 |         1.094 |
| ensemble_school_perf    | ipca_12m |        12 | 108 |  2.084 |     0.536 |        0.776 |         1.15  |
| ensemble_combined_equal | ipca_12m |        12 | 108 |  2.52  |     0.648 |        0.001 |         1.39  |
| ensemble_school_equal   | ipca_12m |        12 | 108 |  3.4   |     0.874 |        0     |         1.876 |
| ensemble_combined_perf  | ipca_m   |         0 | 120 |  0.246 |     0.884 |        0.114 |         0.978 |
| ensemble_combined_equal | ipca_m   |         0 | 120 |  0.249 |     0.896 |        0.138 |         0.992 |
| ensemble_school_perf    | ipca_m   |         0 | 120 |  0.262 |     0.942 |        0.368 |         1.042 |
| ensemble_school_equal   | ipca_m   |         0 | 120 |  0.265 |     0.955 |        0.284 |         1.056 |
| ensemble_combined_perf  | ipca_m   |         1 | 119 |  0.289 |     0.789 |        0.611 |         1.073 |
| ensemble_combined_equal | ipca_m   |         1 | 119 |  0.291 |     0.794 |        0.95  |         1.08  |
| ensemble_school_perf    | ipca_m   |         1 | 119 |  0.301 |     0.821 |        0.858 |         1.117 |
| ensemble_school_equal   | ipca_m   |         1 | 119 |  0.302 |     0.824 |        0.935 |         1.121 |
| ensemble_combined_perf  | ipca_m   |         2 | 118 |  0.298 |     0.769 |        0.589 |         1.052 |
| ensemble_combined_equal | ipca_m   |         2 | 118 |  0.299 |     0.772 |        0.956 |         1.056 |
| ensemble_school_perf    | ipca_m   |         2 | 118 |  0.309 |     0.797 |        0.934 |         1.09  |
| ensemble_school_equal   | ipca_m   |         2 | 118 |  0.31  |     0.802 |        0.764 |         1.097 |
| ensemble_combined_perf  | ipca_m   |         3 | 117 |  0.307 |     0.726 |        0.83  |         1.053 |
| ensemble_combined_equal | ipca_m   |         3 | 117 |  0.309 |     0.733 |        0.606 |         1.063 |
| ensemble_school_perf    | ipca_m   |         3 | 117 |  0.316 |     0.749 |        0.449 |         1.086 |
| ensemble_school_equal   | ipca_m   |         3 | 117 |  0.322 |     0.762 |        0.094 |         1.104 |
| ensemble_combined_perf  | ipca_m   |         4 | 116 |  0.313 |     0.684 |        0.767 |         1.049 |
| ensemble_combined_equal | ipca_m   |         4 | 116 |  0.32  |     0.699 |        0.106 |         1.072 |
| ensemble_school_perf    | ipca_m   |         4 | 116 |  0.32  |     0.7   |        0.21  |         1.072 |
| ensemble_school_equal   | ipca_m   |         4 | 116 |  0.334 |     0.73  |        0.003 |         1.12  |
| ensemble_combined_perf  | ipca_m   |         5 | 115 |  0.315 |     0.689 |        0.811 |         1.021 |
| ensemble_school_perf    | ipca_m   |         5 | 115 |  0.321 |     0.702 |        0.369 |         1.041 |
| ensemble_combined_equal | ipca_m   |         5 | 115 |  0.323 |     0.707 |        0.151 |         1.049 |
| ensemble_school_equal   | ipca_m   |         5 | 115 |  0.346 |     0.755 |        0.002 |         1.121 |
| ensemble_combined_perf  | ipca_m   |         6 | 114 |  0.314 |     0.693 |        0.785 |         1.004 |
| ensemble_school_perf    | ipca_m   |         6 | 114 |  0.321 |     0.708 |        0.332 |         1.025 |
| ensemble_combined_equal | ipca_m   |         6 | 114 |  0.325 |     0.717 |        0.167 |         1.039 |
| ensemble_school_equal   | ipca_m   |         6 | 114 |  0.359 |     0.792 |        0     |         1.147 |
| ensemble_combined_perf  | ipca_m   |         7 | 113 |  0.313 |     0.735 |        0.802 |         0.998 |
| ensemble_school_perf    | ipca_m   |         7 | 113 |  0.324 |     0.761 |        0.087 |         1.033 |
| ensemble_combined_equal | ipca_m   |         7 | 113 |  0.331 |     0.778 |        0.079 |         1.056 |
| ensemble_school_equal   | ipca_m   |         7 | 113 |  0.386 |     0.907 |        0     |         1.232 |
| ensemble_combined_perf  | ipca_m   |         8 | 112 |  0.308 |     0.805 |        0.998 |         0.99  |
| ensemble_school_perf    | ipca_m   |         8 | 112 |  0.325 |     0.849 |        0.023 |         1.043 |
| ensemble_combined_equal | ipca_m   |         8 | 112 |  0.334 |     0.874 |        0.053 |         1.074 |
| ensemble_school_equal   | ipca_m   |         8 | 112 |  0.41  |     1.071 |        0     |         1.317 |
| ensemble_combined_perf  | ipca_m   |         9 | 111 |  0.308 |     0.834 |        0.977 |         0.991 |
| ensemble_school_perf    | ipca_m   |         9 | 111 |  0.328 |     0.886 |        0.005 |         1.053 |
| ensemble_combined_equal | ipca_m   |         9 | 111 |  0.346 |     0.937 |        0.006 |         1.113 |
| ensemble_school_equal   | ipca_m   |         9 | 111 |  0.438 |     1.185 |        0     |         1.408 |
| ensemble_combined_perf  | ipca_m   |        10 | 110 |  0.31  |     0.831 |        0.916 |         0.995 |
| ensemble_school_perf    | ipca_m   |        10 | 110 |  0.328 |     0.879 |        0.002 |         1.052 |
| ensemble_combined_equal | ipca_m   |        10 | 110 |  0.359 |     0.965 |        0     |         1.155 |
| ensemble_school_equal   | ipca_m   |        10 | 110 |  0.463 |     1.243 |        0     |         1.488 |
| ensemble_combined_perf  | ipca_m   |        11 | 109 |  0.312 |     0.812 |        0.653 |         1.006 |
| ensemble_school_perf    | ipca_m   |        11 | 109 |  0.328 |     0.853 |        0     |         1.056 |
| ensemble_combined_equal | ipca_m   |        11 | 109 |  0.375 |     0.976 |        0     |         1.209 |
| ensemble_school_equal   | ipca_m   |        11 | 109 |  0.492 |     1.279 |        0     |         1.584 |
| ensemble_combined_perf  | ipca_m   |        12 | 108 |  0.317 |     0.804 |        0.593 |         1.012 |
| ensemble_school_perf    | ipca_m   |        12 | 108 |  0.33  |     0.838 |        0     |         1.055 |
| ensemble_combined_equal | ipca_m   |        12 | 108 |  0.387 |     0.982 |        0     |         1.237 |
| ensemble_school_equal   | ipca_m   |        12 | 108 |  0.512 |     1.3   |        0     |         1.637 |
| ensemble_combined_perf  | selic    |         3 | 117 |  0.66  |     0.76  |        0.069 |         1.304 |
| ensemble_school_perf    | selic    |         3 | 117 |  0.867 |     0.999 |        0.033 |         1.713 |
| ensemble_combined_equal | selic    |         3 | 117 |  0.913 |     1.052 |        0     |         1.804 |
| ensemble_school_equal   | selic    |         3 | 117 |  1.06  |     1.221 |        0.001 |         2.094 |
| ensemble_combined_perf  | selic    |         6 | 114 |  1.34  |     0.829 |        0.359 |         1.306 |
| ensemble_combined_equal | selic    |         6 | 114 |  1.535 |     0.949 |        0.109 |         1.496 |
| ensemble_school_perf    | selic    |         6 | 114 |  1.573 |     0.973 |        0.252 |         1.533 |
| ensemble_school_equal   | selic    |         6 | 114 |  2.066 |     1.278 |        0.606 |         2.013 |
| ensemble_combined_equal | selic    |        12 | 108 |  2.417 |     0.842 |        0.695 |         1.196 |
| ensemble_combined_perf  | selic    |        12 | 108 |  2.489 |     0.867 |        0.727 |         1.231 |
| ensemble_school_perf    | selic    |        12 | 108 |  2.585 |     0.901 |        0.729 |         1.279 |
| ensemble_school_equal   | selic    |        12 | 108 |  2.845 |     0.991 |        0.111 |         1.408 |

## School weights (performance)

- **school:gdp_qq:0**: monetarist=0.347, new_keynesian=0.306, fiscal_ftpl=0.304, pk_sfc=0.042
- **school:gdp_qq:1**: monetarist=0.415, new_keynesian=0.246, fiscal_ftpl=0.213, pk_sfc=0.127
- **school:gdp_qq:2**: monetarist=0.397, new_keynesian=0.274, pk_sfc=0.257, fiscal_ftpl=0.072
- **school:gdp_qq:3**: monetarist=0.380, new_keynesian=0.302, pk_sfc=0.289, fiscal_ftpl=0.029
- **school:gdp_qq:4**: pk_sfc=0.380, monetarist=0.318, new_keynesian=0.284, fiscal_ftpl=0.018
- **school:ipca_12m:3**: new_keynesian=0.344, monetarist=0.255, pk_sfc=0.210, fiscal_ftpl=0.191
- **school:ipca_12m:6**: new_keynesian=0.400, monetarist=0.275, pk_sfc=0.229, fiscal_ftpl=0.097
- **school:ipca_12m:12**: new_keynesian=0.449, monetarist=0.299, pk_sfc=0.232, fiscal_ftpl=0.020
- **school:ipca_m:0**: new_keynesian=0.323, monetarist=0.259, fiscal_ftpl=0.237, pk_sfc=0.181
- **school:ipca_m:1**: new_keynesian=0.292, monetarist=0.257, fiscal_ftpl=0.228, pk_sfc=0.223
- **school:ipca_m:2**: new_keynesian=0.300, monetarist=0.259, pk_sfc=0.236, fiscal_ftpl=0.204
- **school:ipca_m:3**: new_keynesian=0.311, monetarist=0.270, pk_sfc=0.254, fiscal_ftpl=0.165
- **school:ipca_m:4**: new_keynesian=0.325, monetarist=0.284, pk_sfc=0.266, fiscal_ftpl=0.124
- **school:ipca_m:5**: new_keynesian=0.333, monetarist=0.296, pk_sfc=0.276, fiscal_ftpl=0.096
- **school:ipca_m:6**: new_keynesian=0.337, monetarist=0.308, pk_sfc=0.281, fiscal_ftpl=0.074
- **school:ipca_m:7**: new_keynesian=0.343, monetarist=0.318, pk_sfc=0.284, fiscal_ftpl=0.055
- **school:ipca_m:8**: new_keynesian=0.348, monetarist=0.323, pk_sfc=0.286, fiscal_ftpl=0.043
- **school:ipca_m:9**: new_keynesian=0.353, monetarist=0.326, pk_sfc=0.286, fiscal_ftpl=0.035
- **school:ipca_m:10**: new_keynesian=0.361, monetarist=0.327, pk_sfc=0.284, fiscal_ftpl=0.029
- **school:ipca_m:11**: new_keynesian=0.364, monetarist=0.329, pk_sfc=0.283, fiscal_ftpl=0.024
- **school:ipca_m:12**: new_keynesian=0.360, monetarist=0.334, pk_sfc=0.286, fiscal_ftpl=0.020
- **school:selic:3**: pk_sfc=0.451, new_keynesian=0.419, fiscal_ftpl=0.074, monetarist=0.057
- **school:selic:6**: new_keynesian=0.428, pk_sfc=0.424, monetarist=0.112, fiscal_ftpl=0.036
- **school:selic:12**: new_keynesian=0.406, pk_sfc=0.350, monetarist=0.203, fiscal_ftpl=0.040

## Disagreement (school dispersion)

| target   |   horizon |   std |
|:---------|----------:|------:|
| gdp_qq   |         0 | 0.815 |
| gdp_qq   |         1 | 1.093 |
| gdp_qq   |         2 | 1.342 |
| gdp_qq   |         3 | 1.869 |
| gdp_qq   |         4 | 2.121 |
| ipca_12m |         3 | 0.344 |
| ipca_12m |         6 | 0.954 |
| ipca_12m |        12 | 3.143 |
| ipca_m   |         0 | 0.09  |
| ipca_m   |         1 | 0.074 |
| ipca_m   |         2 | 0.087 |
| ipca_m   |         3 | 0.122 |
| ipca_m   |         4 | 0.164 |
| ipca_m   |         5 | 0.207 |
| ipca_m   |         6 | 0.248 |
| ipca_m   |         7 | 0.286 |
| ipca_m   |         8 | 0.32  |
| ipca_m   |         9 | 0.351 |
| ipca_m   |        10 | 0.383 |
| ipca_m   |        11 | 0.413 |
| ipca_m   |        12 | 0.439 |
| selic    |         0 | 0.428 |
| selic    |         3 | 1.535 |
| selic    |         6 | 2.97  |
| selic    |        12 | 4.62  |

All four schools have a recorded `REJECTED` terminal state; the ensemble is a
diagnostic synthesis, not a validated PASS. The benchmark ensemble is the
stronger comparator.
