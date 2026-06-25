"""Environment checks for Trinity Lite."""

from __future__ import annotations

import os
import shutil
import socket
import sys
from pathlib import Path
from typing import Any

from .adapters import load_specs
from .bus import TASK_EVIDENCE_COLUMNS, TrinityBus
from .guard import scan_public_tree
from .router import load_routes
from .validation import validate_agents_config, validate_routes_config


RETIRED_RUNTIME_ARTIFACTS = {
    "codeproxy.pid",
    "codeproxy.log",
    "trinity_learn.db",
    "trinity_learn.db-wal",
    "trinity_learn.db-shm",
}


def run_doctor(
    db_path: str | None = None,
    routes_path: str | None = None,
    agents_path: str | None = None,
    scan_root: str | None = None,
    runtime_root: str | None = None,
    retired_ports: list[int] | None = None,
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
        checks.extend(_bus_acceptance_checks(bus))
    except Exception as exc:  # pragma: no cover - defensive report
        checks.append({"name": "sqlite_bus", "ok": False, "detail": str(exc)})

    try:
        route_count = len(load_routes(routes_path)["routes"])
        route_issues = validate_routes_config(routes_path, agents_path)
        checks.append({
            "name": "routes",
            "ok": not route_issues,
            "detail": route_issues if route_issues else f"{route_count} routes",
        })
    except Exception as exc:
        checks.append({"name": "routes", "ok": False, "detail": str(exc)})

    try:
        agent_issues = validate_agents_config(agents_path)
        if agent_issues:
            checks.append({"name": "agents", "ok": False, "detail": agent_issues})
            specs = {}
        else:
            specs = load_specs(agents_path)
        missing = []
        for spec in specs.values():
            if spec.mode == "command" and spec.command:
                exe = spec.command[0]
                if shutil.which(exe) is None and not Path(exe).exists():
                    missing.append(exe)
        details: list[str] = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if specs:
            checks.append({
                "name": "agents",
                "ok": not details,
                "detail": details if details else f"{len(specs)} agents",
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

    if runtime_root:
        checks.extend(_runtime_checks(runtime_root))

    for port in retired_ports or []:
        checks.append(_retired_port_check(port))

    return {
        "status": "healthy" if all(c["ok"] for c in checks) else "unhealthy",
        "checks": checks,
    }


def _bus_acceptance_checks(bus: TrinityBus) -> list[dict[str, Any]]:
    with bus.connect() as conn:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
        }
        missing = sorted(set(TASK_EVIDENCE_COLUMNS) - columns)
        consistency_rows = conn.execute(
            """
            SELECT id, gate_status, review_task_id, acceptance_status,
                   accepted_at, verification_json
            FROM tasks
            WHERE (acceptance_status='accepted' AND accepted_at IS NULL)
               OR (acceptance_status='accepted' AND verification_json IS NULL)
               OR (accepted_at IS NOT NULL AND (acceptance_status IS NULL OR acceptance_status!='accepted'))
               OR (review_task_id IS NOT NULL AND gate_status IS NULL)
               OR (gate_status='verification_failed' AND (acceptance_status IS NULL OR acceptance_status!='blocked'))
            ORDER BY created_at DESC
            LIMIT 20
            """
        ).fetchall()

    return [
        {
            "name": "acceptance_schema",
            "ok": not missing,
            "detail": "schema ok" if not missing else {"missing": missing},
        },
        {
            "name": "acceptance_consistency",
            "ok": not consistency_rows,
            "detail": "ok" if not consistency_rows else [dict(row) for row in consistency_rows],
        },
    ]


def _runtime_checks(runtime_root: str) -> list[dict[str, Any]]:
    root = Path(runtime_root).expanduser()
    if not root.exists():
        return [{"name": "runtime_root", "ok": False, "detail": f"missing: {root}"}]
    if not root.is_dir():
        return [{"name": "runtime_root", "ok": False, "detail": f"not a directory: {root}"}]

    checks: list[dict[str, Any]] = [{
        "name": "runtime_root",
        "ok": True,
        "detail": str(root),
    }]

    metrics = root / "metrics.jsonl"
    if not metrics.exists():
        checks.append({
            "name": "runtime_metrics",
            "ok": False,
            "detail": f"missing: {metrics}",
        })
    elif not metrics.is_file():
        checks.append({
            "name": "runtime_metrics",
            "ok": False,
            "detail": f"not a file: {metrics}",
        })
    elif not _is_writable(metrics):
        checks.append({
            "name": "runtime_metrics",
            "ok": False,
            "detail": f"not writable: {metrics}",
        })
    else:
        checks.append({
            "name": "runtime_metrics",
            "ok": True,
            "detail": str(metrics),
        })

    present = sorted(name for name in RETIRED_RUNTIME_ARTIFACTS if (root / name).exists())
    checks.append({
        "name": "retired_runtime_artifacts",
        "ok": not present,
        "detail": "found: " + ", ".join(present) if present else "none",
    })
    return checks


def _is_writable(path: Path) -> bool:
    """Check if a path is writable without modifying it."""
    if path.exists():
        return os.access(path, os.W_OK)
    parent = path.parent
    return parent.exists() and parent.is_dir() and os.access(parent, os.W_OK)


def _retired_port_check(port: int) -> dict[str, Any]:
    if port < 1 or port > 65535:
        return {
            "name": f"retired_port:{port}",
            "ok": False,
            "detail": "invalid TCP port",
        }
    listening = _can_connect("127.0.0.1", port)
    return {
        "name": f"retired_port:{port}",
        "ok": not listening,
        "detail": "free" if not listening else f"listening on 127.0.0.1:{port}",
    }


def _can_connect(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False
