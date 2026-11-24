from __future__ import annotations

from datetime import date
from functools import lru_cache

import pandas as pd

from .config import ROOT

TARGET_FILE = ROOT / "data" / "reference" / "inflation_targets.csv"

TARGET_HORIZONS = {
    "ipca_m": list(range(0, 13)),
    "ipca_12m": [3, 6, 12],
    "gdp_qq": [0, 1, 2, 3, 4],
    "selic": [0, 3, 6, 12],
}

PRIMARY_HORIZONS = {
    "ipca_12m": [6, 12],
    "gdp_qq": [1, 4],
    "selic": [12],
}


@lru_cache(maxsize=1)
def inflation_targets() -> pd.Series:
    df = pd.read_csv(TARGET_FILE)
    return pd.Series(df["target"].to_numpy(), index=df["year"].astype(int))


def target_for(d: date | pd.Period | pd.Timestamp) -> float:
    year = pd.Period(d, "Y").year if not isinstance(d, date) else d.year
    targets = inflation_targets()
    if year <= targets.index.min():
        return float(targets.iloc[0])
    if year >= targets.index.max():
        return float(targets.iloc[-1])
    return float(targets.loc[year])


def month_of(d: date | pd.Timestamp) -> pd.Period:
    return pd.Period(pd.Timestamp(d), "M")


def quarter_of(d: date | pd.Timestamp) -> pd.Period:
    return pd.Period(pd.Timestamp(d), "Q")


def compound(monthly_pct: pd.Series) -> float:
    return float(((1.0 + monthly_pct / 100.0).prod() - 1.0) * 100.0)


def inflation_12m_from_path(path: pd.Series, end: pd.Period) -> float:
    window = pd.period_range(end - 11, end, freq="M")
    missing = [p for p in window if p not in path.index]
    if missing:
        raise ValueError(f"12m window missing months: {missing}")
    return compound(path.loc[window])


def monthly_inflation_series(obs: pd.DataFrame) -> pd.Series:
    g = obs[obs["series_id"] == "ipca_m"].sort_values("ref_date")
    idx = pd.PeriodIndex(pd.to_datetime(g["ref_date"]), freq="M")
    return pd.Series(g["value"].to_numpy(), index=idx).astype(float).sort_index()


def quarterly_gdp_series(obs: pd.DataFrame) -> pd.Series:
    g = obs[obs["series_id"] == "gdp_qq"].sort_values("ref_date")
    idx = pd.PeriodIndex(pd.to_datetime(g["ref_date"]), freq="Q")
    return pd.Series(g["value"].to_numpy(), index=idx).astype(float).sort_index()


def selic_monthly_series(obs: pd.DataFrame) -> pd.Series:
    g = obs[obs["series_id"] == "selic_target"].sort_values("ref_date")
    idx = pd.DatetimeIndex(pd.to_datetime(g["ref_date"]))
    s = pd.Series(g["value"].to_numpy(), index=idx).astype(float).sort_index()
    return s.groupby(s.index.to_period("M")).last()


def realized(
    obs: pd.DataFrame,
    target: str,
    ref_date: date | pd.Timestamp,
) -> float | None:
    """Final-vintage realised value. Evaluation only — never used by models."""
    ref_date = pd.Timestamp(ref_date).date()
    month = month_of(ref_date)
    if target == "ipca_m":
        s = monthly_inflation_series(obs)
        return float(s.loc[month]) if month in s.index else None
    if target == "ipca_12m":
        s = monthly_inflation_series(obs)
        window = pd.period_range(month - 11, month, freq="M")
        if not all(p in s.index for p in window):
            return None
        return compound(s.loc[window])
    if target == "gdp_qq":
        s = quarterly_gdp_series(obs)
        q = quarter_of(ref_date)
        return float(s.loc[q]) if q in s.index else None
    if target == "selic":
        s = selic_monthly_series(obs)
        return float(s.loc[month]) if month in s.index else None
    raise ValueError(f"unknown target {target}")


def ref_date_for(target: str, origin: date, horizon: int) -> date:
    if target in {"ipca_m", "ipca_12m", "selic"}:
        p = month_of(origin) + horizon
        return p.end_time.date()
    if target == "gdp_qq":
        p = quarter_of(origin) + horizon
        return p.end_time.date()
    raise ValueError(target)
