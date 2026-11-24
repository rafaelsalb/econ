from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tail(text: str, limit: int = 4000) -> str:
    return text if len(text) <= limit else text[-limit:]


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return path


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def extract_json(text: str) -> dict | None:
    """Extract the most complete JSON object from an agent reply.

    Agents often wrap their JSON in prose or a fenced block. Scan every opening
    brace, keep the largest decoded object, and prefer the earliest one on a
    tie. Returning the *last* object is wrong because nested objects such as a
    verifier's `checks[0]` would overwrite the top-level artifact.
    """
    if not text:
        return None
    decoder = json.JSONDecoder()
    best: dict | None = None
    best_score: tuple[int, int] | None = None
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        score = (len(json.dumps(value)), -idx)
        if best_score is None or score > best_score:
            best = value
            best_score = score
    return best


class RunArtifacts:
    def __init__(self, repo: Path, task_id: str):
        self.repo = repo
        self.task_id = task_id
        self.root = repo / "runs" / "dev"
        self.run_dir = self.root / "tasks" / task_id
        self.packets = self.run_dir / "packets"
        self.out = self.run_dir / "out"
        self.logs = self.run_dir / "logs"
        self.state_path = self.run_dir / "state.json"
        self.events_path = self.run_dir / "events.jsonl"
        self.cost_path = self.run_dir / "cost.json"
        self.decision_path = self.run_dir / "decision.json"
        self.index_path = self.root / "index.jsonl"

    def ensure(self) -> RunArtifacts:
        for path in (self.run_dir, self.packets, self.out, self.logs):
            path.mkdir(parents=True, exist_ok=True)
        return self

    def write_json(self, relative: str, payload: Any) -> Path:
        return write_json(self.run_dir / relative, payload)

    def read_json(self, relative: str, default: Any = None) -> Any:
        return read_json(self.run_dir / relative, default)

    def write_text(self, relative: str, text: str) -> Path:
        path = self.run_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def read_text(self, relative: str, default: str = "") -> str:
        path = self.run_dir / relative
        return path.read_text() if path.exists() else default

    def append_event(self, kind: str, **data: Any) -> None:
        self.ensure()
        event = {"ts": utcnow(), "task_id": self.task_id, "event": kind, **data}
        with self.events_path.open("a") as fh:
            fh.write(json.dumps(event, default=str) + "\n")

    def append_index(self, entry: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("a") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")

    def load_state(self) -> dict:
        return self.read_json("state.json", {}) or {}

    def save_state(self, state: dict) -> None:
        self.write_json("state.json", state)

    def update_state(self, **updates: Any) -> dict:
        state = self.load_state()
        state.update(updates)
        state["updated_at"] = utcnow()
        self.save_state(state)
        return state

    def archive_role(self, worktree: Path, role: str) -> dict | None:
        source = worktree / ".dev" / "out" / f"{role}.json"
        if not source.exists():
            return None
        payload = read_json(source)
        if payload is not None:
            write_json(self.out / f"{role}.json", payload)
        return payload

    def write_packet(self, worktree: Path, text: str) -> Path:
        dev = worktree / ".dev"
        dev.mkdir(parents=True, exist_ok=True)
        packet = dev / "packet.md"
        packet.write_text(text)
        self.write_text("packets/latest.md", text)
        return packet

    def add_cost(self, role: str, cost_usd: float, tokens: int = 0) -> None:
        cost = self.read_json("cost.json", {"total_usd": 0.0, "roles": {}}) or {}
        cost.setdefault("roles", {})
        entry = cost["roles"].setdefault(role, {"usd": 0.0, "tokens": 0})
        entry["usd"] = round(float(entry["usd"]) + float(cost_usd), 6)
        entry["tokens"] = int(entry.get("tokens", 0)) + int(tokens)
        cost["total_usd"] = round(
            sum(float(v.get("usd", 0)) for v in cost["roles"].values()), 6
        )
        write_json(self.cost_path, cost)

    def cost(self) -> dict:
        return self.read_json("cost.json", {"total_usd": 0.0, "roles": {}}) or {
            "total_usd": 0.0,
            "roles": {},
        }

    def add_steps(
        self, role: str, round_no: int, steps: int, limit: int | None
    ) -> dict[str, Any]:
        """Record one agent call's step usage against its per-turn cap."""
        data = self.read_json("steps.json", {}) or {}
        data.setdefault("calls", [])
        cap = int(limit) if limit is not None else None
        used = max(0, int(steps))
        utilization = round(used / cap, 3) if cap else 0.0
        entry = {
            "role": role,
            "round": int(round_no),
            "steps": used,
            "limit": cap,
            "utilization": utilization,
            "limit_reached": bool(cap and used >= cap),
        }
        data["calls"].append(entry)
        data["max_utilization"] = max(
            float(data.get("max_utilization", 0.0)), utilization
        )
        data["limit_reached"] = bool(data.get("limit_reached")) or entry[
            "limit_reached"
        ]
        write_json(self.run_dir / "steps.json", data)
        return entry

    def steps(self) -> dict:
        return self.read_json("steps.json", {}) or {
            "calls": [],
            "max_utilization": 0.0,
            "limit_reached": False,
        }
