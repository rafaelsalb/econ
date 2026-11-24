from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pandas as pd

from . import config
from .backtest import run_backtest
from .critics import adequacy_critique, fidelity_critique
from .diagnostics import Defect, fit_diagnostics, forecast_sanity, irf_signs, stability
from .evaluate import evaluate
from .ingest import load_observations
from .models.new_keynesian import NewKeynesian
from .specs import hash_card, load_card, validate_card
from .vintage import Panel

VARIANTS = ["R1", "R2", "R3"]
DIAG_ORIGINS = [date(2015, 12, 31), date(2019, 12, 31)]

REVISION_TEXT = {
    "R2": (
        "Replace the gap-implied IBC-Br path in the GDP satellite bridge with an "
        "AR(1) path on monthly IBC-Br growth. The structural inflation and policy "
        "block is unchanged. Hypothesis: the GDP defect is a mapping defect, not an "
        "inflation-block defect."
    ),
    "R3": (
        "Replace lagged 12-month inflation in the Taylor rule with the Focus 12-month "
        "expectation, making the policy rule forward-looking. Keeps R2. Hypothesis: "
        "the Selic defect is a policy-response timing defect."
    ),
}


def _decide(defects: list[Defect], round_no: int, max_rounds: int) -> dict:
    high = [d for d in defects if d.severity == "high"]
    core = [d for d in defects if d.code == "D5" and d.evidence.get("target") == "ipca_12m"]
    aux = [
        d
        for d in defects
        if d.code == "D5" and d.evidence.get("target") in {"gdp_qq", "selic"}
    ]
    medium = [d for d in defects if d.severity == "medium"]

    if high:
        return {
            "status": "REVISE" if round_no < max_rounds else "REJECTED",
            "reason": "high-severity defects remain",
            "blocking": [d.to_dict() for d in high],
            "next": None,
        }
    if core:
        return {
            "status": "REVISE" if round_no < max_rounds else "REJECTED",
            "reason": "core inflation target fails",
            "blocking": [d.to_dict() for d in core],
            "next": None,
        }
    if aux:
        if round_no < max_rounds:
            targets = {d.evidence.get("target") for d in aux}
            next_variant = "R2" if "gdp_qq" in targets else "R3"
            return {
                "status": "REVISE",
                "reason": f"auxiliary target defect: {sorted(targets)}",
                "blocking": [d.to_dict() for d in aux],
                "next": next_variant,
            }
        return {
            "status": "PASS_WITH_LIMITATIONS",
            "reason": "core inflation passes; auxiliary target limitations remain after the ladder",
            "blocking": [d.to_dict() for d in aux],
            "next": None,
        }
    if medium:
        return {
            "status": "PASS_WITH_LIMITATIONS",
            "reason": "core and auxiliary gates pass; medium-severity limitations recorded",
            "limitations": [d.to_dict() for d in medium],
            "next": None,
        }
    return {"status": "PASS", "reason": "all gates pass", "next": None}


def _modeler_view(defects: list[Defect]) -> list[dict]:
    """Typed defects without numeric validation scores (binary gate, not gradient)."""
    out = []
    for d in defects:
        dd = d.to_dict()
        if dd["code"] == "D5":
            ev = dd.get("evidence", {})
            dd["evidence"] = {
                "target": ev.get("target"),
                "horizon": ev.get("horizon"),
                "gate": "fail",
            }
            dd["message"] = (
                f"{ev.get('target')} h={ev.get('horizon')} fails the forecast gate"
            )
        out.append(dd)
    return out


def _packets(out: Path, card: dict, card_hash: str, round_no: int, variant: str,
             defects: list[Defect], decision: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    blind = [d.to_dict() for d in defects]
    modeler = _modeler_view(defects)
    (out / "critic_packet.md").write_text(
        "# Blind critic packet\n\n"
        f"Model card hash: `{card_hash}`\n\n"
        f"Round: {round_no} · variant: {variant}\n\n"
        "You see only the frozen card, the code, and the diagnostics. You do not see "
        "the modeler's rationale or the validation score table.\n\n"
        "## Typed defects\n\n```json\n"
        + json.dumps(blind, indent=2)
        + "\n```\n"
    )
    (out / "modeler_packet.md").write_text(
        "# Modeler packet\n\n"
        f"Round: {round_no} · variant: {variant}\n\n"
        "You receive typed defects only, with no numeric validation scores. You may "
        "apply one revision from the pre-registered ladder in the card; you may not "
        "add variables or change the estimation sample.\n\n"
        "## Defects\n\n```json\n"
        + json.dumps(modeler, indent=2)
        + "\n```\n"
    )
    (out / "theorist_packet.md").write_text(
        "# Theorist packet\n\n"
        f"Frozen card: `specs/{card['model_id']}.yaml` (sha256 `{card_hash}`)\n\n"
        f"Round {round_no} decision: **{decision['status']}** — {decision.get('reason','')}\n\n"
        "If the loop continues, the only admissible revision is the next rung of the "
        "pre-registered ladder. The card itself is not editable inside the loop.\n"
    )


def _run_advisory(
    model_id: str,
    card: dict,
    card_hash: str,
    out: Path,
    defects: list[Defect],
    nk_metrics: pd.DataFrame,
    run_id: str,
    round_no: int,
    variant: str,
) -> list[dict]:
    """Run the sandboxed LLM critics. Advisory only: the mechanical gate decides."""
    from .sandbox import run_agent

    gate = []
    for _, row in nk_metrics[nk_metrics["primary"]].iterrows():
        passed = bool(
            pd.notna(row["theil_u"])
            and row["theil_u"] <= 1.05
            and pd.notna(row["mz_slope_p"])
            and row["mz_slope_p"] >= 0.05
        )
        gate.append(
            {
                "target": row["target"],
                "horizon": int(row["horizon"]),
                "pass": passed,
            }
        )
    advisory_dir = out / "advisory"
    advisory_dir.mkdir(parents=True, exist_ok=True)
    (advisory_dir / "metrics_gate.json").write_text(json.dumps(gate, indent=2))

    packet = (
        f"# Advisory critic packet — round {round_no}\n\n"
        f"Model: {model_id} · variant: {variant} · card hash: `{card_hash}`\n\n"
        "The mechanical gate is authoritative. Your role is advisory: return "
        "typed defects and a recommendation, but do not claim to grant PASS.\n\n"
        "Files in /workspace/in: spec.yaml, defects.json, diagnostics.json, "
        "metrics_gate.json (pass/fail only), src/ (code snapshot).\n"
    )
    inputs = {
        "spec.yaml": config.SPECS / f"{model_id}.yaml",
        "defects.json": out / "defects.json",
        "diagnostics.json": out / "diagnostics.json",
        "metrics_gate.json": advisory_dir / "metrics_gate.json",
        "src": config.ROOT / "src" / "econ",
    }

    results = []
    for role in ["critic_fidelity", "critic_adequacy"]:
        record = {"role": role, "status": "skipped"}
        try:
            res = run_agent(
                role,
                f"{run_id}-r{round_no}",
                inputs=inputs,
                packet=packet,
            )
            result_file = res.workspace.outbox / "result.json"
            if res.exit_code == 0 and result_file.exists():
                payload = json.loads(result_file.read_text())
                (advisory_dir / f"{role}.json").write_text(
                    json.dumps(payload, indent=2)
                )
                record.update(
                    {
                        "status": "ok",
                        "exit_code": res.exit_code,
                        "audit": str(res.audit_path),
                        "n_defects": len(payload.get("defects", [])),
                    }
                )
            else:
                record.update(
                    {
                        "status": "error",
                        "exit_code": res.exit_code,
                        "audit": str(res.audit_path),
                        "stderr_tail": res.stderr()[-800:],
                    }
                )
        except Exception as exc:  # noqa: BLE001
            record.update({"status": "skipped", "error": f"{type(exc).__name__}: {exc}"})
        results.append(record)
        print(f"  advisory {role}: {record['status']}")
    (advisory_dir / "summary.json").write_text(json.dumps(results, indent=2))
    return results


def run_loop(
    model_id: str = "new_keynesian",
    start: date = date.fromisoformat(config.VALIDATION_START),
    end: date = date.fromisoformat(config.VALIDATION_END),
    max_rounds: int = 3,
    agents: bool = False,
) -> dict:
    card = load_card(model_id)
    problems = validate_card(card)
    if problems:
        raise ValueError(f"invalid card: {problems}")
    card_hash = hash_card(model_id)

    obs = load_observations()
    loop_dir = config.RUNS / "loop" / model_id
    loop_dir.mkdir(parents=True, exist_ok=True)
    history = []
    final = None

    for round_no, variant in enumerate(VARIANTS[:max_rounds], start=1):
        print(f"loop round {round_no}: {variant}")
        ctx, fc = run_backtest(
            ["random_walk", "focus_consensus", model_id],
            start,
            end,
            model_kwargs={model_id: {"variant": variant}},
        )
        metrics = evaluate(fc[fc["run_id"] == ctx.run_id], obs)
        nk_metrics = metrics[metrics["model_id"] == model_id]

        diags = {str(o): fit_diagnostics(Panel.build(o, obs), variant) for o in DIAG_ORIGINS}
        diag_late = diags[str(DIAG_ORIGINS[-1])]
        stab = stability(diags[str(DIAG_ORIGINS[0])], diag_late)
        irf = irf_signs(diag_late["params"])

        sanity_rows = NewKeynesian(variant=variant).forecast(Panel.build(DIAG_ORIGINS[-1], obs))
        sanity = forecast_sanity(sanity_rows)

        defects = fidelity_critique(diag_late, irf, card)
        defects += adequacy_critique(diag_late, nk_metrics, stab, card=card)
        if not all(v["in_range"] for v in sanity.values()):
            defects.append(
                Defect("D6", "high", "Forecast path outside admissible range", {"sanity": sanity})
            )

        decision = _decide(defects, round_no, max_rounds)
        out = loop_dir / f"round-{round_no}"
        _packets(out, card, card_hash, round_no, variant, defects, decision)
        (out / "diagnostics.json").write_text(
            json.dumps({"late": diag_late, "stability": stab, "irf": irf, "sanity": sanity}, indent=2)
        )
        (out / "defects.json").write_text(json.dumps([d.to_dict() for d in defects], indent=2))
        # The score table is stored for the human, not passed to the modeler packet.
        nk_metrics.to_csv(out / "metrics.csv", index=False)
        (out / "decision.json").write_text(json.dumps(decision, indent=2))

        advisory: list[dict] = []
        if agents:
            advisory = _run_advisory(
                model_id,
                card,
                card_hash,
                out,
                defects,
                nk_metrics,
                ctx.run_id,
                round_no,
                variant,
            )

        entry = {
            "round": round_no,
            "variant": variant,
            "run_id": ctx.run_id,
            "status": decision["status"],
            "reason": decision.get("reason"),
            "n_high": sum(d.severity == "high" for d in defects),
            "n_medium": sum(d.severity == "medium" for d in defects),
            "defect_codes": sorted({d.code for d in defects}),
            "core": nk_metrics[
                (nk_metrics["target"] == "ipca_12m")
                & (nk_metrics["horizon"].isin([6, 12]))
            ][["horizon", "theil_u", "mz_slope_p"]].to_dict(orient="records"),
            "advisory": advisory,
        }
        history.append(entry)
        final = {**decision, "round": round_no, "variant": variant, "run_id": ctx.run_id}

        if decision["status"] in {"PASS", "PASS_WITH_LIMITATIONS", "REJECTED", "UNESTIMABLE", "UNRESOLVED"}:
            break
        if decision["status"] == "REVISE" and not decision.get("next"):
            final = {
                **decision,
                "status": "REJECTED",
                "round": round_no,
                "variant": variant,
                "run_id": ctx.run_id,
                "reason": decision.get("reason", "") + "; no admissible revision targets the blocking defect",
            }
            break
        if decision.get("next"):
            (out / "revision.json").write_text(
                json.dumps(
                    {
                        "next_round": round_no + 1,
                        "applied": decision["next"],
                        "hypothesis": REVISION_TEXT.get(decision["next"], ""),
                    },
                    indent=2,
                )
            )

    result = {
        "model_id": model_id,
        "card_hash": card_hash,
        "validation_window": [str(start), str(end)],
        "max_rounds": max_rounds,
        "history": history,
        "terminal": final,
    }
    (loop_dir / "decision.json").write_text(json.dumps(result, indent=2))
    (config.SPECS / f"{model_id}.decision.json").write_text(json.dumps(result, indent=2))
    return result
