# Modeler packet

Round: 1 · variant: R1

You receive typed defects only, with no numeric validation scores. You may apply one revision from the pre-registered ladder in the card; you may not add variables or change the estimation sample.

## Defects

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
    "message": "ipca_12m h=6 fails the forecast gate",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 6,
      "gate": "fail"
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "high",
    "message": "ipca_12m h=6 fails the forecast gate",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 6,
      "gate": "fail"
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "high",
    "message": "ipca_12m h=6 fails the forecast gate",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 6,
      "gate": "fail"
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "high",
    "message": "ipca_12m h=12 fails the forecast gate",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 12,
      "gate": "fail"
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "high",
    "message": "ipca_12m h=12 fails the forecast gate",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 12,
      "gate": "fail"
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "high",
    "message": "ipca_12m h=12 fails the forecast gate",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 12,
      "gate": "fail"
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "low",
    "message": "ipca_12m h=None fails the forecast gate",
    "evidence": {
      "target": "ipca_12m",
      "horizon": null,
      "gate": "fail"
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "medium",
    "message": "selic h=12 fails the forecast gate",
    "evidence": {
      "target": "selic",
      "horizon": 12,
      "gate": "fail"
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "medium",
    "message": "selic h=12 fails the forecast gate",
    "evidence": {
      "target": "selic",
      "horizon": 12,
      "gate": "fail"
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "medium",
    "message": "selic h=12 fails the forecast gate",
    "evidence": {
      "target": "selic",
      "horizon": 12,
      "gate": "fail"
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "low",
    "message": "selic h=None fails the forecast gate",
    "evidence": {
      "target": "selic",
      "horizon": null,
      "gate": "fail"
    },
    "owner": "modeler"
  }
]
```
