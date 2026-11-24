# Blind critic packet

Model card hash: `c1236e1b26d311fc2d08e38b0d5d45a556ec613739788f8aa9497a24541cf67b`

Round: 1 · variant: R1

You see only the frozen card, the code, and the diagnostics. You do not see the modeler's rationale or the validation score table.

## Typed defects

```json
[
  {
    "code": "D1",
    "severity": "high",
    "message": "Primary balance responds positively to debt; the sample is Ricardian and the FTPL mechanism is refuted.",
    "evidence": {
      "test": "ftpl_non_ricardian",
      "block": "fiscal_reaction",
      "key": "debt_gdp_1",
      "stat": "coef",
      "value": 0.22272612532430408,
      "threshold": 0.0
    },
    "owner": "modeler"
  },
  {
    "code": "D7",
    "severity": "high",
    "message": "Debt lowers inflation; the fiscal-inflation channel has the wrong sign.",
    "evidence": {
      "test": "ftpl_debt_inflation",
      "block": "inflation",
      "key": "debt_gdp_1",
      "stat": "coef",
      "value": -0.009891973034974973,
      "threshold": 0.0
    },
    "owner": "modeler"
  },
  {
    "code": "D7",
    "severity": "high",
    "message": "A higher primary surplus raises inflation; the fiscal-tightening channel is refuted.",
    "evidence": {
      "test": "ftpl_primary_inflation",
      "block": "inflation",
      "key": "primary_balance_12m_1",
      "stat": "coef",
      "value": 0.02618402542218239,
      "threshold": 0.0
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "Residual autocorrelation in fiscal_reaction equation (Ljung-Box p=0.0000)",
    "evidence": {
      "equation": "fiscal_reaction",
      "pvalue": 8.128090644185003e-228
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "low",
    "message": "Weak residual autocorrelation in inflation equation (p=0.0461)",
    "evidence": {
      "equation": "inflation",
      "pvalue": 0.046132846620749374
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "Residual autocorrelation in policy equation (Ljung-Box p=0.0000)",
    "evidence": {
      "equation": "policy",
      "pvalue": 1.8656955128568994e-14
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "Multicollinearity in fiscal_reaction (cond=630.1)",
    "evidence": {
      "equation": "fiscal_reaction",
      "condition": 630.1411604265847
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "Multicollinearity in inflation (cond=962.9)",
    "evidence": {
      "equation": "inflation",
      "condition": 962.9428214183822
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "Multicollinearity in policy (cond=651.4)",
    "evidence": {
      "equation": "policy",
      "condition": 651.3608125890005
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "low",
    "message": "One sign flip in fiscal_reaction across sub-samples",
    "evidence": {
      "equation": "fiscal_reaction",
      "flips": 1
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "2 sign flips in inflation across sub-samples",
    "evidence": {
      "equation": "inflation",
      "flips": 2
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "2 sign flips in policy across sub-samples",
    "evidence": {
      "equation": "policy",
      "flips": 2
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "high",
    "message": "ipca_12m h=6 loses to random walk (Theil U=1.050)",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 6,
      "theil_u": 1.0501769693217777
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "high",
    "message": "ipca_12m h=6 fails Mincer-Zarnowitz calibration (p=0.0000)",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 6,
      "mz_p": 1.2911350057320803e-05
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "high",
    "message": "ipca_12m h=6 does not improve on the Focus consensus (RMSE ratio 2.269, DM p=0.001)",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 6,
      "focus_ratio": 2.268530156087984,
      "dm_focus_p": 0.001248126272098915
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "high",
    "message": "ipca_12m h=12 loses to random walk (Theil U=2.196)",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 12,
      "theil_u": 2.1958066282668063
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "high",
    "message": "ipca_12m h=12 fails Mincer-Zarnowitz calibration (p=0.0000)",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 12,
      "mz_p": 0.0
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "high",
    "message": "ipca_12m h=12 does not improve on the Focus consensus (RMSE ratio 4.713, DM p=0.011)",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 12,
      "focus_ratio": 4.7131831602614485,
      "dm_focus_p": 0.010991339002224043
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "low",
    "message": "ipca_12m h=12 directional accuracy below 45%",
    "evidence": {
      "target": "ipca_12m",
      "direction": 0.42592592592592593
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "medium",
    "message": "selic h=12 loses to random walk (Theil U=2.973)",
    "evidence": {
      "target": "selic",
      "horizon": 12,
      "theil_u": 2.9734312337676365
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "medium",
    "message": "selic h=12 fails Mincer-Zarnowitz calibration (p=0.0000)",
    "evidence": {
      "target": "selic",
      "horizon": 12,
      "mz_p": 0.0
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "medium",
    "message": "selic h=12 does not improve on the Focus consensus (RMSE ratio 4.223, DM p=0.001)",
    "evidence": {
      "target": "selic",
      "horizon": 12,
      "focus_ratio": 4.2227763493267245,
      "dm_focus_p": 0.0007456954260900428
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "low",
    "message": "selic h=12 directional accuracy below 45%",
    "evidence": {
      "target": "selic",
      "direction": 0.39814814814814814
    },
    "owner": "modeler"
  }
]
```
