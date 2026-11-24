# Blind critic packet

Model card hash: `ba493755c9599700c70091d1e0918743d727c0e31eb89f691b8482eb43e74896`

Round: 1 · variant: R1

You see only the frozen card, the code, and the diagnostics. You do not see the modeler's rationale or the validation score table.

## Typed defects

```json
[
  {
    "code": "D7",
    "severity": "high",
    "message": "Consumption responds positively to the real rate; the interest-rate channel is refuted.",
    "evidence": {
      "test": "consumption_rate",
      "block": "consumption",
      "key": "real_rate_1",
      "stat": "coef",
      "value": 655.1163708585125,
      "threshold": 0.0
    },
    "owner": "modeler"
  },
  {
    "code": "D7",
    "severity": "high",
    "message": "Deflator inflation persistence is non-positive.",
    "evidence": {
      "test": "deflator_persistence",
      "block": "deflator",
      "key": "pi_deflator_1",
      "stat": "coef",
      "value": -0.6117846376273235,
      "threshold": 0.0
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "Residual autocorrelation in consumption equation (Ljung-Box p=0.0000)",
    "evidence": {
      "equation": "consumption",
      "pvalue": 1.1612576509699624e-08
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "Residual autocorrelation in investment equation (Ljung-Box p=0.0000)",
    "evidence": {
      "equation": "investment",
      "pvalue": 9.687646482293072e-40
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "Residual autocorrelation in government equation (Ljung-Box p=0.0000)",
    "evidence": {
      "equation": "government",
      "pvalue": 5.883573338668446e-24
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "Residual autocorrelation in exports equation (Ljung-Box p=0.0000)",
    "evidence": {
      "equation": "exports",
      "pvalue": 2.3808585639309322e-08
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "Residual autocorrelation in imports equation (Ljung-Box p=0.0000)",
    "evidence": {
      "equation": "imports",
      "pvalue": 5.98410512999875e-06
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "Residual autocorrelation in deflator equation (Ljung-Box p=0.0000)",
    "evidence": {
      "equation": "deflator",
      "pvalue": 4.915922464883947e-07
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "low",
    "message": "Weak residual autocorrelation in ipca_bridge equation (p=0.0235)",
    "evidence": {
      "equation": "ipca_bridge",
      "pvalue": 0.023502243591442443
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "high",
    "message": "Severe multicollinearity in consumption (cond=4476235.5)",
    "evidence": {
      "equation": "consumption",
      "condition": 4476235.495617835
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "high",
    "message": "Severe multicollinearity in investment (cond=4476235.5)",
    "evidence": {
      "equation": "investment",
      "condition": 4476235.495617835
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "high",
    "message": "Severe multicollinearity in government (cond=540311.9)",
    "evidence": {
      "equation": "government",
      "condition": 540311.9112632747
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "high",
    "message": "Severe multicollinearity in exports (cond=289566.5)",
    "evidence": {
      "equation": "exports",
      "condition": 289566.54484099953
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "high",
    "message": "Severe multicollinearity in imports (cond=4298493.7)",
    "evidence": {
      "equation": "imports",
      "condition": 4298493.695859678
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "low",
    "message": "One sign flip in exports across sub-samples",
    "evidence": {
      "equation": "exports",
      "flips": 1
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "medium",
    "message": "2 sign flips in investment across sub-samples",
    "evidence": {
      "equation": "investment",
      "flips": 2
    },
    "owner": "modeler"
  },
  {
    "code": "D4",
    "severity": "low",
    "message": "One sign flip in ipca_bridge across sub-samples",
    "evidence": {
      "equation": "ipca_bridge",
      "flips": 1
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "medium",
    "message": "gdp_qq h=1 loses to random walk (Theil U=1.550)",
    "evidence": {
      "target": "gdp_qq",
      "horizon": 1,
      "theil_u": 1.5504573423749195
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "medium",
    "message": "gdp_qq h=1 fails Mincer-Zarnowitz calibration (p=0.0000)",
    "evidence": {
      "target": "gdp_qq",
      "horizon": 1,
      "mz_p": 4.440892098500626e-16
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "medium",
    "message": "gdp_qq h=1 does not improve on the Focus consensus (RMSE ratio 2.072, DM p=0.000)",
    "evidence": {
      "target": "gdp_qq",
      "horizon": 1,
      "focus_ratio": 2.071722463992313,
      "dm_focus_p": 1.5006398843331326e-05
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "low",
    "message": "gdp_qq h=4 does not improve on the Focus consensus (RMSE ratio 1.076, DM p=0.704)",
    "evidence": {
      "target": "gdp_qq",
      "horizon": 4,
      "focus_ratio": 1.0762643969370782,
      "dm_focus_p": 0.7042903932524136
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "high",
    "message": "ipca_12m h=6 does not improve on the Focus consensus (RMSE ratio 1.434, DM p=0.000)",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 6,
      "focus_ratio": 1.4340408875880453,
      "dm_focus_p": 6.756789088058213e-05
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "high",
    "message": "ipca_12m h=12 fails Mincer-Zarnowitz calibration (p=0.0001)",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 12,
      "mz_p": 7.660458465208464e-05
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "high",
    "message": "ipca_12m h=12 does not improve on the Focus consensus (RMSE ratio 1.316, DM p=0.018)",
    "evidence": {
      "target": "ipca_12m",
      "horizon": 12,
      "focus_ratio": 1.3164759146629128,
      "dm_focus_p": 0.017867138382646974
    },
    "owner": "modeler"
  }
]
```
