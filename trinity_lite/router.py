"""Task routing for Trinity Lite."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DEFAULT_ROUTES: dict[str, dict[str, Any]] = {
    "implementation": {"agent": "codex", "review_required": True},
    "testing": {"agent": "codex", "review_required": True},
    "project_audit": {"agent": "codex", "review_required": True},
    "architecture_design": {"agent": "codex", "review_required": True},
    "code_review": {"agent": "opposite", "review_required": False},
    "secondary_review": {"agent": "claude_code", "review_required": False},
    "orchestration": {"agent": "hermes", "review_required": False},
    "acceptance": {"agent": "hermes", "review_required": False},
}

DEFAULT_OPPOSITES = {
    "codex": "claude_code",
    "claude_code": "codex",
    "hermes": "claude_code",
}

DEFAULT_PATTERNS = [
    (re.compile(r"(review|审查|二审|复核).*(patch|diff|改动|输出|result)", re.I), "code_review"),
    (re.compile(r"(audit|全面审查|项目审查|仓库审查|代码库审查)", re.I), "project_audit"),
    (re.compile(r"(implement|build|fix|实现|修复|开发|写代码)", re.I), "implementation"),
    (re.compile(r"(test|测试|验证)", re.I), "testing"),
    (re.compile(r"(route|dispatch|orchestrate|派发|路由|编排)", re.I), "orchestration"),
]


class RouteError(ValueError):
    """Raised when a route cannot be resolved."""


def load_routes(path: str | None = None) -> dict[str, Any]:
    if path is None:
        return {"routes": DEFAULT_ROUTES, "opposites": DEFAULT_OPPOSITES}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "routes": data.get("routes", DEFAULT_ROUTES),
        "opposites": data.get("opposites", DEFAULT_OPPOSITES),
    }


def infer_task_type(task: str) -> str | None:
    for pattern, task_type in DEFAULT_PATTERNS:
        if pattern.search(task):
            return task_type
    return None


def resolve_route(
    task: str,
    task_type: str | None = None,
    previous_agent: str | None = None,
    routes_path: str | None = None,
) -> dict[str, Any]:
    config = load_routes(routes_path)
    routes: dict[str, dict[str, Any]] = config["routes"]
    opposites: dict[str, str] = config["opposites"]
    resolved_type = task_type or infer_task_type(task) or "implementation"
    rule = routes.get(resolved_type)
    if not rule:
        raise RouteError(f"unknown task_type: {resolved_type}")
    agent = rule.get("agent")
    if agent == "opposite":
        if previous_agent is None:
            raise RouteError("previous_agent is required for opposite routing")
        agent = opposites.get(previous_agent)
        if agent is None:
            raise RouteError(f"no opposite agent configured for {previous_agent}")
    return {
        "agent": agent,
        "task_type": resolved_type,
        "review_required": bool(rule.get("review_required", False)),
        "source": "explicit" if task_type else "pattern/default",
    }
