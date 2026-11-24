from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from .report import load_index
from .workspace import commit_release, is_clean

_VERSION = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def read_version(repo: Path) -> str:
    pyproject = repo / "pyproject.toml"
    match = _VERSION.search(pyproject.read_text())
    if not match:
        raise ValueError("pyproject.toml has no version")
    return match.group(1)


def bump_version(version: str, bump: str) -> str:
    parts = [int(p) for p in version.split(".")]
    while len(parts) < 3:
        parts.append(0)
    major, minor, patch = parts[:3]
    if bump == "major":
        major, minor, patch = major + 1, 0, 0
    elif bump == "minor":
        minor, patch = minor + 1, 0
    elif bump == "patch":
        patch += 1
    else:
        raise ValueError(f"unknown bump: {bump}")
    return f"{major}.{minor}.{patch}"


def _write_version(repo: Path, version: str) -> None:
    pyproject = repo / "pyproject.toml"
    text = pyproject.read_text()
    text, count = _VERSION.subn(f'version = "{version}"', text, count=1)
    if count != 1:
        raise ValueError("could not update version")
    pyproject.write_text(text)


def _release_notes(repo: Path, limit: int = 20) -> list[str]:
    rows = [r for r in load_index(repo) if r.get("status") == "done"]
    if not rows:
        return ["- Development pipeline maintenance."]
    return [
        f"- `{row.get('task_id')}`: {str(row.get('reason', '') or 'completed')[:120]}"
        for row in rows[-limit:]
    ]


def _prepend_changelog(repo: Path, version: str, notes: list[str]) -> Path:
    path = repo / "CHANGELOG.md"
    existing = path.read_text() if path.exists() else "# Changelog\n"
    entry = "\n".join(
        [f"## v{version} — {date.today().isoformat()}", "", *notes, ""]
    )
    if existing.startswith("# Changelog"):
        rest = existing[len("# Changelog") :].lstrip("\n")
        path.write_text(f"# Changelog\n\n{entry}\n{rest}".rstrip() + "\n")
    else:
        path.write_text(f"# Changelog\n\n{entry}\n{existing}".rstrip() + "\n")
    return path


def _run_check(repo: Path) -> tuple[bool, str]:
    commands = [
        [sys.executable, "-m", "pytest", "-q"],
        [sys.executable, "-m", "econ.cli", "check"],
    ]
    for command in commands:
        proc = subprocess.run(
            command, cwd=repo, capture_output=True, text=True, check=False
        )
        if proc.returncode != 0:
            return False, f"{' '.join(command)} failed: {(proc.stdout + proc.stderr)[-1200:]}"
    return True, "gate passed"


def release(
    repo: Path,
    *,
    bump: str = "patch",
    dry_run: bool = False,
    message: str | None = None,
    check: bool = True,
    allow_dirty: bool = False,
) -> dict:
    if not is_clean(repo) and not allow_dirty:
        raise RuntimeError("working tree is dirty; commit or stash before release")
    if check:
        ok, detail = _run_check(repo)
        if not ok:
            raise RuntimeError(detail)
    old = read_version(repo)
    new = bump_version(old, bump)
    tag = f"v{new}"
    notes = _release_notes(repo)
    info = {
        "old_version": old,
        "new_version": new,
        "tag": tag,
        "notes": notes,
        "dry_run": dry_run,
        "repo": str(repo),
    }
    if dry_run:
        return info
    _write_version(repo, new)
    _prepend_changelog(repo, new, notes)
    commit_message = message or f"chore(release): {tag}"
    sha = commit_release(repo, commit_message, tag=tag)
    return {**info, "commit": sha, "commit_message": commit_message}
