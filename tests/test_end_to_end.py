from datetime import date

import numpy as np

from econ.backtest import run_backtest
from econ.checks import run_checks
from econ.diagnostics import fit_diagnostics, forecast_sanity
from econ.evaluate import evaluate
from econ.models.new_keynesian import NewKeynesian
from econ.vintage import Panel


def test_end_to_end_validation(obs):
    ctx, fc = run_backtest(
        ["random_walk", "new_keynesian"],
        date(2019, 1, 1),
        date(2019, 12, 31),
        save=False,
        model_kwargs={"new_keynesian": {"variant": "R3"}},
    )
    metrics = evaluate(fc, obs)
    nk = metrics[metrics["model_id"] == "new_keynesian"]
    assert len(fc) == 300
    assert max(fc["ref_date"]) <= date(2019, 12, 31)
    assert set(nk["target"]) == {"ipca_m", "ipca_12m", "gdp_qq", "selic"}
    assert nk["theil_u"].dropna().max() < 3.0
    assert nk[nk["primary"]]["n"].min() >= 5


def test_diagnostics_and_sanity(obs):
    panel = Panel.build(date(2019, 12, 31), obs)
    diag = fit_diagnostics(panel, "R3")
    assert diag["leak_ok"] is True
    assert all(np.isfinite(v) for v in diag["params"]["nkpc"].values())
    rows = NewKeynesian(variant="R3").forecast(panel)
    sanity = forecast_sanity(rows)
    assert all(v["in_range"] for v in sanity.values())


def test_phase_checks_structure():
    checks = run_checks()
    assert len(checks) >= 6
    names = {c["check"] for c in checks}
    assert "release-date leak test" in names
    assert "Focus benchmark for IPCA and Selic" in names
