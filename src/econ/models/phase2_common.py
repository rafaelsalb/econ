from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import acorr_ljungbox

from ..targets import month_of, quarter_of
from .base import Forecast


def monthly_frame(panel, series_ids: list[str]) -> pd.DataFrame:
    cols = {sid: panel.monthly(sid) for sid in series_ids}
    return pd.DataFrame(cols).sort_index().dropna()


def ols_hac(y: pd.Series, X: pd.DataFrame, maxlags: int = 12) -> dict:
    design = sm.add_constant(X)
    res = sm.OLS(y, design).fit(
        cov_type="HAC", cov_kwds={"maxlags": maxlags}, use_t=True
    )
    return {
        "params": res.params,
        "tstats": res.tvalues,
        "resid": pd.Series(res.resid.to_numpy(), index=y.index),
        "rsquared": float(res.rsquared),
        "condition": float(np.linalg.cond(design.to_numpy())),
    }


def lb_p(resid: pd.Series, lags: int = 12) -> float:
    resid = resid.dropna()
    if len(resid) < lags + 5:
        return float("nan")
    return float(acorr_ljungbox(resid, lags=[lags], return_df=True)["lb_pvalue"].iloc[0])


def diagnostics_payload(
    panel,
    *,
    variant: str,
    equations: dict[str, dict],
    sample: pd.DataFrame,
    extra: dict | None = None,
) -> dict:
    return {
        "origin": str(panel.origin),
        "variant": variant,
        "nobs": {name: int(len(eq["resid"])) for name, eq in equations.items()},
        "sample_start": str(sample.index.min()),
        "sample_end": str(sample.index.max()),
        "sample_n": int(len(sample)),
        "rsquared": {name: eq["rsquared"] for name, eq in equations.items()},
        "condition": {name: eq["condition"] for name, eq in equations.items()},
        "ljung_box_p": {name: lb_p(eq["resid"]) for name, eq in equations.items()},
        "resid_sd": {name: float(eq["resid"].std()) for name, eq in equations.items()},
        "params": {name: {k: float(v) for k, v in eq["params"].items()} for name, eq in equations.items()},
        "tstats": {name: {k: float(v) for k, v in eq["tstats"].items()} for name, eq in equations.items()},
        "leak_ok": bool(panel.obs["release_date"].max() <= panel.origin),
        "max_release": str(panel.obs["release_date"].max()),
        **(extra or {}),
    }


def bridge_gdp(
    panel,
    ibc_level: pd.Series,
    origin: date,
    est_start: str = "2005-01-01",
) -> tuple[dict[int, float], dict]:
    hist = panel.monthly("ibc_br")
    qkey = hist.index.asfreq("Q")
    counts = hist.groupby(qkey).count()
    qlevel = hist.groupby(qkey).mean()[counts == 3]
    ibc_qq = 100 * np.log(qlevel).diff()
    gdp = panel.quarterly("gdp_qq")
    df = pd.concat([gdp.rename("gdp"), ibc_qq.rename("ibc")], axis=1, join="inner")
    df["ibc_lag"] = df["ibc"].shift(1)
    df = df.dropna()
    df = df[df.index >= pd.Period(est_start, "Q")]
    if len(df) < 16:
        raise ValueError("bridge: insufficient history")
    X = np.column_stack([np.ones(len(df)), df["ibc"].to_numpy(), df["ibc_lag"].to_numpy()])
    beta, *_ = np.linalg.lstsq(X, df["gdp"].to_numpy(), rcond=None)

    m0 = month_of(origin)
    q0 = quarter_of(origin)

    def qlev(q: pd.Period) -> float:
        months = pd.period_range(q.start_time, q.end_time, freq="M")
        vals = []
        for m in months:
            if m <= m0 - 1:
                vals.append(float(hist.loc[m]))
            else:
                vals.append(float(ibc_level.loc[m]))
        return float(np.mean(vals))

    qlevels = {q: qlev(q) for q in pd.period_range(q0 - 3, q0 + 4, freq="Q")}
    ibc_fc = {
        q: 100 * np.log(qlevels[q] / qlevels[q - 1])
        for q in pd.period_range(q0 - 2, q0 + 4, freq="Q")
    }
    gdp_fc = {
        h: float(beta[0] + beta[1] * ibc_fc[q0 + h] + beta[2] * ibc_fc[q0 + h - 1])
        for h in range(5)
    }
    return gdp_fc, {
        "params": {"const": float(beta[0]), "ibc": float(beta[1]), "ibc_lag": float(beta[2])},
        "nobs": int(len(df)),
    }


def level_path_from_growth(
    last_month: pd.Period,
    last_level: float,
    growth: np.ndarray,
    steps: int,
) -> pd.Series:
    levels = {last_month: float(last_level)}
    for j, g in enumerate(growth[: steps + 1]):
        t = last_month + 1 + j
        levels[t] = levels[t - 1] * np.exp(float(g) / 100.0)
    return pd.Series(levels).sort_index()


def marked(rows: list[Forecast], note: str) -> list[Forecast]:
    for row in rows:
        row.notes = note
    return rows
