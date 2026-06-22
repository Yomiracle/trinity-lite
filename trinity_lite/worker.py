"""Worker loop for Trinity Lite."""

from __future__ import annotations

import time
import traceback
from typing import Any

from .adapters import AdapterError, build_adapter, load_specs
from .bus import TrinityBus


def run_once(
    agent: str,
    bus: TrinityBus,
    agents_path: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any] | None:
    task = bus.task_for_worker(agent, task_id=task_id)
    if task is None:
        return None
    specs = load_specs(agents_path)
    spec = specs.get(agent)
    if spec is None:
        return bus.finish_worker(task["id"], error=f"agent not configured: {agent}")
    try:
        result = build_adapter(spec).run(task)
        return bus.finish_worker(task["id"], result=result)
    except (KeyboardInterrupt, SystemExit, MemoryError):
        raise
    except Exception as exc:
        tb = traceback.format_exc()
        return bus.finish_worker(task["id"], error=f"{exc}\n{tb}")


def run_loop(
    agent: str,
    bus: TrinityBus,
    agents_path: str | None = None,
    poll_seconds: float = 2.0,
) -> None:
    while True:
        handled = run_once(agent, bus, agents_path)
        if handled is None:
            time.sleep(poll_seconds)
