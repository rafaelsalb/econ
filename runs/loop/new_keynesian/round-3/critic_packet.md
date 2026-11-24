# Blind critic packet

Model card hash: `22594f22605187741ef9e58629abe9a060f326a0527ab6d869e26031ec2d43c0`

Round: 3 · variant: R3

You see only the frozen card, the code, and the diagnostics. You do not see the modeler's rationale or the validation score table.

## Typed defects

```json
[
  {
    "code": "D7",
    "severity": "medium",
    "message": "Output-gap transmission is economically negligible (<0.02pp monthly inflation per 1pp gap)",
    "evidence": {
      "gap_coef": 0.008188701199785778
    },
    "owner": "modeler"
  },
  {
    "code": "D7",
    "severity": "medium",
    "message": "FX pass-through coefficient is non-positive; the external channel is not identified",
    "evidence": {
      "fx_coef": -0.0004039316878437804
    },
    "owner": "modeler"
  },
  {
    "code": "D1",
    "severity": "medium",
    "message": "gap coefficient is not precisely estimated (|t| < 1.65)",
    "evidence": {
      "block": "nkpc",
      "key": "gap_1",
      "tstat": 1.3701837788662155
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "low",
    "message": "Weak residual autocorrelation in nkpc equation (p=0.0212)",
    "evidence": {
      "equation": "nkpc",
      "pvalue": 0.021184844558098857
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "Residual autocorrelation in taylor equation (Ljung-Box p=0.0000)",
    "evidence": {
      "equation": "taylor",
      "pvalue": 3.2137628462984513e-26
    },
    "owner": "modeler"
  }
]
```
