"""Safety helpers for public Trinity Lite."""

from __future__ import annotations

import os
import re
from pathlib import Path


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-or-v1-[A-Za-z0-9_\-]{20,}"),
    re.compile(
        r"(?i)(?<![-A-Za-z0-9_])(?:[A-Za-z_][A-Za-z0-9_]*[_-])?"
        r"(?:api_?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s]+"
    ),
]

SAFE_PUBLIC_PATTERNS = [
    re.compile(r"(?i)^\s*id-token\s*:\s*(read|write|none)\s*(?:#.*)?$"),
]

BLOCKED_PUBLIC_NAMES = {
    ".env",
    "auth.json",
    "codeproxy.pid",
    "codeproxy.log",
    "trinity_bus.db",
    "trinity_learn.db",
    "trinity_learn.db-wal",
    "trinity_learn.db-shm",
    "trinity_state.json",
    "metrics.jsonl",
}


class GuardError(ValueError):
    """Raised when a safety rule blocks an operation."""


def redact_secrets(text: str) -> str:
    """Replace likely secrets with a placeholder."""
    redacted_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        line_body = line.rstrip("\r\n")
        if any(pattern.match(line_body) for pattern in SAFE_PUBLIC_PATTERNS):
            redacted_lines.append(line)
            continue
        redacted = line
        for pattern in SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        redacted_lines.append(redacted)
    return "".join(redacted_lines)


def ensure_inside_roots(path: str | os.PathLike[str], roots: list[Path]) -> Path:
    """Resolve a directory and require it to be inside an allowed root."""
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise GuardError(f"cwd does not exist: {resolved}")
    if not resolved.is_dir():
        raise GuardError(f"cwd is not a directory: {resolved}")
    for root in roots:
        root_resolved = root.expanduser().resolve()
        try:
            resolved.relative_to(root_resolved)
            return resolved
        except ValueError:
            continue
    roots_text = ", ".join(str(r) for r in roots)
    raise GuardError(f"cwd is outside allowed roots: {resolved} not in [{roots_text}]")


def scan_public_tree(root: str | os.PathLike[str]) -> list[str]:
    """Return publish blockers found under a tree."""
    root_path = Path(root).resolve()
    issues: list[str] = []
    for current, dirnames, filenames in os.walk(root_path, followlinks=False):
        current_path = Path(current)
        rel_current = current_path.relative_to(root_path)
        if ".git" in rel_current.parts or "__pycache__" in rel_current.parts:
            dirnames[:] = []
            continue
        for dirname in list(dirnames):
            directory = current_path / dirname
            rel = directory.relative_to(root_path)
            if directory.is_symlink():
                issues.append(f"symlink is not allowed in public tree: {rel}")
                dirnames.remove(dirname)
                continue
            if dirname in {".git", "__pycache__"}:
                dirnames.remove(dirname)
        for filename in filenames:
            path = current_path / filename
            rel = path.relative_to(root_path)
            if path.is_symlink():
                issues.append(f"symlink is not allowed in public tree: {rel}")
                continue
            if ".git" in rel.parts or "__pycache__" in rel.parts:
                continue
            issues.extend(_scan_public_file(path, rel))
    return issues


def _scan_public_file(path: Path, rel: Path) -> list[str]:
    issues: list[str] = []
    if path.suffix == ".pyc":
        return issues
    if path.name in BLOCKED_PUBLIC_NAMES:
        issues.append(f"blocked runtime/private file: {rel}")
    if path.suffix in {".db", ".sqlite", ".log"}:
        issues.append(f"blocked runtime artifact: {rel}")
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return issues
    if size > 512_000:
        return issues
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return issues
    if redact_secrets(content) != content:
        issues.append(f"possible secret in: {rel}")
    return issues
