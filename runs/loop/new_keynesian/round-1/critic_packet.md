# Blind critic packet

Model card hash: `bdaebdd440873f3ad16471fe24f48702db886d74b7e5eebb5db699c41729c581`

Round: 1 · variant: R1

You see only the frozen card, the code, and the diagnostics. You do not see the modeler's rationale or the validation score table.

## Typed defects

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
    "message": "ipca_12m h=6 does not improve on the Focus consensus (RMSE ratio 1.114, DM p=0.029)",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 6,
      "focus_ratio": 1.1144725192420102,
      "dm_focus_p": 0.029384549540460103
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "medium",
    "message": "selic h=12 does not improve on the Focus consensus (RMSE ratio 1.328, DM p=0.013)",
    "evidence": {
      "target": "selic",
      "horizon": 12,
      "focus_ratio": 1.3282600785413572,
      "dm_focus_p": 0.0131760067191673
    },
    "owner": "modeler"
  }
]
```
