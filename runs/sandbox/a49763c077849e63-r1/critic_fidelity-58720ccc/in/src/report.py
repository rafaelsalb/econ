from __future__ import annotations

from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from . import config
from .backtest import model_registry
from .ingest import load_observations
from .models.base import Forecast
from .models.new_keynesian import NewKeynesian
from .utils import last_weekday
from .vintage import Panel

OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]


def _instances():
    import json

    variant = "R3"
    decision_path = config.SPECS / "new_keynesian.decision.json"
    if decision_path.exists():
        decision = json.loads(decision_path.read_text())
        variant = decision.get("terminal", {}).get("variant", variant)
    reg = model_registry()
    out = {}
    for name, cls in reg.items():
        out[name] = cls(variant=variant) if name == "new_keynesian" else cls()
    return out


def _latest_origin(obs: pd.DataFrame) -> date:
    last = pd.Timestamp(obs["ref_date"].max()).date()
    current = pd.Period(date.today(), "M")
    origin_month = current - 1 if pd.Period(last, "M") >= current else pd.Period(last, "M")
    return last_weekday(origin_month.end_time.date())


def collect_latest(obs: pd.DataFrame | None = None, origin: date | None = None):
    obs = obs if obs is not None else load_observations()
    origin = origin or _latest_origin(obs)
    panel = Panel.build(origin, obs)
    rows: list[dict] = []
    failures = []
    for name, model in _instances().items():
        try:
            fcs: list[Forecast] = model.forecast(panel)
        except Exception as exc:  # noqa: BLE001
            failures.append({"model": name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        for f in fcs:
            rows.append(
                {
                    "model_id": name,
                    "target": f.target,
                    "horizon": f.horizon,
                    "ref_date": f.ref_date,
                    "point": f.point,
                }
            )
    return origin, pd.DataFrame(rows), failures


def _table(df: pd.DataFrame, target: str, horizons: list[int]) -> pd.DataFrame:
    sub = df[(df["target"] == target) & (df["horizon"].isin(horizons))]
    if sub.empty:
        return pd.DataFrame()
    return sub.pivot_table(index="model_id", columns="horizon", values="point")


def _plot(df: pd.DataFrame, path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    specs = [
        ("ipca_12m", [3, 6, 12], "IPCA 12m (%)", axes[0]),
        ("gdp_qq", [0, 1, 2, 3, 4], "GDP q/q (%)", axes[1]),
        ("selic", [3, 6, 12], "Selic (%)", axes[2]),
    ]
    for target, horizons, title, ax in specs:
        sub = df[(df["target"] == target) & (df["horizon"].isin(horizons))]
        for i, (model, g) in enumerate(sub.groupby("model_id")):
            g = g.sort_values("horizon")
            ax.plot(
                g["horizon"],
                g["point"],
                marker="o",
                ms=4,
                lw=1.6,
                label=model,
                color=OKABE_ITO[i % len(OKABE_ITO)],
            )
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("horizon")
        ax.grid(alpha=0.25, lw=0.5)
    handles, labels = [], []
    for ax in axes:
        h, l = ax.get_legend_handles_labels()
        for hh, ll in zip(h, l):
            if ll not in labels:
                handles.append(hh)
                labels.append(ll)
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8, frameon=False)
    fig.suptitle("Brazil macro model hub — latest forecasts", fontsize=12)
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def build_report() -> dict:
    obs = load_observations()
    origin, df, failures = collect_latest(obs)
    config.REPORTS.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.REPORTS / "forecasts_latest.csv", index=False)
    _plot(df, config.REPORTS / "latest_forecasts.png")

    score = pd.read_csv(config.EVAL / "scoreboard.csv") if (config.EVAL / "scoreboard.csv").exists() else pd.DataFrame()
    decision = None
    dec_path = config.SPECS / "new_keynesian.decision.json"
    if dec_path.exists():
        import json

        decision = json.loads(dec_path.read_text())

    lines = [
        "# Brazil macro model hub — monthly report",
        "",
        f"Origin: **{origin}** · data vintage: pseudo-real-time (release dates, no revision history)",
        "",
        "## Latest forecasts",
        "",
    ]
    for target, horizons, title in [
        ("ipca_12m", [3, 6, 12], "IPCA 12-month accumulated (%)"),
        ("gdp_qq", [0, 1, 2, 3, 4], "GDP q/q (%)"),
        ("selic", [3, 6, 12], "Selic target (%)"),
    ]:
        tab = _table(df, target, horizons)
        lines.append(f"### {title}")
        lines.append("")
        if tab.empty:
            lines.append("_No forecasts._")
        else:
            lines.append(tab.round(2).to_markdown())
        lines.append("")

    lines += ["## Validation scoreboard (primary cells)", ""]
    if score.empty:
        lines.append("_Run `econ score` first._")
    else:
        p = score[score["primary"]][
            ["model_id", "target", "horizon", "n", "rmse", "theil_u", "dm_p", "mz_slope_p", "rank"]
        ].copy()
        lines.append(p.round(3).to_markdown(index=False))
    lines.append("")

    lines += ["## School model status", ""]
    if decision:
        t = decision["terminal"]
        lines.append(
            f"- **{decision['model_id']}**: `{t['status']}` after {t['round']} rounds "
            f"(variant {t['variant']}, run `{t['run_id']}`)."
        )
        lines.append(f"- Reason: {t.get('reason', '')}.")
        if t["status"] == "REJECTED":
            lines.append(
                "- The model is shown for reference only; its forecasts are not a "
                "validated school forecast. The terminal state is recorded in "
                "`specs/new_keynesian.decision.json`."
            )
        for h in decision["history"]:
            lines.append(
                f"  - Round {h['round']} ({h['variant']}): {h['status']}; "
                f"{h['n_high']} high / {h['n_medium']} medium defects."
            )
        lines.append("")
        lines.append("Known limitations carried forward: output-gap transmission is small and "
                     "imprecisely estimated; FX pass-through is not identified; the Taylor "
                     "rule residuals are autocorrelated.")
    else:
        lines.append("_No loop decision recorded yet._")
    lines.append("")

    lines += [
        "## Data and method notes",
        "",
        "- Vintage: observations are filtered by `release_date <= origin`; revision history is not available for most series, so this is pseudo-real-time.",
        "- Evaluation: final-vintage outcomes, joined only in the evaluator.",
        "- Lockbox 2020-01..2026-10 is sealed for model selection.",
        "- The 12-month IPCA forecast is derived by compounding the monthly path.",
        "- New Keynesian variant R3: forward-looking Taylor rule using the Focus 12m expectation; GDP satellite bridge uses an AR(1) IBC-Br path.",
        "",
    ]
    if failures:
        lines += ["## Model failures at this origin", ""]
        for f in failures:
            lines.append(f"- `{f['model']}`: {f['error']}")
        lines.append("")

    (config.REPORTS / "monthly_report.md").write_text("\n".join(lines))
    return {"origin": str(origin), "rows": len(df), "failures": failures}
