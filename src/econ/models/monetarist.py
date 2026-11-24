from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..targets import month_of
from ..vintage import Panel
from .base import Forecast, validate_rows
from .common import MinnesotaBVAR, gdp_rows, ipca_rows, selic_rows
from .phase2_common import (
    bridge_gdp,
    diagnostics_payload,
    level_path_from_growth,
    marked,
    monthly_frame,
    ols_hac,
)

START = "2004-01-01"


@dataclass
class MonetaristFit:
    money: dict
    pstar: dict
    bvar: MinnesotaBVAR
    Y: pd.DataFrame
    data: pd.DataFrame
    long_run: pd.Series
    price_gap: pd.Series


def estimate(panel: Panel) -> MonetaristFit:
    df = monthly_frame(
        panel,
        ["m2", "credit_total", "ipca_m", "ibc_br", "selic_target", "fx_usdbrl"],
    )
    df = df[df.index >= pd.Period(START, "M")]
    if len(df) < 60:
        raise ValueError("monetarist: insufficient history")
    cpi = (1 + df["ipca_m"] / 100).cumprod()
    df["m2_real"] = np.log(df["m2"]) - np.log(cpi)
    df["y"] = np.log(df["ibc_br"])
    df["i"] = np.log1p(df["selic_target"] / 100)
    df["m2_g"] = 100 * np.log(df["m2"]).diff()
    df["credit_g"] = 100 * np.log(df["credit_total"]).diff()
    df["ibc_g"] = 100 * np.log(df["ibc_br"]).diff()
    df["fx_g"] = 100 * np.log(df["fx_usdbrl"]).diff()
    for col in ["m2_real", "m2_g", "credit_g", "ibc_g", "fx_g", "ipca_m", "selic_target"]:
        df[f"{col}_1"] = df[col].shift(1)

    md = df.dropna(subset=["m2_real", "m2_real_1", "y", "i"]).copy()
    money = ols_hac(md["m2_real"], md[["y", "i", "m2_real_1"]])
    a = money["params"]
    long_run = (a["const"] + a["y"] * df["y"] + a["i"] * df["i"]) / (1 - a["m2_real_1"])
    price_gap = np.log(cpi) - (np.log(df["m2"]) - long_run)

    ps = df.dropna(subset=["ipca_m", "ipca_m_1", "fx_g_1"]).copy()
    ps["gap_1"] = price_gap.shift(1)
    ps = ps.dropna(subset=["gap_1"])
    pstar = ols_hac(ps["ipca_m"], ps[["ipca_m_1", "gap_1", "fx_g_1"]])

    Y = df[["ipca_m", "m2_g", "credit_g", "ibc_g", "selic_target", "fx_g"]].dropna()
    Y = Y[Y.index >= pd.Period(START, "M")]
    if len(Y) < 60:
        raise ValueError("monetarist BVAR: insufficient history")
    bvar = MinnesotaBVAR(p=2, lam=0.2, delta=0.5).fit(Y.to_numpy())
    return MonetaristFit(
        money=money,
        pstar=pstar,
        bvar=bvar,
        Y=Y,
        data=df,
        long_run=long_run,
        price_gap=price_gap,
    )


class Monetarist:
    model_id = "monetarist"
    school = "monetarist"

    def __init__(self, variant: str = "R1", est_start: str = START):
        if variant not in {"R1"}:
            raise ValueError(f"unknown monetarist variant {variant}")
        self.variant = variant
        self.est_start = est_start

    def diagnostics(self, panel: Panel) -> dict:
        fit = estimate(panel)
        return diagnostics_payload(
            panel,
            variant=self.variant,
            equations={"money_demand": fit.money, "pstar_inflation": fit.pstar},
            sample=fit.Y,
            extra={
                "bvar_stable": bool(fit.bvar._stable(fit.bvar.B)),
                "bvar_lambda": float(fit.bvar.lam_used),
                "price_gap_last": float(fit.price_gap.dropna().iloc[-1]),
            },
        )

    def forecast(self, panel: Panel) -> list[Forecast]:
        fit = estimate(panel)
        m0 = month_of(panel.origin)
        pi_hist = panel.monthly("ipca_m")
        fc = fit.bvar.forecast(15)
        idx = pd.period_range(m0, m0 + 12, freq="M")
        pi_path = pd.Series(fc[:13, 0], index=idx)
        selic_path = pd.Series(fc[:13, 4], index=idx)

        last_month, last_level = panel.latest("ibc_br")
        if last_month != m0 - 1:
            raise ValueError(f"monetarist: IBC ends {last_month}, expected {m0 - 1}")
        ibc_level = level_path_from_growth(
            last_month, float(last_level), fc[:, 3], 14
        )
        gdp_fc, _ = bridge_gdp(panel, ibc_level, panel.origin)

        rows = ipca_rows(pi_path, pi_hist, panel.origin)
        gdp = panel.quarterly("gdp_qq")
        rows += marked(
            gdp_rows(gdp_fc, panel.origin, float(gdp.iloc[-1])),
            "satellite_bridge; monetarist activity mapping",
        )
        rows += selic_rows(selic_path, panel.origin, float(panel.latest("selic_target")[1]))
        return validate_rows(rows, self.model_id)
