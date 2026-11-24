from datetime import date

import pandas as pd
import pytest

from econ.targets import (
    compound,
    inflation_12m_from_path,
    monthly_inflation_series,
    realized,
    ref_date_for,
    target_for,
)


def test_compound():
    s = pd.Series([1.0, 1.0, 1.0])
    assert compound(s) == pytest.approx(3.0301, rel=1e-4)


def test_target_history():
    assert target_for(date(2015, 6, 1)) == 4.5
    assert target_for(date(2019, 6, 1)) == 4.25
    assert target_for(date(2024, 6, 1)) == 3.0
    assert target_for(date(2026, 6, 1)) == 3.0


def test_12m_identity(obs):
    s = monthly_inflation_series(obs)
    month = pd.Period("2019-12", "M")
    window = pd.period_range(month - 11, month, freq="M")
    direct = realized(obs, "ipca_12m", date(2019, 12, 31))
    assert direct == pytest.approx(compound(s.loc[window]), rel=1e-10)


def test_12m_from_path(obs):
    s = monthly_inflation_series(obs)
    assert inflation_12m_from_path(s, pd.Period("2019-12", "M")) == pytest.approx(
        realized(obs, "ipca_12m", date(2019, 12, 31)), rel=1e-10
    )


def test_ref_dates():
    assert ref_date_for("ipca_12m", date(2019, 1, 31), 6) == date(2019, 7, 31)
    assert ref_date_for("gdp_qq", date(2019, 1, 31), 4) == date(2020, 3, 31)
