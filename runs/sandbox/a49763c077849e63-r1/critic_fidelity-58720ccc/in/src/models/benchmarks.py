from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from ..config import ESTIMATION_START
from ..targets import compound, month_of, quarter_of
from ..vintage import Panel
from .base import Forecast, validate_rows
from .common import (
    MinnesotaBVAR,
    fit_ar,
    focus_annual,
    forecast_ar,
    gdp_rows,
    ipca_rows,
    selic_rows,
)


def _monthly_path(values, origin: date) -> pd.Series:
    m0 = month_of(origin)
    idx = pd.period_range(m0, m0 + 12, freq="M")
    return pd.Series(np.asarray(values, dtype=float), index=idx)


def _est_start() -> pd.Period:
    return pd.Period(ESTIMATION_START, "M")


class RandomWalk:
    model_id = "random_walk"
    school = "benchmark"

    def forecast(self, panel: Panel) -> list[Forecast]:
        ipca = panel.monthly("ipca_m")
        gdp = panel.quarterly("gdp_qq")
        selic = panel.monthly("selic_target")

        last_pi = float(ipca.iloc[-1])
        path = _monthly_path([last_pi] * 13, panel.origin)
        rows = ipca_rows(path, ipca, panel.origin)

        last_g = float(gdp.iloc[-1])
        rows += gdp_rows({h: last_g for h in range(5)}, panel.origin, last_g)

        last_s = float(selic.iloc[-1])
        spath = _monthly_path([last_s] * 13, panel.origin)
        rows += selic_rows(spath, panel.origin, last_s)
        return validate_rows(rows, self.model_id)


class SeasonalNaive:
    model_id = "seasonal_naive"
    school = "benchmark"

    def forecast(self, panel: Panel) -> list[Forecast]:
        ipca = panel.monthly("ipca_m")
        gdp = panel.quarterly("gdp_qq")
        selic = panel.monthly("selic_target")

        last12 = ipca.iloc[-12:].to_numpy()
        if len(last12) < 12:
            raise ValueError("seasonal naive needs 12 months")
        path = _monthly_path([last12[j % 12] for j in range(13)], panel.origin)
        rows = ipca_rows(path, ipca, panel.origin)

        q0 = quarter_of(panel.origin)
        last_g = float(gdp.iloc[-1])
        gvals = {}
        for h in range(5):
            q = q0 + h - 4
            gvals[h] = float(gdp.loc[q]) if q in gdp.index else last_g
        rows += gdp_rows(gvals, panel.origin, last_g)

        last_s = float(selic.iloc[-1])
        spath = _monthly_path([last_s] * 13, panel.origin)
        rows += selic_rows(spath, panel.origin, last_s)
        return validate_rows(rows, self.model_id)


def _ar_monthly(panel: Panel, series_id: str, max_p: int) -> tuple[np.ndarray, pd.Series]:
    s = panel.monthly(series_id)
    s = s[s.index >= _est_start()]
    if len(s) < 30:
        raise ValueError(f"{series_id}: insufficient history")
    p, beta = fit_ar(s.to_numpy(), max_p)
    fc = forecast_ar(s.to_numpy(), p, beta, 13)
    return fc, s


class ARBenchmark:
    model_id = "ar"
    school = "benchmark"

    def forecast(self, panel: Panel) -> list[Forecast]:
        ipca = panel.monthly("ipca_m")
        gdp = panel.quarterly("gdp_qq")
        selic = panel.monthly("selic_target")

        pi_fc, _ = _ar_monthly(panel, "ipca_m", 6)
        path = _monthly_path(pi_fc, panel.origin)
        rows = ipca_rows(path, ipca, panel.origin)

        q0 = quarter_of(panel.origin)
        g = gdp[gdp.index >= pd.Period(ESTIMATION_START, "Q")]
        if len(g) < 20:
            raise ValueError("gdp: insufficient history")
        p, beta = fit_ar(g.to_numpy(), 4)
        lead = (q0 - g.index[-1]).n
        steps = lead + 4
        gfc = forecast_ar(g.to_numpy(), p, beta, steps)
        gvals = {h: float(gfc[h + lead - 1]) for h in range(5)}
        rows += gdp_rows(gvals, panel.origin, float(g.iloc[-1]))

        s_fc, selic_hist = _ar_monthly(panel, "selic_target", 6)
        m0 = month_of(panel.origin)
        spath = pd.Series(index=pd.period_range(m0, m0 + 12, freq="M"), dtype=float)
        spath.loc[m0] = float(selic_hist.iloc[-1])
        for h in range(1, 13):
            spath.loc[m0 + h] = float(s_fc[h - 1])
        rows += selic_rows(spath, panel.origin, float(selic_hist.iloc[-1]))
        return validate_rows(rows, self.model_id)


def _quarterly_from_monthly(panel: Panel) -> pd.DataFrame:
    ipca = panel.monthly("ipca_m")
    selic = panel.monthly("selic_target")
    fx = panel.monthly("fx_usdbrl")
    gdp = panel.quarterly("gdp_qq")

    ipca_q = ipca.groupby(ipca.index.asfreq("Q")).apply(compound)
    selic_q = selic.groupby(selic.index.asfreq("Q")).mean()
    fx_q = fx.groupby(fx.index.asfreq("Q")).mean()
    fx_q = 100.0 * np.log(fx_q).diff()

    df = pd.concat(
        [gdp.rename("gdp_qq"), ipca_q.rename("ipca_q"), selic_q.rename("selic_q"), fx_q.rename("fx_q")],
        axis=1,
        join="inner",
    )
    return df.dropna()


class BVARBenchmark:
    model_id = "bvar"
    school = "benchmark"

    def forecast(self, panel: Panel) -> list[Forecast]:
        ipca = panel.monthly("ipca_m")
        ibc = panel.monthly("ibc_br")
        selic = panel.monthly("selic_target")
        fx = panel.monthly("fx_usdbrl")

        mdf = pd.concat(
            [
                ipca.rename("pi"),
                (100 * np.log(ibc).diff()).rename("ibc_g"),
                selic.rename("selic"),
                (100 * np.log(fx).diff()).rename("fx_g"),
            ],
            axis=1,
            join="inner",
        ).dropna()
        mdf = mdf[mdf.index >= _est_start()]
        if len(mdf) < 40:
            raise ValueError("monthly BVAR: insufficient history")

        bvar_m = MinnesotaBVAR(p=2, lam=0.2, delta=0.5).fit(mdf.to_numpy())
        fc_m = bvar_m.forecast(13)
        path = _monthly_path(fc_m[:, 0], panel.origin)
        rows = ipca_rows(path, ipca, panel.origin)

        qdf = _quarterly_from_monthly(panel)
        qdf = qdf[qdf.index >= pd.Period(ESTIMATION_START, "Q")]
        if len(qdf) < 24:
            raise ValueError("quarterly BVAR: insufficient history")
        bvar_q = MinnesotaBVAR(p=2, lam=0.2, delta=0.5).fit(qdf.to_numpy())
        q0 = quarter_of(panel.origin)
        lead = (q0 - qdf.index[-1]).n
        fc_q = bvar_q.forecast(max(lead + 4, 2))
        gvals = {h: float(fc_q[h + lead - 1, 0]) for h in range(5)}
        gdp = panel.quarterly("gdp_qq")
        rows += gdp_rows(gvals, panel.origin, float(gdp.iloc[-1]))

        spath = _monthly_path(fc_m[:, 2], panel.origin)
        rows += selic_rows(spath, panel.origin, float(selic.iloc[-1]))
        return validate_rows(rows, self.model_id)


class IBCBridge:
    model_id = "ibc_bridge"
    school = "benchmark"

    def forecast(self, panel: Panel) -> list[Forecast]:
        ibc = panel.monthly("ibc_br")
        ibc = ibc[ibc.index >= _est_start()]
        gdp = panel.quarterly("gdp_qq")

        qtr = ibc.index.asfreq("Q")
        grp = ibc.groupby(qtr)
        counts = grp.count()
        qlevel = grp.mean()[counts == 3]
        ibc_qq = 100 * np.log(qlevel).diff()

        df = pd.concat([gdp.rename("gdp"), ibc_qq.rename("ibc")], axis=1, join="inner")
        df["ibc_lag"] = df["ibc"].shift(1)
        reg = df.dropna()
        if len(reg) < 20:
            raise ValueError("bridge: insufficient history")
        X = np.column_stack([np.ones(len(reg)), reg["ibc"].to_numpy(), reg["ibc_lag"].to_numpy()])
        y = reg["gdp"].to_numpy()
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)

        growth = 100 * np.log(ibc).diff().dropna()
        p, ar_beta = fit_ar(growth.to_numpy(), 3)
        n_fc = 16
        gfc = forecast_ar(growth.to_numpy(), p, ar_beta, n_fc)
        last_month = ibc.index[-1]
        levels = {last_month: float(ibc.iloc[-1])}
        for j, g in enumerate(gfc, start=1):
            p_m = last_month + j
            levels[p_m] = levels[p_m - 1] * np.exp(g / 100.0)

        m0 = month_of(panel.origin)
        q0 = quarter_of(panel.origin)

        def quarter_level(q: pd.Period) -> float:
            months = pd.period_range(q.start_time, q.end_time, freq="M")
            vals = []
            for m in months:
                if m in levels:
                    vals.append(levels[m])
                elif m in ibc.index:
                    vals.append(float(ibc.loc[m]))
                elif m < m0:
                    vals.append(float(ibc.loc[m]))
                else:
                    raise ValueError(f"bridge: no level for {m}")
            return float(np.mean(vals))

        qlevels = {}
        for q in pd.period_range(q0 - 2, q0 + 4, freq="Q"):
            qlevels[q] = quarter_level(q)

        gvals = {}
        for h in range(5):
            q = q0 + h
            ibc_q = 100 * np.log(qlevels[q] / qlevels[q - 1])
            ibc_lag = 100 * np.log(qlevels[q - 1] / qlevels[q - 2])
            gvals[h] = float(beta[0] + beta[1] * ibc_q + beta[2] * ibc_lag)

        rows = gdp_rows(gvals, panel.origin, float(gdp.iloc[-1]))
        return validate_rows(rows, self.model_id)


class FocusConsensus:
    model_id = "focus_consensus"
    school = "benchmark"

    def forecast(self, panel: Panel) -> list[Forecast]:
        ipca = panel.monthly("ipca_m")
        gdp_series = panel.quarterly("gdp_qq")
        selic = panel.monthly("selic_target")
        m0 = month_of(panel.origin)
        q0 = quarter_of(panel.origin)

        def ipca_path() -> pd.Series:
            ann = focus_annual(panel, "focus_ipca_annual")
            y = m0.year
            e_y, e_y1, e_y2 = ann.get(y), ann.get(y + 1), ann.get(y + 2)
            if e_y is None:
                f12 = panel.monthly("focus_ipca_12m")
                monthly = ((1 + float(f12.iloc[-1]) / 100) ** (1 / 12) - 1) * 100
                return _monthly_path([monthly] * 13, panel.origin)
            ytd_months = pd.period_range(pd.Period(str(y), "M"), m0 - 1, freq="M")
            ytd = compound(ipca.loc[[p for p in ytd_months if p in ipca.index]])
            n_rem = 13 - m0.month
            r_y = ((1 + e_y / 100) / (1 + ytd / 100)) ** (1 / n_rem) - 1
            r_y1 = ((1 + e_y1 / 100) ** (1 / 12) - 1) if e_y1 is not None else r_y
            r_y2 = ((1 + e_y2 / 100) ** (1 / 12) - 1) if e_y2 is not None else r_y1
            vals = []
            for j in range(13):
                p = m0 + j
                r = r_y if p.year == y else (r_y1 if p.year == y + 1 else r_y2)
                vals.append(r * 100)
            return _monthly_path(vals, panel.origin)

        path = ipca_path()
        rows = ipca_rows(path, ipca, panel.origin)

        ann_gdp = focus_annual(panel, "focus_gdp_annual")
        last_g = float(gdp_series.iloc[-1])
        gvals = {}
        for h in range(5):
            q = q0 + h
            e = ann_gdp.get(q.year)
            if e is None:
                gvals[h] = last_g
            else:
                gvals[h] = ((1 + e / 100) ** (1 / 4) - 1) * 100
        rows += gdp_rows(gvals, panel.origin, last_g)

        ann_selic = focus_annual(panel, "focus_selic_annual")
        s0 = float(selic.iloc[-1])
        y = m0.year
        e_y = ann_selic.get(y, s0)
        e_y1 = ann_selic.get(y + 1, e_y)
        spath = pd.Series(index=pd.period_range(m0, m0 + 12, freq="M"), dtype=float)
        n_rem = 12 - m0.month + 1
        for k in range(n_rem):
            p = m0 + k
            if p.year != y:
                break
            spath.loc[p] = s0 + (e_y - s0) * (k + 1) / n_rem
        for p in spath.index[spath.isna()]:
            if p.year == y + 1:
                k = p.month
                spath.loc[p] = e_y + (e_y1 - e_y) * k / 12
            else:
                spath.loc[p] = e_y1
        spath = spath.ffill().bfill()
        rows += selic_rows(spath, panel.origin, s0)
        return validate_rows(rows, self.model_id)


MODELS = {
    "random_walk": RandomWalk,
    "seasonal_naive": SeasonalNaive,
    "ar": ARBenchmark,
    "bvar": BVARBenchmark,
    "ibc_bridge": IBCBridge,
    "focus_consensus": FocusConsensus,
}
