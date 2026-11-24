from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from . import config
from .config import EPISODES
from .targets import (
    PRIMARY_HORIZONS,
    compound,
    monthly_inflation_series,
    quarterly_gdp_series,
    selic_monthly_series,
)


def realized_table(obs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    pi = monthly_inflation_series(obs)
    for m, v in pi.items():
        rows.append({"target": "ipca_m", "ref_date": m.end_time.date(), "realized": float(v)})
    for m in pi.index:
        window = pd.period_range(m - 11, m, freq="M")
        if all(p in pi.index for p in window):
            rows.append(
                {
                    "target": "ipca_12m",
                    "ref_date": m.end_time.date(),
                    "realized": compound(pi.loc[window]),
                }
            )
    for q, v in quarterly_gdp_series(obs).items():
        rows.append({"target": "gdp_qq", "ref_date": q.end_time.date(), "realized": float(v)})
    for m, v in selic_monthly_series(obs).items():
        rows.append({"target": "selic", "ref_date": m.end_time.date(), "realized": float(v)})
    df = pd.DataFrame(rows)
    df["ref_date"] = pd.to_datetime(df["ref_date"]).dt.date
    return df


def attach_realized(forecasts: pd.DataFrame, obs: pd.DataFrame) -> pd.DataFrame:
    rt = realized_table(obs)
    fc = forecasts.copy()
    fc["ref_date"] = pd.to_datetime(fc["ref_date"]).dt.date
    fc["origin_date"] = pd.to_datetime(fc["origin_date"]).dt.date
    out = fc.merge(rt, on=["target", "ref_date"], how="left")
    out["error"] = out["point"] - out["realized"]
    return out


def dm_test(e1: np.ndarray, e2: np.ndarray, h: int) -> tuple[float, float]:
    d = np.asarray(e1, float) ** 2 - np.asarray(e2, float) ** 2
    n = len(d)
    if n < 8:
        return np.nan, np.nan
    dbar = float(np.mean(d))
    gamma0 = float(np.var(d, ddof=0))
    L = max(h, 1)
    var = gamma0
    for j in range(1, L + 1):
        if j >= n:
            break
        gj = float(np.mean((d[j:] - dbar) * (d[:-j] - dbar)))
        var += 2.0 * (1.0 - j / (L + 1)) * gj
    var /= n
    if var <= 0:
        return np.nan, np.nan
    stat = dbar / np.sqrt(var)
    if h > 0:
        stat *= np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    p = 2 * (1 - stats.t.cdf(abs(stat), df=n - 1))
    return float(stat), float(p)


def mz_test(y: np.ndarray, fc: np.ndarray, h: int) -> dict:
    y = np.asarray(y, float)
    fc = np.asarray(fc, float)
    nan = {
        "mz_slope": np.nan,
        "mz_slope_p": np.nan,
        "mz_intercept": np.nan,
        "mz_intercept_p": np.nan,
        "mz_r2": np.nan,
    }
    if len(y) < 8 or np.std(fc) < 1e-10 or np.std(y) < 1e-10:
        return nan
    X = sm.add_constant(fc)
    if np.linalg.matrix_rank(X) < 2:
        return nan
    model = sm.OLS(y, X).fit(
        cov_type="HAC", cov_kwds={"maxlags": max(h, 1)}, use_t=True
    )
    b = float(model.params[1])
    se = float(model.bse[1])
    a = float(model.params[0])
    p_b1 = 2 * (1 - stats.t.cdf(abs((b - 1) / se), df=int(model.df_resid)))
    p_a0 = 2 * (1 - stats.t.cdf(abs(a / float(model.bse[0])), df=int(model.df_resid)))
    return {
        "mz_slope": b,
        "mz_slope_p": float(p_b1),
        "mz_intercept": a,
        "mz_intercept_p": float(p_a0),
        "mz_r2": float(model.rsquared),
    }


def evaluate(
    forecasts: pd.DataFrame,
    obs: pd.DataFrame,
    validation_end: date | None = None,
) -> pd.DataFrame:
    fc = attach_realized(forecasts, obs)
    fc = fc.dropna(subset=["realized", "point"])
    fc = fc[~((fc["target"] == "selic") & (fc["horizon"] == 0))]
    if validation_end is not None:
        fc = fc[pd.to_datetime(fc["ref_date"]).dt.date <= validation_end]
    rw = fc[fc["model_id"] == "random_walk"]
    focus = fc[fc["model_id"] == "focus_consensus"]

    out = []
    groups = fc.groupby(["model_id", "school", "target", "horizon"], dropna=False)
    for (model_id, school, target, horizon), g in groups:
        g = g.sort_values("origin_date")
        err = g["error"].to_numpy()
        y = g["realized"].to_numpy()
        p = g["point"].to_numpy()
        n = len(g)
        rmse = float(np.sqrt(np.mean(err**2)))
        mae = float(np.mean(np.abs(err)))
        bias = float(np.mean(err))
        satellite = bool(
            g["notes"].fillna("").astype(str).str.contains("satellite").any()
        )

        rwg = rw[(rw["target"] == target) & (rw["horizon"] == horizon)]
        joint = g.merge(
            rwg[["origin_date", "error", "point", "realized"]],
            on="origin_date",
            suffixes=("", "_rw"),
            how="inner",
        )
        if len(joint) >= 8:
            theil = float(
                np.sqrt(np.mean(joint["error"] ** 2))
                / np.sqrt(np.mean(joint["error_rw"] ** 2))
            )
            dm_stat, dm_p = dm_test(
                joint["error"].to_numpy(), joint["error_rw"].to_numpy(), int(horizon)
            )
        else:
            theil, dm_stat, dm_p = np.nan, np.nan, np.nan

        fg = focus[(focus["target"] == target) & (focus["horizon"] == horizon)]
        jf = g.merge(
            fg[["origin_date", "error"]],
            on="origin_date",
            suffixes=("", "_focus"),
            how="inner",
        )
        if len(jf) >= 8 and model_id != "focus_consensus":
            rmse_joint = float(np.sqrt(np.mean(jf["error"] ** 2)))
            rmse_focus = float(np.sqrt(np.mean(jf["error_focus"] ** 2)))
            focus_ratio = rmse_joint / rmse_focus if rmse_focus > 0 else np.nan
            dm_focus_stat, dm_focus_p = dm_test(
                jf["error"].to_numpy(), jf["error_focus"].to_numpy(), int(horizon)
            )
        else:
            focus_ratio, dm_focus_stat, dm_focus_p = np.nan, np.nan, np.nan

        mz = mz_test(y, p, int(horizon))
        dir_mask = g["anchor"].notna()
        if dir_mask.sum() > 0:
            da = float(
                np.mean(
                    np.sign(g.loc[dir_mask, "point"] - g.loc[dir_mask, "anchor"])
                    == np.sign(g.loc[dir_mask, "realized"] - g.loc[dir_mask, "anchor"])
                )
            )
        else:
            da = np.nan

        out.append(
            {
                "model_id": model_id,
                "school": school,
                "target": target,
                "horizon": int(horizon),
                "n": n,
                "rmse": rmse,
                "mae": mae,
                "bias": bias,
                "theil_u": theil,
                "dm_stat": dm_stat,
                "dm_p": dm_p,
                "focus_ratio": focus_ratio,
                "dm_focus_stat": dm_focus_stat,
                "dm_focus_p": dm_focus_p,
                **mz,
                "direction": da,
                "satellite": satellite,
                "max_ref_date": g["ref_date"].max(),
                "primary": int(horizon) in PRIMARY_HORIZONS.get(target, []),
                "first_origin": g["origin_date"].min(),
                "last_origin": g["origin_date"].max(),
            }
        )
    metrics = pd.DataFrame(out)
    metrics["rank"] = (
        metrics.groupby(["target", "horizon"])["rmse"].rank(method="min").astype("Int64")
    )
    return metrics.sort_values(["target", "horizon", "rmse"]).reset_index(drop=True)


def episode_metrics(
    forecasts: pd.DataFrame,
    obs: pd.DataFrame,
    validation_end: date | None = None,
) -> pd.DataFrame:
    fc = attach_realized(forecasts, obs).dropna(subset=["realized", "point"])
    fc = fc[~((fc["target"] == "selic") & (fc["horizon"] == 0))]
    if validation_end is not None:
        fc = fc[pd.to_datetime(fc["ref_date"]).dt.date <= validation_end]
    rows = []
    for name, (lo, hi) in EPISODES.items():
        lo_d, hi_d = date.fromisoformat(lo), date.fromisoformat(hi)
        sub = fc[(fc["origin_date"] >= lo_d) & (fc["origin_date"] <= hi_d)]
        if sub.empty:
            continue
        rw = sub[sub["model_id"] == "random_walk"]
        for (model_id, target, horizon), g in sub.groupby(
            ["model_id", "target", "horizon"]
        ):
            rmse = float(np.sqrt(np.mean(g["error"] ** 2)))
            rwg = rw[(rw["target"] == target) & (rw["horizon"] == horizon)]
            joint = g.merge(rwg[["origin_date", "error"]], on="origin_date", suffixes=("", "_rw"))
            theil = (
                float(
                    np.sqrt(np.mean(joint["error"] ** 2))
                    / np.sqrt(np.mean(joint["error_rw"] ** 2))
                )
                if len(joint) >= 5
                else np.nan
            )
            rows.append(
                {
                    "episode": name,
                    "model_id": model_id,
                    "target": target,
                    "horizon": int(horizon),
                    "n": len(g),
                    "rmse": rmse,
                    "theil_u": theil,
                }
            )
    return pd.DataFrame(rows)


def write_outputs(metrics: pd.DataFrame, episodes: pd.DataFrame) -> None:
    config.EVAL.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(config.EVAL / "scoreboard.csv", index=False)
    episodes.to_csv(config.EVAL / "episodes.csv", index=False)

    lines = ["# Brazil macro model hub — scoreboard", ""]
    lines.append(f"Generated from registry run(s). {len(metrics)} model-target-horizon rows.")
    lines.append("")
    for target in ["ipca_m", "ipca_12m", "gdp_qq", "selic"]:
        sub = metrics[metrics["target"] == target]
        if sub.empty:
            continue
        lines.append(f"## {target}")
        lines.append("")
        lines.append(
            "| model | h | n | RMSE | Theil U | DM p | MZ slope | MZ p(b=1) | Dir. |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for _, r in sub.iterrows():
            def fmt(v, d=3):
                return "—" if pd.isna(v) else f"{v:.{d}f}"

            lines.append(
                f"| {r['model_id']} | {int(r['horizon'])} | {int(r['n'])} | "
                f"{fmt(r['rmse'])} | {fmt(r['theil_u'])} | {fmt(r['dm_p'])} | "
                f"{fmt(r['mz_slope'])} | {fmt(r['mz_slope_p'])} | {fmt(r['direction'], 2)} |"
            )
        lines.append("")

    if not episodes.empty:
        lines.append("## Episode scorecard (RMSE / Theil U)")
        lines.append("")
        for ep in episodes["episode"].unique():
            sub = episodes[episodes["episode"] == ep]
            lines.append(f"### {ep}")
            lines.append("")
            lines.append("| model | target | h | n | RMSE | Theil U |")
            lines.append("|---|---|---:|---:|---:|---:|")
            for _, r in sub.iterrows():
                trials = "—" if pd.isna(r["theil_u"]) else f"{r['theil_u']:.3f}"
                lines.append(
                    f"| {r['model_id']} | {r['target']} | {int(r['horizon'])} | "
                    f"{int(r['n'])} | {r['rmse']:.3f} | {trials} |"
                )
            lines.append("")

    (config.EVAL / "scoreboard.md").write_text("\n".join(lines))


def summary_by_model(metrics: pd.DataFrame) -> pd.DataFrame:
    sub = metrics[metrics["primary"] & ~metrics["satellite"]]
    return (
        sub.groupby(["model_id", "school"])
        .agg(
            mean_rank=("rank", "mean"),
            mean_theil=("theil_u", "mean"),
            n_cells=("rmse", "size"),
        )
        .sort_values("mean_rank")
        .reset_index()
    )
