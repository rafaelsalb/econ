from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..targets import month_of
from ..vintage import Panel
from .base import Forecast, validate_rows
from .common import gdp_rows, ipca_rows, selic_rows
from .phase2_common import (
    bridge_gdp,
    diagnostics_payload,
    level_path_from_growth,
    marked,
    monthly_frame,
    ols_hac,
)

START = "2007-01-01"


@dataclass
class FiscalFit:
    fiscal: dict
    inflation: dict
    activity: dict
    policy: dict
    data: pd.DataFrame


def estimate(panel: Panel) -> FiscalFit:
    df = monthly_frame(
        panel,
        [
            "debt_gdp",
            "primary_balance_12m",
            "ipca_m",
            "ibc_br",
            "selic_target",
            "fx_usdbrl",
        ],
    )
    df = df[df.index >= pd.Period(START, "M")]
    if len(df) < 30:
        raise ValueError("ftpl: insufficient history")
    df["ibc_g"] = 100 * np.log(df["ibc_br"]).diff()
    df["fx_g"] = 100 * np.log(df["fx_usdbrl"]).diff()
    for col in ["debt_gdp", "primary_balance_12m", "ipca_m", "ibc_g", "fx_g", "selic_target"]:
        df[f"{col}_1"] = df[col].shift(1)

    fr = df.dropna(subset=["primary_balance_12m", "debt_gdp_1", "ibc_g_1", "selic_target_1"])
    fiscal = ols_hac(
        fr["primary_balance_12m"],
        fr[["debt_gdp_1", "ibc_g_1", "selic_target_1"]],
    )

    inf = df.dropna(
        subset=[
            "ipca_m",
            "ipca_m_1",
            "primary_balance_12m_1",
            "debt_gdp_1",
            "fx_g_1",
            "ibc_g_1",
        ]
    )
    inflation = ols_hac(
        inf["ipca_m"],
        inf[["ipca_m_1", "primary_balance_12m_1", "debt_gdp_1", "fx_g_1", "ibc_g_1"]],
    )

    act = df.dropna(subset=["ibc_g", "ibc_g_1", "selic_target_1", "ipca_m_1"])
    act = act.assign(real_rate=act["selic_target_1"] - act["ipca_m_1"])
    activity = ols_hac(act["ibc_g"], act[["ibc_g_1", "real_rate"]])

    pol = df.dropna(
        subset=["selic_target", "selic_target_1", "ipca_m_1", "ibc_g_1", "debt_gdp_1"]
    )
    policy = ols_hac(
        pol["selic_target"],
        pol[["selic_target_1", "ipca_m_1", "ibc_g_1", "debt_gdp_1"]],
    )
    return FiscalFit(
        fiscal=fiscal, inflation=inflation, activity=activity, policy=policy, data=df
    )


def _c(params: pd.Series, name: str) -> float:
    return float(params[name]) if name in params.index else 0.0


class FiscalFTPL:
    model_id = "fiscal_ftpl"
    school = "fiscal_ftpl"

    def __init__(self, variant: str = "R1", est_start: str = START):
        if variant not in {"R1"}:
            raise ValueError(f"unknown FTPL variant {variant}")
        self.variant = variant
        self.est_start = est_start

    def diagnostics(self, panel: Panel) -> dict:
        fit = estimate(panel)
        return diagnostics_payload(
            panel,
            variant=self.variant,
            equations={
                "fiscal_reaction": fit.fiscal,
                "inflation": fit.inflation,
                "activity": fit.activity,
                "policy": fit.policy,
            },
            sample=fit.data,
        )

    def forecast(self, panel: Panel) -> list[Forecast]:
        fit = estimate(panel)
        df = fit.data
        m0 = month_of(panel.origin)
        last = min(df.index.max(), m0 - 1)
        actual_selic = float(panel.latest("selic_target")[1])

        b_f = fit.fiscal["params"]
        b_pi = fit.inflation["params"]
        b_a = fit.activity["params"]
        b_s = fit.policy["params"]

        debt_path: dict[pd.Period, float] = {last: float(df.loc[last, "debt_gdp"])}
        pb_path: dict[pd.Period, float] = {last: float(df.loc[last, "primary_balance_12m"])}
        pi_path: dict[pd.Period, float] = {last: float(df.loc[last, "ipca_m"])}
        ibc_path: dict[pd.Period, float] = {last: float(df.loc[last, "ibc_g"])}
        selic_path: dict[pd.Period, float] = {last: float(df.loc[last, "selic_target"])}
        # Seed the last few actual months so the first forecast step has lags
        # even when the fiscal release lag leaves the frame two months stale.
        for m in df.index[-3:]:
            if m <= m0:
                debt_path[m] = float(df.loc[m, "debt_gdp"])
                pb_path[m] = float(df.loc[m, "primary_balance_12m"])
                pi_path[m] = float(df.loc[m, "ipca_m"])
                ibc_path[m] = float(df.loc[m, "ibc_g"])
                selic_path[m] = float(df.loc[m, "selic_target"])
        selic_path[m0] = actual_selic
        fx_last = float(df.loc[last, "fx_g"])

        for t in pd.period_range(last + 1, m0 + 14, freq="M"):
            fx_term = fx_last if t == last + 1 else 0.0
            pb_t = (
                _c(b_f, "const")
                + _c(b_f, "debt_gdp_1") * debt_path[t - 1]
                + _c(b_f, "ibc_g_1") * ibc_path[t - 1]
                + _c(b_f, "selic_target_1") * selic_path[t - 1]
            )
            ibc_t = (
                _c(b_a, "const")
                + _c(b_a, "ibc_g_1") * ibc_path[t - 1]
                + _c(b_a, "real_rate")
                * (selic_path[t - 1] - pi_path[t - 1])
            )
            pi_t = (
                _c(b_pi, "const")
                + _c(b_pi, "ipca_m_1") * pi_path[t - 1]
                + _c(b_pi, "primary_balance_12m_1") * pb_path[t - 1]
                + _c(b_pi, "debt_gdp_1") * debt_path[t - 1]
                + _c(b_pi, "fx_g_1") * fx_term
                + _c(b_pi, "ibc_g_1") * ibc_path[t - 1]
            )
            if t == m0:
                selic_t = actual_selic
            else:
                selic_t = (
                    _c(b_s, "const")
                    + _c(b_s, "selic_target_1") * selic_path[t - 1]
                    + _c(b_s, "ipca_m_1") * pi_path[t - 1]
                    + _c(b_s, "ibc_g_1") * ibc_path[t - 1]
                    + _c(b_s, "debt_gdp_1") * debt_path[t - 1]
                )
            nominal_growth = ((1 + pi_t / 100) * (1 + ibc_t / 100) - 1) * 100
            debt_t = debt_path[t - 1] + (
                (selic_path[t - 1] / 100 - nominal_growth / 100)
                / (1 + nominal_growth / 100)
            ) * debt_path[t - 1] - pb_t / 12
            pb_path[t] = float(pb_t)
            ibc_path[t] = float(ibc_t)
            pi_path[t] = float(pi_t)
            debt_path[t] = float(debt_t)
            selic_path[t] = float(selic_t)

        idx = pd.period_range(m0, m0 + 12, freq="M")
        pi_series = pd.Series({t: pi_path[t] for t in idx})
        selic_series = pd.Series({t: selic_path[t] for t in idx})

        ibc_last_month, ibc_last_level = panel.latest("ibc_br")
        ibc_level = level_path_from_growth(
            ibc_last_month,
            float(ibc_last_level),
            np.array([ibc_path[m0 + j] for j in range(15)]),
            14,
        )
        gdp_fc, _ = bridge_gdp(panel, ibc_level, panel.origin)

        rows = ipca_rows(pi_series, panel.monthly("ipca_m"), panel.origin)
        gdp = panel.quarterly("gdp_qq")
        rows += marked(
            gdp_rows(gdp_fc, panel.origin, float(gdp.iloc[-1])),
            "satellite_bridge; fiscal activity mapping",
        )
        rows += selic_rows(
            selic_series, panel.origin, actual_selic
        )
        return validate_rows(rows, self.model_id)
