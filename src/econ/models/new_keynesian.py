from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.filters.hp_filter import hpfilter

from ..config import ESTIMATION_START, NK_ESTIMATION_START
from ..targets import compound, month_of, quarter_of, target_for
from ..vintage import Panel
from .base import Forecast, validate_rows
from .common import fit_ar, forecast_ar, gdp_rows, ipca_rows, selic_rows

RSTAR = 4.0
HP_LAMBDA = 129600.0
COVID_START = pd.Period("2020-03", "M")
COVID_END = pd.Period("2020-12", "M")


def covid_flag(p: pd.Period) -> float:
    return 1.0 if COVID_START <= p <= COVID_END else 0.0


@dataclass
class NKFit:
    is_params: pd.Series
    nkpc_params: pd.Series
    taylor_params: pd.Series
    is_tstats: pd.Series
    nkpc_tstats: pd.Series
    taylor_tstats: pd.Series
    is_resid: pd.Series
    nkpc_resid: pd.Series
    taylor_resid: pd.Series
    is_rsquared: float
    nkpc_rsquared: float
    taylor_rsquared: float
    data: pd.DataFrame
    gap: pd.Series
    trend: pd.Series
    condition_is: float
    condition_nkpc: float
    condition_taylor: float
    nobs: dict[str, int] = field(default_factory=dict)


def _ols(y: pd.Series, X: pd.DataFrame, constant: bool = True):
    design = sm.add_constant(X) if constant else X
    return sm.OLS(y, design).fit(
        cov_type="HAC", cov_kwds={"maxlags": 12}, use_t=True
    )


def _covid_terms(df: pd.DataFrame) -> list[str]:
    return ["covid"] if df["covid"].nunique(dropna=True) > 1 else []


def build_dataset(panel: Panel, est_start: str = NK_ESTIMATION_START) -> pd.DataFrame:
    pi = panel.monthly("ipca_m")
    ibc = panel.monthly("ibc_br")
    selic = panel.monthly("selic_target")
    fx = panel.monthly("fx_usdbrl")
    focus = panel.monthly("focus_ipca_12m")

    df = pd.concat(
        [
            pi.rename("pi"),
            ibc.rename("ibc"),
            selic.rename("selic"),
            fx.rename("fx"),
            focus.rename("focus"),
        ],
        axis=1,
        join="inner",
    ).dropna()
    start = pd.Period(est_start, "M")
    df = df[df.index >= start]
    if len(df) < 60:
        raise ValueError(f"NK: insufficient history ({len(df)} months)")

    cycle, trend = hpfilter(np.log(df["ibc"]), lamb=HP_LAMBDA)
    df["gap"] = 100.0 * cycle
    df["trend_log"] = trend
    df["dfx"] = 100.0 * np.log(df["fx"]).diff()
    df["pi12"] = ((1 + df["pi"] / 100).rolling(12).apply(np.prod, raw=True) - 1) * 100
    df["pi_e"] = ((1 + df["focus"] / 100) ** (1 / 12) - 1) * 100
    df["r"] = df["selic"] - df["focus"]
    df["target"] = [target_for(p.start_time.date()) for p in df.index]
    df["covid"] = [covid_flag(p) for p in df.index]
    return df


def estimate(panel: Panel, est_start: str = NK_ESTIMATION_START, variant: str = "R1") -> NKFit:
    df = build_dataset(panel, est_start)
    d = df.copy()
    for col in ["gap", "pi", "r", "dfx", "pi12", "selic"]:
        d[f"{col}_1"] = d[col].shift(1)
        d[f"{col}_2"] = d[col].shift(2)

    # --- IS curve -----------------------------------------------------------
    is_df = d.dropna(subset=["gap", "gap_1", "gap_2", "r_1"]).copy()
    is_df["rr"] = is_df["r_1"] - RSTAR
    cols_is = ["gap_1", "gap_2", "rr"] + _covid_terms(is_df)
    X_is = is_df[cols_is]
    is_res = _ols(is_df["gap"], X_is)
    is_resid = pd.Series(is_res.resid.to_numpy(), index=is_df.index)

    # --- Hybrid NKPC with long-run neutrality imposed -----------------------
    # pi_t - pi_e_t = c + b1 (pi_{t-1} - pi_e_t) + b2 (pi_{t-2} - pi_e_t)
    #                 + b4 gap_{t-1} + b5 dfx_{t-1} + e
    nk_df = d.dropna(subset=["pi", "pi_1", "pi_2", "pi_e", "gap_1", "dfx_1"]).copy()
    nk_df["pi_rel"] = nk_df["pi"] - nk_df["pi_e"]
    nk_df["pi1_rel"] = nk_df["pi_1"] - nk_df["pi_e"]
    nk_df["pi2_rel"] = nk_df["pi_2"] - nk_df["pi_e"]
    cols_nk = ["pi1_rel", "pi2_rel", "gap_1", "dfx_1"] + _covid_terms(nk_df)
    X_nk = nk_df[cols_nk]
    nk_res = _ols(nk_df["pi_rel"], X_nk)
    nk_resid = pd.Series(nk_res.resid.to_numpy(), index=nk_df.index)
    nk_params = nk_res.params.copy()
    nk_params["pi_e"] = 1.0 - nk_params["pi1_rel"] - nk_params["pi2_rel"]

    # --- Taylor rule with neutral real rate imposed -------------------------
    # i_t - target_t - rstar = rho (i_{t-1} - target_t - rstar)
    #                          + g1 (pi12_{t-1} - target_t) + g2 gap_{t-1} + e
    # R3 replaces lagged inflation with the survey 12m expectation.
    tr_df = d.dropna(subset=["selic", "selic_1", "gap_1"]).copy()
    if variant == "R3":
        tr_df = tr_df.dropna(subset=["focus"])
        tr_df["anchor_gap"] = tr_df["focus"] - tr_df["target"]
        anchor_col = "anchor_gap"
    else:
        tr_df = tr_df.dropna(subset=["pi12_1"])
        tr_df["anchor_gap"] = tr_df["pi12_1"] - tr_df["target"]
        anchor_col = "anchor_gap"
    tr_df["lhs"] = tr_df["selic"] - tr_df["target"] - RSTAR
    tr_df["i_lag"] = tr_df["selic_1"] - tr_df["target"] - RSTAR
    cols_tr = ["i_lag", anchor_col, "gap_1"]
    tr_res = _ols(tr_df["lhs"], tr_df[cols_tr], constant=False)
    tr_resid = pd.Series(tr_res.resid.to_numpy(), index=tr_df.index)
    tr_params = tr_res.params.copy()
    tr_params["const"] = 0.0
    tr_params = tr_params.rename({anchor_col: "pi_gap"})
    tr_tstats = tr_res.tvalues.rename({anchor_col: "pi_gap"})

    def cond(X: pd.DataFrame, constant: bool = True) -> float:
        x = (sm.add_constant(X) if constant else X).to_numpy()
        return float(np.linalg.cond(x))

    return NKFit(
        is_params=is_res.params,
        nkpc_params=nk_params,
        taylor_params=tr_params,
        is_tstats=is_res.tvalues,
        nkpc_tstats=nk_res.tvalues,
        taylor_tstats=tr_tstats,
        is_resid=is_resid,
        nkpc_resid=nk_resid,
        taylor_resid=tr_resid,
        is_rsquared=float(is_res.rsquared),
        nkpc_rsquared=float(nk_res.rsquared),
        taylor_rsquared=float(tr_res.rsquared),
        data=df,
        gap=df["gap"],
        trend=df["trend_log"],
        condition_is=cond(X_is),
        condition_nkpc=cond(X_nk),
        condition_taylor=cond(tr_df[cols_tr], constant=False),
        nobs={
            "is": int(is_res.nobs),
            "nkpc": int(nk_res.nobs),
            "taylor": int(tr_res.nobs),
        },
    )


def _coef(params: pd.Series, name: str) -> float:
    return float(params[name]) if name in params.index else 0.0


def _forecast_paths(panel: Panel, fit: NKFit, variant: str = "R1", steps: int = 14):
    m0 = month_of(panel.origin)
    pi_hist = panel.monthly("ipca_m")
    selic_hist = panel.monthly("selic_target")
    focus_hist = panel.monthly("focus_ipca_12m")
    ibc_hist = panel.monthly("ibc_br")
    fx_hist = panel.monthly("fx_usdbrl")

    gap = fit.gap
    if gap.index[-1] != m0 - 1:
        raise ValueError(f"NK gap ends {gap.index[-1]}, expected {m0 - 1}")

    i_M = float(selic_hist.loc[m0])
    focus_M = float(focus_hist.loc[m0])
    pi_e_m = ((1 + focus_M / 100) ** (1 / 12) - 1) * 100

    b_is = fit.is_params
    b_nk = fit.nkpc_params
    b_tr = fit.taylor_params

    path_pi: dict[pd.Period, float] = {
        m0 - 1: float(pi_hist.loc[m0 - 1]),
        m0 - 2: float(pi_hist.loc[m0 - 2]),
    }
    path_gap: dict[pd.Period, float] = {
        m0 - 1: float(gap.loc[m0 - 1]),
        m0 - 2: float(gap.loc[m0 - 2]),
    }
    path_i: dict[pd.Period, float] = {m0: i_M}

    dfx_minus1 = float(100 * np.log(fx_hist.loc[m0 - 1] / fx_hist.loc[m0 - 2]))
    # A pre-COVID origin cannot know the pandemic regime. The dummy is only used
    # for forecast months when the origin is already inside the COVID window.
    origin_has_covid = panel.origin >= COVID_START.start_time.date()

    for j in range(0, steps + 1):
        t = m0 + j
        covid_term = covid_flag(t) if origin_has_covid else 0.0
        gap_1, gap_2 = path_gap[t - 1], path_gap[t - 2]
        r_1 = (
            float(selic_hist.loc[m0 - 1] - focus_hist.loc[m0 - 1])
            if j == 0
            else path_i[t - 1] - focus_M
        )
        path_gap[t] = float(
            _coef(b_is, "const")
            + _coef(b_is, "gap_1") * gap_1
            + _coef(b_is, "gap_2") * gap_2
            + _coef(b_is, "rr") * (r_1 - RSTAR)
            + _coef(b_is, "covid") * covid_term
        )

        pi_1, pi_2 = path_pi[t - 1], path_pi[t - 2]
        dfx_1 = dfx_minus1 if j == 0 else 0.0
        path_pi[t] = float(
            _coef(b_nk, "const")
            + _coef(b_nk, "pi1_rel") * pi_1
            + _coef(b_nk, "pi2_rel") * pi_2
            + _coef(b_nk, "pi_e") * pi_e_m
            + _coef(b_nk, "gap_1") * gap_1
            + _coef(b_nk, "dfx_1") * dfx_1
            + _coef(b_nk, "covid") * covid_term
        )

        if j > 0:
            full_pi = pd.concat([pi_hist, pd.Series(path_pi).sort_index()])
            full_pi = full_pi[~full_pi.index.duplicated(keep="last")].sort_index()
            window = pd.period_range(t - 12, t - 1, freq="M")
            pi12_prev = compound(full_pi.loc[window])
            target_t = target_for(t.start_time.date())
            anchor = focus_M if variant == "R3" else pi12_prev
            path_i[t] = float(
                target_t
                + RSTAR
                + _coef(b_tr, "i_lag") * (path_i[t - 1] - target_t - RSTAR)
                + _coef(b_tr, "pi_gap") * (anchor - target_t)
                + _coef(b_tr, "gap_1") * path_gap[t - 1]
            )

    pi_path = pd.Series(path_pi).sort_index()
    gap_path = pd.Series(path_gap).sort_index()
    i_path = pd.Series(path_i).sort_index()

    # --- GDP bridge ---------------------------------------------------------
    if variant in {"R2", "R3"}:
        growth = (100 * np.log(ibc_hist).diff()).dropna()
        p_g, beta_g = fit_ar(growth.to_numpy(), 3)
        gfc = forecast_ar(growth.to_numpy(), p_g, beta_g, steps + 1)
        levels: dict[pd.Period, float] = {m0 - 1: float(ibc_hist.loc[m0 - 1])}
        for j, g in enumerate(gfc):
            t = m0 + j
            levels[t] = levels[t - 1] * np.exp(g / 100.0)
    else:
        trend = fit.trend
        g_trend = float(np.mean(np.diff(trend.to_numpy())[-12:]))
        levels = {m0 - 1: float(ibc_hist.loc[m0 - 1])}
        for j in range(0, steps + 1):
            t = m0 + j
            levels[t] = levels[t - 1] * np.exp(
                g_trend + (gap_path[t] - gap_path[t - 1]) / 100.0
            )

    q0 = quarter_of(panel.origin)

    def quarter_ibc(q: pd.Period) -> float:
        months = pd.period_range(q.start_time, q.end_time, freq="M")
        vals = []
        for m in months:
            vals.append(
                float(ibc_hist.loc[m]) if m <= m0 - 1 else float(levels[m])
            )
        return float(np.mean(vals))

    qlevels = {q: quarter_ibc(q) for q in pd.period_range(q0 - 3, q0 + 4, freq="Q")}
    ibc_qq = {
        q: 100 * np.log(qlevels[q] / qlevels[q - 1])
        for q in pd.period_range(q0 - 2, q0 + 4, freq="Q")
    }

    ibc_q = ibc_hist.groupby(ibc_hist.index.asfreq("Q")).mean()
    counts = ibc_hist.groupby(ibc_hist.index.asfreq("Q")).count()
    ibc_q = ibc_q[counts == 3]
    ibc_q_qq = 100 * np.log(ibc_q).diff()
    gdp = panel.quarterly("gdp_qq")
    bridge = pd.concat([gdp.rename("gdp"), ibc_q_qq.rename("ibc")], axis=1, join="inner")
    bridge["ibc_lag"] = bridge["ibc"].shift(1)
    bridge = bridge.dropna()
    bridge = bridge[bridge.index >= pd.Period(ESTIMATION_START, "Q")]
    if len(bridge) < 20:
        raise ValueError("NK bridge: insufficient history")
    Xb = np.column_stack(
        [np.ones(len(bridge)), bridge["ibc"].to_numpy(), bridge["ibc_lag"].to_numpy()]
    )
    beta, *_ = np.linalg.lstsq(Xb, bridge["gdp"].to_numpy(), rcond=None)

    gdp_fc = {
        h: float(
            beta[0] + beta[1] * ibc_qq[q0 + h] + beta[2] * ibc_qq[q0 + h - 1]
        )
        for h in range(5)
    }

    return pi_path, i_path, gap_path, pd.Series(gdp_fc), focus_M


class NewKeynesian:
    model_id = "new_keynesian"
    school = "new_keynesian"

    def __init__(self, est_start: str = NK_ESTIMATION_START, variant: str = "R1"):
        if variant not in {"R1", "R2", "R3"}:
            raise ValueError(f"unknown NK variant {variant}")
        self.est_start = est_start
        self.variant = variant
        self.fit: NKFit | None = None

    def forecast(self, panel: Panel) -> list[Forecast]:
        self.fit = estimate(panel, self.est_start, self.variant)
        pi_path, i_path, gap_path, gdp_fc, _ = _forecast_paths(
            panel, self.fit, self.variant
        )

        pi_hist = panel.monthly("ipca_m")
        gdp = panel.quarterly("gdp_qq")
        selic = panel.monthly("selic_target")

        rows = ipca_rows(pi_path, pi_hist, panel.origin)
        gdp_forecasts = gdp_rows(gdp_fc.to_dict(), panel.origin, float(gdp.iloc[-1]))
        for row in gdp_forecasts:
            row.notes = "satellite_bridge; shared with ibc_bridge"
        rows += gdp_forecasts
        rows += selic_rows(i_path, panel.origin, float(selic.iloc[-1]))
        return validate_rows(rows, self.model_id)
