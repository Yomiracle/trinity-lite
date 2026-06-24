"""Command line interface for Trinity Lite."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .bus import TrinityBus
from .doctor import run_doctor
from .orchestrator import run_review_flow
from .pipeline import load_pipeline, run_pipeline
from .router import resolve_route
from .worker import _default_pid_path, run_loop, run_once


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _version() -> str:
    """Return the installed version, favouring importlib.metadata."""
    try:
        from importlib.metadata import PackageNotFoundError, version  # Python >= 3.8
        return version("trinity-lite")
    except (ImportError, PackageNotFoundError):
        from . import __version__
        return __version__  # pragma: no cover — fallback for development


BANNER = """\
Trinity Lite — multi-agent task bus
====================================

Quick demo:  trinity-lite demo
Full help:   trinity-lite --help

Commands: demo, dispatch, dispatch-auto, worker, orchestrate,
          status, tasks, route, doctor, send, inbox, mcp,
          setup-models, detect-models"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trinity-lite")
    parser.add_argument("--version", action="store_true", help="show version and exit")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", default=None, help="SQLite database path")
    common.add_argument("--routes", default=None, help="routes JSON path")
    common.add_argument("--agents", default=None, help="agents JSON path")
    sub = parser.add_subparsers(dest="command")

    route = sub.add_parser("route", parents=[common], help="resolve a route without dispatching")
    route.add_argument("task")
    route.add_argument("--type", dest="task_type")
    route.add_argument("--previous-agent")

    dispatch = sub.add_parser("dispatch", parents=[common], help="dispatch to an explicit agent")
    dispatch.add_argument("target_agent")
    dispatch.add_argument("task")
    dispatch.add_argument("--source", default="user")
    dispatch.add_argument("--type", dest="task_type")
    dispatch.add_argument("--cwd", default=os.getcwd())
    dispatch.add_argument("--wait", action="store_true", help="block until task completes and print final result")
    dispatch.add_argument("--wait-timeout", type=float, default=300, help="timeout in seconds for --wait (default: 300)")

    auto = sub.add_parser("dispatch-auto", parents=[common], help="resolve route then dispatch")
    auto.add_argument("task")
    auto.add_argument("--source", default="user")
    auto.add_argument("--type", dest="task_type")
    auto.add_argument("--previous-agent")
    auto.add_argument("--cwd", default=os.getcwd())
    auto.add_argument("--wait", action="store_true", help="block until task completes and print final result")
    auto.add_argument("--wait-timeout", type=float, default=300, help="timeout in seconds for --wait (default: 300)")

    orchestrate = sub.add_parser("orchestrate", parents=[common], help="dispatch and run a primary task with optional review")
    orchestrate.add_argument("task")
    orchestrate.add_argument("--pipeline", default=None, help="path to pipeline YAML (uses pipeline orchestration instead of review flow)")
    orchestrate.add_argument("--source", default="user")
    orchestrate.add_argument("--type", dest="task_type")
    orchestrate.add_argument("--previous-agent")
    orchestrate.add_argument("--cwd", default=os.getcwd())
    orchestrate.add_argument("--no-run", action="store_true", help="dispatch the primary task without running workers")
    orchestrate.add_argument("--wait", action="store_true", help="block until orchestrated flow completes")
    orchestrate.add_argument("--wait-timeout", type=float, default=300, help="timeout in seconds for --wait (default: 300)")

    status = sub.add_parser("status", parents=[common], help="show task status")
    status.add_argument("task_id")

    tasks = sub.add_parser("tasks", parents=[common], help="list recent tasks")
    tasks.add_argument("--agent")
    tasks.add_argument("--limit", type=int, default=20)

    worker = sub.add_parser("worker", parents=[common], help="run a worker for one agent")
    worker.add_argument("agent")
    worker.add_argument("--once", action="store_true", help="run a single worker cycle and exit")
    worker.add_argument("--poll", type=float, default=2.0, help="poll interval in seconds (default: 2.0)")
    worker.add_argument("--daemon", action="store_true", help="run in continuous daemon mode with signal handling and PID locking")
    worker.add_argument("--pid-file", default=None, help="custom PID file path (default: ~/.trinity/workers/<agent>.pid)")

    send = sub.add_parser("send", parents=[common], help="send a durable message")
    send.add_argument("target_agent")
    send.add_argument("message")
    send.add_argument("--source", default="user")
    send.add_argument("--task-id")

    inbox = sub.add_parser("inbox", parents=[common], help="read durable messages")
    inbox.add_argument("agent")
    inbox.add_argument("--all", action="store_true")
    inbox.add_argument("--mark-read", action="store_true")
    inbox.add_argument("--limit", type=int, default=20)

    doctor = sub.add_parser("doctor", parents=[common], help="run environment checks")
    doctor.add_argument("--scan-root")
    doctor.add_argument("--runtime-root", help="runtime state directory for hygiene checks")
    doctor.add_argument(
        "--retired-port",
        action="append",
        type=int,
        default=[],
        help="TCP port that should not be listening, repeatable",
    )

    version_cmd = sub.add_parser("version", parents=[common], help="show version and exit")

    demo = sub.add_parser("demo", parents=[common], help="run a guided first-run demo")

    # Model pool commands
    setup_models = sub.add_parser("setup-models", parents=[common],
                                   help="interactive model pool setup (no JSON knowledge needed)")
    detect_models = sub.add_parser("detect-models", parents=[common],
                                    help="auto-detect available LLM backends from your environment")
    detect_models.add_argument("--no-save", action="store_true",
                                help="print result without saving to disk")

    mcp = sub.add_parser("mcp", help="MCP server control")
    mcp_sub = mcp.add_subparsers(dest="mcp_command")
    mcp_sub.required = False
    mcp_serve = mcp_sub.add_parser("serve", parents=[common], help="start MCP server on stdio")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()

    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print(BANNER)
        return 0

    args = parser.parse_args(argv)

    if args.version:
        print(f"trinity-lite {_version()}")
        return 0

    if args.command is None:
        print(BANNER)
        return 0

    try:
        return run_command(args)
    except (KeyError, OSError, ValueError) as exc:
        print_json({"error": str(exc)})
        return 2


def run_command(args: argparse.Namespace) -> int:
    bus = TrinityBus(args.db)

    if args.command == "version":
        print(f"trinity-lite {_version()}")
        return 0

    if args.command == "route":
        print_json(resolve_route(args.task, args.task_type, args.previous_agent, args.routes, args.agents))
        return 0
    if args.command == "dispatch":
        task = bus.submit_task(
            source_agent=args.source,
            target_agent=args.target_agent,
            prompt=args.task,
            task_type=args.task_type,
            cwd=args.cwd,
        )
        if getattr(args, "wait", False):
            task = _wait_for_task(bus, task["id"], args.target_agent, args.agents, args.wait_timeout)
        print_json(task)
        return 0
    if args.command == "dispatch-auto":
        route = resolve_route(args.task, args.task_type, args.previous_agent, args.routes, args.agents)
        task = bus.submit_task(
            source_agent=args.source,
            target_agent=route["agent"],
            prompt=args.task,
            task_type=route["task_type"],
            cwd=args.cwd,
        )
        task["route"] = route
        if getattr(args, "wait", False):
            task = _wait_for_task(bus, task["id"], route["agent"], args.agents, args.wait_timeout)
        print_json(task)
        return 0
    if args.command == "orchestrate":
        if args.pipeline:
            pipeline = load_pipeline(args.pipeline)
            result = run_pipeline(
                pipeline,
                args.task,
                bus,
                args.routes,
                args.agents,
                args.source,
                cwd=args.cwd,
                run_workers=not args.no_run and not getattr(args, "wait", False),
            )
        else:
            result = run_review_flow(
                args.task,
                bus,
                args.routes,
                args.agents,
                args.source,
                args.task_type,
                args.previous_agent,
                args.cwd,
                run_workers=not args.no_run and not getattr(args, "wait", False),
            )
        if getattr(args, "wait", False):
            result = _wait_for_flow(bus, result, args.agents, args.routes, args.wait_timeout)
        print_json(result)
        return 0
    if args.command == "status":
        print_json(bus.get_task(args.task_id))
        return 0
    if args.command == "tasks":
        print_json(bus.list_tasks(args.agent, args.limit))
        return 0
    if args.command == "worker":
        if args.once:
            print_json(run_once(args.agent, bus, args.agents))
            return 0
        if args.daemon:
            pid_file = args.pid_file or str(_default_pid_path(args.agent))
            return run_loop(args.agent, bus, args.agents, args.poll, pid_file=pid_file)
        run_loop(args.agent, bus, args.agents, args.poll)
        return 0
    if args.command == "send":
        print_json(bus.send_message(args.source, args.target_agent, args.message, args.task_id))
        return 0
    if args.command == "inbox":
        print_json(bus.inbox(args.agent, unread_only=not args.all, mark_read=args.mark_read, limit=args.limit))
        return 0
    if args.command == "doctor":
        print_json(run_doctor(
            args.db,
            args.routes,
            args.agents,
            args.scan_root,
            args.runtime_root,
            args.retired_port,
        ))
        return 0
    if args.command == "demo":
        return _demo(args, bus)
    if args.command == "mcp":
        return _mcp(args, bus)

    # Model pool commands (no bus needed)
    if args.command == "setup-models":
        from .model_pool_wizard import main as wizard_main
        wizard_main()
        return 0
    if args.command == "detect-models":
        from .model_autodetect import scan, save_pool
        pool = scan()
        print(f"Detected {len(pool)} backend(s):")
        for name, info in pool.items():
            print(f"  • {name} ({info['tier']}) — {', '.join(info['strengths'][:3])}")
        if not getattr(args, "no_save", False):
            path = save_pool(pool)
            print(f"Saved to {path}")
        return 0

    raise AssertionError(f"unhandled command: {args.command}")
def _wait_for_task(
    bus: TrinityBus,
    task_id: str,
    agent: str,
    agents_path: str | None,
    timeout: float,
) -> dict[str, Any]:
    """Run worker cycles for agent until task completes or timeout."""
    import time as _time
    from .bus import TERMINAL_STATUSES
    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        task = bus.get_task(task_id)
        if task["status"] in TERMINAL_STATUSES:
            return task
        # Try to process one queued/running task
        run_once(agent, bus, agents_path, task_id=task_id)
        _time.sleep(0.1)
    raise TimeoutError(f"task {task_id} did not finish within {timeout}s")


def _wait_for_flow(
    bus: TrinityBus,
    flow: dict[str, Any],
    agents_path: str | None,
    routes_path: str | None,
    timeout: float,
) -> dict[str, Any]:
    """Run workers to complete a review flow until terminal."""
    import time as _time
    from .bus import TERMINAL_STATUSES
    from .orchestrator import _review_prompt

    primary_id = flow["primary_task"]["id"]
    primary_agent = flow["route"]["agent"]
    route = flow["route"]

    # Review may not have been dispatched yet (if run_workers=False was used)
    review_id = None
    review_agent = None
    review = flow.get("review_task")
    if review:
        review_id = review["id"]
        review_agent = flow.get("review_route", {}).get("agent") if flow.get("review_route") else None

    deadline = _time.monotonic() + timeout
    review_dispatched = review_id is not None

    while _time.monotonic() < deadline:
        primary = bus.get_task(primary_id)

        # If primary just completed and review is required but not yet dispatched
        if (primary["status"] == "completed"
                and route["review_required"]
                and not review_dispatched):
            review_prompt_text = _review_prompt(primary)
            review_route = resolve_route(
                review_prompt_text,
                "code_review",
                route["agent"],
                routes_path,
                agents_path,
            )
            review_task = bus.submit_task(
                source_agent=route["agent"],
                target_agent=review_route["agent"],
                prompt=review_prompt_text,
                task_type=review_route["task_type"],
                cwd=primary["cwd"],
                depth=int(primary["depth"]) + 1,
            )
            review_id = review_task["id"]
            review_agent = review_route["agent"]
            review_dispatched = True
            flow["review_route"] = review_route
            flow["review_task"] = review_task

        review_done = True
        if review_id is not None:
            review_task = bus.get_task(review_id)
            review_done = review_task["status"] in TERMINAL_STATUSES

        if primary["status"] in TERMINAL_STATUSES and review_done:
            flow["primary_task"] = primary
            if review_id is not None:
                flow["review_task"] = bus.get_task(review_id)
            flow["acceptance_status"] = _acceptance_status_from_flow(
                flow["route"], primary, flow.get("review_task")
            )
            return flow

        if primary["status"] not in TERMINAL_STATUSES:
            run_once(primary_agent, bus, agents_path, task_id=primary_id)
        elif review_id is not None and review_agent:
            run_once(review_agent, bus, agents_path, task_id=review_id)
        _time.sleep(0.1)
    raise TimeoutError(f"flow for {primary_id} did not finish within {timeout}s")


def _acceptance_status_from_flow(
    route: dict[str, Any],
    primary_task: dict[str, Any],
    review_task: dict[str, Any] | None,
) -> str:
    from .orchestrator import _acceptance_status
    return _acceptance_status(route, primary_task, review_task)


def _mcp(args: argparse.Namespace, bus: TrinityBus) -> int:
    """Handle 'trinity-lite mcp' subcommand."""
    if args.mcp_command == "serve":
        from .mcp_server import serve as mcp_serve

        mcp_serve(bus, agents_path=args.agents, routes_path=args.routes)
        return 0
    # Show mcp help
    print("usage: trinity-lite mcp serve [--db PATH] [--routes PATH] [--agents PATH]")
    print("")
    print("MCP server control")
    print("")
    print("commands:")
    print("  serve   start MCP server on stdio")
    return 0


def _demo(args: argparse.Namespace, bus: TrinityBus) -> int:
    """Run a guided demo flow with human-friendly output."""

    print("Trinity Lite Demo")
    print("=================")

    # ---- 1. Doctor ----
    print("→ Running environment checks...")
    try:
        health = run_doctor(args.db, args.routes, args.agents)
        status_label = "healthy" if health["status"] == "healthy" else "unhealthy"
        icon = "✓" if health["status"] == "healthy" else "✗"
        print(f"  {icon} Doctor: {status_label}")
        for check in health.get("checks", []):
            mark = "✓" if check["ok"] else "✗"
            print(f"    {mark} {check['name']}: {str(check.get('detail', '')).strip()}")
    except Exception as exc:
        print(f"  ✗ Doctor: {exc}")
    print()

    # ---- 2. Dispatch + worker cycle (full orchestrated flow) ----
    demo_prompt = "write a hello world function in Python"
    print("→ Dispatching demo task...")
    flow = run_review_flow(
        demo_prompt,
        bus,
        args.routes,
        args.agents,
        source_agent="user",
        cwd=str(Path.home()),
        run_workers=True,
    )
    primary = flow["primary_task"]
    route = flow["route"]

    print(f"  Task ID: {primary['id']}")
    print(f"  Routed to: {route['agent']}")
    print()

    # ---- 3. Codex worker already ran in run_review_flow ----
    print(f"→ Running mock worker ({route['agent']})...")
    icon = "✓" if primary["status"] == "completed" else "✗"
    print(f"  {icon} Task {primary['id']} {primary['status']}")
    print()

    # ---- 4. Claude Code review (already ran via run_review_flow) ----
    print("→ Running mock worker (claude_code)...")
    review_task = flow.get("review_task")
    if review_task:
        icon = "✓" if review_task.get("status") == "completed" else "✗"
        print(f"  {icon} Review {review_task.get('status')}")
    else:
        print("  - No review task required for this demo")
    print()

    # ---- 5. Results ----
    print("→ Results:")
    final = bus.get_task(primary["id"])
    print(f"  Task: {final['prompt']}")
    print(f"  Status: {final['status']}")
    if final.get("result"):
        result_text = final["result"]
        if len(result_text) > 200:
            result_text = result_text[:200] + "..."
        print(f"  Result: {result_text}")
    if final.get("error"):
        print(f"  Error: {final['error']}")
    if review_task:
        review_final = bus.get_task(review_task["id"])
        print(f"  Review: {review_final.get('status')}")
        if review_final.get("result"):
            r_text = review_final["result"]
            if len(r_text) > 200:
                r_text = r_text[:200] + "..."
            print(f"  Review result: {r_text}")
    print()

    # ---- 6. Next steps ----
    print("Next steps:")
    print("  • See all tasks: trinity-lite tasks")
    print("  • Connect real agents: docs/REAL_AGENTS.md")
    print("  • Full docs: https://github.com/Yomiracle/trinity-lite")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
