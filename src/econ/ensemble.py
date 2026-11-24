from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config
from .evaluate import attach_realized, evaluate
from .ingest import load_observations
from .registry import read_forecasts

SCHOOLS = ["new_keynesian", "monetarist", "fiscal_ftpl", "pk_sfc"]
BENCHMARKS = [
    "random_walk",
    "seasonal_naive",
    "ar",
    "bvar",
    "ibc_bridge",
    "focus_consensus",
]
ALL_MODELS = SCHOOLS + BENCHMARKS
ENSEMBLE_IDS = [
    "ensemble_school_equal",
    "ensemble_school_perf",
    "ensemble_combined_equal",
    "ensemble_combined_perf",
]
OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]


def latest_per_model(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    meta = df[["model_id", "run_id", "produced_at"]].drop_duplicates().copy()
    meta["produced_at"] = pd.to_datetime(meta["produced_at"])
    idx = meta.groupby("model_id")["produced_at"].idxmax()
    pairs = meta.loc[idx, ["model_id", "run_id"]]
    return df.merge(pairs, on=["model_id", "run_id"], how="inner").reset_index(drop=True)


def compute_weights(
    forecasts: pd.DataFrame,
    obs: pd.DataFrame,
    validation_end: date = date.fromisoformat(config.VALIDATION_END),
) -> dict:
    ev = evaluate(forecasts, obs, validation_end=validation_end)
    out: dict[str, dict[str, float]] = {}
    for prefix, ids in [("school", SCHOOLS), ("combined", ALL_MODELS)]:
        sub = ev[ev["model_id"].isin(ids)]
        for (target, horizon), g in sub.groupby(["target", "horizon"]):
            rmse = g.set_index("model_id")["rmse"].dropna()
            if rmse.empty:
                continue
            w = 1.0 / np.maximum(rmse.to_numpy(), 0.1) ** 2
            w = w / w.sum()
            out[f"{prefix}:{target}:{int(horizon)}"] = {
                model: float(weight) for model, weight in zip(rmse.index, w)
            }
    return out


def build_ensembles(forecasts: pd.DataFrame, weights: dict) -> pd.DataFrame:
    rows = []
    for (target, horizon, origin), g in forecasts.groupby(
        ["target", "horizon", "origin_date"]
    ):
        for prefix, ids in [("school", SCHOOLS), ("combined", ALL_MODELS)]:
            sub = g[g["model_id"].isin(ids)].dropna(subset=["point"])
            if sub.empty:
                continue
            for weighting in ["equal", "perf"]:
                if weighting == "equal":
                    w = np.ones(len(sub))
                else:
                    wmap = weights.get(f"{prefix}:{target}:{int(horizon)}", {})
                    w = np.array([wmap.get(m, 0.0) for m in sub["model_id"]])
                    if w.sum() <= 0:
                        w = np.ones(len(sub))
                w = w / w.sum()
                anchors = sub["anchor"].fillna(0).to_numpy()
                rows.append(
                    {
                        "model_id": f"ensemble_{prefix}_{weighting}",
                        "school": "ensemble",
                        "target": target,
                        "horizon": int(horizon),
                        "origin_date": origin,
                        "ref_date": sub["ref_date"].iloc[0],
                        "point": float(np.average(sub["point"], weights=w)),
                        "anchor": float(np.average(anchors, weights=w)),
                        "notes": f"{prefix}_{weighting}",
                        "n_models": int(len(sub)),
                    }
                )
    return pd.DataFrame(rows)


def disagreement(forecasts: pd.DataFrame) -> pd.DataFrame:
    school = forecasts[forecasts["model_id"].isin(SCHOOLS)]
    out = []
    for (target, horizon, origin), g in school.groupby(
        ["target", "horizon", "origin_date"]
    ):
        vals = g["point"].dropna().to_numpy()
        if len(vals) < 2:
            continue
        out.append(
            {
                "target": target,
                "horizon": int(horizon),
                "origin_date": origin,
                "n_schools": int(len(vals)),
                "mean": float(np.mean(vals)),
                "std": float(np.std(vals, ddof=1)),
                "iqr": float(np.quantile(vals, 0.75) - np.quantile(vals, 0.25)),
            }
        )
    return pd.DataFrame(out)


def _fan_chart(forecasts: pd.DataFrame, ensembles: pd.DataFrame, path: Path) -> None:
    specs = [
        ("ipca_12m", 12, "IPCA 12m, h=12 (%)", 0),
        ("gdp_qq", 4, "GDP q/q, h=4 (%)", 1),
        ("selic", 12, "Selic, h=12 (%)", 2),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for target, horizon, title, idx in specs:
        ax = axes[idx]
        cell = ensembles[
            (ensembles["target"] == target) & (ensembles["horizon"] == horizon)
        ]
        if cell.empty:
            ax.set_title(title, fontsize=10)
            continue
        origin = max(cell["origin_date"])
        sub = forecasts[
            forecasts["model_id"].isin(SCHOOLS)
            & (forecasts["target"] == target)
            & (forecasts["horizon"] == horizon)
            & (forecasts["origin_date"] == origin)
        ]
        for i, (model, row) in enumerate(sub.groupby("model_id")):
            ax.scatter(
                [0], [row["point"].iloc[0]], s=55, color=OKABE_ITO[i], label=model, zorder=3
            )
        vals = sub["point"].to_numpy()
        if len(vals) >= 2:
            mean, sd = float(np.mean(vals)), float(np.std(vals, ddof=1))
            ax.fill_between(
                [-0.35, 0.35], [mean - sd, mean - sd], [mean + sd, mean + sd],
                color="#999999", alpha=0.18, zorder=1, label="school ±1 sd",
            )
            ax.hlines(mean, -0.35, 0.35, color="#333333", lw=1.5, zorder=2, label="school mean")
        ens = ensembles[
            (ensembles["target"] == target)
            & (ensembles["horizon"] == horizon)
            & (ensembles["origin_date"] == origin)
            & (ensembles["model_id"].isin(["ensemble_school_equal", "ensemble_combined_equal"]))
        ]
        for j, (model, row) in enumerate(ens.groupby("model_id")):
            ax.scatter([0.55 + 0.12 * j], [row["point"].iloc[0]], marker="D", s=45,
                       color="#000000", zorder=4, label=model)
        ax.set_xlim(-0.6, 0.95)
        ax.set_xticks([])
        ax.set_title(f"{title}\norigin {origin}", fontsize=9)
        ax.grid(axis="y", alpha=0.25, lw=0.5)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8, frameon=False)
    fig.suptitle(f"Fan of schools — validation origin {origin}", fontsize=12)
    fig.tight_layout(rect=(0, 0.10, 1, 0.94))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def build_ensembles_and_report(
    validation_end: date = date.fromisoformat(config.VALIDATION_END),
    write: bool = True,
) -> dict:
    obs = load_observations()
    raw = read_forecasts()
    latest = latest_per_model(raw)
    latest = latest[pd.to_datetime(latest["ref_date"]).dt.date <= validation_end]
    weights = compute_weights(latest, obs, validation_end=validation_end)
    ens = build_ensembles(latest, weights)
    if ens.empty:
        raise RuntimeError("no ensemble forecasts produced")

    rw_focus = latest[latest["model_id"].isin(["random_walk", "focus_consensus"])]
    eval_fc = pd.concat([ens, rw_focus], ignore_index=True)
    ev = evaluate(eval_fc, obs, validation_end=validation_end)
    ens_ev = ev[ev["model_id"].isin(ENSEMBLE_IDS)].copy()
    dis = disagreement(latest)

    if write:
        config.EVAL.mkdir(parents=True, exist_ok=True)
        config.REPORTS.mkdir(parents=True, exist_ok=True)
        ens.to_parquet(config.EVAL / "ensemble_forecasts.parquet", index=False)
        ens_ev.to_csv(config.EVAL / "ensemble_scoreboard.csv", index=False)
        dis.to_csv(config.REPORTS / "disagreement.csv", index=False)
        (config.EVAL / "ensemble_weights.json").write_text(
            json.dumps(
                {
                    "validation_end": str(validation_end),
                    "weights": weights,
                },
                indent=2,
            )
        )
        _fan_chart(latest, ens, config.REPORTS / "fan_chart.png")

        lines = [
            "# Ensemble and disagreement — validation window",
            "",
            f"Validation end: {validation_end}. Weights are fitted on this window and frozen.",
            "",
            "## Ensemble scoreboard",
            "",
            ens_ev[
                ["model_id", "target", "horizon", "n", "rmse", "theil_u", "mz_slope_p", "focus_ratio"]
            ].round(3).to_markdown(index=False),
            "",
            "## School weights (performance)",
            "",
        ]
        for key, w in weights.items():
            if key.startswith("school:"):
                lines.append(f"- **{key}**: " + ", ".join(f"{m}={v:.3f}" for m, v in w.items()))
        lines += [
            "",
            "## Disagreement (school dispersion)",
            "",
            dis.groupby(["target", "horizon"])["std"].mean().reset_index().round(3).to_markdown(index=False),
            "",
            "All four schools have a recorded `REJECTED` terminal state; the ensemble is a",
            "diagnostic synthesis, not a validated PASS. The benchmark ensemble is the",
            "stronger comparator.",
            "",
        ]
        (config.REPORTS / "ensemble_report.md").write_text("\n".join(lines))
    return {
        "weights": weights,
        "n_ensemble_rows": int(len(ens)),
        "scoreboard": ens_ev,
        "disagreement": dis,
    }
