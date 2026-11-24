from datetime import date

import pandas as pd
import pytest

from econ.config import load_catalog
from econ.vintage import Panel


def test_catalog_series_present(obs):
    catalog = load_catalog()
    present = set(obs["series_id"].unique())
    assert set(catalog) <= present


def test_schema(obs):
    required = {
        "series_id",
        "ref_date",
        "period_end",
        "release_date",
        "vintage_date",
        "value",
        "source",
        "unit",
        "freq",
        "sa_flag",
        "extra",
    }
    assert required <= set(obs.columns)
    assert not obs.duplicated(subset=["series_id", "ref_date", "extra"]).any()
    assert (obs["value"].map(lambda v: pd.notna(v))).all()


def test_release_after_period_end(obs):
    assert (obs["release_date"] >= obs["period_end"]).all()


@pytest.mark.parametrize(
    "origin",
    [date(2010, 1, 29), date(2015, 6, 30), date(2019, 12, 31), date(2026, 10, 30)],
)
def test_asof_never_leaks(obs, origin):
    panel = Panel.build(origin, obs)
    assert panel.obs["release_date"].max() <= origin


def test_latest_available_month(obs):
    panel = Panel.build(date(2019, 1, 31), obs)
    month, _ = panel.latest("ipca_m")
    assert month == pd.Period("2018-12", "M")
    q, _ = panel.latest("gdp_qq")
    assert q <= pd.Period("2018Q4", "Q")


def test_monthly_alignment(obs):
    panel = Panel.build(date(2019, 1, 31), obs)
    s = panel.monthly("ipca_m")
    assert isinstance(s.index, pd.PeriodIndex)
    assert s.index.freqstr == "M"
    assert s.index.is_monotonic_increasing
