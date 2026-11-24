from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from . import config
from .backtest import run_backtest
from .ensemble import (
    ALL_MODELS,
    ENSEMBLE_IDS,
    build_ensembles,
    build_ensembles_and_report,
    compute_weights,
    disagreement,
)
from .evaluate import episode_metrics, evaluate
from .ingest import load_observations
from .registry import read_forecasts

LEDGER = config.REGISTRY / "lockbox.json"
WEIGHTS = config.EVAL / "ensemble_weights.json"
LOCKBOX_START = date.fromisoformat(config.LOCKBOX_START)
LOCKBOX_END = date.fromisoformat(config.LOCKBOX_END)


def load_weights() -> dict:
    if not WEIGHTS.exists():
        info = build_ensembles_and_report()
        return info["weights"]
    payload = json.loads(WEIGHTS.read_text())
    return payload["weights"]


def lockbox_status() -> dict | None:
    if not LEDGER.exists():
        return None
    return json.loads(LEDGER.read_text())


def open_lockbox(force: bool = False, reason: str = "") -> dict:
    existing = lockbox_status()
    if existing and not force:
        raise RuntimeError(
            f"lockbox already opened at {existing['opened_at']} (run {existing['run_id']}); "
            "use --force only with a documented reason"
        )
    if force and not reason:
        raise ValueError("--force requires --reason")

    weights = load_weights()
    ctx, fc = run_backtest(
        ALL_MODELS,
        LOCKBOX_START,
        LOCKBOX_END,
        embargo_until=LOCKBOX_END,
    )
    run_fc = fc[fc["run_id"] == ctx.run_id]
    obs = load_observations()
    ev = evaluate(run_fc, obs, validation_end=LOCKBOX_END)
    episodes = episode_metrics(run_fc, obs, validation_end=LOCKBOX_END)

    ens = build_ensembles(run_fc, weights)
    rw_focus = run_fc[run_fc["model_id"].isin(["random_walk", "focus_consensus"])]
    ens_fc = pd.concat([ens, rw_focus], ignore_index=True)
    ens_ev = evaluate(ens_fc, obs, validation_end=LOCKBOX_END)
    ens_ev = ens_ev[ens_ev["model_id"].isin(ENSEMBLE_IDS)]
    dis = disagreement(run_fc)

    config.EVAL.mkdir(parents=True, exist_ok=True)
    config.REPORTS.mkdir(parents=True, exist_ok=True)
    ev.to_csv(config.EVAL / "lockbox_scoreboard.csv", index=False)
    episodes.to_csv(config.EVAL / "lockbox_episodes.csv", index=False)
    ens_ev.to_csv(config.EVAL / "lockbox_ensemble_scoreboard.csv", index=False)
    ens.to_parquet(config.EVAL / "lockbox_ensemble_forecasts.parquet", index=False)
    dis.to_csv(config.REPORTS / "lockbox_disagreement.csv", index=False)

    decisions = {}
    for model_id in ["new_keynesian", "monetarist", "fiscal_ftpl", "pk_sfc"]:
        path = config.SPECS / f"{model_id}.decision.json"
        if path.exists():
            decisions[model_id] = json.loads(path.read_text())["terminal"]

    primary = ev[ev["primary"]][
        ["model_id", "target", "horizon", "n", "rmse", "theil_u", "mz_slope_p", "focus_ratio", "rank"]
    ]
    lines = [
        "# Lockbox report — 2020-01 to 2026-10",
        "",
        f"Opened: {datetime.now().isoformat(timespec='seconds')} · run `{ctx.run_id}`",
        f"Data hash: `{ctx.data_hash}` · code hash: `{ctx.code_hash}`",
        f"Models: {', '.join(ALL_MODELS)}",
        "",
        "This is the single lockbox evaluation. The weights were fitted on the",
        "2010–2019 validation window and frozen before this run.",
        "",
        "## School terminal states (validation)",
        "",
        "| model | status | reason |",
        "|---|---|---|",
    ]
    for model_id, terminal in decisions.items():
        lines.append(
            f"| {model_id} | {terminal['status']} | {terminal.get('reason','')} |"
        )
    lines += [
        "",
        "## Lockbox scoreboard (primary cells)",
        "",
        primary.round(3).to_markdown(index=False),
        "",
        "## Ensemble scoreboard",
        "",
        ens_ev[
            ["model_id", "target", "horizon", "n", "rmse", "theil_u", "mz_slope_p", "focus_ratio"]
        ].round(3).to_markdown(index=False),
        "",
    ]
    ipca12 = ens_ev[(ens_ev["target"] == "ipca_12m") & (ens_ev["horizon"] == 12)]
    if not ipca12.empty:
        best = ipca12.loc[ipca12["focus_ratio"].idxmin()]
        lines.append(
            f"Best ensemble on IPCA h=12: `{best['model_id']}` with Focus ratio "
            f"{best['focus_ratio']:.3f} (Theil U {best['theil_u']:.3f})."
        )
    mon = ev[(ev["model_id"] == "monetarist") & (ev["target"] == "ipca_12m") & (ev["horizon"] == 12)]
    if not mon.empty:
        lines.append(
            f"Monetarist on IPCA h=12: Theil U {mon['theil_u'].iloc[0]:.3f}, "
            f"Focus ratio {mon['focus_ratio'].iloc[0]:.3f}."
        )
    lines += [
        "",
        "## Caveats",
        "",
        "- All four school models were `REJECTED` on the validation window. The",
        "  lockbox is a final out-of-sample reading of those rejected models and",
        "  of the benchmark/ensemble comparators, not a rescue.",
        "- The SFC and FTPL models have shorter effective samples; their lockbox",
        "  rows reflect only the origins where they produced forecasts.",
        "- The lockbox is now sealed in `registry/lockbox.json`. Do not reuse it",
        "  for model selection or another report.",
        "",
    ]
    (config.REPORTS / "lockbox_report.md").write_text("\n".join(lines))

    ledger = {
        "opened_at": datetime.now().isoformat(timespec="seconds"),
        "run_id": ctx.run_id,
        "data_hash": ctx.data_hash,
        "code_hash": ctx.code_hash,
        "models": ALL_MODELS,
        "lockbox_start": str(LOCKBOX_START),
        "lockbox_end": str(LOCKBOX_END),
        "weights_file": str(WEIGHTS),
        "rows": int(len(run_fc)),
        "force_reason": reason if force else None,
    }
    fail_path = config.RUNS / ctx.run_id / "failures.json"
    if fail_path.exists():
        try:
            ledger["failures"] = len(json.loads(fail_path.read_text()))
        except Exception:
            ledger["failures"] = None
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=2))
    return {
        "run_id": ctx.run_id,
        "scoreboard_rows": int(len(ev)),
        "ensemble_rows": int(len(ens_ev)),
        "ledger": str(LEDGER),
        "report": str(config.REPORTS / "lockbox_report.md"),
    }


def build_final_report() -> Path:
    decisions = {}
    for model_id in ["new_keynesian", "monetarist", "fiscal_ftpl", "pk_sfc"]:
        path = config.SPECS / f"{model_id}.decision.json"
        if path.exists():
            decisions[model_id] = json.loads(path.read_text())["terminal"]

    score = pd.read_csv(config.EVAL / "scoreboard.csv") if (config.EVAL / "scoreboard.csv").exists() else pd.DataFrame()
    ens = pd.read_csv(config.EVAL / "ensemble_scoreboard.csv") if (config.EVAL / "ensemble_scoreboard.csv").exists() else pd.DataFrame()
    lock = pd.read_csv(config.EVAL / "lockbox_scoreboard.csv") if (config.EVAL / "lockbox_scoreboard.csv").exists() else pd.DataFrame()
    lock_ens = pd.read_csv(config.EVAL / "lockbox_ensemble_scoreboard.csv") if (config.EVAL / "lockbox_ensemble_scoreboard.csv").exists() else pd.DataFrame()
    ledger = lockbox_status()

    lines = [
        "# Brazil macro model hub — final report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Phase status",
        "",
        "| Phase | State |",
        "|---|---|",
        "| 0 — data, benchmarks, registry, evaluator | Complete |",
        "| 1 — New Keynesian, critic loop | Complete, `REJECTED` |",
        "| 2 — Monetarist, FTPL, SFC | Complete, all `REJECTED` with reasons |",
        "| 3 — ensembles, fan, lockbox | Complete |",
        "",
        "## School terminal states",
        "",
        "| model | status | reason |",
        "|---|---|---|",
    ]
    for model_id, terminal in decisions.items():
        lines.append(
            f"| {model_id} | {terminal['status']} | {terminal.get('reason','')} |"
        )
    lines += [
        "",
        "## Validation scoreboard (primary cells)",
        "",
    ]
    if score.empty:
        lines.append("_No validation scoreboard._")
    else:
        cells = score[score["primary"]][
            ["model_id", "target", "horizon", "n", "rmse", "theil_u", "focus_ratio", "satellite"]
        ]
        lines.append(cells.round(3).to_markdown(index=False))
    lines += [
        "",
        "## Ensemble",
        "",
    ]
    if ens.empty:
        lines.append("_No ensemble scoreboard._")
    else:
        lines.append(
            ens[
                ["model_id", "target", "horizon", "n", "rmse", "theil_u", "focus_ratio"]
            ].round(3).to_markdown(index=False)
        )
    lines += [
        "",
        "## Lockbox",
        "",
    ]
    if ledger:
        lines.append(
            f"Opened once at {ledger['opened_at']} · run `{ledger['run_id']}` · "
            f"data hash `{ledger['data_hash']}`."
        )
        if not lock.empty:
            lines.append("")
            lines.append(
                lock[lock["primary"]][
                    ["model_id", "target", "horizon", "n", "rmse", "theil_u", "focus_ratio"]
                ].round(3).to_markdown(index=False)
            )
        if not lock_ens.empty:
            lines += ["", "### Lockbox ensemble", ""]
            lines.append(
                lock_ens[lock_ens["primary"]][
                    ["model_id", "target", "horizon", "n", "rmse", "theil_u", "focus_ratio"]
                ].round(3).to_markdown(index=False)
            )
    else:
        lines.append("_Lockbox not opened._")
    lines += [
        "",
        "## Interpretation",
        "",
        "- The benchmark suite, led by the Focus consensus, remains the strongest",
        "  comparator on the validation window. No school model passed its",
        "  pre-registered gate.",
        "- On the one-time lockbox, the combined ensemble beats Focus on IPCA h=12",
        "  and Selic h=12. The Monetarist and AR models also beat Focus on IPCA",
        "  h=12. This is a combination/benchmark result; it does not reverse the",
        "  validation rejections of the individual schools.",
        "- The New Keynesian model fails on gap significance, FX sign and Focus",
        "  value added; Monetarist fails the P-star channel on validation; FTPL is",
        "  rejected as Ricardian; the SFC-lite fails its behavioral sign restrictions.",
        "- The ensemble is a diagnostic synthesis of rejected models, not a",
        "  validated forecast. The benchmark ensemble is the stronger comparator.",
        "- The lockbox is a one-time reading. It must not be reused for selection.",
        "",
        "## Reproducibility",
        "",
        "Every run is identified by a hash of models, config, seed, data and code.",
        "The registry is append-only; the model cards and decisions are in `specs/`.",
        "",
    ]
    path = config.REPORTS / "final_report.md"
    path.write_text("\n".join(lines))
    return path
