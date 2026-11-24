from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import requests

from .config import SeriesSpec

SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
SIDRA_URL = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/{aggregate}/periodos/"
    "{periods}/variaveis/{variable}"
)
FOCUS_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/{endpoint}"
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "econ-model-hub/0.1 (research)"})


def _get(url: str, params: dict[str, Any], attempts: int = 4) -> requests.Response:
    last: Exception | None = None
    for i in range(attempts):
        try:
            r = SESSION.get(url, params=params, timeout=90)
            if r.status_code == 200:
                return r
            last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"request failed: {url} {params}: {last}")


def _br_date(s: str) -> date:
    return datetime.strptime(s, "%d/%m/%Y").date()


def _windows(start: date, end: date, years: int):
    cur = start
    while cur <= end:
        try:
            stop = date(cur.year + years, cur.month, cur.day) - timedelta(days=1)
        except ValueError:
            stop = date(cur.year + years, cur.month, 28)
        yield cur, min(stop, end)
        cur = stop + timedelta(days=1)


def fetch_sgs(spec: SeriesSpec, end: date) -> pd.DataFrame:
    span = 9 if spec.freq == "D" else 20
    rows = []
    for lo, hi in _windows(date.fromisoformat(spec.start), end, span):
        params = {
            "formato": "json",
            "dataInicial": lo.strftime("%d/%m/%Y"),
            "dataFinal": hi.strftime("%d/%m/%Y"),
        }
        payload = _get(SGS_URL.format(code=spec.code), params).json()
        for item in payload:
            raw = item.get("valor", "").strip()
            if raw in {"", "...", "..", "-"}:
                continue
            rows.append({"ref_date": _br_date(item["data"]), "value": float(raw)})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["ref_date"], keep="last")
    return df


def _sidra_period(d: date, freq: str = "M") -> str:
    if freq == "Q":
        quarter = (d.month - 1) // 3 + 1
        return f"{d.year:04d}{quarter:02d}"
    return f"{d.year:04d}{d.month:02d}"


def _sidra_ref_date(period: str, freq: str) -> date:
    year = int(period[:4])
    code = int(period[4:6])
    if freq == "Q":
        month = (code - 1) * 3 + 1
    else:
        month = code
    return date(year, month, 1)


def _sidra_fim(aggregate: int) -> str | None:
    try:
        r = _get(
            f"https://servicodados.ibge.gov.br/api/v3/agregados/{aggregate}/metadados",
            {},
        )
        return str(r.json()["periodicidade"]["fim"])
    except Exception:  # noqa: BLE001
        return None


def fetch_sidra(spec: SeriesSpec, end: date) -> pd.DataFrame:
    params = {
        "localidades": "N1[all]",
        "classificacao": spec.classification,
    }
    fim = _sidra_fim(spec.aggregate)
    end_period = _sidra_period(end, spec.freq)
    if fim and end_period > fim:
        end_period = fim
    url = SIDRA_URL.format(
        aggregate=spec.aggregate,
        variable=spec.variable,
        periods=(
            f"{_sidra_period(date.fromisoformat(spec.start), spec.freq)}-"
            f"{end_period}"
        ),
    )
    payload = _get(url, params).json()
    rows = []
    for var in payload:
        for res in var.get("resultados", []):
            for series in res.get("series", []):
                for period, raw in series.get("serie", {}).items():
                    raw = str(raw).strip()
                    if raw in {"", "...", "..", "-", "X"}:
                        continue
                    rows.append(
                        {
                            "ref_date": _sidra_ref_date(period, spec.freq),
                            "value": float(raw.replace(",", ".")),
                        }
                    )
    return pd.DataFrame(rows)


def fetch_focus(spec: SeriesSpec, end: date) -> pd.DataFrame:
    from urllib.parse import quote

    rows: list[dict[str, Any]] = []
    skip = 0
    page = 5000
    while True:
        query = "&".join(
            [
                "$filter=" + quote(spec.filter, safe="'()"),
                "$orderby=Data%20asc",
                f"$top={page}",
                f"$skip={skip}",
                "$format=json",
            ]
        )
        url = FOCUS_URL.format(endpoint=spec.endpoint) + "?" + query
        payload = _get(url, {}).json()
        batch = payload.get("value", [])
        if not batch:
            break
        for item in batch:
            raw = item.get("Mediana")
            if raw is None:
                continue
            ref = pd.Timestamp(item["Data"]).date()
            if ref > end:
                continue
            rows.append(
                {
                    "ref_date": ref,
                    "value": float(raw),
                    "extra": str(item.get("DataReferencia", "") or ""),
                }
            )
        if len(batch) < page:
            break
        skip += page
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["ref_date", "extra"], keep="last")
    return df


def fetch(spec: SeriesSpec, end: date) -> pd.DataFrame:
    if spec.source == "sgs":
        return fetch_sgs(spec, end)
    if spec.source == "sidra":
        return fetch_sidra(spec, end)
    if spec.source in {"focus", "focus_annual"}:
        return fetch_focus(spec, end)
    raise ValueError(f"unknown source {spec.source}")


def dump_raw(spec: SeriesSpec, df: pd.DataFrame, path) -> None:
    path.write_text(
        json.dumps(
            {
                "series_id": spec.series_id,
                "source": spec.source,
                "rows": df.to_dict(orient="records"),
            },
            default=str,
            indent=1,
        )
    )
