# Modeler packet

Round: 1 · variant: R1

You receive typed defects only, with no numeric validation scores. You may apply one revision from the pre-registered ladder in the card; you may not add variables or change the estimation sample.

## Defects

```json
[
  {
    "code": "D4",
    "severity": "medium",
    "message": "Residual autocorrelation in money_demand equation (Ljung-Box p=0.0000)",
    "evidence": {
      "equation": "money_demand",
      "pvalue": 6.481703439031665e-21
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "low",
    "message": "Weak residual autocorrelation in pstar_inflation equation (p=0.0309)",
    "evidence": {
      "equation": "pstar_inflation",
      "pvalue": 0.03087590242383363
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "high",
    "message": "Severe multicollinearity in money_demand (cond=1936.8)",
    "evidence": {
      "equation": "money_demand",
      "condition": 1936.7773529887386
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "low",
    "message": "One sign flip in money_demand across sub-samples",
    "evidence": {
      "equation": "money_demand",
      "flips": 1
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "2 sign flips in pstar_inflation across sub-samples",
    "evidence": {
      "equation": "pstar_inflation",
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
  }
]
```
