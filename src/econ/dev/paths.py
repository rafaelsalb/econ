from __future__ import annotations

import fnmatch
import re
from pathlib import PurePosixPath

_GLOB_CACHE: dict[str, re.Pattern[str]] = {}


def normalize(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def compile_glob(pattern: str) -> re.Pattern[str]:
    """Translate a gitignore-style glob into a path regex.

    ``**/`` matches zero or more directories, ``**`` matches anything, and a
    single ``*`` does not cross a slash.
    """
    pattern = normalize(pattern)
    cached = _GLOB_CACHE.get(pattern)
    if cached is not None:
        return cached
    out = ["^"]
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if i + 1 < len(pattern) and pattern[i + 1] == "*":
                if i + 2 < len(pattern) and pattern[i + 2] == "/":
                    out.append("(?:.*/)?")
                    i += 3
                    continue
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
            i += 1
            continue
        if ch == "?":
            out.append("[^/]")
            i += 1
            continue
        out.append(re.escape(ch))
        i += 1
    out.append("$")
    compiled = re.compile("".join(out))
    _GLOB_CACHE[pattern] = compiled
    return compiled


def matches_any(path: str, patterns: list[str] | tuple[str, ...]) -> bool:
    path = normalize(path)
    return any(compile_glob(pattern).match(path) for pattern in patterns)


def matches(pattern: str, path: str) -> bool:
    return compile_glob(pattern).match(normalize(path)) is not None


def literal_prefix(pattern: str) -> str:
    pattern = normalize(pattern)
    wild = len(pattern)
    for token in "*?[":
        idx = pattern.find(token)
        if idx != -1:
            wild = min(wild, idx)
    prefix = pattern[:wild].rstrip("/")
    return prefix


def overlap(left: str, right: str) -> bool:
    """Conservative overlap test for two glob patterns.

    Two patterns conflict when their literal prefixes are equal or one is inside
    the other, or when a concrete sample path from one matches the other. This
    is intentionally conservative: a false conflict only serializes work.
    """
    left, right = normalize(left), normalize(right)
    if left == right:
        return True
    lp, rp = literal_prefix(left), literal_prefix(right)
    if lp and rp and (lp == rp or lp.startswith(rp + "/") or rp.startswith(lp + "/")):
        return True
    for sample in _samples(left):
        if matches(right, sample):
            return True
    for sample in _samples(right):
        if matches(left, sample):
            return True
    return False


def _samples(pattern: str) -> list[str]:
    prefix = literal_prefix(pattern)
    if not prefix:
        return []
    if any(token in pattern for token in "*?["):
        return [prefix, f"{prefix}/__sample__.py", f"{prefix}/__sample__"]
    return [prefix]


def scope_violations(
    changed: list[str], allow: list[str], deny: list[str]
) -> list[str]:
    problems = []
    for path in changed:
        if matches_any(path, deny):
            problems.append(f"denied path changed: {path}")
        elif not matches_any(path, allow):
            problems.append(f"path outside scope.allow: {path}")
    return problems


def claims_conflict(left: list[str], right: list[str]) -> bool:
    return any(overlap(a, b) for a in left for b in right)


def sample_path(pattern: str) -> str:
    """Return a concrete-looking path for diagnostics and tests."""
    prefix = literal_prefix(pattern)
    if not prefix:
        return "x"
    if "**" in pattern or "*" in pattern:
        return f"{prefix}/x.py"
    return prefix


def basename(path: str) -> str:
    return PurePosixPath(path).name


# Keep fnmatch imported for third-party callers that expect it via this module.
__all__ = [
    "basename",
    "claims_conflict",
    "compile_glob",
    "fnmatch",
    "literal_prefix",
    "matches",
    "matches_any",
    "normalize",
    "overlap",
    "sample_path",
    "scope_violations",
]
