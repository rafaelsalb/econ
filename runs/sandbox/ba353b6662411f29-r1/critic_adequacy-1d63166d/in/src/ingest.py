from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from . import config
from .config import load_catalog
from .sources import dump_raw, fetch
from .utils import month_end, quarter_end, sha256_file


def _period_end(ref: date, freq: str) -> date:
    if freq == "M":
        return month_end(ref)
    if freq == "Q":
        return quarter_end(ref)
    return ref


def build() -> pd.DataFrame:
    specs = load_catalog()
    today = date.today()
    config.RAW.mkdir(parents=True, exist_ok=True)
    frames = []
    for sid, spec in specs.items():
        print(f"fetching {sid} ({spec.source})")
        df = fetch(spec, today)
        if df.empty:
            raise RuntimeError(f"{sid}: no observations returned")
        df["series_id"] = sid
        df["source"] = spec.source
        df["unit"] = spec.unit
        df["freq"] = spec.freq
        df["sa_flag"] = False
        df["vintage_date"] = today
        df["period_end"] = df["ref_date"].map(lambda d: _period_end(d, spec.freq))
        df["release_date"] = df["period_end"].map(
            lambda d: d + timedelta(days=spec.release_lag_days)
        )
        if "extra" not in df:
            df["extra"] = ""
        df["extra"] = df["extra"].fillna("")
        dump_raw(spec, df, config.RAW / f"{sid}.json")
        frames.append(df)

    obs = pd.concat(frames, ignore_index=True)
    obs = obs.sort_values(["series_id", "ref_date", "extra"]).reset_index(drop=True)
    dup = obs.duplicated(subset=["series_id", "ref_date", "extra"]).sum()
    if dup:
        raise RuntimeError(f"duplicate observations: {dup}")
    obs = obs[
        [
            "series_id",
            "ref_date",
            "period_end",
            "release_date",
            "vintage_date",
            "value",
            "source",
            "unit",
            "freq",
            "sa_flag",
            "extra",
        ]
    ]
    config.CURATED.mkdir(parents=True, exist_ok=True)
    obs.to_parquet(config.OBSERVATIONS, index=False)
    print(f"wrote {config.OBSERVATIONS} ({len(obs)} rows)")
    return obs


def write_manifest(obs: pd.DataFrame) -> dict:
    manifest = {
        "file": str(config.OBSERVATIONS.name),
        "sha256": sha256_file(config.OBSERVATIONS),
        "rows": int(len(obs)),
        "series": {},
    }
    for sid, g in obs.groupby("series_id"):
        manifest["series"][sid] = {
            "rows": int(len(g)),
            "min_ref": str(g["ref_date"].min()),
            "max_ref": str(g["ref_date"].max()),
            "vintages": sorted({str(v) for v in g["vintage_date"].unique()}),
            "source": str(g["source"].iloc[0]),
        }
    config.CURATED.mkdir(parents=True, exist_ok=True)
    path = config.CURATED / "manifest.json"
    import json

    path.write_text(json.dumps(manifest, indent=2))
    return manifest


def load_observations(path: Path | None = None) -> pd.DataFrame:
    path = path or config.OBSERVATIONS
    df = pd.read_parquet(path)
    for col in ("ref_date", "period_end", "release_date", "vintage_date"):
        df[col] = pd.to_datetime(df[col]).dt.date
    return df


def main() -> None:
    obs = build()
    manifest = write_manifest(obs)
    print(f"data hash: {manifest['sha256']}")


if __name__ == "__main__":
    main()
