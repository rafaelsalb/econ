from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from .. import config
from .artifacts import write_json
from .canary import run_canaries, run_smoke, validate_canaries
from .locks import PauseSwitch
from .maintenance import run_maintenance
from .models import Task, validate_task
from .pipeline import DevPipeline
from .policy import load_policy, policy_path
from .release import release, read_version
from .report import dashboard_markdown, daily_digest, metrics, write_dashboard
from .runner import runner_for
from .scheduler import DevScheduler
from .sync import GitHubSyncError, sync_pull, sync_push
from .tasks import TaskStore, new_task_payload, promote_task
from .workspace import current_branch, is_clean


def _json(payload) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _repo() -> Path:
    return config.ROOT


def _store() -> TaskStore:
    store = TaskStore(_repo())
    store.ensure()
    return store


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "dev", help="multi-agent development pipeline and scheduler"
    )
    sp = p.add_subparsers(dest="dev_action", required=True)

    agents = sp.add_parser("agents", help="render and validate the development roster")
    agents.add_argument("action", choices=["render", "check", "list", "validate"])

    validate = sp.add_parser("validate", help="validate task contracts")
    validate.add_argument("task", nargs="?", help="task id or YAML path")
    validate.add_argument("--all", action="store_true", help="validate every task")
    validate.add_argument("--canaries", action="store_true", help="also validate canaries")

    listing = sp.add_parser("list", help="list task contracts")
    listing.add_argument("--json", action="store_true")

    run = sp.add_parser("run", help="run one task through the full pipeline")
    run.add_argument("--task", required=True)
    run.add_argument("--shadow", action="store_true", help="run without merging")
    run.add_argument("--no-auto-merge", action="store_true")
    run.add_argument("--fake", action="store_true", help="use the deterministic fake runner")
    run.add_argument("--executor", choices=["local", "docker"], default="local")
    run.add_argument("--base", default=None)
    run.add_argument("--json", action="store_true")

    daemon = sp.add_parser("daemon", help="run the autonomous scheduler")
    daemon.add_argument("--once", action="store_true")
    daemon.add_argument("--max-parallel", type=int, default=1)
    daemon.add_argument("--max-tasks", type=int, default=None)
    daemon.add_argument("--daily-budget", type=float, default=None)
    daemon.add_argument("--sleep", type=int, default=60)
    daemon.add_argument("--fake", action="store_true")
    daemon.add_argument("--shadow", action="store_true")
    daemon.add_argument("--no-auto-merge", action="store_true")
    daemon.add_argument("--executor", choices=["local", "docker"], default="local")
    daemon.add_argument("--sync", action="store_true", help="import dev:ready issues each tick")

    status = sp.add_parser("status", help="show scheduler and queue status")
    status.add_argument("--json", action="store_true")

    pause = sp.add_parser("pause", help="pause the scheduler")
    pause.add_argument("--reason", default="")
    resume = sp.add_parser("resume", help="resume the scheduler")

    report = sp.add_parser("report", help="write the development dashboard")
    report.add_argument("--write", action="store_true")
    report.add_argument("--json", action="store_true")
    report.add_argument("--digest", action="store_true")
    report.add_argument("--days", type=int, default=1)

    sync = sp.add_parser("sync", help="sync task contracts with GitHub issues")
    sync.add_argument("--pull", action="store_true")
    sync.add_argument("--push", action="store_true")
    sync.add_argument("--promote", action="store_true")
    sync.add_argument("--no-promote", action="store_true")
    sync.add_argument("--label", default=None)

    canary = sp.add_parser("canary", help="validate or run the held-out canaries")
    canary.add_argument("--validate", action="store_true")
    canary.add_argument("--run", action="store_true")
    canary.add_argument("--only", default=None)
    canary.add_argument("--keep", action="store_true")
    canary.add_argument("--fake", action="store_true", default=True)
    canary.add_argument(
        "--promote",
        default=None,
        metavar="ID",
        help="human step: promote a generated canary into the suite",
    )

    smoke = sp.add_parser("smoke", help="end-to-end fake-agent pipeline smoke test")
    smoke.add_argument("--keep", action="store_true")

    rel = sp.add_parser("release", help="deterministic version bump, changelog and tag")
    rel.add_argument("--bump", choices=["patch", "minor", "major"], default="patch")
    rel.add_argument("--dry-run", action="store_true")
    rel.add_argument("--message", default=None)
    rel.add_argument("--skip-check", action="store_true")
    rel.add_argument("--allow-dirty", action="store_true")

    doctor = sp.add_parser("doctor", help="check the local development environment")

    new = sp.add_parser("new", help="create a proposed task contract")
    new.add_argument("--title", required=True)
    new.add_argument("--goal", required=True)
    new.add_argument("--acceptance", action="append", required=True)
    new.add_argument("--allow", action="append", required=True)
    new.add_argument("--risk", type=int, choices=[0, 1, 2, 3], default=1)
    new.add_argument("--priority", type=int, default=50)
    new.add_argument("--json", action="store_true")

    promote = sp.add_parser(
        "promote", help="validate a proposed contract and move it to tasks/ready"
    )
    promote.add_argument("task", help="task id or YAML path")
    promote.add_argument("--json", action="store_true")

    maintenance = sp.add_parser(
        "maintenance", help="run the deterministic maintenance gate and digest"
    )
    maintenance.add_argument("--create-issue", action="store_true")
    maintenance.add_argument("--skip-tests", action="store_true")
    maintenance.add_argument("--json", action="store_true")

    p.set_defaults(func=dispatch)


def dispatch(args: argparse.Namespace) -> None:
    action = getattr(args, "dev_action", None)
    if action == "agents":
        _agents(args)
    elif action == "validate":
        _validate(args)
    elif action == "list":
        _list(args)
    elif action == "run":
        _run(args)
    elif action == "daemon":
        _daemon(args)
    elif action == "status":
        _status(args)
    elif action == "pause":
        _pause(args)
    elif action == "resume":
        _resume(args)
    elif action == "report":
        _report(args)
    elif action == "sync":
        _sync(args)
    elif action == "canary":
        _canary(args)
    elif action == "smoke":
        _smoke(args)
    elif action == "release":
        _release(args)
    elif action == "doctor":
        _doctor(args)
    elif action == "new":
        _new(args)
    elif action == "promote":
        _promote(args)
    elif action == "maintenance":
        _maintenance(args)
    else:
        raise SystemExit(f"unknown dev action: {action}")


def _agents(args: argparse.Namespace) -> None:
    from ..agents import (
        check_dev_all,
        dev_agents,
        load_dev_config,
        validate_dev_variants,
        write_dev_all,
    )

    if args.action == "render":
        for path in write_dev_all():
            print(path)
    elif args.action == "check":
        problems = check_dev_all()
        print("dev agents up to date" if not problems else "\n".join(problems))
        if problems:
            raise SystemExit(1)
    elif args.action == "list":
        for spec in dev_agents(load_dev_config()):
            print(
                f"{spec.agent_id:26s} {spec.mode:9s} {spec.selector:44s} "
                f"hidden={spec.hidden} steps={spec.steps}"
            )
    elif args.action == "validate":
        problems = validate_dev_variants()
        print("dev model variants valid" if not problems else "\n".join(problems))
        if problems and all("catalog cache unavailable" not in p for p in problems):
            raise SystemExit(1)


def _validate(args: argparse.Namespace) -> None:
    policy = load_policy(_repo())
    store = _store()
    problems: list[str] = []
    if args.task:
        try:
            task = (
                store.load_path(Path(args.task))
                if args.task.endswith(".yaml")
                else store.load(args.task)
            )
            problems.extend(validate_task(task, policy))
        except Exception as exc:  # noqa: BLE001
            problems.append(str(exc))
    else:
        problems = store.validate_all(policy)
    if args.canaries:
        problems.extend(validate_canaries(_repo(), policy))
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        raise SystemExit(1)
    print("tasks valid")


def _list(args: argparse.Namespace) -> None:
    tasks = _store().all()
    if args.json:
        _json([task.model_dump(mode="json", exclude_none=True) for task in tasks])
        return
    if not tasks:
        print("no tasks")
        return
    print(f"{'ID':12s} {'STATUS':10s} {'RISK':4s} {'PRI':3s} TITLE")
    for task in sorted(tasks, key=lambda t: (t.status, t.id)):
        print(f"{task.id:12s} {task.status:10s} {task.risk:<4d} {task.priority:<3d} {task.title}")


def _run(args: argparse.Namespace) -> None:
    policy = load_policy(_repo())
    if args.fake:
        runner = runner_for(_repo(), "fake")
    elif args.executor == "docker":
        runner = runner_for(_repo(), "docker")
    else:
        runner = runner_for(_repo(), "opencode")
    pipeline = DevPipeline(
        _repo(),
        policy,
        runner=runner,
        shadow=args.shadow,
        auto_merge=not args.no_auto_merge,
        base=args.base,
        executor=args.executor,
    )
    outcome = pipeline.run_task(args.task)
    if args.json:
        _json(outcome.as_dict())
    else:
        print(
            f"task={outcome.task_id} status={outcome.status} "
            f"rounds={outcome.rounds} commit={outcome.commit} "
            f"run={outcome.run_dir}"
        )
        print(outcome.decision.get("reason", ""))
    if outcome.status in {"failed"}:
        raise SystemExit(1)


def _daemon(args: argparse.Namespace) -> None:
    scheduler = DevScheduler(
        _repo(),
        load_policy(_repo()),
        runner_kind="fake" if args.fake else "opencode",
        executor=args.executor,
        shadow=args.shadow,
        auto_merge=not args.no_auto_merge,
        max_parallel=args.max_parallel,
        daily_usd=args.daily_budget,
        sync_github=args.sync,
    )
    outcomes = scheduler.loop(
        interval_s=args.sleep, once=args.once, max_tasks=args.max_tasks
    )
    _json([outcome.as_dict() for outcome in outcomes])


def _status(args: argparse.Namespace) -> None:
    status = DevScheduler(_repo(), load_policy(_repo())).status()
    if args.json:
        _json(status)
        return
    print(f"paused: {status['paused']}")
    print(f"ready: {', '.join(status['ready']) or '(none)'}")
    print(f"active: {', '.join(status['active']) or '(none)'}")
    print(f"lock: {status['lock']}")
    print(f"budget: {status['budget']}")


def _pause(args: argparse.Namespace) -> None:
    path = PauseSwitch(_repo()).pause(args.reason)
    print(f"paused: {path}")


def _resume(args: argparse.Namespace) -> None:
    print("resumed" if PauseSwitch(_repo()).resume() else "not paused")


def _report(args: argparse.Namespace) -> None:
    if args.digest:
        print(daily_digest(_repo(), days=args.days))
        return
    if args.write:
        info = write_dashboard(_repo())
        if args.json:
            _json(info)
        else:
            print(info["markdown"])
            print(f"wrote {info['html']}")
        return
    if args.json:
        _json(metrics(_repo()))
    else:
        print(dashboard_markdown(_repo()))


def _sync(args: argparse.Namespace) -> None:
    policy = load_policy(_repo())
    store = _store()
    do_pull = args.pull or not args.push
    promote = None
    if args.promote:
        promote = True
    elif args.no_promote:
        promote = False
    try:
        out = {}
        if do_pull:
            out["pull"] = sync_pull(
                _repo(), policy, store, label=args.label, promote=promote
            )
        if args.push:
            out["push"] = sync_push(_repo(), policy, store)
    except GitHubSyncError as exc:
        raise SystemExit(str(exc)) from exc
    _json(out)


def _canary(args: argparse.Namespace) -> None:
    if args.promote:
        from .canary import promote_canary

        try:
            canary, path = promote_canary(_repo(), args.promote, load_policy(_repo()))
        except ValueError as exc:
            raise SystemExit(f"promote failed: {exc}") from exc
        print(f"promoted {canary.id} into the suite: {path}")
        return
    if args.run:
        results = run_canaries(
            _repo(), only=args.only, keep=args.keep, fake=args.fake
        )
        _json(results)
        if not all(result.get("ok") for result in results):
            raise SystemExit(1)
        return
    policy = load_policy(_repo())
    problems = validate_canaries(_repo(), policy)
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        raise SystemExit(1)
    print("canaries valid")


def _smoke(args: argparse.Namespace) -> None:
    result = run_smoke(_repo(), keep=args.keep)
    _json(result)
    if not result.get("ok"):
        raise SystemExit(1)


def _release(args: argparse.Namespace) -> None:
    try:
        info = release(
            _repo(),
            bump=args.bump,
            dry_run=args.dry_run,
            message=args.message,
            check=not args.skip_check,
            allow_dirty=args.allow_dirty,
        )
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(str(exc)) from exc
    _json(info)


def _doctor(args: argparse.Namespace) -> None:
    repo = _repo()
    checks: list[tuple[str, bool, str]] = []
    checks.append(("git repository", (repo / ".git").exists(), str(repo)))
    checks.append(("policy file", policy_path(repo).exists(), str(policy_path(repo))))
    try:
        policy = load_policy(repo)
        checks.append(("policy loads", True, f"{len(policy.protected)} protected paths"))
    except Exception as exc:  # noqa: BLE001
        policy = None
        checks.append(("policy loads", False, str(exc)))
    try:
        branch = current_branch(repo)
        checks.append(("branch", branch == "main", branch))
    except Exception as exc:  # noqa: BLE001
        checks.append(("branch", False, str(exc)))
    checks.append(
        (
            "worktree",
            True,
            "clean" if is_clean(repo) else "dirty (expected during active development)",
        )
    )
    checks.append(("venv", (repo / ".venv" / "bin" / "python").exists(), ".venv/bin/python"))
    checks.append(("opencode", shutil.which("opencode") is not None, shutil.which("opencode") or "missing"))
    docker = shutil.which("docker") is not None
    checks.append(("docker", docker, "available; container executor optional" if docker else "missing; local executor still works"))
    try:
        problems = _store().validate_all(policy)
        checks.append(("tasks", not problems, "; ".join(problems[:3]) or "all valid"))
    except Exception as exc:  # noqa: BLE001
        checks.append(("tasks", False, str(exc)))
    from ..agents import check_dev_all, validate_dev_variants

    try:
        problems = check_dev_all()
        checks.append(("dev agents", not problems, "; ".join(problems[:3]) or "rendered"))
    except Exception as exc:  # noqa: BLE001
        checks.append(("dev agents", False, str(exc)))
    try:
        problems = validate_dev_variants()
        cache_warning = any("catalog cache unavailable" in p for p in problems)
        checks.append(("dev variants", not problems or cache_warning, "; ".join(problems) or "valid"))
    except Exception as exc:  # noqa: BLE001
        checks.append(("dev variants", False, str(exc)))

    failed = [name for name, ok, _ in checks if not ok]
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if failed:
        raise SystemExit(1)


def _promote(args: argparse.Namespace) -> None:
    store = _store()
    policy = load_policy(_repo())
    try:
        task, path = promote_task(store, args.task, policy)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"promote failed: {exc}") from exc
    if args.json:
        _json(
            {
                "task_id": task.id,
                "status": task.status,
                "path": str(path),
                "next": [
                    f"econ dev run --task {task.id} --shadow",
                    f"econ dev run --task {task.id}",
                ],
            }
        )
        return
    print(f"task={task.id} status={task.status} path={path}")
    print(f"safe dry run: econ dev run --task {task.id} --shadow")
    print(f"real run:    econ dev run --task {task.id}")


def _maintenance(args: argparse.Namespace) -> None:
    info = run_maintenance(
        _repo(),
        create_issue=args.create_issue,
        skip_tests=args.skip_tests,
    )
    if args.json:
        _json(info)
    else:
        print(f"maintenance ok={info['ok']}")
        for check in info["checks"]:
            print(f"  exit={check['exit_code']} {check['command']}")
        print(f"report: {info['report']}")
    if not info["ok"]:
        raise SystemExit(1)


def _new(args: argparse.Namespace) -> None:
    store = _store()
    task_id = store.next_id("DEV")
    payload = new_task_payload(
        task_id=task_id,
        title=args.title,
        goal=args.goal,
        acceptance=args.acceptance,
        allow=args.allow,
        risk=args.risk,
        priority=args.priority,
        status="proposed",
    )
    task = Task.model_validate(payload)
    policy = load_policy(_repo())
    problems = validate_task(task, policy)
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        raise SystemExit(1)
    store.save(task)
    path = store.path_for(task)
    if args.json:
        _json(task.model_dump(mode="json", exclude_none=True))
    else:
        print(path)
