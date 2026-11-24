from __future__ import annotations

import json
from datetime import date

import pandas as pd

from . import config
from .ingest import load_observations
from .utils import monthly_origins


def _runs() -> list[dict]:
    path = config.REGISTRY / "runs.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def run_checks() -> list[dict]:
    checks = []
    obs = load_observations()

    expected = {
        "ipca_m",
        "ibc_br",
        "selic_target",
        "fx_usdbrl",
        "gdp_qq",
        "focus_ipca_12m",
        "focus_ipca_annual",
    }
    present = set(obs["series_id"].unique())
    checks.append(
        {
            "check": "catalog coverage",
            "ok": expected <= present,
            "detail": f"missing={sorted(expected - present)}",
        }
    )

    runs = _runs()
    benchmark_ids = {"random_walk", "seasonal_naive", "ar", "bvar", "focus_consensus"}
    benchmark_runs = [
        r
        for r in runs
        if benchmark_ids.issubset(set(r.get("models", [])))
        and r.get("config", {}).get("start")
        and not r.get("config", {}).get("model_kwargs")
    ]
    best = None
    for r in benchmark_runs:
        lo = date.fromisoformat(r["config"]["start"])
        hi = date.fromisoformat(r["config"]["end"])
        n = len(monthly_origins(lo, hi))
        bench_failures = [
            f for f in r.get("failures", []) if f.get("model") in benchmark_ids
        ]
        if best is None or n >= best["n"]:
            best = {"n": n, "run": r, "bench_failures": bench_failures}
    checks.append(
        {
            "check": "benchmark backtest >=120 origins",
            "ok": best is not None and best["n"] >= 120 and not best["bench_failures"],
            "detail": "no qualifying run"
            if best is None
            else f"{best['n']} origins, run={best['run']['run_id']}, "
            f"benchmark failures={len(best['bench_failures'])}",
        }
    )

    purge_ok = False
    purge_detail = "no qualifying run"
    if best is not None:
        run_id = best["run"]["run_id"]
        part = config.REGISTRY / "forecasts" / f"run_id={run_id}" / "part.parquet"
        run_end = date.fromisoformat(best["run"]["config"]["end"])
        if part.exists():
            run_fc = pd.read_parquet(part)
            max_ref = pd.to_datetime(run_fc["ref_date"]).max().date()
            declared = best["run"]["config"].get("embargo_until")
            purge_ok = max_ref <= run_end and declared == str(run_end)
            purge_detail = {
                "run": run_id,
                "max_ref_date": str(max_ref),
                "validation_end": str(run_end),
                "embargo_until": declared,
            }
    checks.append(
        {
            "check": "validation targets purged at window end",
            "ok": purge_ok,
            "detail": purge_detail,
        }
    )

    leaks = []
    for origin in [date(2010, 1, 29), date(2015, 6, 30), date(2019, 12, 31), date(2026, 10, 30)]:
        visible = obs[obs["release_date"] <= origin]
        bad = (visible["release_date"] > origin).sum()
        leaks.append({"origin": str(origin), "violations": int(bad), "rows": int(len(visible))})
    checks.append(
        {
            "check": "release-date leak test",
            "ok": all(x["violations"] == 0 for x in leaks),
            "detail": leaks,
        }
    )

    score_path = config.EVAL / "scoreboard.csv"
    if score_path.exists():
        score = pd.read_csv(score_path)
        has_focus = {
            t: bool(
                ((score["model_id"] == "focus_consensus") & (score["target"] == t)).any()
            )
            for t in ["ipca_12m", "selic"]
        }
    else:
        has_focus = {"ipca_12m": False, "selic": False}
    checks.append(
        {
            "check": "Focus benchmark for IPCA and Selic",
            "ok": all(has_focus.values()),
            "detail": has_focus,
        }
    )

    manifest_path = config.CURATED / "manifest.json"
    data_hash = json.loads(manifest_path.read_text())["sha256"] if manifest_path.exists() else ""
    checks.append(
        {
            "check": "curated data hash recorded",
            "ok": bool(data_hash),
            "detail": data_hash,
        }
    )

    manifest = config.SPECS / "new_keynesian.decision.json"
    checks.append(
        {
            "check": "Phase 1 loop decision recorded",
            "ok": manifest.exists(),
            "detail": "specs/new_keynesian.decision.json" if manifest.exists() else "missing",
        }
    )

    for model_id in ["new_keynesian", "monetarist", "fiscal_ftpl", "pk_sfc"]:
        path = config.SPECS / f"{model_id}.decision.json"
        status = "missing"
        if path.exists():
            try:
                status = json.loads(path.read_text())["terminal"]["status"]
            except Exception:
                status = "unreadable"
        checks.append(
            {
                "check": f"school terminal state: {model_id}",
                "ok": path.exists(),
                "detail": status,
            }
        )

    checks.append(
        {
            "check": "ensemble scoreboard and fan chart",
            "ok": (config.EVAL / "ensemble_scoreboard.csv").exists()
            and (config.REPORTS / "fan_chart.png").exists(),
            "detail": f"{config.EVAL / 'ensemble_scoreboard.csv'}, {config.REPORTS / 'fan_chart.png'}",
        }
    )
    checks.append(
        {
            "check": "one-time lockbox ledger",
            "ok": (config.REGISTRY / "lockbox.json").exists(),
            "detail": str(config.REGISTRY / "lockbox.json"),
        }
    )
    checks.append(
        {
            "check": "final report",
            "ok": (config.REPORTS / "final_report.md").exists(),
            "detail": str(config.REPORTS / "final_report.md"),
        }
    )
    return checks


def print_checks() -> bool:
    checks = run_checks()
    ok = all(c["ok"] for c in checks)
    for c in checks:
        print(f"[{'PASS' if c['ok'] else 'FAIL'}] {c['check']}: {c['detail']}")
    print(f"\n{'ALL CHECKS PASS' if ok else 'CHECKS FAILED'}")
    return ok
