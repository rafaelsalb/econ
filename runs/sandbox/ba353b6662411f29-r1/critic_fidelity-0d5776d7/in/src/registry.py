from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import config
from .utils import code_hash as compute_code_hash
from .utils import json_default, sha256_file, sha256_obj

FORECAST_COLUMNS = [
    "model_id",
    "school",
    "target",
    "horizon",
    "origin_date",
    "ref_date",
    "vintage_date",
    "point",
    "anchor",
    "spec_hash",
    "code_hash",
    "seed",
    "run_id",
    "produced_at",
    "notes",
    "q05",
    "q10",
    "q25",
    "q50",
    "q75",
    "q90",
    "q95",
]


def data_hash() -> str:
    path = config.CURATED / "manifest.json"
    if path.exists():
        return json.loads(path.read_text())["sha256"]
    return sha256_file(config.OBSERVATIONS) if config.OBSERVATIONS.exists() else ""


def spec_hash(model_id: str) -> str:
    path = config.SPECS / f"{model_id}.yaml"
    if path.exists():
        return sha256_file(path)
    return ""


@dataclass
class RunContext:
    run_id: str
    models: list[str]
    config: dict[str, Any]
    seed: int
    data_hash: str
    code_hash: str
    spec_hashes: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @classmethod
    def create(
        cls,
        models: list[str],
        config_dict: dict[str, Any],
        seed: int = 7,
    ) -> "RunContext":
        payload = {
            "models": sorted(models),
            "config": config_dict,
            "seed": seed,
            "data_hash": data_hash(),
            "code_hash": compute_code_hash(config.ROOT),
            "specs": {m: spec_hash(m) for m in sorted(models)},
        }
        return cls(
            run_id=sha256_obj(payload)[:16],
            models=sorted(models),
            config=config_dict,
            seed=seed,
            data_hash=payload["data_hash"],
            code_hash=payload["code_hash"],
            spec_hashes=payload["specs"],
        )

    @property
    def directory(self) -> Path:
        return config.REGISTRY / "forecasts" / f"run_id={self.run_id}"

    def exists(self) -> bool:
        return (self.directory / "part.parquet").exists()

    def manifest(self, n_rows: int, failures: list[dict]) -> dict:
        return {
            "run_id": self.run_id,
            "models": self.models,
            "config": self.config,
            "seed": self.seed,
            "data_hash": self.data_hash,
            "code_hash": self.code_hash,
            "spec_hashes": self.spec_hashes,
            "created_at": self.created_at,
            "n_forecasts": n_rows,
            "failures": failures,
        }


def append_run(ctx: RunContext, rows: list[dict], failures: list[dict]) -> Path:
    if not rows:
        raise ValueError("no forecast rows to write")
    df = pd.DataFrame(rows)
    for col in FORECAST_COLUMNS:
        if col not in df:
            df[col] = None
    df = df[FORECAST_COLUMNS]
    ctx.directory.mkdir(parents=True, exist_ok=True)
    target = ctx.directory / "part.parquet"
    df.to_parquet(target, index=False)

    manifest = ctx.manifest(len(df), failures)
    run_dir = config.RUNS / ctx.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=json_default)
    )
    ledger = config.REGISTRY / "runs.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as fh:
        fh.write(json.dumps(manifest, default=json_default) + "\n")
    return target


def read_forecasts() -> pd.DataFrame:
    path = config.REGISTRY / "forecasts"
    if not path.exists():
        return pd.DataFrame(columns=FORECAST_COLUMNS)
    files = sorted(path.glob("run_id=*/part.parquet"))
    if not files:
        return pd.DataFrame(columns=FORECAST_COLUMNS)
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    if df.empty:
        return df
    df["origin_date"] = pd.to_datetime(df["origin_date"]).dt.date
    df["ref_date"] = pd.to_datetime(df["ref_date"]).dt.date
    return df


def read_manifest(run_id: str) -> dict:
    path = config.RUNS / run_id / "manifest.json"
    return json.loads(path.read_text())
