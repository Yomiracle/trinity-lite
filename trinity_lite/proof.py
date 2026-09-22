"""Proof bundle export for Trinity Lite tasks.

A proof bundle captures one task's full evidence chain — route, work result,
review, verification, and acceptance — as a portable JSON document and a
human-readable Markdown summary. Stages that were never recorded are exported
as explicit nulls, never as fabricated data.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from . import __version__
from .bus import TrinityBus, utc_now_iso


PROOF_BUNDLE_VERSION = 1

_TASK_FIELDS = [
    "id", "source_agent", "target_agent", "task_type", "prompt", "cwd",
    "status", "depth", "result", "error", "created_at", "started_at",
    "finished_at",
]

_REVIEW_FIELDS = [
    "id", "source_agent", "target_agent", "task_type", "status", "result",
    "error", "created_at", "started_at", "finished_at",
]


def _json_field(value: Any) -> Any:
    """Parse a stored JSON evidence column, preserving non-JSON values."""
    if not isinstance(value, str) or not value:
        return value
    try:
        return json.loads(value)
    except ValueError:
        return value


def _pick(task: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    return {key: task.get(key) for key in fields}


def build_proof_bundle(bus: TrinityBus, task_id: str) -> dict[str, Any]:
    """Assemble the proof bundle for one task from the SQLite bus.

    Raises KeyError when the task id does not exist. Stages without recorded
    evidence are exported as None so consumers can distinguish "not recorded"
    from "recorded but empty".
    """
    task = bus.get_task(task_id)

    route = _json_field(task.get("route_json"))
    verification = _json_field(task.get("verification_json"))

    review = None
    review_task_id = task.get("review_task_id")
    if review_task_id:
        review = {"task_id": review_task_id, "task": None}
        try:
            review["task"] = _pick(bus.get_task(review_task_id), _REVIEW_FIELDS)
        except KeyError:
            # The link exists but the review row is gone; keep the link visible.
            pass

    acceptance = None
    if task.get("acceptance_status") is not None:
        acceptance = {
            "status": task.get("acceptance_status"),
            "reason": task.get("acceptance_reason"),
            "accepted_at": task.get("accepted_at"),
            "gate_status": task.get("gate_status"),
            "gate_updated_at": task.get("gate_updated_at"),
        }

    bundle: dict[str, Any] = {
        "proof_bundle_version": PROOF_BUNDLE_VERSION,
        "generated_at": utc_now_iso(),
        "generator": f"trinity-lite {__version__}",
        "task": _pick(task, _TASK_FIELDS),
        "route": route,
        "work": {
            "status": task.get("status"),
            "started_at": task.get("started_at"),
            "finished_at": task.get("finished_at"),
            "result": task.get("result"),
            "error": task.get("error"),
        },
        "review": review,
        "verification": verification,
        "acceptance": acceptance,
    }
    bundle["timeline"] = _build_timeline(bundle)
    return bundle


def _build_timeline(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a chronological stage timeline from recorded timestamps."""
    task = bundle["task"]
    events: list[dict[str, Any]] = []

    def add(stage: str, at: Any, actor: Any, detail: str) -> None:
        if at:
            events.append({"stage": stage, "at": at, "actor": actor, "detail": detail})

    add("route", task.get("created_at"), task.get("source_agent"),
        f"task created for {task.get('target_agent')}")
    add("work", task.get("started_at"), task.get("target_agent"), "work started")
    add("work", task.get("finished_at"), task.get("target_agent"),
        f"work {task.get('status')}")

    review = bundle.get("review")
    if review and review.get("task"):
        review_task = review["task"]
        add("review", review_task.get("created_at"), review_task.get("source_agent"),
            f"review created for {review_task.get('target_agent')}")
        add("review", review_task.get("started_at"), review_task.get("target_agent"),
            "review started")
        add("review", review_task.get("finished_at"), review_task.get("target_agent"),
            f"review {review_task.get('status')}")

    acceptance = bundle.get("acceptance")
    if acceptance:
        add("verify", acceptance.get("gate_updated_at"), "acceptance_gate",
            f"gate {acceptance.get('gate_status')}")
        add("accept", acceptance.get("accepted_at"), "acceptance_gate",
            f"acceptance {acceptance.get('status')}")

    return sorted(events, key=lambda event: event["at"])


def render_markdown(bundle: dict[str, Any]) -> str:
    """Render a proof bundle as a human-readable Markdown document."""
    task = bundle["task"]
    lines = [
        f"# Proof Bundle: {task.get('id')}",
        "",
        f"- Generator: {bundle.get('generator')}",
        f"- Generated at: {bundle.get('generated_at')}",
        f"- Proof bundle version: {bundle.get('proof_bundle_version')}",
        f"- Task: {task.get('prompt')}",
        f"- Status: {task.get('status')}",
        "",
        "## Route",
        "",
    ]

    route = bundle.get("route")
    if route is None:
        lines.append("_Not recorded._")
    else:
        lines.extend([
            f"- Agent: {route.get('agent')}",
            f"- Task type: {route.get('task_type')}",
            f"- Review required: {route.get('review_required')}",
        ])
        reason = route.get("reason") or route.get("rationale")
        if reason:
            lines.append(f"- Reason: {reason}")
    lines.extend(["", "## Work", ""])

    work = bundle.get("work") or {}
    lines.extend([
        f"- Worker: {task.get('target_agent')}",
        f"- Status: {work.get('status')}",
        f"- Started at: {work.get('started_at')}",
        f"- Finished at: {work.get('finished_at')}",
    ])
    if work.get("error"):
        lines.append(f"- Error: {work['error']}")
    lines.extend(["", "### Result", ""])
    if work.get("result"):
        lines.extend(["```", str(work["result"]), "```"])
    else:
        lines.append("_Not recorded._")
    lines.extend(["", "## Review", ""])

    review = bundle.get("review")
    if review is None:
        lines.append("_Not recorded._")
    else:
        lines.append(f"- Review task id: {review.get('task_id')}")
        review_task = review.get("task")
        if review_task is None:
            lines.append("- Review task record: not found")
        else:
            lines.extend([
                f"- Reviewer: {review_task.get('target_agent')}",
                f"- Status: {review_task.get('status')}",
                f"- Finished at: {review_task.get('finished_at')}",
            ])
            if review_task.get("result"):
                lines.extend(["", "### Review Result", "", "```",
                              str(review_task["result"]), "```"])
    lines.extend(["", "## Verification", ""])

    verification = bundle.get("verification")
    if verification is None:
        lines.append("_Not recorded._")
    elif isinstance(verification, dict):
        lines.append(f"- Status: {verification.get('status')}")
        checks = verification.get("checks") or []
        if checks:
            lines.extend(["", "| Check | OK | Detail |", "| --- | --- | --- |"])
            for check in checks:
                if isinstance(check, dict):
                    detail = str(check.get("detail", "")).replace("|", "\\|")
                    lines.append(f"| {check.get('name')} | {check.get('ok')} | {detail} |")
        if verification.get("reason"):
            lines.append(f"- Reason: {verification['reason']}")
    else:
        lines.extend(["```", str(verification), "```"])
    lines.extend(["", "## Acceptance", ""])

    acceptance = bundle.get("acceptance")
    if acceptance is None:
        lines.append("_Not recorded._")
    else:
        lines.extend([
            f"- Status: {acceptance.get('status')}",
            f"- Reason: {acceptance.get('reason')}",
            f"- Gate status: {acceptance.get('gate_status')}",
            f"- Gate updated at: {acceptance.get('gate_updated_at')}",
            f"- Accepted at: {acceptance.get('accepted_at')}",
        ])
    lines.extend(["", "## Timeline", ""])

    timeline = bundle.get("timeline") or []
    if not timeline:
        lines.append("_Not recorded._")
    else:
        lines.extend(["| Stage | At | Actor | Detail |", "| --- | --- | --- | --- |"])
        for event in timeline:
            detail = str(event.get("detail", "")).replace("|", "\\|")
            lines.append(
                f"| {event.get('stage')} | {event.get('at')} | {event.get('actor')} | {detail} |"
            )
    lines.append("")
    return "\n".join(lines)


def export_proof_bundle(
    bus: TrinityBus,
    task_id: str,
    out_dir: str | os.PathLike[str] | None = None,
    formats: tuple[str, ...] = ("json", "md"),
) -> dict[str, Any]:
    """Write proof bundle files for one task and return the written paths.

    Files are named proof-<task_id>.json and proof-<task_id>.md. The default
    output directory is the current working directory because bundles are
    export artifacts meant to leave the managed state directory.
    """
    bundle = build_proof_bundle(bus, task_id)
    directory = Path(out_dir).expanduser() if out_dir else Path.cwd()
    directory.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {}
    if "json" in formats:
        json_path = directory / f"proof-{task_id}.json"
        json_path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        files["json"] = str(json_path)
    if "md" in formats:
        md_path = directory / f"proof-{task_id}.md"
        md_path.write_text(render_markdown(bundle), encoding="utf-8")
        files["md"] = str(md_path)

    return {
        "task_id": task_id,
        "proof_bundle_version": PROOF_BUNDLE_VERSION,
        "out_dir": str(directory),
        "files": files,
    }
