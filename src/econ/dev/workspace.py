from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from .artifacts import tail, utcnow


class GitError(RuntimeError):
    pass


def git(
    args: list[str],
    cwd: Path,
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.update(env or {})
    merged.setdefault("GIT_TERMINAL_PROMPT", "0")
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=merged,
        check=False,
    )
    if check and proc.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed in {cwd} ({proc.returncode}):\n"
            f"{tail(proc.stderr) or tail(proc.stdout)}"
        )
    return proc


def repo_root(path: Path) -> Path:
    proc = git(["rev-parse", "--show-toplevel"], path)
    return Path(proc.stdout.strip()).resolve()


def current_branch(repo: Path) -> str:
    return git(["rev-parse", "--abbrev-ref", "HEAD"], repo).stdout.strip()


def dirty_paths(repo: Path) -> list[str]:
    out = git(["status", "--porcelain"], repo).stdout
    paths = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:] if len(line) > 3 else line
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return paths


def is_clean(repo: Path, *, ignore_prefixes: tuple[str, ...] = ()) -> bool:
    paths = dirty_paths(repo)
    return all(
        any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in ignore_prefixes)
        for path in paths
    ) if ignore_prefixes else not paths


def rev_parse(repo: Path, ref: str) -> str:
    return git(["rev-parse", ref], repo).stdout.strip()


def branch_exists(repo: Path, branch: str) -> bool:
    return (
        git(["rev-parse", "--verify", "--quiet", branch], repo, check=False).returncode
        == 0
    )


def command_env(repo: Path, worktree: Path) -> dict[str, str]:
    env = os.environ.copy()
    venv_bin = repo / ".venv" / "bin"
    interpreter_dir = Path(sys.executable).parent
    path_parts = [
        str(venv_bin) if venv_bin.exists() else str(interpreter_dir),
        str(Path(env.get("PATH", ""))),
    ]
    env["PATH"] = os.pathsep.join(p for p in path_parts if p)
    env["PYTHONPATH"] = str(worktree / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def run_command(
    argv: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: int = 900,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=check,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return subprocess.CompletedProcess(
            argv, 124, stdout=stdout, stderr=stderr + "\n[timeout]"
        )


@dataclass
class Worktree:
    repo: Path
    path: Path
    branch: str
    base: str
    task_id: str

    @classmethod
    def create(
        cls,
        repo: Path,
        task_id: str,
        *,
        base: str = "main",
        worktrees_dir: Path | None = None,
    ) -> "Worktree":
        repo = repo.resolve()
        if not branch_exists(repo, base) and base == "main":
            base = "HEAD"
        base_sha = rev_parse(repo, base)
        worktrees_dir = worktrees_dir or (repo / "runs" / "dev" / "worktrees")
        worktrees_dir.mkdir(parents=True, exist_ok=True)
        suffix = uuid.uuid4().hex[:8]
        path = worktrees_dir / f"{task_id}-{suffix}"
        branch = f"dev/{task_id}-{suffix}"
        git(["worktree", "add", "-b", branch, str(path), base_sha], repo)
        return cls(repo=repo, path=path, branch=branch, base=base_sha, task_id=task_id)

    def git(self, args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        return git(args, self.path, **kwargs)

    def commit_all(self, message: str, *, author: str = "econ-dev") -> str | None:
        git(["add", "-A"], self.path)
        # Agent scratch is never part of a commit. This is a no-op when .dev is
        # already ignored, and a safety net when a fixture lacks a .gitignore.
        git(["reset", "-q", "--", ".dev"], self.path, check=False)
        staged = git(["diff", "--cached", "--quiet"], self.path, check=False)
        if staged.returncode == 0:
            return None
        git(
            [
                "-c",
                f"user.name={author}",
                "-c",
                f"user.email={author}@localhost",
                "commit",
                "-q",
                "-m",
                message,
            ],
            self.path,
        )
        return rev_parse(self.path, "HEAD")

    def changed_files(self, base: str | None = None) -> list[str]:
        base = base or self.base
        out = git(["diff", "--name-only", f"{base}..HEAD"], self.path).stdout
        return [line.strip() for line in out.splitlines() if line.strip()]

    def diff(self, base: str | None = None, *, binary: bool = True) -> str:
        base = base or self.base
        args = ["diff", "--binary" if binary else "", f"{base}..HEAD"]
        args = [a for a in args if a]
        return git(args, self.path).stdout

    def diff_numstat(self, base: str | None = None) -> tuple[int, int]:
        base = base or self.base
        out = git(["diff", "--numstat", f"{base}..HEAD"], self.path).stdout
        added = deleted = 0
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            a, d = parts[0], parts[1]
            if a.isdigit():
                added += int(a)
            if d.isdigit():
                deleted += int(d)
        return added, deleted

    def commit_sha(self) -> str:
        return rev_parse(self.path, "HEAD")

    def write_patch(self, target: Path, base: str | None = None) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.diff(base))
        return target

    def apply_check(self, patch_path: Path, *, timeout: int = 120) -> tuple[bool, str]:
        scratch = self.repo / "runs" / "dev"
        scratch.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix="econ-apply-", dir=scratch))
        checkout = tmp / "tree"
        try:
            git(
                ["worktree", "add", "--detach", str(checkout), self.base],
                self.repo,
            )
            target = tmp / "patch.diff"
            shutil.copy2(patch_path, target)
            proc = git(
                ["apply", "--check", str(target)], checkout, check=False, timeout=timeout
            )
            return proc.returncode == 0, tail(proc.stderr or proc.stdout)
        finally:
            git(
                ["worktree", "remove", "--force", str(checkout)],
                self.repo,
                check=False,
            )
            shutil.rmtree(tmp, ignore_errors=True)

    def rebase_onto(self, target: str = "main") -> tuple[bool, str]:
        proc = git(["rebase", target], self.path, check=False)
        if proc.returncode == 0:
            return True, ""
        git(["rebase", "--abort"], self.path, check=False)
        return False, tail(proc.stderr or proc.stdout)

    def remove(self, *, delete_branch: bool = True, force: bool = True) -> None:
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(self.path))
        proc = git(args, self.repo, check=False)
        if proc.returncode != 0:
            shutil.rmtree(self.path, ignore_errors=True)
            git(["worktree", "prune"], self.repo, check=False)
        if delete_branch:
            git(["branch", "-D", self.branch], self.repo, check=False)

    def remove_scratch(self) -> None:
        shutil.rmtree(self.path / ".dev", ignore_errors=True)


def checkout_main(repo: Path, branch: str = "main") -> None:
    if current_branch(repo) == branch:
        return
    if not is_clean(repo, ignore_prefixes=("tasks/",)):
        raise GitError(f"cannot checkout {branch}: repository is dirty")
    git(["checkout", branch], repo)


def merge_ff(repo: Path, branch: str, branch_name: str = "main") -> str:
    checkout_main(repo, branch_name)
    # Task contracts are runtime state: status transitions move files between
    # tasks/ subdirectories and must not block an unrelated fast-forward merge.
    if not is_clean(repo, ignore_prefixes=("tasks/",)):
        raise GitError(f"cannot merge into {branch_name}: repository is dirty")
    git(["merge", "--ff-only", branch], repo)
    return rev_parse(repo, "HEAD")


def commit_release(
    repo: Path,
    message: str,
    *,
    author: str = "econ-dev",
    tag: str | None = None,
) -> str:
    git(["add", "-A"], repo)
    git(
        [
            "-c",
            f"user.name={author}",
            "-c",
            f"user.email={author}@localhost",
            "commit",
            "-q",
            "-m",
            message,
        ],
        repo,
    )
    sha = rev_parse(repo, "HEAD")
    if tag:
        git(
            [
                "-c",
                f"user.name={author}",
                "-c",
                f"user.email={author}@localhost",
                "tag",
                "-a",
                tag,
                "-m",
                tag,
            ],
            repo,
        )
    return sha


def worktree_status(worktree: Path) -> dict:
    return {
        "path": str(worktree),
        "branch": git(["rev-parse", "--abbrev-ref", "HEAD"], worktree).stdout.strip(),
        "head": rev_parse(worktree, "HEAD"),
        "dirty": not is_clean(worktree),
        "checked_at": utcnow(),
    }
