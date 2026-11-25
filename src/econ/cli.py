from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from . import config
from .backtest import model_registry, run_backtest
from .checks import print_checks
from .diagnostics import fit_diagnostics
from .evaluate import evaluate, episode_metrics, summary_by_model, write_outputs
from .ingest import load_observations
from .loop import run_generic_loop, run_loop
from .registry import read_forecasts
from .specs import hash_card, load_card, validate_card
from .vintage import Panel


def _load_key(path: str | None, env_var: str) -> None:
    if not path:
        return
    key_path = Path(path).expanduser()
    if not key_path.exists():
        raise SystemExit(f"api key file not found: {key_path}")
    mode = key_path.stat().st_mode
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        print(
            f"warning: {key_path} is group/world readable; chmod 600 is recommended",
            file=sys.stderr,
        )
    key = key_path.read_text().strip()
    if not key:
        raise SystemExit(f"api key file is empty: {key_path}")
    os.environ[env_var] = key


def _load_api_key(path: str | None) -> None:
    """Load an OpenCode key from a file without printing it."""
    _load_key(path, "OPENCODE_API_KEY")


def _load_anthropic_key(path: str | None) -> None:
    """Load an Anthropic key from a file without printing it."""
    _load_key(path, "ANTHROPIC_API_KEY")


def _latest_per_model(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    meta = df[["model_id", "run_id", "produced_at"]].drop_duplicates().copy()
    meta["produced_at"] = pd.to_datetime(meta["produced_at"])
    idx = meta.groupby("model_id")["produced_at"].idxmax()
    pairs = meta.loc[idx, ["model_id", "run_id"]]
    return df.merge(pairs, on=["model_id", "run_id"], how="inner").reset_index(drop=True)


def cmd_ingest(args) -> None:
    from .ingest import build, write_manifest

    obs = build()
    manifest = write_manifest(obs)
    print(f"rows={len(obs)} hash={manifest['sha256']}")


def cmd_backtest(args) -> None:
    models = list(model_registry()) if args.models == "all" else args.models.split(",")
    ctx, df = run_backtest(
        models,
        date.fromisoformat(args.start),
        date.fromisoformat(args.end),
        seed=args.seed,
        force=args.force,
    )
    print(f"run_id={ctx.run_id} rows={len(df)}")
    print(df.groupby(["model_id", "target"]).size().to_string())


def cmd_score(args) -> None:
    fc = read_forecasts()
    if args.run_id:
        fc = fc[fc["run_id"] == args.run_id]
    else:
        fc = _latest_per_model(fc)
    obs = load_observations()
    validation_end = date.fromisoformat(
        config.LOCKBOX_END if args.lockbox else config.VALIDATION_END
    )
    metrics = evaluate(fc, obs, validation_end=validation_end)
    episodes = episode_metrics(fc, obs, validation_end=validation_end)
    write_outputs(metrics, episodes)
    print(summary_by_model(metrics).to_string(index=False))
    print(f"\nwrote {config.EVAL / 'scoreboard.md'}")


def cmd_panel(args) -> None:
    obs = load_observations()
    panel = Panel.build(date.fromisoformat(args.origin), obs)
    print(f"origin={panel.origin} visible_rows={len(panel.obs)}")
    for sid in [
        "ipca_m",
        "ibc_br",
        "selic_target",
        "fx_usdbrl",
        "focus_ipca_12m",
        "gdp_qq",
    ]:
        print(f"  {sid:18s} latest={panel.latest(sid)}")


def cmd_web(args) -> None:
    import uvicorn

    from .web import app

    uvicorn.run(app, host=args.host, port=args.port)


def cmd_console(args) -> None:
    import uvicorn

    from .webui.app import app

    uvicorn.run(app, host=args.host, port=args.port)


def cmd_loop(args) -> None:
    _load_api_key(getattr(args, "api_key_file", None))
    _load_anthropic_key(getattr(args, "anthropic_key_file", None))
    if args.model == "new_keynesian":
        res = run_loop(
            model_id=args.model,
            start=date.fromisoformat(args.start),
            end=date.fromisoformat(args.end),
            max_rounds=args.max_rounds,
            agents=args.agents,
        )
    else:
        res = run_generic_loop(
            model_id=args.model,
            start=date.fromisoformat(args.start),
            end=date.fromisoformat(args.end),
        )
    t = res["terminal"]
    print(f"terminal={t['status']} round={t['round']} variant={t['variant']} run={t['run_id']}")
    for h in res["history"]:
        print(f"  round {h['round']} {h['variant']}: {h['status']} ({h['n_high']} high, {h['n_medium']} medium)")


def cmd_agents(args) -> None:
    from .agents import (
        agents as list_agents,
        check_all,
        load_config,
        validate_runtime_config,
        validate_variants,
        write_all,
    )

    if args.action == "render":
        for path in write_all():
            print(path)
        return
    if args.action == "check":
        problems = check_all()
        problems += validate_runtime_config(load_config())
        print("agents up to date" if not problems else "\n".join(problems))
        raise SystemExit(0 if not problems else 1)
    if args.action == "list":
        for spec in list_agents(load_config()):
            model = (
                f"{spec.claude_model}#{spec.claude_effort or 'default'}"
                if spec.runtime == "claude"
                else spec.selector
            )
            print(
                f"{spec.agent_id:24s} {spec.runtime:8s} {model:48s} "
                f"sandbox={spec.sandbox:8s} steps={spec.steps}"
            )
        return
    if args.action == "validate":
        problems = validate_variants() + validate_runtime_config(load_config())
        print("model variants valid" if not problems else "\n".join(problems))
        raise SystemExit(0 if not problems else 1)


def cmd_sandbox(args) -> None:
    from pathlib import Path

    from .sandbox import (
        build_image,
        docker_available,
        project_workspace,
        run_agent,
        run_in_sandbox,
        setup_networks,
    )

    if args.action == "build":
        result = build_image()
        print(result.stdout[-4000:])
        print(result.stderr[-4000:], file=__import__("sys").stderr)
        raise SystemExit(result.returncode)
    if args.action == "setup":
        result = setup_networks()
        print(result.stdout)
        print(result.stderr, file=__import__("sys").stderr)
        raise SystemExit(result.returncode)
    if args.action == "smoke":
        ws = project_workspace("smoke", "smoke", packet="sandbox smoke")
        argv = [
            "python",
            "-c",
            "import pandas, numpy, statsmodels, pyarrow; print('sandbox ok')",
        ]
        res = run_in_sandbox(ws, argv, network="none", timeout_s=180)
        print(f"docker={docker_available()} exit={res.exit_code} audit={res.audit_path}")
        print(res.stdout())
        print(res.stderr(), file=__import__("sys").stderr)
        raise SystemExit(0 if res.exit_code == 0 else 1)
    if args.action == "run":
        _load_api_key(args.api_key_file)
        _load_anthropic_key(getattr(args, "anthropic_key_file", None))
        inputs = {}
        for item in args.input or []:
            dest, src = item.split("=", 1)
            inputs[dest] = src
        packet = Path(args.packet_file).read_text() if args.packet_file else args.packet
        res = run_agent(
            args.role,
            args.run_id,
            inputs=inputs,
            packet=packet,
            network=args.network,
        )
        print(f"exit={res.exit_code} audit={res.audit_path}")
        result_path = res.workspace.outbox / "result.json"
        if result_path.exists():
            print(result_path.read_text())
        else:
            print(res.stdout()[-3000:])
            print(res.stderr()[-3000:], file=__import__("sys").stderr)
        raise SystemExit(0 if res.exit_code == 0 else 1)


def cmd_ensemble(args) -> None:
    from .ensemble import build_ensembles_and_report

    info = build_ensembles_and_report()
    print(info["scoreboard"].to_string(index=False))
    print(f"\nweights: {len(info['weights'])} cells")
    print(f"wrote {config.EVAL / 'ensemble_scoreboard.csv'}")


def cmd_lockbox(args) -> None:
    from .lockbox import build_final_report, lockbox_status, open_lockbox

    if args.action == "status":
        status = lockbox_status()
        print(json.dumps(status, indent=2) if status else "lockbox not opened")
        return
    info = open_lockbox(force=args.force, reason=args.reason or "")
    print(json.dumps(info, indent=2))


def cmd_final_report(args) -> None:
    from .lockbox import build_final_report

    path = build_final_report()
    print(path)


def cmd_report(args) -> None:
    from .report import build_report

    info = build_report()
    print(json.dumps(info, indent=2))


def cmd_check(args) -> None:
    ok = print_checks()
    raise SystemExit(0 if ok else 1)


def cmd_spec(args) -> None:
    card = load_card(args.model)
    problems = validate_card(card)
    print(f"model={args.model} hash={hash_card(args.model)}")
    print("valid" if not problems else f"invalid: {problems}")
    raise SystemExit(0 if not problems else 1)


def cmd_audit(args) -> None:
    obs = load_observations()
    diag = fit_diagnostics(Panel.build(date.fromisoformat(args.origin), obs), args.variant)
    print(json.dumps(diag, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="econ", description="Brazil macro model hub")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest", help="fetch and curate all catalog series")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("backtest", help="run models over monthly origins")
    p.add_argument("--models", default="all")
    p.add_argument("--start", default=config.VALIDATION_START)
    p.add_argument("--end", default=config.VALIDATION_END)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_backtest)

    p = sub.add_parser("score", help="evaluate registry forecasts")
    p.add_argument("--run-id", default=None)
    p.add_argument("--lockbox", action="store_true", help="evaluate through the lockbox end")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("panel", help="inspect an as-of data slice")
    p.add_argument("--origin", required=True)
    p.set_defaults(func=cmd_panel)

    p = sub.add_parser("web", help="serve the read-only local dashboard")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_web)

    p = sub.add_parser("console", help="serve the local development console shell")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8100)
    p.set_defaults(func=cmd_console)

    p = sub.add_parser("loop", help="run the school-model critic loop")
    p.add_argument("--model", default="new_keynesian")
    p.add_argument("--start", default=config.VALIDATION_START)
    p.add_argument("--end", default=config.VALIDATION_END)
    p.add_argument("--max-rounds", type=int, default=3)
    p.add_argument("--agents", action="store_true", help="add sandboxed LLM advisory critics")
    p.add_argument("--api-key-file", default=None, help="file containing OPENCODE_API_KEY")
    p.add_argument(
        "--anthropic-key-file",
        default=None,
        help="file containing ANTHROPIC_API_KEY for Claude-runtime agents",
    )
    p.set_defaults(func=cmd_loop)

    p = sub.add_parser("report", help="build the monthly report and chart")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("ensemble", help="build equal/performance ensembles and the fan chart")
    p.set_defaults(func=cmd_ensemble)

    p = sub.add_parser("lockbox", help="open or inspect the one-time lockbox")
    p.add_argument("action", choices=["open", "status"])
    p.add_argument("--force", action="store_true")
    p.add_argument("--reason", default="")
    p.set_defaults(func=cmd_lockbox)

    p = sub.add_parser("final-report", help="build the final cross-phase report")
    p.set_defaults(func=cmd_final_report)

    p = sub.add_parser("check", help="run the Phase 0 / Phase 1 gates")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("spec", help="validate and hash a model card")
    p.add_argument("--model", default="new_keynesian")
    p.set_defaults(func=cmd_spec)

    p = sub.add_parser("audit", help="print NK diagnostics at an origin")
    p.add_argument("--origin", required=True)
    p.add_argument("--variant", default="R1")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("agents", help="render and validate the research agents")
    p.add_argument("action", choices=["render", "check", "list", "validate"])
    p.set_defaults(func=cmd_agents)

    p = sub.add_parser("sandbox", help="build and run the agent sandbox")
    p.add_argument("action", choices=["build", "setup", "smoke", "run"])
    p.add_argument("--role", default=None)
    p.add_argument("--run-id", default="manual")
    p.add_argument("--packet-file", default=None)
    p.add_argument("--packet", default=None)
    p.add_argument("--input", action="append", default=[])
    p.add_argument("--network", choices=["offline", "data", "none"], default=None)
    p.add_argument("--api-key-file", default=None, help="file containing OPENCODE_API_KEY")
    p.add_argument(
        "--anthropic-key-file",
        default=None,
        help="file containing ANTHROPIC_API_KEY for Claude-runtime agents",
    )
    p.set_defaults(func=cmd_sandbox)

    from .dev.cli import add_parser as add_dev_parser

    add_dev_parser(sub)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
