# Modeler packet

Round: 1 · variant: R1

You receive typed defects only, with no numeric validation scores. You may apply one revision from the pre-registered ladder in the card; you may not add variables or change the estimation sample.

## Defects

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
    "message": "gdp_qq h=1 fails the forecast gate",
    "evidence": {
      "target": "gdp_qq",
      "horizon": 1,
      "gate": "fail"
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "medium",
    "message": "gdp_qq h=1 fails the forecast gate",
    "evidence": {
      "target": "gdp_qq",
      "horizon": 1,
      "gate": "fail"
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "medium",
    "message": "gdp_qq h=1 fails the forecast gate",
    "evidence": {
      "target": "gdp_qq",
      "horizon": 1,
      "gate": "fail"
    },
    "owner": "modeler"
  },
  {
    "code": "D5",
    "severity": "low",
    "message": "gdp_qq h=4 fails the forecast gate",
    "evidence": {
      "target": "gdp_qq",
      "horizon": 4,
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
  }
]
```
