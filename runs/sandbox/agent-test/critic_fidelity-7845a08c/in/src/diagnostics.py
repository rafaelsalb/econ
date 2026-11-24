from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd
from statsmodels.stats.diagnostic import acorr_ljungbox

from .models.new_keynesian import NKFit, estimate
from .vintage import Panel


def _lb_p(resid: pd.Series, lags: int = 12) -> float:
    if len(resid.dropna()) < lags + 5:
        return float("nan")
    out = acorr_ljungbox(resid.dropna(), lags=[lags], return_df=True)
    return float(out["lb_pvalue"].iloc[0])


def fit_diagnostics(panel: Panel, variant: str = "R1") -> dict:
    fit = estimate(panel, variant=variant)
    rows = {
        "origin": str(panel.origin),
        "variant": variant,
        "nobs": fit.nobs,
        "sample_start": str(fit.data.index.min()),
        "sample_end": str(fit.data.index.max()),
        "sample_n": int(len(fit.data)),
        "rsquared": {
            "is": fit.is_rsquared,
            "nkpc": fit.nkpc_rsquared,
            "taylor": fit.taylor_rsquared,
        },
        "condition": {
            "is": fit.condition_is,
            "nkpc": fit.condition_nkpc,
            "taylor": fit.condition_taylor,
        },
        "ljung_box_p": {
            "is": _lb_p(fit.is_resid),
            "nkpc": _lb_p(fit.nkpc_resid),
            "taylor": _lb_p(fit.taylor_resid),
        },
        "resid_sd": {
            "is": float(fit.is_resid.std()),
            "nkpc": float(fit.nkpc_resid.std()),
            "taylor": float(fit.taylor_resid.std()),
        },
        "params": {
            "is": {k: float(v) for k, v in fit.is_params.items()},
            "nkpc": {k: float(v) for k, v in fit.nkpc_params.items()},
            "taylor": {k: float(v) for k, v in fit.taylor_params.items()},
        },
        "tstats": {
            "is": {k: float(v) for k, v in fit.is_tstats.items()},
            "nkpc": {k: float(v) for k, v in fit.nkpc_tstats.items()},
            "taylor": {k: float(v) for k, v in fit.taylor_tstats.items()},
        },
        "leak_ok": bool(panel.obs["release_date"].max() <= panel.origin),
        "max_release": str(panel.obs["release_date"].max()),
        "gap": {
            "last": float(fit.gap.iloc[-1]),
            "mean": float(fit.gap.mean()),
            "sd": float(fit.gap.std()),
        },
    }
    return rows


def stability(before: dict, after: dict) -> dict:
    out = {}
    for block in ["is", "nkpc", "taylor"]:
        b = before["params"][block]
        a = after["params"][block]
        keys = sorted(set(b) & set(a))
        out[block] = {
            k: {
                "before": float(b[k]),
                "after": float(a[k]),
                "sign_flip": bool(np.sign(b[k]) != np.sign(a[k])),
                "abs_change": float(abs(a[k] - b[k])),
            }
            for k in keys
        }
        out[block]["_sign_flips"] = int(
            sum(1 for k in keys if np.sign(b[k]) != np.sign(a[k]))
        )
    return out


def irf_signs(params: dict) -> dict:
    """Sign of the implied transmission: policy -> real rate -> gap -> inflation."""
    is_p = params["is"]
    nk_p = params["nkpc"]
    tr_p = params["taylor"]
    return {
        "real_rate_to_gap": float(np.sign(is_p.get("rr", np.nan))),
        "gap_to_inflation": float(np.sign(nk_p.get("gap_1", np.nan))),
        "fx_to_inflation": float(np.sign(nk_p.get("dfx_1", np.nan))),
        "policy_smoothing": float(np.sign(tr_p.get("i_lag", np.nan))),
        "inflation_to_policy": float(np.sign(tr_p.get("pi_gap", np.nan))),
        "gap_to_policy": float(np.sign(tr_p.get("gap_1", np.nan))),
    }


def forecast_sanity(rows: list) -> dict:
    checks = {}
    for target, lo, hi in [
        ("ipca_m", -5.0, 5.0),
        ("ipca_12m", -5.0, 40.0),
        ("gdp_qq", -15.0, 15.0),
        ("selic", 0.0, 40.0),
    ]:
        vals = [r.point for r in rows if r.target == target]
        checks[target] = {
            "min": float(min(vals)) if vals else None,
            "max": float(max(vals)) if vals else None,
            "finite": bool(all(np.isfinite(vals))),
            "in_range": bool(vals and min(vals) >= lo and max(vals) <= hi),
        }
    return checks


@dataclass
class Defect:
    code: str
    severity: str
    message: str
    evidence: dict = field(default_factory=dict)
    owner: str = "modeler"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence,
            "owner": self.owner,
        }
