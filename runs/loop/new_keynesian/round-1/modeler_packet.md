# Modeler packet

Round: 1 · variant: R1

You receive typed defects only, with no numeric validation scores. You may apply one revision from the pre-registered ladder in the card; you may not add variables or change the estimation sample.

## Defects

```json
[
  {
    "code": "D1",
    "severity": "high",
    "message": "Output-gap coefficient in the NKPC is statistically insignificant; the card's core transmission refutation condition is triggered.",
    "evidence": {
      "test": "nkpc_gap_significance",
      "block": "nkpc",
      "key": "gap_1",
      "stat": "tstat",
      "value": 1.1547179187664627,
      "threshold": 1.65
    },
    "owner": "modeler"
  },
  {
    "code": "D7",
    "severity": "high",
    "message": "FX pass-through coefficient is non-positive; the external channel violates the declared sign restriction.",
    "evidence": {
      "test": "fx_pass_through_sign",
      "block": "nkpc",
      "key": "dfx_1",
      "stat": "coef",
      "value": -0.0005962078571183169,
      "threshold": 0.0
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "Residual autocorrelation in nkpc equation (Ljung-Box p=0.0075)",
    "evidence": {
      "equation": "nkpc",
      "pvalue": 0.007490062313336825
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "Residual autocorrelation in taylor equation (Ljung-Box p=0.0000)",
    "evidence": {
      "equation": "taylor",
      "pvalue": 1.2973151351117282e-10
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
