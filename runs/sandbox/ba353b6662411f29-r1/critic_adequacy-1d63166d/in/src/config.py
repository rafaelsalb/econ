from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
CURATED = DATA / "curated"
SPECS = ROOT / "specs"
REGISTRY = ROOT / "registry"
RUNS = ROOT / "runs"
EVAL = ROOT / "eval"
REPORTS = ROOT / "reports"

OBSERVATIONS = CURATED / "observations.parquet"
CATALOG = ROOT / "catalog.yaml"

# Backtest configuration (frozen for v1).
ESTIMATION_START = "2000-01-01"
NK_ESTIMATION_START = "2005-01-01"
VALIDATION_START = "2010-01-01"
VALIDATION_END = "2019-12-31"
LOCKBOX_START = "2020-01-01"
LOCKBOX_END = "2026-10-31"

# Event windows used by the episode scorecard.
EPISODES = {
    "recession_2015_16": ("2015-01-01", "2016-12-31"),
    "truckers_2018": ("2018-05-01", "2018-08-31"),
    "covid_2020_21": ("2020-01-01", "2021-12-31"),
    "inflation_2021_22": ("2021-01-01", "2022-12-31"),
    "disinflation_2023_24": ("2023-01-01", "2024-12-31"),
}


@dataclass(frozen=True)
class SeriesSpec:
    series_id: str
    description: str
    source: str
    freq: str
    unit: str
    start: str
    release_lag_days: int
    role: tuple[str, ...] = ()
    code: int | None = None
    aggregate: int | None = None
    variable: int | None = None
    classification: str | None = None
    endpoint: str | None = None
    filter: str | None = None


def load_catalog(path: Path | None = None) -> dict[str, SeriesSpec]:
    path = path or CATALOG
    raw = yaml.safe_load(path.read_text())
    out: dict[str, SeriesSpec] = {}
    for sid, item in raw["series"].items():
        out[sid] = SeriesSpec(
            series_id=sid,
            description=item.get("description", ""),
            source=item["source"],
            freq=item["freq"],
            unit=item.get("unit", ""),
            start=str(item.get("start", "1994-01-01")),
            release_lag_days=int(item.get("release_lag_days", 0)),
            role=tuple(item.get("role", [])),
            code=item.get("code"),
            aggregate=item.get("aggregate"),
            variable=item.get("variable"),
            classification=item.get("classification"),
            endpoint=item.get("endpoint"),
            filter=item.get("filter"),
        )
    return out
