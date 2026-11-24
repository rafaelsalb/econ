from datetime import date

from econ.backtest import run_backtest
from econ.registry import RunContext, read_forecasts


def test_run_id_deterministic():
    cfg = {"start": "2010-01-01", "end": "2019-12-31", "models": ["random_walk"]}
    a = RunContext.create(["random_walk"], cfg, seed=7)
    b = RunContext.create(["random_walk"], cfg, seed=7)
    assert a.run_id == b.run_id
    assert a.data_hash == b.data_hash
    assert a.code_hash == b.code_hash


def test_run_id_changes_with_config():
    a = RunContext.create(["random_walk"], {"start": "2010-01-01", "end": "2019-12-31"}, 7)
    b = RunContext.create(["random_walk"], {"start": "2010-01-01", "end": "2019-12-31"}, 8)
    assert a.run_id != b.run_id


def test_forecast_schema():
    ctx, df = run_backtest(
        ["random_walk", "ar"], date(2019, 1, 1), date(2019, 12, 31), save=False
    )
    assert len(df) > 0
    assert df["run_id"].nunique() == 1
    assert df["run_id"].iloc[0] == ctx.run_id
    assert set(df["target"]) == {"ipca_m", "ipca_12m", "gdp_qq", "selic"}
    assert df["point"].map(lambda v: abs(v) < 1e6).all()


def test_registry_read_is_not_empty():
    df = read_forecasts()
    assert not df.empty
    assert "run_id" in df.columns
