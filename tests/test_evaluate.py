from datetime import date

import numpy as np
import pandas as pd
import pytest

from econ.evaluate import dm_test, evaluate, mz_test
from econ.backtest import run_backtest


def test_dm_detects_worse_model():
    rng = np.random.default_rng(0)
    err_rw = rng.normal(0, 1, 120)
    err_model = 1.5 * err_rw
    stat, p = dm_test(err_model, err_rw, 1)
    assert stat > 0
    assert p < 0.10


def test_mz_perfect_calibration():
    rng = np.random.default_rng(1)
    fc = rng.normal(0, 1, 200)
    y = 2.0 * fc + 1.0 + rng.normal(0, 0.01, 200)
    out = mz_test(y, fc, 1)
    assert out["mz_slope"] == pytest.approx(2.0, abs=0.02)
    assert out["mz_slope_p"] < 0.01


def test_mz_constant_forecast_is_undefined():
    out = mz_test(np.arange(10.0), np.ones(10), 1)
    assert np.isnan(out["mz_slope"])


def test_random_walk_theil_is_one(obs):
    _, fc = run_backtest(
        ["random_walk"], date(2019, 1, 1), date(2019, 12, 31), save=False
    )
    metrics = evaluate(fc, obs)
    rw = metrics[metrics["model_id"] == "random_walk"]
    assert np.allclose(rw["theil_u"].dropna().to_numpy(), 1.0, atol=1e-6)
    assert (rw["rank"] >= 1).all()


def test_evaluate_all_targets(obs):
    _, fc = run_backtest(
        ["random_walk", "ar"], date(2019, 1, 1), date(2019, 12, 31), save=False
    )
    metrics = evaluate(fc, obs)
    assert set(metrics["target"]) == {"ipca_m", "ipca_12m", "gdp_qq", "selic"}
    assert metrics[metrics["primary"]]["n"].min() >= 5
    assert metrics["n"].max() <= 12
