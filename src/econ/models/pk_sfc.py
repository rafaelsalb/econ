from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..targets import compound, month_of, quarter_of
from ..vintage import Panel
from .base import Forecast, validate_rows
from .common import gdp_rows, ipca_rows, selic_rows
from .phase2_common import diagnostics_payload, monthly_frame, ols_hac

START = "2000-01-01"


@dataclass
class SFCFit:
    consumption: dict
    investment: dict
    government: dict
    exports: dict
    imports: dict
    deflator: dict
    ipca_bridge: dict
    data: pd.DataFrame
    identity_error: float


def _quarterly(panel: Panel) -> pd.DataFrame:
    nom_ids = [
        "gdp_nominal",
        "consumption_nominal",
        "govt_consumption_nominal",
        "investment_nominal",
        "exports_nominal",
        "imports_nominal",
        "taxes_nominal",
    ]
    nom = {sid: panel.quarterly(sid) for sid in nom_ids}
    df = pd.DataFrame(nom)
    df["real_gdp"] = panel.quarterly("gdp_level")
    ipca = panel.monthly("ipca_m")
    df["ipca_q"] = ipca.groupby(ipca.index.asfreq("Q")).apply(compound)
    selic = panel.monthly("selic_target")
    df["selic_q"] = selic.groupby(selic.index.asfreq("Q")).mean()
    fx = panel.monthly("fx_usdbrl")
    fx_q = fx.groupby(fx.index.asfreq("Q")).mean()
    df["fx_g"] = 100 * np.log(fx_q).diff()
    pb = panel.monthly("primary_balance_12m")
    df["pb_q"] = pb.groupby(pb.index.asfreq("Q")).mean()
    debt = panel.monthly("debt_gdp")
    df["debt_q"] = debt.groupby(debt.index.asfreq("Q")).last()
    df = df.dropna()
    df["deflator"] = 100 * df["gdp_nominal"] / df["real_gdp"]
    df["pi_deflator"] = 100 * (df["deflator"] / df["deflator"].shift(1) - 1)
    df["gdp_g"] = 100 * np.log(df["real_gdp"]).diff()
    for name in ["consumption", "investment", "govt_consumption", "exports", "imports"]:
        df[f"{name}_real"] = 100 * df[f"{name}_nominal"] / df["deflator"]
    df["real_rate"] = df["selic_q"] / 4 - df["pi_deflator"]
    df = df[df.index >= pd.Period(START, "Q")]
    return df


def estimate(panel: Panel) -> SFCFit:
    df = _quarterly(panel)
    if len(df) < 20:
        raise ValueError("sfc: insufficient history")
    d = df.copy()
    for col in [
        "real_gdp",
        "real_rate",
        "fx_g",
        "pi_deflator",
        "gdp_g",
        "govt_consumption_real",
        "exports_real",
        "imports_real",
    ]:
        d[f"{col}_1"] = d[col].shift(1)

    cons = d.dropna(subset=["consumption_real", "real_gdp_1", "real_rate_1"])
    consumption = ols_hac(
        cons["consumption_real"], cons[["real_gdp_1", "real_rate_1"]]
    )
    inv = d.dropna(subset=["investment_real", "real_gdp_1", "real_rate_1"])
    investment = ols_hac(
        inv["investment_real"], inv[["real_gdp_1", "real_rate_1"]]
    )
    gov = d.dropna(subset=["govt_consumption_real", "govt_consumption_real_1"])
    government = ols_hac(
        gov["govt_consumption_real"], gov[["govt_consumption_real_1"]]
    )
    exp = d.dropna(subset=["exports_real", "exports_real_1", "fx_g_1"])
    exports = ols_hac(exp["exports_real"], exp[["exports_real_1", "fx_g_1"]])
    imp = d.dropna(subset=["imports_real", "real_gdp_1", "fx_g_1"])
    imports = ols_hac(imp["imports_real"], imp[["real_gdp_1", "fx_g_1"]])
    defl = d.dropna(subset=["pi_deflator", "pi_deflator_1", "fx_g_1", "gdp_g_1"])
    deflator = ols_hac(
        defl["pi_deflator"], defl[["pi_deflator_1", "fx_g_1", "gdp_g_1"]]
    )
    br = d.dropna(subset=["ipca_q", "pi_deflator"])
    ipca_bridge = ols_hac(br["ipca_q"], br[["pi_deflator"]])

    identity = (
        df["consumption_real"]
        + df["investment_real"]
        + df["govt_consumption_real"]
        + df["exports_real"]
        - df["imports_real"]
    )
    identity_error = float(
        np.mean(np.abs(identity - df["real_gdp"]) / df["real_gdp"])
    )
    return SFCFit(
        consumption=consumption,
        investment=investment,
        government=government,
        exports=exports,
        imports=imports,
        deflator=deflator,
        ipca_bridge=ipca_bridge,
        data=df,
        identity_error=identity_error,
    )


def _c(params: pd.Series, name: str) -> float:
    return float(params[name]) if name in params.index else 0.0


class PostKeynesianSFC:
    model_id = "pk_sfc"
    school = "pk_sfc"

    def __init__(self, variant: str = "R1", est_start: str = START):
        if variant not in {"R1"}:
            raise ValueError(f"unknown SFC variant {variant}")
        self.variant = variant
        self.est_start = est_start

    def diagnostics(self, panel: Panel) -> dict:
        fit = estimate(panel)
        return diagnostics_payload(
            panel,
            variant=self.variant,
            equations={
                "consumption": fit.consumption,
                "investment": fit.investment,
                "government": fit.government,
                "exports": fit.exports,
                "imports": fit.imports,
                "deflator": fit.deflator,
                "ipca_bridge": fit.ipca_bridge,
            },
            sample=fit.data,
            extra={
                "identity_error": fit.identity_error,
                "identity_ok": bool(fit.identity_error < 0.05),
            },
        )

    def forecast(self, panel: Panel) -> list[Forecast]:
        fit = estimate(panel)
        df = fit.data
        q0 = quarter_of(panel.origin)
        m0 = month_of(panel.origin)
        last_q = df.index.max()
        start_q = last_q + 1
        end_q = q0 + 5

        b_c, b_i, b_g, b_x, b_m = (
            fit.consumption["params"],
            fit.investment["params"],
            fit.government["params"],
            fit.exports["params"],
            fit.imports["params"],
        )
        b_d, b_p = fit.deflator["params"], fit.ipca_bridge["params"]

        selic = float(panel.latest("selic_target")[1])
        y = {last_q: float(df.loc[last_q, "real_gdp"])}
        p = {last_q: float(df.loc[last_q, "deflator"])}
        pi_d = {last_q: float(df.loc[last_q, "pi_deflator"])}
        pb = {last_q: float(df.loc[last_q, "pb_q"])}
        debt = {last_q: float(df.loc[last_q, "debt_q"])}
        c = {last_q: float(df.loc[last_q, "consumption_real"])}
        i = {last_q: float(df.loc[last_q, "investment_real"])}
        g = {last_q: float(df.loc[last_q, "govt_consumption_real"])}
        x = {last_q: float(df.loc[last_q, "exports_real"])}
        m = {last_q: float(df.loc[last_q, "imports_real"])}
        gdp_g = {last_q: float(df.loc[last_q, "gdp_g"])}
        fx_last = float(df.loc[last_q, "fx_g"])

        for q in pd.period_range(start_q, end_q, freq="Q"):
            real_rate = selic / 4 - pi_d[q - 1]
            c[q] = _c(b_c, "const") + _c(b_c, "real_gdp_1") * y[q - 1] + _c(b_c, "real_rate_1") * real_rate
            i[q] = _c(b_i, "const") + _c(b_i, "real_gdp_1") * y[q - 1] + _c(b_i, "real_rate_1") * real_rate
            g[q] = _c(b_g, "const") + _c(b_g, "govt_consumption_real_1") * g[q - 1]
            fx_g = fx_last if q == start_q else 0.0
            x[q] = _c(b_x, "const") + _c(b_x, "exports_real_1") * x[q - 1] + _c(b_x, "fx_g_1") * fx_g
            m[q] = _c(b_m, "const") + _c(b_m, "real_gdp_1") * y[q - 1] + _c(b_m, "fx_g_1") * fx_g
            y[q] = c[q] + i[q] + g[q] + x[q] - m[q]
            gdp_g[q] = 100 * np.log(y[q] / y[q - 1]) if y[q] > 0 else 0.0
            pi_d[q] = (
                _c(b_d, "const")
                + _c(b_d, "pi_deflator_1") * pi_d[q - 1]
                + _c(b_d, "fx_g_1") * fx_g
                + _c(b_d, "gdp_g_1") * gdp_g[q - 1]
            )
            p[q] = p[q - 1] * (1 + pi_d[q] / 100)
            nominal_growth = ((1 + pi_d[q] / 100) * (1 + gdp_g[q] / 100) - 1) * 100
            debt[q] = debt[q - 1] + (
                (selic / 400 - nominal_growth / 100) / (1 + nominal_growth / 100)
            ) * debt[q - 1] - pb[q - 1] / 4
            pb[q] = pb[q - 1]

        quarters = pd.period_range(q0, q0 + 5, freq="Q")
        pi_ipca_q = {
            q: _c(b_p, "const") + _c(b_p, "pi_deflator") * pi_d[q] for q in quarters
        }
        monthly = {}
        for q in quarters:
            rate = pi_ipca_q[q]
            monthly_rate = ((1 + rate / 100) ** (1 / 3) - 1) * 100
            for mth in pd.period_range(q.start_time, q.end_time, freq="M"):
                monthly[mth] = monthly_rate
        idx = pd.period_range(m0, m0 + 12, freq="M")
        pi_path = pd.Series({t: monthly.get(t, np.nan) for t in idx})
        if pi_path.isna().any():
            raise ValueError("sfc: monthly IPCA path incomplete")
        pi_path = pi_path.interpolate().ffill().bfill()

        gdp_fc = {h: float(gdp_g.get(q0 + h, gdp_g[end_q])) for h in range(5)}
        selic_path = pd.Series(selic, index=idx)
        rows = ipca_rows(pi_path, panel.monthly("ipca_m"), panel.origin)
        gdp = panel.quarterly("gdp_qq")
        gdp_rows_list = gdp_rows(gdp_fc, panel.origin, float(gdp.iloc[-1]))
        for row in gdp_rows_list:
            row.notes = "sfc_identity"
        rows += gdp_rows_list
        srows = selic_rows(selic_path, panel.origin, selic)
        for row in srows:
            row.notes = "satellite_exogenous_selic"
        rows += srows
        return validate_rows(rows, self.model_id)
