"""Optional local orchestration helpers."""

from __future__ import annotations

import os
from typing import Any

from .bus import TrinityBus
from .router import resolve_route
from .worker import run_once


def run_review_flow(
    task: str,
    bus: TrinityBus,
    routes_path: str | None = None,
    agents_path: str | None = None,
    source_agent: str = "user",
    task_type: str | None = None,
    previous_agent: str | None = None,
    cwd: str | None = None,
    run_workers: bool = True,
) -> dict[str, Any]:
    """Dispatch primary work and an optional review using configured routes."""
    route = resolve_route(task, task_type, previous_agent, routes_path, agents_path)
    primary_task = bus.submit_task(
        source_agent=source_agent,
        target_agent=route["agent"],
        prompt=task,
        task_type=route["task_type"],
        cwd=cwd or os.getcwd(),
    )
    primary_result = run_once(route["agent"], bus, agents_path, task_id=primary_task["id"]) if run_workers else primary_task
    if primary_result is None:
        primary_result = bus.get_task(primary_task["id"])

    review_route = None
    review_task = None
    review_result = None

    if route["review_required"] and primary_result["status"] == "completed":
        review_prompt = _review_prompt(primary_result)
        review_route = resolve_route(
            review_prompt,
            "code_review",
            route["agent"],
            routes_path,
            agents_path,
        )
        review_task = bus.submit_task(
            source_agent=route["agent"],
            target_agent=review_route["agent"],
            prompt=review_prompt,
            task_type=review_route["task_type"],
            cwd=primary_result["cwd"],
            depth=int(primary_result["depth"]) + 1,
        )
        review_result = run_once(review_route["agent"], bus, agents_path, task_id=review_task["id"]) if run_workers else review_task
        if review_result is None:
            review_result = bus.get_task(review_task["id"])

    return {
        "route": route,
        "primary_task": primary_result,
        "review_route": review_route,
        "review_task": review_result,
        "acceptance_status": _acceptance_status(route, primary_result, review_result),
    }


def _review_prompt(primary_task: dict[str, Any]) -> str:
    return (
        f"Review task {primary_task['id']} from {primary_task['target_agent']}.\n\n"
        f"Task type: {primary_task.get('task_type') or 'unspecified'}\n"
        f"Prompt:\n{primary_task['prompt']}\n\n"
        f"Result:\n{primary_task.get('result') or ''}"
    )


def _acceptance_status(
    route: dict[str, Any],
    primary_task: dict[str, Any],
    review_task: dict[str, Any] | None,
) -> str:
    if primary_task["status"] == "failed":
        return "blocked"
    if primary_task["status"] != "completed":
        return "queued"
    if not route["review_required"]:
        return "accepted"
    if review_task is None:
        return "needs_review"
    if review_task["status"] == "failed":
        return "blocked"
    if review_task["status"] == "completed":
        return "accepted"
    return "needs_review"
