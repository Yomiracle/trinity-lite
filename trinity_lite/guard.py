"""Safety helpers for public Trinity Lite."""

from __future__ import annotations

import os
import re
from pathlib import Path


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-or-v1-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s]+"),
]

BLOCKED_PUBLIC_NAMES = {
    ".env",
    "auth.json",
    "trinity_bus.db",
    "trinity_state.json",
    "metrics.jsonl",
}


class GuardError(ValueError):
    """Raised when a safety rule blocks an operation."""


def redact_secrets(text: str) -> str:
    """Replace likely secrets with a placeholder."""
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


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
    for path in root_path.rglob("*"):
        rel = path.relative_to(root_path)
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.is_symlink():
            issues.append(f"symlink is not allowed in public tree: {rel}")
            continue
        if path.is_dir():
            continue
        if path.suffix == ".pyc":
            continue
        if path.name in BLOCKED_PUBLIC_NAMES:
            issues.append(f"blocked runtime/private file: {rel}")
        if path.suffix in {".db", ".sqlite", ".log"}:
            issues.append(f"blocked runtime artifact: {rel}")
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            continue
        if size > 512_000:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if redact_secrets(content) != content:
            issues.append(f"possible secret in: {rel}")
    return issues
