from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from .ingest import load_observations


@dataclass
class Panel:
    """As-of view of the curated data at a forecast origin.

    Only observations whose `release_date` is on or before `origin` are visible.
    Series are exposed as pandas objects indexed by period end:
      monthly -> PeriodIndex freq 'M'
      quarterly -> PeriodIndex freq 'Q'
      daily -> DatetimeIndex
    """

    origin: date
    obs: pd.DataFrame
    _cache: dict = field(default_factory=dict, repr=False)

    @classmethod
    def build(cls, origin: date, obs: pd.DataFrame | None = None) -> "Panel":
        if obs is None:
            obs = load_observations()
        visible = obs[obs["release_date"] <= origin].copy()
        return cls(origin=origin, obs=visible)

    def _raw(self, series_id: str) -> pd.DataFrame:
        if series_id not in self._cache:
            g = self.obs[self.obs["series_id"] == series_id]
            if g.empty:
                raise KeyError(f"series {series_id} not available at {self.origin}")
            g = g.sort_values(["ref_date", "vintage_date"])
            g = g.groupby("ref_date", as_index=False).tail(1)
            self._cache[series_id] = g
        return self._cache[series_id]

    def monthly(self, series_id: str) -> pd.Series:
        g = self._raw(series_id)
        freq = str(g["freq"].iloc[0])
        if freq == "D":
            idx = pd.DatetimeIndex(pd.to_datetime(g["ref_date"]))
            s = pd.Series(g["value"].to_numpy(), index=idx).sort_index()
            s = s.groupby(s.index.to_period("M")).last()
        elif freq == "M":
            idx = pd.PeriodIndex(pd.to_datetime(g["ref_date"]), freq="M")
            s = pd.Series(g["value"].to_numpy(), index=idx).sort_index()
        else:
            raise ValueError(f"{series_id}: freq {freq} is not monthly")
        s.index.name = "month"
        return s.astype(float)

    def quarterly(self, series_id: str) -> pd.Series:
        g = self._raw(series_id)
        freq = str(g["freq"].iloc[0])
        if freq != "Q":
            raise ValueError(f"{series_id}: freq {freq} is not quarterly")
        idx = pd.PeriodIndex(pd.to_datetime(g["ref_date"]), freq="Q")
        s = pd.Series(g["value"].to_numpy(), index=idx).sort_index()
        s.index.name = "quarter"
        return s.astype(float)

    def daily(self, series_id: str) -> pd.Series:
        g = self._raw(series_id)
        idx = pd.DatetimeIndex(pd.to_datetime(g["ref_date"]))
        s = pd.Series(g["value"].to_numpy(), index=idx).sort_index()
        s.index.name = "date"
        return s.astype(float)

    def latest(self, series_id: str) -> tuple[pd.Period | pd.Timestamp, float]:
        g = self._raw(series_id)
        row = g.iloc[-1]
        freq = str(g["freq"].iloc[0])
        if freq == "M":
            return pd.Period(pd.Timestamp(row["ref_date"]), "M"), float(row["value"])
        if freq == "Q":
            return pd.Period(pd.Timestamp(row["ref_date"]), "Q"), float(row["value"])
        return pd.Timestamp(row["ref_date"]), float(row["value"])


def common_monthly(panel: Panel, series_ids: list[str]) -> pd.DataFrame:
    cols = {sid: panel.monthly(sid) for sid in series_ids}
    df = pd.DataFrame(cols).sort_index()
    return df
