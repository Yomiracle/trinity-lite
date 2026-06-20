"""Config validation for Trinity Lite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapters import load_specs
from .config import string_list
from .router import RouteError, load_routes, resolve_route


def validate_agents_config(path: str | None = None) -> list[str]:
    """Return schema issues for an agents config."""
    if path is None:
        return []
    try:
        data = _read_json_object(path)
        agents = data.get("agents", {})
        if not isinstance(agents, dict):
            return ["agents must be an object"]
        issues: list[str] = []
        for agent_id, raw in agents.items():
            prefix = f"agents.{agent_id}"
            if not isinstance(agent_id, str) or not agent_id:
                issues.append("agent ids must be non-empty strings")
                continue
            if not isinstance(raw, dict):
                issues.append(f"{prefix} must be an object")
                continue
            mode = raw.get("mode", "mock")
            if mode not in {"mock", "command"}:
                issues.append(f"{prefix}.mode must be 'mock' or 'command'")
            command = raw.get("command")
            if mode == "command" and not command:
                issues.append(f"{prefix}.command is required for command mode")
            if command is not None and not _is_string_list(command):
                issues.append(f"{prefix}.command must be a list of strings")
            issues.extend(_validate_string_list_field(prefix, raw, "roles"))
            issues.extend(_validate_string_list_field(prefix, raw, "capabilities"))
            for field in ("timeout", "priority"):
                if field in raw and not _is_int_like(raw[field]):
                    issues.append(f"{prefix}.{field} must be an integer")
        if issues:
            return issues
        load_specs(path)
        return issues
    except Exception as exc:
        return [str(exc)]


def validate_routes_config(
    routes_path: str | None = None,
    agents_path: str | None = None,
) -> list[str]:
    """Return schema and resolution issues for a routes config."""
    try:
        config = load_routes(routes_path)
        specs = load_specs(agents_path)
    except Exception as exc:
        return [str(exc)]

    routes = config.get("routes", {})
    opposites = config.get("opposites", {})
    issues: list[str] = []

    if not isinstance(routes, dict):
        return ["routes must be an object"]
    if not isinstance(opposites, dict):
        issues.append("opposites must be an object")
        opposites = {}

    for source, target in opposites.items():
        if not isinstance(source, str) or not isinstance(target, str):
            issues.append("opposites keys and values must be strings")
            continue
        if source not in specs:
            issues.append(f"opposites.{source} references unknown source agent")
        if target not in specs:
            issues.append(f"opposites.{source} references unknown target agent: {target}")

    for task_type, rule in routes.items():
        prefix = f"routes.{task_type}"
        if not isinstance(task_type, str) or not task_type:
            issues.append("route task types must be non-empty strings")
            continue
        if not isinstance(rule, dict):
            issues.append(f"{prefix} must be an object")
            continue

        agent = rule.get("agent")
        if agent is not None and not isinstance(agent, str):
            issues.append(f"{prefix}.agent must be a string")
            continue
        if agent and agent != "opposite" and agent not in specs:
            issues.append(f"{prefix}.agent references unknown agent: {agent}")

        for field in ("requires", "prefer", "avoid"):
            issues.extend(_validate_string_list_field(prefix, rule, field))

        if "review_required" in rule and not isinstance(rule["review_required"], bool):
            issues.append(f"{prefix}.review_required must be a boolean")

        if agent == "opposite":
            if not opposites:
                issues.append(f"{prefix}.agent uses opposite but no opposites are configured")
            continue

        if not agent:
            try:
                resolve_route(
                    "doctor route validation",
                    task_type=task_type,
                    routes_path=routes_path,
                    agents_path=agents_path,
                )
            except RouteError as exc:
                issues.append(f"{prefix} cannot resolve: {exc}")

    return issues


def _read_json_object(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _validate_string_list_field(prefix: str, raw: dict[str, Any], field: str) -> list[str]:
    if field not in raw:
        return []
    try:
        string_list(raw[field])
    except ValueError as exc:
        return [f"{prefix}.{field}: {exc}"]
    return []


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_int_like(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False
