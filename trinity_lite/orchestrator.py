"""Optional local orchestration helpers."""

from __future__ import annotations

import os
import inspect
from typing import Any

from .bus import TrinityBus, utc_now_iso
from .doctor import run_doctor
from .router import resolve_route
from .worker import run_once


BUILTIN_REVIEW_PIPELINE = {
    "name": "review",
    "description": "Built-in implement-then-review pipeline",
    "steps": [
        {"id": "implement", "agent": "", "task_type": "", "prompt_template": "{task}"},
        {"id": "review_step", "agent": "", "task_type": "code_review",
         "prompt_template": "Review: {task}\n\nResult:\n{steps.implement.result}"},
    ],
}


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
    verify: bool = True,
    verifier: Any | None = None,
) -> dict[str, Any]:
    """Dispatch primary work and an optional review using configured routes."""
    route = resolve_route(task, task_type, previous_agent, routes_path, agents_path)
    primary_task = bus.submit_task(
        source_agent=source_agent,
        target_agent=route["agent"],
        prompt=task,
        task_type=route["task_type"],
        cwd=cwd or os.getcwd(),
        route=route,
        gate_status="primary_pending",
        acceptance_status="queued",
        acceptance_reason="primary task queued",
    )
    primary_result = run_once(route["agent"], bus, agents_path, task_id=primary_task["id"]) if run_workers else primary_task
    if primary_result is None:
        primary_result = bus.get_task(primary_task["id"])

    review_route = None
    review_task = None
    review_result = None

    if route["review_required"] and primary_result["status"] == "completed":
        review_route, review_task = dispatch_review_task(
            bus, primary_result, route, routes_path, agents_path
        )
        review_result = run_once(review_route["agent"], bus, agents_path, task_id=review_task["id"]) if run_workers else review_task
        if review_result is None:
            review_result = bus.get_task(review_task["id"])

    primary_result = apply_acceptance_gate(
        bus,
        route,
        primary_result,
        review_result,
        routes_path=routes_path,
        agents_path=agents_path,
        verify=verify,
        verifier=verifier,
    )
    if review_result is not None:
        review_result = bus.get_task(review_result["id"])

    return {
        "route": route,
        "primary_task": primary_result,
        "review_route": review_route,
        "review_task": review_result,
        "verification": _json_field(primary_result.get("verification_json")),
        "acceptance_status": primary_result.get("acceptance_status"),
        "accepted_at": primary_result.get("accepted_at"),
    }


def _review_prompt(primary_task: dict[str, Any]) -> str:
    return (
        f"Review task {primary_task['id']} from {primary_task['target_agent']}.\n\n"
        f"Task type: {primary_task.get('task_type') or 'unspecified'}\n"
        f"Prompt:\n{primary_task['prompt']}\n\n"
        f"Result:\n{primary_task.get('result') or ''}"
    )


def dispatch_review_task(
    bus: TrinityBus,
    primary_task: dict[str, Any],
    route: dict[str, Any],
    routes_path: str | None = None,
    agents_path: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a secondary review task and link it to the primary task."""
    review_prompt = _review_prompt(primary_task)
    review_route = resolve_route(
        review_prompt,
        "code_review",
        route["agent"],
        routes_path,
        agents_path,
    )
    bus.update_task_evidence(
        primary_task["id"],
        gate_status="review_pending",
        gate_updated_at=utc_now_iso(),
        acceptance_status="needs_review",
        acceptance_reason="secondary review pending",
    )
    review_task = bus.submit_task(
        source_agent=route["agent"],
        target_agent=review_route["agent"],
        prompt=review_prompt,
        task_type=review_route["task_type"],
        cwd=primary_task["cwd"],
        depth=int(primary_task["depth"]) + 1,
        parent_task_id=primary_task["id"],
        route=review_route,
        acceptance_status="queued",
        acceptance_reason="secondary review queued",
    )
    bus.update_task_evidence(
        primary_task["id"],
        review_task_id=review_task["id"],
        gate_status="review_pending",
        gate_updated_at=utc_now_iso(),
        acceptance_status="needs_review",
        acceptance_reason="secondary review pending",
    )
    return review_route, review_task


def classify_review_result(result: str | None) -> str:
    text = (result or "").lower()
    no_p0 = "no p0" in text or "无 p0" in text or "无p0" in text
    no_p1 = "no p1" in text or "无 p1" in text or "无p1" in text
    if no_p0 and no_p1:
        return "review_passed"
    if "p0" in text or "p1" in text:
        return "review_attention"
    return "review_passed"


def run_acceptance_verification(
    bus: TrinityBus,
    routes_path: str | None = None,
    agents_path: str | None = None,
    enabled: bool = True,
    verifier: Any | None = None,
    task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run local acceptance checks before marking a flow accepted."""
    if not enabled:
        return {
            "status": "skipped",
            "checks": [],
            "reason": "verification disabled",
        }
    if verifier is not None:
        result = _call_verifier(
            verifier,
            {
                "bus": bus,
                "task": task,
                "task_id": task.get("id") if task else None,
                "routes_path": routes_path,
                "agents_path": agents_path,
            },
        )
        if not isinstance(result, dict):
            raise ValueError("verifier must return a dictionary")
        return result

    report = run_doctor(str(bus.db_path), routes_path, agents_path)
    failed = [item for item in report.get("checks", []) if not item.get("ok")]
    return {
        "status": "passed" if report.get("status") == "healthy" else "failed",
        "checks": [
            {
                "name": "doctor",
                "ok": report.get("status") == "healthy",
                "detail": "healthy" if not failed else failed,
            }
        ],
    }


def apply_acceptance_gate(
    bus: TrinityBus,
    route: dict[str, Any],
    primary_task: dict[str, Any],
    review_task: dict[str, Any] | None,
    routes_path: str | None = None,
    agents_path: str | None = None,
    verify: bool = True,
    verifier: Any | None = None,
) -> dict[str, Any]:
    """Update persistent acceptance evidence for the primary task."""
    primary = bus.get_task(primary_task["id"])
    review = bus.get_task(review_task["id"]) if review_task is not None else None
    verification = {"status": "not_required", "checks": []}
    accepted_at = None

    if primary["status"] == "failed":
        gate_status = "primary_failed"
        acceptance_status = "blocked"
        acceptance_reason = "primary task failed"
    elif primary["status"] != "completed":
        gate_status = "primary_pending"
        acceptance_status = "queued"
        acceptance_reason = "primary task is not complete"
    elif route["review_required"]:
        if review is None:
            gate_status = "review_pending"
            acceptance_status = "needs_review"
            acceptance_reason = "secondary review pending"
        elif review["status"] == "failed":
            gate_status = "review_failed"
            acceptance_status = "blocked"
            acceptance_reason = "secondary review task failed"
        elif review["status"] != "completed":
            gate_status = "review_pending"
            acceptance_status = "needs_review"
            acceptance_reason = "secondary review is not complete"
        else:
            gate_status = classify_review_result(review.get("result"))
            if gate_status == "review_passed":
                verification = run_acceptance_verification(
                    bus, routes_path, agents_path, enabled=verify, verifier=verifier, task=primary
                )
                if verification.get("status") in {"passed", "skipped"}:
                    accepted_at = utc_now_iso()
                    acceptance_status = "accepted"
                    acceptance_reason = "secondary review passed and verification passed"
                    if verification.get("status") == "skipped":
                        acceptance_reason = "secondary review passed; verification skipped"
                else:
                    gate_status = "verification_failed"
                    acceptance_status = "blocked"
                    acceptance_reason = "acceptance verification failed after secondary review"
            else:
                acceptance_status = "review_attention"
                acceptance_reason = "secondary review reported P0/P1 attention"
    else:
        verification = run_acceptance_verification(
            bus, routes_path, agents_path, enabled=verify, verifier=verifier, task=primary
        )
        if verification.get("status") in {"passed", "skipped"}:
            gate_status = "accepted"
            accepted_at = utc_now_iso()
            acceptance_status = "accepted"
            acceptance_reason = "primary task completed and verification passed"
            if verification.get("status") == "skipped":
                acceptance_reason = "primary task completed; verification skipped"
        else:
            gate_status = "verification_failed"
            acceptance_status = "blocked"
            acceptance_reason = "acceptance verification failed"

    return bus.update_task_evidence(
        primary["id"],
        gate_status=gate_status,
        gate_updated_at=utc_now_iso(),
        verification_json=verification,
        acceptance_status=acceptance_status,
        acceptance_reason=acceptance_reason,
        accepted_at=accepted_at,
    )


def _json_field(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    try:
        import json

        return json.loads(value)
    except ValueError:
        return value


def _call_verifier(verifier: Any, context: dict[str, Any]) -> Any:
    try:
        signature = inspect.signature(verifier)
    except (TypeError, ValueError):
        return verifier(context)

    params = list(signature.parameters.values())
    positional = [
        param for param in params
        if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    has_varargs = any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in params)
    if has_varargs or len(positional) >= 2:
        return verifier(context["bus"], context["task_id"])
    if len(positional) == 1:
        return verifier(context)
    return verifier()
