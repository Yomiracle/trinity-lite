"""Command line interface for Trinity Lite."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from .bus import TrinityBus
from .doctor import run_doctor
from .orchestrator import run_review_flow
from .router import resolve_route
from .worker import run_loop, run_once


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
          status, tasks, route, doctor, send, inbox"""


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

    auto = sub.add_parser("dispatch-auto", parents=[common], help="resolve route then dispatch")
    auto.add_argument("task")
    auto.add_argument("--source", default="user")
    auto.add_argument("--type", dest="task_type")
    auto.add_argument("--previous-agent")
    auto.add_argument("--cwd", default=os.getcwd())

    orchestrate = sub.add_parser("orchestrate", parents=[common], help="dispatch and run a primary task with optional review")
    orchestrate.add_argument("task")
    orchestrate.add_argument("--source", default="user")
    orchestrate.add_argument("--type", dest="task_type")
    orchestrate.add_argument("--previous-agent")
    orchestrate.add_argument("--cwd", default=os.getcwd())
    orchestrate.add_argument("--no-run", action="store_true", help="dispatch the primary task without running workers")

    status = sub.add_parser("status", parents=[common], help="show task status")
    status.add_argument("task_id")

    tasks = sub.add_parser("tasks", parents=[common], help="list recent tasks")
    tasks.add_argument("--agent")
    tasks.add_argument("--limit", type=int, default=20)

    worker = sub.add_parser("worker", parents=[common], help="run a worker for one agent")
    worker.add_argument("agent")
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--poll", type=float, default=2.0)

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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()

    # No-args: show friendly intro
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print(BANNER)
        return 0

    args = parser.parse_args(argv)

    # --version flag (before subcommand)
    if args.version:
        print(f"trinity-lite {_version()}")
        return 0

    # No subcommand but unknown args → show friendly intro
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
        print_json(bus.submit_task(
            source_agent=args.source,
            target_agent=args.target_agent,
            prompt=args.task,
            task_type=args.task_type,
            cwd=args.cwd,
        ))
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
        print_json(task)
        return 0
    if args.command == "orchestrate":
        print_json(run_review_flow(
            args.task,
            bus,
            args.routes,
            args.agents,
            args.source,
            args.task_type,
            args.previous_agent,
            args.cwd,
            run_workers=not args.no_run,
        ))
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

    raise AssertionError(f"unhandled command: {args.command}")


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
        cwd=os.getcwd(),
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
