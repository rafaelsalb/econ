from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

import numpy as np
import pandas as pd

from . import config
from .ingest import load_observations
from .models.base import Model
from .models.benchmarks import MODELS as BENCHMARK_MODELS
from .registry import RunContext, append_run, read_forecasts, spec_hash
from .utils import monthly_origins
from .vintage import Panel

QUANTILES = ["q05", "q10", "q25", "q50", "q75", "q90", "q95"]


def model_registry() -> dict[str, type[Model]]:
    from .models.new_keynesian import NewKeynesian

    reg = dict(BENCHMARK_MODELS)
    reg["new_keynesian"] = NewKeynesian
    return reg


def run_backtest(
    models: Iterable[str],
    start: date,
    end: date,
    seed: int = 7,
    force: bool = False,
    save: bool = True,
    model_kwargs: dict[str, dict] | None = None,
    embargo_until: date | None = None,
) -> tuple[RunContext, pd.DataFrame]:
    reg = model_registry()
    model_ids = list(models)
    model_kwargs = model_kwargs or {}
    if embargo_until is None:
        embargo_until = end
    unknown = [m for m in model_ids if m not in reg]
    if unknown:
        raise ValueError(f"unknown models: {unknown}")

    config_dict = {
        "start": str(start),
        "end": str(end),
        "embargo_until": str(embargo_until),
        "models": model_ids,
        "model_kwargs": model_kwargs,
        "estimation_start": config.ESTIMATION_START,
    }
    ctx = RunContext.create(model_ids, config_dict, seed=seed)
    if save and ctx.exists() and not force:
        df = pd.read_parquet(ctx.directory / "part.parquet")
        return ctx, df

    obs = load_observations()
    origins = monthly_origins(start, end)
    if len(origins) < 12:
        raise ValueError("backtest needs at least 12 origins")

    instances = {m: reg[m](**model_kwargs.get(m, {})) for m in model_ids}
    rows: list[dict] = []
    failures: list[dict] = []
    np.random.seed(seed)
    produced_at = datetime.now().isoformat(timespec="seconds")

    for i, origin in enumerate(origins):
        panel = Panel.build(origin, obs)
        vintage = max(panel.obs["vintage_date"]) if not panel.obs.empty else None
        for model_id, model in instances.items():
            try:
                fcs = model.forecast(panel)
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {"model": model_id, "origin": str(origin), "error": f"{type(exc).__name__}: {exc}"}
                )
                continue
            for f in fcs:
                if f.ref_date > embargo_until:
                    continue
                row = {
                    "model_id": model_id,
                    "school": getattr(model, "school", "unknown"),
                    "target": f.target,
                    "horizon": int(f.horizon),
                    "origin_date": origin,
                    "ref_date": f.ref_date,
                    "vintage_date": vintage,
                    "point": float(f.point),
                    "anchor": None if f.anchor is None else float(f.anchor),
                    "spec_hash": ctx.spec_hashes.get(model_id, ""),
                    "code_hash": ctx.code_hash,
                    "seed": seed,
                    "run_id": ctx.run_id,
                    "produced_at": produced_at,
                    "notes": f.notes,
                }
                for q in QUANTILES:
                    row[q] = None
                rows.append(row)
        if (i + 1) % 24 == 0:
            print(f"  {i + 1}/{len(origins)} origins, {len(rows)} rows, {len(failures)} failures")

    if not rows:
        raise RuntimeError(f"no forecasts produced; failures={failures[:3]}")

    df = pd.DataFrame(rows)
    if save:
        append_run(ctx, rows, failures)
        run_dir = config.RUNS / ctx.run_id
        (run_dir / "failures.json").write_text(
            pd.DataFrame(failures).to_json(orient="records", indent=2)
            if failures
            else "[]"
        )
        print(f"run {ctx.run_id}: {len(df)} forecasts, {len(failures)} failures")
    return ctx, df


def latest_run_forecasts() -> pd.DataFrame:
    df = read_forecasts()
    if df.empty:
        raise RuntimeError("registry is empty; run a backtest first")
    return df[df["run_id"] == df["run_id"].iloc[-1]]
