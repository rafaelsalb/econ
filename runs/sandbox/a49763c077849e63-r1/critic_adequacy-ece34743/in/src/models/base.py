from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd

from ..vintage import Panel


@dataclass
class Forecast:
    target: str
    horizon: int
    ref_date: date
    point: float
    anchor: float | None = None
    notes: str = ""


class Model(Protocol):
    model_id: str
    school: str

    def forecast(self, panel: Panel) -> list[Forecast]: ...


def _finite(value: float | None) -> bool:
    return value is not None and pd.notna(value) and abs(float(value)) < 1e6


def validate_rows(rows: list[Forecast], model_id: str) -> list[Forecast]:
    if not rows:
        raise ValueError(f"{model_id}: produced no forecasts")
    out = []
    for row in rows:
        if not _finite(row.point):
            raise ValueError(f"{model_id}: non-finite forecast {row}")
        out.append(row)
    return out
