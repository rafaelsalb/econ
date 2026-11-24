from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path

from .artifacts import write_json


class BudgetLedger:
    def __init__(self, repo: Path, daily_usd: float = 20.0):
        self.path = repo / "runs" / "dev" / "budget.json"
        self.daily_usd = float(daily_usd)
        self._lock = threading.Lock()
        self.data = self._load()

    def _load(self) -> dict:
        today = date.today().isoformat()
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}
        if data.get("date") != today:
            data = {"date": today, "spent_usd": 0.0, "tasks": 0}
            self._save(data)
        data.setdefault("spent_usd", 0.0)
        data.setdefault("tasks", 0)
        return data

    def _save(self, data: dict) -> None:
        write_json(self.path, data)

    @property
    def spent(self) -> float:
        return float(self.data.get("spent_usd", 0.0))

    @property
    def remaining(self) -> float:
        return max(0.0, self.daily_usd - self.spent)

    def can_start_task(self, per_task_usd: float) -> bool:
        return self.remaining > 0 and per_task_usd > 0

    def add(self, usd: float) -> None:
        with self._lock:
            self.data["spent_usd"] = round(self.spent + max(0.0, float(usd)), 6)
            self._save(self.data)

    def count_task(self) -> None:
        with self._lock:
            self.data["tasks"] = int(self.data.get("tasks", 0)) + 1
            self._save(self.data)

    def as_dict(self) -> dict:
        return {
            "date": self.data.get("date"),
            "spent_usd": self.spent,
            "daily_usd": self.daily_usd,
            "remaining_usd": round(self.remaining, 6),
            "tasks": self.data.get("tasks", 0),
        }
