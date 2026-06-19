"""Path helpers for Trinity Lite."""

from __future__ import annotations

import os
from pathlib import Path


APP_DIR_ENV = "TRINITY_LITE_HOME"
DB_PATH_ENV = "TRINITY_LITE_DB"


def app_dir() -> Path:
    """Return the local Trinity Lite state directory."""
    raw = os.environ.get(APP_DIR_ENV)
    return Path(raw).expanduser() if raw else Path.home() / ".trinity-lite"


def default_db_path() -> Path:
    """Return the default SQLite database path."""
    raw = os.environ.get(DB_PATH_ENV)
    return Path(raw).expanduser() if raw else app_dir() / "trinity_lite.db"


def default_allowed_roots() -> list[Path]:
    """Return workspace roots allowed for task execution."""
    raw = os.environ.get("TRINITY_LITE_ALLOWED_ROOTS")
    if raw:
        return [Path(p).expanduser().resolve() for p in raw.split(os.pathsep) if p]
    return [Path.home().resolve()]
