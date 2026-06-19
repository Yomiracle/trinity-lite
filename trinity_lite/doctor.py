"""Environment checks for Trinity Lite."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

from .adapters import load_specs
from .bus import TrinityBus
from .guard import scan_public_tree
from .router import load_routes


def run_doctor(
    db_path: str | None = None,
    routes_path: str | None = None,
    agents_path: str | None = None,
    scan_root: str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    checks.append({
        "name": "python_version",
        "ok": sys.version_info >= (3, 10),
        "detail": sys.version.split()[0],
    })

    try:
        bus = TrinityBus(db_path)
        bus.list_tasks(limit=1)
        checks.append({"name": "sqlite_bus", "ok": True, "detail": str(bus.db_path)})
    except Exception as exc:  # pragma: no cover - defensive report
        checks.append({"name": "sqlite_bus", "ok": False, "detail": str(exc)})

    try:
        route_count = len(load_routes(routes_path)["routes"])
        checks.append({"name": "routes", "ok": True, "detail": f"{route_count} routes"})
    except Exception as exc:
        checks.append({"name": "routes", "ok": False, "detail": str(exc)})

    try:
        specs = load_specs(agents_path)
        missing = []
        for spec in specs.values():
            if spec.mode == "command" and spec.command:
                exe = spec.command[0]
                if shutil.which(exe) is None and not Path(exe).exists():
                    missing.append(exe)
        checks.append({
            "name": "agents",
            "ok": not missing,
            "detail": "missing: " + ", ".join(missing) if missing else f"{len(specs)} agents",
        })
    except Exception as exc:
        checks.append({"name": "agents", "ok": False, "detail": str(exc)})

    if scan_root:
        issues = scan_public_tree(scan_root)
        checks.append({
            "name": "public_tree_scan",
            "ok": not issues,
            "detail": issues,
        })

    return {
        "status": "healthy" if all(c["ok"] for c in checks) else "unhealthy",
        "checks": checks,
    }
