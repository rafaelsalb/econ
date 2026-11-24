from __future__ import annotations

import hashlib
import json
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_obj(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()


def code_hash(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted((root / "src").rglob("*.py")):
        h.update(path.relative_to(root).as_posix().encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def month_end(d: date) -> date:
    return date(d.year, d.month, monthrange(d.year, d.month)[1])


def quarter_end(d: date) -> date:
    q = (d.month - 1) // 3
    month = q * 3 + 3
    return month_end(date(d.year, month, 1))


def quarter_start(d: date) -> date:
    month = ((d.month - 1) // 3) * 3 + 1
    return date(d.year, month, 1)


def last_weekday(d: date) -> date:
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def monthly_origins(start: date, end: date) -> list[date]:
    origins = []
    cur = date(start.year, start.month, 1)
    while cur <= end:
        origins.append(last_weekday(month_end(cur)))
        cur = (pd.Timestamp(cur) + pd.offsets.MonthBegin(1)).date()
    return [o for o in origins if start <= o <= end]


def json_default(value: Any) -> Any:
    if isinstance(value, (date, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"not serializable: {type(value)}")
