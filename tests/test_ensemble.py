from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from econ.ensemble import build_ensembles, disagreement, latest_per_model


def _frame():
    rows = []
    for model, point, anchor in [
        ("new_keynesian", 4.0, 3.5),
        ("monetarist", 6.0, 3.5),
    ]:
        rows.append(
            {
                "model_id": model,
                "school": model,
                "target": "ipca_12m",
                "horizon": 12,
                "origin_date": date(2019, 12, 31),
                "ref_date": date(2020, 12, 31),
                "point": point,
                "anchor": anchor,
                "notes": "",
            }
        )
    return pd.DataFrame(rows)


def test_latest_per_model_keeps_latest_run():
    df = _frame()
    df["run_id"] = ["a", "a"]
    df["produced_at"] = ["2026-01-01T00:00:00", "2026-01-01T00:00:00"]
    extra = df.copy()
    extra["run_id"] = "b"
    extra["produced_at"] = "2026-02-01T00:00:00"
    extra["point"] = [5.0, 7.0]
    out = latest_per_model(pd.concat([df, extra], ignore_index=True))
    assert set(out["run_id"]) == {"b"}
    assert out["point"].tolist() == [5.0, 7.0]


def test_equal_ensemble_is_the_mean():
    ens = build_ensembles(_frame(), {})
    row = ens[
        (ens["model_id"] == "ensemble_school_equal")
        & (ens["target"] == "ipca_12m")
        & (ens["horizon"] == 12)
    ].iloc[0]
    assert row["point"] == 5.0
    assert row["anchor"] == 3.5
    assert row["n_models"] == 2


def test_disagreement_uses_school_dispersion():
    dis = disagreement(_frame())
    row = dis.iloc[0]
    assert row["n_schools"] == 2
    assert row["mean"] == 5.0
    assert np.isclose(row["std"], np.sqrt(2.0))
