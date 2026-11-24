from datetime import date

import numpy as np
import pandas as pd
import pytest

from econ.models.benchmarks import (
    ARBenchmark,
    BVARBenchmark,
    FocusConsensus,
    IBCBridge,
    RandomWalk,
    SeasonalNaive,
)
from econ.models.common import MinnesotaBVAR
from econ.models.new_keynesian import NewKeynesian
from econ.vintage import Panel


@pytest.fixture(scope="module")
def panel(obs):
    return Panel.build(date(2019, 1, 31), obs)


@pytest.mark.parametrize(
    "cls",
    [RandomWalk, SeasonalNaive, ARBenchmark, BVARBenchmark, FocusConsensus],
)
def test_benchmarks_finite(panel, cls):
    rows = cls().forecast(panel)
    assert len(rows) >= 20
    assert all(np.isfinite(r.point) for r in rows)
    assert {r.target for r in rows} == {"ipca_m", "ipca_12m", "gdp_qq", "selic"}


def test_bridge_finite(panel):
    rows = IBCBridge().forecast(panel)
    assert len(rows) == 5
    assert all(np.isfinite(r.point) for r in rows)


@pytest.mark.parametrize("variant", ["R1", "R2", "R3"])
def test_nk_variants_finite(panel, variant):
    rows = NewKeynesian(variant=variant).forecast(panel)
    assert len(rows) == 25
    assert all(np.isfinite(r.point) for r in rows)


def test_r2_changes_gdp_only(panel):
    r1 = NewKeynesian(variant="R1").forecast(panel)
    r2 = NewKeynesian(variant="R2").forecast(panel)
    g1 = [r.point for r in r1 if r.target == "gdp_qq"]
    g2 = [r.point for r in r2 if r.target == "gdp_qq"]
    p1 = [r.point for r in r1 if r.target == "ipca_12m"]
    p2 = [r.point for r in r2 if r.target == "ipca_12m"]
    assert g1 != g2
    assert p1 == pytest.approx(p2)


def test_r3_tstat_keys(panel):
    from econ.models.new_keynesian import estimate

    fit = estimate(panel, variant="R3")
    assert "pi_gap" in fit.taylor_params.index
    assert "pi_gap" in fit.taylor_tstats.index


def test_12m_derived_from_monthly(panel):
    rows = NewKeynesian(variant="R3").forecast(panel)
    monthly = {r.horizon: r.point for r in rows if r.target == "ipca_m"}
    known = panel.monthly("ipca_m")
    m0 = pd.Period(panel.origin, "M")
    for h in [3, 6, 12]:
        path = {}
        for j in range(0, 13):
            path[m0 + j] = monthly[j]
        for back in range(1, 12):
            path[m0 - back] = float(known.loc[m0 - back])
        window = pd.period_range(m0 + h - 11, m0 + h, freq="M")
        expected = (np.prod([1 + path[p] / 100 for p in window]) - 1) * 100
        got = [r.point for r in rows if r.target == "ipca_12m" and r.horizon == h][0]
        assert got == pytest.approx(expected, rel=1e-9)


def test_bvar_stable_on_synthetic():
    rng = np.random.default_rng(3)
    n = 240
    y = np.zeros((n, 2))
    for t in range(1, n):
        y[t, 0] = 0.5 * y[t - 1, 0] + rng.normal(0, 1)
        y[t, 1] = 0.3 * y[t - 1, 0] + 0.4 * y[t - 1, 1] + rng.normal(0, 1)
    model = MinnesotaBVAR(p=2).fit(y)
    fc = model.forecast(8)
    assert fc.shape == (8, 2)
    assert np.isfinite(fc).all()
    assert model._stable(model.B)
