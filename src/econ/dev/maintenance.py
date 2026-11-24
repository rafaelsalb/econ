from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .artifacts import write_json
from .report import daily_digest, write_dashboard


def _run(repo: Path, argv: list[str], timeout: int = 900) -> dict:
    proc = subprocess.run(
        argv, cwd=repo, capture_output=True, text=True, timeout=timeout, check=False
    )
    return {
        "command": " ".join(argv),
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
    }


def run_maintenance(
    repo: Path,
    *,
    create_issue: bool = False,
    skip_tests: bool = False,
) -> dict:
    """Run the deterministic local checks and write a maintenance report.

    This is what the nightly workflow runs. It never edits code or opens a
    ready task automatically: failures become an issue for triage, so a red
    pipeline cannot silently generate a plausible "fix".
    """
    checks = []
    if not skip_tests:
        checks.append(_run(repo, [sys.executable, "-m", "pytest", "-q"]))
    checks.append(_run(repo, [sys.executable, "-m", "econ.cli", "check"]))
    checks.append(_run(repo, [sys.executable, "-m", "econ.cli", "agents", "check"]))
    checks.append(_run(repo, [sys.executable, "-m", "econ.cli", "dev", "agents", "check"]))
    checks.append(_run(repo, [sys.executable, "-m", "econ.cli", "dev", "validate", "--all"]))
    failed = [check for check in checks if check["exit_code"] != 0]
    dashboard = write_dashboard(repo)
    digest = daily_digest(repo, days=1)
    report_path = repo / "reports" / "dev_maintenance.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Development maintenance",
        "",
        f"Checks: {len(checks) - len(failed)} passed, {len(failed)} failed.",
        "",
    ]
    for check in checks:
        mark = "PASS" if check["exit_code"] == 0 else "FAIL"
        lines.append(f"- [{mark}] `{check['command']}` (exit {check['exit_code']})")
    lines += ["", digest]
    report_path.write_text("\n".join(lines))
    info = {
        "ok": not failed,
        "failed": [check["command"] for check in failed],
        "checks": checks,
        "report": str(report_path),
        "dashboard": dashboard["html"],
        "issue": None,
    }
    if failed and create_issue:
        body = (
            "The scheduled development gate failed.\n\n"
            + "\n".join(f"- `{check['command']}` exit {check['exit_code']}" for check in failed)
            + f"\n\nSee `{report_path}`."
        )
        proc = subprocess.run(
            [
                "gh",
                "issue",
                "create",
                "--title",
                "dev maintenance gate failed",
                "--body",
                body,
                "--label",
                "dev:maintenance",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        info["issue"] = {
            "exit_code": proc.returncode,
            "url": proc.stdout.strip(),
            "stderr": proc.stderr.strip()[-1000:],
        }
    write_json(repo / "runs" / "dev" / "maintenance.json", info)
    return info
