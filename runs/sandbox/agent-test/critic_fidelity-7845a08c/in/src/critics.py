from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .diagnostics import Defect


def _num(params: dict, block: str, key: str) -> float:
    return float(params.get(block, {}).get(key, float("nan")))


def _sig(params: dict, key: str, block: str = "nkpc") -> float:
    return _num(params, block, key)


def check_refutations(diag: dict, card: dict) -> list[Defect]:
    """Evaluate the card's machine-readable refutation tests.

    A test states the condition the estimate must satisfy to be admissible.
    If the condition fails, the model's own pre-registered falsification rule
    fires and the returned defect carries the declared severity.
    """
    out: list[Defect] = []
    for test in card.get("refutation_tests", []) or []:
        block = test["block"]
        key = test["key"]
        stat = test.get("stat", "coef")
        source = diag["tstats"] if stat == "tstat" else diag["params"]
        val = float(source.get(block, {}).get(key, float("nan")))
        op = test["op"]
        threshold = float(test["threshold"])
        ok = False
        if math.isfinite(val):
            if op == "gt":
                ok = val > threshold
            elif op == "lt":
                ok = val < threshold
            elif op == "abs_ge":
                ok = abs(val) >= threshold
        if not ok:
            out.append(
                Defect(
                    test.get("code", "D1"),
                    test.get("severity", "high"),
                    test["message"],
                    {
                        "test": test.get("id", ""),
                        "block": block,
                        "key": key,
                        "stat": stat,
                        "value": val,
                        "threshold": threshold,
                    },
                )
            )
    return out


def fidelity_critique(diag: dict, irf: dict, card: dict) -> list[Defect]:
    p = diag["params"]
    t = diag["tstats"]
    defects: list[Defect] = []

    checks = [
        ("rr", "is", -1, "Real-rate coefficient in the IS curve must be negative"),
        ("gap_1", "nkpc", 1, "Output-gap coefficient in the NKPC must be positive"),
        ("i_lag", "taylor", 1, "Policy smoothing coefficient must lie in (0,1)"),
        ("pi_gap", "taylor", 1, "Inflation response in the Taylor rule must be positive"),
        ("gap_1", "taylor", 1, "Gap response in the Taylor rule must be positive"),
    ]
    for key, block, expected, msg in checks:
        val = _num(p, block, key)
        if not math.isfinite(val):
            defects.append(Defect("D7", "high", f"{msg}; coefficient missing", {"block": block, "key": key}))
            continue
        if expected > 0 and val <= 0:
            defects.append(Defect("D7", "high", msg, {"block": block, "key": key, "value": val}))
        if expected < 0 and val >= 0:
            defects.append(Defect("D7", "high", msg, {"block": block, "key": key, "value": val}))

    rho = _num(p, "taylor", "i_lag")
    if not (0 < rho < 1):
        defects.append(Defect("D7", "high", "Taylor-rule smoothing outside (0,1)", {"rho": rho}))
    elif rho > 0.98:
        defects.append(
            Defect(
                "D7",
                "medium",
                "Policy inertia is near a unit root; the rate path may respond too slowly",
                {"rho": rho},
            )
        )

    # Long-run neutrality is imposed by construction; verify the implemented sum.
    b1, b2, b3 = _sig(p, "pi1_rel"), _sig(p, "pi2_rel"), _sig(p, "pi_e")
    if abs((b1 + b2 + b3) - 1.0) > 1e-6:
        defects.append(
            Defect("D2", "high", "NKPC long-run neutrality violated", {"sum": b1 + b2 + b3})
        )

    gap_coef = _sig(p, "gap_1")
    if math.isfinite(gap_coef) and 0 < gap_coef < 0.02:
        defects.append(
            Defect(
                "D7",
                "medium",
                "Output-gap transmission is economically negligible (<0.02pp monthly inflation per 1pp gap)",
                {"gap_coef": gap_coef},
            )
        )

    fx_coef = _sig(p, "dfx_1")
    # The sign restriction is evaluated by the card's refutation tests below.
    # Keep a fallback for cards that predate the machine-readable tests.
    if not card.get("refutation_tests") and math.isfinite(fx_coef) and fx_coef <= 0:
        defects.append(
            Defect(
                "D7",
                "high",
                "FX pass-through coefficient is non-positive; the external channel is not identified",
                {"fx_coef": fx_coef},
            )
        )

    for key, block, label in [
        ("rr", "is", "real-rate"),
        ("pi_gap", "taylor", "inflation-response"),
    ]:
        tval = _num(t, block, key)
        if math.isfinite(tval) and abs(tval) < 1.65:
            defects.append(
                Defect(
                    "D1",
                    "medium",
                    f"{label} coefficient is not precisely estimated (|t| < 1.65)",
                    {"block": block, "key": key, "tstat": tval},
                )
            )

    if card.get("observables", {}).get("expectations", {}).get("series") != "focus_ipca_12m":
        defects.append(
            Defect("D1", "high", "Expectations are not mapped to the survey series declared in the card")
        )

    for name, sign in irf.items():
        if name == "real_rate_to_gap" and sign >= 0:
            defects.append(Defect("D7", "high", "Monetary transmission sign wrong: real rate does not lower the gap"))
        if name == "gap_to_inflation" and sign <= 0:
            defects.append(Defect("D7", "high", "Monetary transmission sign wrong: gap does not raise inflation"))

    defects.extend(check_refutations(diag, card))
    return defects


def adequacy_critique(
    diag: dict,
    metrics: pd.DataFrame,
    stability: dict | None = None,
    card: dict | None = None,
) -> list[Defect]:
    defects: list[Defect] = []
    model_id = "new_keynesian"

    if diag.get("leak_ok") is False:
        defects.append(
            Defect("D3", "high", "As-of slice contains observations released after the origin",
                   {"max_release": diag.get("max_release")})
        )

    if card:
        declared = card.get("estimation", {}).get("start")
        if declared:
            declared_start = pd.Period(str(declared), "M")
            actual_start = pd.Period(str(diag["sample_start"]), "M")
            if actual_start < declared_start:
                defects.append(
                    Defect(
                        "D3",
                        "high",
                        f"Estimation sample starts {actual_start}, before the card's declared {declared_start}",
                        {"card_start": str(declared_start), "actual_start": str(actual_start)},
                    )
                )

    for block, pval in diag["ljung_box_p"].items():
        if not math.isfinite(pval):
            continue
        if pval < 0.01:
            defects.append(
                Defect("D4", "medium", f"Residual autocorrelation in {block} equation (Ljung-Box p={pval:.4f})",
                       {"equation": block, "pvalue": pval})
            )
        elif pval < 0.05:
            defects.append(
                Defect("D4", "low", f"Weak residual autocorrelation in {block} equation (p={pval:.4f})",
                       {"equation": block, "pvalue": pval})
            )

    for block, cond in diag["condition"].items():
        if cond > 1000:
            defects.append(Defect("D4", "high", f"Severe multicollinearity in {block} (cond={cond:.1f})",
                                  {"equation": block, "condition": cond}))
        elif cond > 100:
            defects.append(Defect("D4", "medium", f"Multicollinearity in {block} (cond={cond:.1f})",
                                  {"equation": block, "condition": cond}))

    for block, r2 in diag["rsquared"].items():
        if block == "nkpc" and r2 < 0.10:
            defects.append(Defect("D4", "low", f"NKPC fit is weak (R2={r2:.3f})", {"r2": r2}))

    if stability:
        for block, info in stability.items():
            flips = info.get("_sign_flips", 0)
            if flips >= 2:
                defects.append(Defect("D4", "medium", f"{flips} sign flips in {block} across sub-samples",
                                      {"equation": block, "flips": flips}))
            elif flips == 1:
                defects.append(Defect("D4", "low", f"One sign flip in {block} across sub-samples",
                                      {"equation": block, "flips": flips}))

    if card:
        validation_end = card.get("validation_end")
        if validation_end and "max_ref_date" in metrics.columns:
            latest = pd.to_datetime(metrics["max_ref_date"]).max()
            if pd.notna(latest) and latest > pd.Timestamp(validation_end):
                defects.append(
                    Defect(
                        "D3",
                        "high",
                        "Validation targets extend beyond the declared validation end; the lockbox is contaminated",
                        {"max_ref_date": str(latest.date()), "validation_end": str(validation_end)},
                    )
                )

    sub = metrics[(metrics["model_id"] == model_id) & (metrics["primary"])]
    for _, row in sub.iterrows():
        if bool(row.get("satellite", False)):
            continue
        target = row["target"]
        severity = "high" if target == "ipca_12m" else "medium"
        if pd.notna(row["theil_u"]) and row["theil_u"] > 1.05:
            defects.append(
                Defect("D5", severity, f"{target} h={int(row['horizon'])} loses to random walk (Theil U={row['theil_u']:.3f})",
                       {"target": target, "horizon": int(row["horizon"]), "theil_u": float(row["theil_u"])})
            )
        if pd.notna(row["mz_slope_p"]) and row["mz_slope_p"] < 0.05:
            defects.append(
                Defect("D5", severity, f"{target} h={int(row['horizon'])} fails Mincer-Zarnowitz calibration (p={row['mz_slope_p']:.4f})",
                       {"target": target, "horizon": int(row["horizon"]), "mz_p": float(row["mz_slope_p"])})
            )
        if (
            "focus_ratio" in row
            and pd.notna(row["focus_ratio"])
            and row["focus_ratio"] > 1.0
        ):
            sig = row.get("dm_focus_p", 1.0)
            significantly_worse = (
                row["focus_ratio"] > 1.05 and pd.notna(sig) and sig < 0.10
            )
            severity = (
                "high"
                if (target == "ipca_12m" and significantly_worse)
                else "medium"
                if significantly_worse
                else "low"
            )
            defects.append(
                Defect(
                    "D5",
                    severity,
                    f"{target} h={int(row['horizon'])} does not improve on the Focus consensus "
                    f"(RMSE ratio {row['focus_ratio']:.3f}, DM p={sig:.3f})",
                    {
                        "target": target,
                        "horizon": int(row["horizon"]),
                        "focus_ratio": float(row["focus_ratio"]),
                        "dm_focus_p": float(sig) if pd.notna(sig) else None,
                    },
                )
            )
        if row["n"] < 30:
            defects.append(
                Defect("D5", "low", f"{target} h={int(row['horizon'])} has only {int(row['n'])} evaluation origins",
                       {"target": target, "n": int(row["n"])})
            )
        if pd.notna(row["direction"]) and row["direction"] < 0.45:
            defects.append(
                Defect("D5", "low", f"{target} h={int(row['horizon'])} directional accuracy below 45%",
                       {"target": target, "direction": float(row["direction"])})
            )

    nonfinite = [
        f"{block}.{k}"
        for block, vals in diag["params"].items()
        for k, v in vals.items()
        if not math.isfinite(v)
    ]
    if nonfinite:
        defects.append(Defect("D6", "high", "Non-finite parameter estimates", {"params": nonfinite}))
    return defects
