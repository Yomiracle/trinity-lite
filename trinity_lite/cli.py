"""Command line interface for Trinity Lite."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from .bus import TrinityBus
from .doctor import run_doctor
from .router import resolve_route
from .worker import run_loop, run_once


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trinity-lite")
    parser.add_argument("--db", default=None, help="SQLite database path")
    parser.add_argument("--routes", default=None, help="routes JSON path")
    parser.add_argument("--agents", default=None, help="agents JSON path")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", default=argparse.SUPPRESS, help="SQLite database path")
    common.add_argument("--routes", default=argparse.SUPPRESS, help="routes JSON path")
    common.add_argument("--agents", default=argparse.SUPPRESS, help="agents JSON path")
    sub = parser.add_subparsers(dest="command", required=True)

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

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_command(args)
    except (KeyError, OSError, ValueError) as exc:
        print_json({"error": str(exc)})
        return 2


def run_command(args: argparse.Namespace) -> int:
    bus = TrinityBus(args.db)

    if args.command == "route":
        print_json(resolve_route(args.task, args.task_type, args.previous_agent, args.routes))
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
        route = resolve_route(args.task, args.task_type, args.previous_agent, args.routes)
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
        print_json(run_doctor(args.db, args.routes, args.agents, args.scan_root))
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
