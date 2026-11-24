from __future__ import annotations

import html
import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .artifacts import write_json

STATUS_ORDER = ["done", "shadow", "escalated", "failed", "awaiting_merge", "active"]


def load_index(repo: Path) -> list[dict]:
    path = repo / "runs" / "dev" / "index.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def canary_status(repo: Path) -> dict:
    path = repo / "runs" / "dev" / "canaries" / "latest.json"
    if not path.exists():
        return {"total": 0, "passed": 0, "failed": 0, "results": []}
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"total": 0, "passed": 0, "failed": 0, "results": []}
    results = payload.get("results") or []
    return {
        "generated_at": payload.get("generated_at"),
        "total": len(results),
        "passed": sum(1 for row in results if row.get("ok")),
        "failed": sum(1 for row in results if not row.get("ok")),
        "results": results,
    }


def metrics(repo: Path) -> dict:
    rows = load_index(repo)
    by_status = Counter(row.get("status", "unknown") for row in rows)
    by_risk = Counter(str(row.get("risk", "?")) for row in rows)
    done = [row for row in rows if row.get("status") in {"done", "shadow"}]
    merged = [row for row in rows if row.get("merged_commit")]
    first_pass = [row for row in done if int(row.get("rounds", 0)) <= 1]
    escalated = by_status.get("escalated", 0)
    failed = by_status.get("failed", 0)
    total = len(rows)
    cost = sum(float(row.get("cost_usd", 0) or 0) for row in rows)
    rounds = [int(row.get("rounds", 0)) for row in done if row.get("rounds")]
    step_limited = sum(1 for row in rows if row.get("step_limit_reached"))
    max_utilization = max(
        (float(row.get("max_step_utilization", 0.0) or 0.0) for row in rows),
        default=0.0,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": total,
        "by_status": dict(by_status),
        "by_risk": dict(by_risk),
        "merged": len(merged),
        "shadow": by_status.get("shadow", 0),
        "escalated": escalated,
        "failed": failed,
        "first_pass": len(first_pass),
        "first_pass_rate": round(len(first_pass) / len(done), 3) if done else 0.0,
        "autonomy_rate": round(len(merged) / total, 3) if total else 0.0,
        "human_intervention_rate": round(escalated / total, 3) if total else 0.0,
        "avg_rounds": round(sum(rounds) / len(rounds), 2) if rounds else 0.0,
        "cost_usd": round(cost, 6),
        "step_limited": step_limited,
        "max_step_utilization": round(max_utilization, 3),
        "recent": rows[-15:],
        "canaries": canary_status(repo),
    }


def dashboard_markdown(repo: Path) -> str:
    m = metrics(repo)
    lines = [
        "# Development dashboard",
        "",
        f"Generated: `{m['generated_at']}`",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Tasks recorded | {m['total']} |",
        f"| Merged | {m['merged']} |",
        f"| Shadow approvals | {m['shadow']} |",
        f"| Escalated to human | {m['escalated']} |",
        f"| Failed | {m['failed']} |",
        f"| First-pass rate | {m['first_pass_rate']:.1%} |",
        f"| Autonomy rate (merged / total) | {m['autonomy_rate']:.1%} |",
        f"| Human intervention rate | {m['human_intervention_rate']:.1%} |",
        f"| Average review rounds | {m['avg_rounds']} |",
        f"| Step-limited runs | {m['step_limited']} |",
        f"| Highest step utilization | {m['max_step_utilization']:.0%} |",
        f"| Recorded model cost | ${m['cost_usd']:.2f} |",
        "",
        "## By risk",
        "",
        "| Risk | Tasks |",
        "|---|---:|",
    ]
    for risk, count in sorted(m["by_risk"].items()):
        lines.append(f"| {risk} | {count} |")
    c = m["canaries"]
    lines += [
        "",
        "## Held-out canaries",
        "",
        f"Passed {c['passed']} of {c['total']}."
        + (f" Generated: `{c.get('generated_at')}`." if c.get("generated_at") else ""),
        "",
        "| Task | Result | Status | Rounds |",
        "|---|---|---|---:|",
    ]
    if c["results"]:
        for row in c["results"]:
            lines.append(
                f"| {row.get('task_id','?')} | {'PASS' if row.get('ok') else 'FAIL'} | "
                f"{row.get('status','?')} | {row.get('rounds','?')} |"
            )
    else:
        lines.append("| — | — | — | — |")
    lines += ["", "## Recent tasks", "", "| Task | Status | Risk | Rounds | Reason |", "|---|---|---:|---:|---|"]
    for row in m["recent"]:
        reason = str(row.get("reason", "")).replace("|", "\\|")[:100]
        lines.append(
            f"| {row.get('task_id','?')} | {row.get('status','?')} | "
            f"{row.get('risk','?')} | {row.get('rounds','?')} | {reason} |"
        )
    return "\n".join(lines) + "\n"


def dashboard_html(repo: Path) -> str:
    m = metrics(repo)
    rows = []
    for row in m["recent"]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('task_id','')))}</td>"
            f"<td><span class='pill {html.escape(str(row.get('status','')))}'>"
            f"{html.escape(str(row.get('status','')))}</span></td>"
            f"<td>{html.escape(str(row.get('risk','')))}</td>"
            f"<td>{html.escape(str(row.get('rounds','')))}</td>"
            f"<td>{html.escape(str(row.get('reason',''))[:160])}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Development dashboard</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ font: 15px/1.5 system-ui, sans-serif; margin: 2rem auto; max-width: 1000px; padding: 0 1rem; }}
h1 {{ margin-bottom: .25rem; }}
.muted {{ color: #666; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: .75rem; margin: 1.5rem 0; }}
.card {{ border: 1px solid #8884; border-radius: 10px; padding: .9rem 1rem; }}
.card b {{ display: block; font-size: 1.5rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ text-align: left; border-bottom: 1px solid #8884; padding: .45rem .5rem; }}
.pill {{ border-radius: 999px; padding: .1rem .55rem; font-size: .85em; background: #8883; }}
.pill.done {{ background: #2a7f3f33; }}
.pill.escalated {{ background: #b7791f33; }}
.pill.failed {{ background: #b8323233; }}
.pill.shadow {{ background: #4a556833; }}
</style></head><body>
<h1>Development dashboard</h1>
<p class="muted">Generated {html.escape(m['generated_at'])}</p>
<div class="cards">
  <div class="card"><span>Tasks</span><b>{m['total']}</b></div>
  <div class="card"><span>Merged</span><b>{m['merged']}</b></div>
  <div class="card"><span>Escalated</span><b>{m['escalated']}</b></div>
  <div class="card"><span>First-pass</span><b>{m['first_pass_rate']:.0%}</b></div>
  <div class="card"><span>Autonomy</span><b>{m['autonomy_rate']:.0%}</b></div>
  <div class="card"><span>Canaries</span><b>{m['canaries']['passed']}/{m['canaries']['total']}</b></div>
  <div class="card"><span>Step-limited</span><b>{m['step_limited']}</b></div>
  <div class="card"><span>Max steps</span><b>{m['max_step_utilization']:.0%}</b></div>
  <div class="card"><span>Cost</span><b>${m['cost_usd']:.2f}</b></div>
</div>
<h2>Recent tasks</h2>
<table><thead><tr><th>Task</th><th>Status</th><th>Risk</th><th>Rounds</th><th>Reason</th></tr></thead>
<tbody>{''.join(rows) or '<tr><td colspan="5">No tasks yet.</td></tr>'}</tbody></table>
</body></html>
"""


def write_dashboard(repo: Path) -> dict:
    reports = repo / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    md = reports / "dev_dashboard.md"
    html_path = reports / "dev_dashboard.html"
    md.write_text(dashboard_markdown(repo))
    html_path.write_text(dashboard_html(repo))
    write_json(repo / "runs" / "dev" / "dashboard.json", metrics(repo))
    return {"markdown": str(md), "html": str(html_path), "metrics": metrics(repo)}


def daily_digest(repo: Path, *, days: int = 1) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = []
    for row in load_index(repo):
        try:
            ts = datetime.fromisoformat(str(row.get("ts", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts >= cutoff:
            rows.append(row)
    m = metrics(repo)
    lines = [
        f"# Development digest — {date.today().isoformat()}",
        "",
        f"Last {days} day(s): {len(rows)} task outcome(s).",
        f"Merged: {sum(1 for r in rows if r.get('merged_commit'))}; "
        f"escalated: {sum(1 for r in rows if r.get('status') == 'escalated')}; "
        f"failed: {sum(1 for r in rows if r.get('status') == 'failed')}.",
        "",
        "## Outcomes",
        "",
    ]
    for row in rows:
        lines.append(
            f"- `{row.get('task_id')}` — **{row.get('status')}** "
            f"(risk {row.get('risk')}, {row.get('rounds', 0)} round(s)): "
            f"{row.get('reason', '')}"
        )
    if not rows:
        lines.append("- No outcomes in this window.")
    lines += ["", f"Overall first-pass rate: {m['first_pass_rate']:.1%}", ""]
    return "\n".join(lines)
