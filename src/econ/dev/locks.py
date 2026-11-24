from __future__ import annotations

import json
import os
import time
from pathlib import Path


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class FileLock:
    """Small advisory lock that survives crashes via a stale timeout.

    This is intentionally not a distributed lock. The daemon and the merge queue
    both run on the repository host; stale recovery is more useful than
    complexity here.
    """

    def __init__(self, path: Path, *, stale_seconds: int = 6 * 3600):
        self.path = path
        self.stale_seconds = stale_seconds
        self.acquired = False

    def read(self) -> dict | None:
        if not self.path.exists():
            return None
        try:
            return json.loads(self.path.read_text())
        except Exception:  # noqa: BLE001
            return None

    def is_stale(self) -> bool:
        info = self.read()
        if not info:
            return True
        try:
            age = time.time() - float(info.get("ts", 0))
        except (TypeError, ValueError):
            return True
        if age > self.stale_seconds:
            return True
        return not pid_alive(int(info.get("pid", 0)))

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                if self.is_stale():
                    try:
                        self.path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                return False
            with os.fdopen(fd, "w") as fh:
                fh.write(
                    json.dumps(
                        {
                            "pid": os.getpid(),
                            "ts": time.time(),
                            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        }
                    )
                )
            self.acquired = True
            return True
        return False

    def release(self) -> None:
        if self.acquired:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            self.acquired = False

    def __enter__(self) -> "FileLock":
        if not self.acquire():
            raise RuntimeError(f"lock is held: {self.path}")
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


class PauseSwitch:
    def __init__(self, root: Path):
        self.path = root / "runs" / "dev" / "PAUSED"

    def paused(self) -> bool:
        return self.path.exists()

    def pause(self, reason: str = "") -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(reason or "paused by operator")
        return self.path

    def resume(self) -> bool:
        if self.path.exists():
            self.path.unlink()
            return True
        return False
