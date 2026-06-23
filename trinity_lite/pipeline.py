"""YAML pipeline orchestration for Trinity Lite.

Defines load/validate/execute for N-step sequential pipelines.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .bus import TrinityBus
from .router import resolve_route
from .worker import run_once


def _load_yaml(path: str) -> dict[str, Any]:
    """Load a YAML file, falling back gracefully."""
    try:
        import yaml

        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except ImportError:
        pass

    import json

    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, ValueError):
        raise ValueError(
            f"Cannot parse pipeline file {path}: yaml module not available and file is not valid JSON"
        )


_RE_STEP_REF = re.compile(
    r"\{steps\.([a-zA-Z_][a-zA-Z0-9_]*)\.result\}"
)

REQUIRED_STEP_FIELDS = ("id", "agent", "task_type", "prompt_template")

def _validate_pipeline(pipeline: dict[str, Any]) -> None:
    """Validate a loaded pipeline dictionary."""
    if not isinstance(pipeline, dict):
        raise ValueError("pipeline must be a dictionary")

    name = pipeline.get("name")
    if not name or not isinstance(name, str):
        raise ValueError("pipeline must have non-empty name")

    steps = pipeline.get("steps")
    if not steps or not isinstance(steps, list):
        raise ValueError("pipeline must have non-empty steps list")

    step_ids: set[str] = set()

    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"step[{i}] must be dict, got {type(step).__name__}")

        for field in REQUIRED_STEP_FIELDS:
            val = step.get(field)
            if not val or not isinstance(val, str):
                raise ValueError(f"step[{i}] missing field {field}: {val!r}")

        sid = step["id"]
        if sid in step_ids:
            raise ValueError(f"duplicate step id: {sid!r}")
        step_ids.add(sid)

    for step in steps:
        refs = _RE_STEP_REF.findall(step["prompt_template"])
        for ref in refs:
            if ref not in step_ids:
                raise ValueError(f"step references unknown step: {ref}")

def load_pipeline(path: str) -> dict[str, Any]:
    """Load and validate a pipeline YAML (or JSON) file."""
    pipeline = _load_yaml(path)
    _validate_pipeline(pipeline)
    return pipeline

def resolve_step_prompt(step: dict[str, Any], task: str, step_results: dict[str, Any]) -> str:
    """Render prompt_template with {task} and step references."""
    template = step["prompt_template"]

    def _replace_step_ref(m):
        sid = m.group(1)
        info = step_results.get(sid, {})
        return str(info.get("result") or info.get("error") or "")

    rendered = _RE_STEP_REF.sub(_replace_step_ref, template)
    rendered = rendered.replace("{task}", task)
    return rendered

def run_pipeline(
    pipeline: dict[str, Any],
    task: str,
    bus: TrinityBus,
    routes_path: str | None = None,
    agents_path: str | None = None,
    source_agent: str = "user",
    cwd: str | None = None,
    run_workers: bool = True,
) -> dict[str, Any]:
    """Execute pipeline steps sequentially."""
    workdir = cwd or os.getcwd()
    step_results: dict[str, Any] = {}
    step_summaries: list[dict[str, Any]] = []

    for step in pipeline["steps"]:
        sid = step["id"]
        rendered_prompt = resolve_step_prompt(step, task, step_results)
        target_agent = step["agent"]

        submitted = bus.submit_task(
            source_agent=source_agent,
            target_agent=target_agent,
            prompt=rendered_prompt,
            task_type=step.get("task_type"),
            cwd=workdir,
        )

        if run_workers:
            result = run_once(target_agent, bus, agents_path, task_id=submitted["id"])
            if result is None:
                result = bus.get_task(submitted["id"])
        else:
            result = submitted

        step_results[sid] = result
        summary = {
            "id": sid,
            "task_id": result["id"] if result else submitted["id"],
            "status": result.get("status", "unknown") if result else "unknown",
            "result": result.get("result") if result else None,
        }
        step_summaries.append(summary)

        if result and result.get("status") == "failed":
            break

    all_done = all(s["status"] == "completed" for s in step_summaries)
    any_fail = any(s["status"] == "failed" for s in step_summaries)
    if any_fail:
        overall = "failed"
    elif all_done:
        overall = "completed"
    else:
        overall = "queued"

    return {
        "pipeline_name": pipeline["name"],
        "steps": step_summaries,
        "overall_status": overall,
    }