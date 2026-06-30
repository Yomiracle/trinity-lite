"""MCP server for Trinity Lite. Zero-dependency JSON-RPC 2.0 over stdio.

Reads line-delimited JSON-RPC 2.0 from stdin, writes responses to stdout.
All diagnostic output goes to stderr.
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Any

from .bus import TERMINAL_STATUSES, TrinityBus
from .doctor import run_doctor
from .guard import GuardError
from .pipeline import load_pipeline, run_pipeline
from .router import resolve_route
from .worker import _default_pid_path, _read_pid_file, run_once as worker_run_once
from . import __version__

# ---------------------------------------------------------------------------
# agent-skill-system integration (optional, graceful fallback)
# ---------------------------------------------------------------------------

_SKILL_ENGINE_AVAILABLE = False
_SKILL_BANK = None
_SKILL_BANK_DIR = None


def _find_skills_dir() -> str:
    """Locate the agent-skill-system skills/ bank directory."""
    # Env override
    env_dir = os.environ.get("TRINITY_SKILLS_DIR", "")
    if env_dir and Path(env_dir).is_dir():
        return env_dir
    # Check ~/.trinity/skills
    home_skills = Path.home() / ".trinity" / "skills"
    if home_skills.is_dir():
        return str(home_skills)
    # Check ~/agent-skill-system/skills (git-clone default)
    dev_skills = Path.home() / "agent-skill-system" / "skills"
    if dev_skills.is_dir():
        return str(dev_skills)
    # Default (will be auto-created by SkillBank)
    return str(home_skills)


def _init_skill_engine() -> bool:
    """Lazy-init the agent-skill-system engine.  Cached after first call."""
    global _SKILL_ENGINE_AVAILABLE, _SKILL_BANK, _SKILL_BANK_DIR
    if _SKILL_ENGINE_AVAILABLE:
        return True
    try:
        from engine.bank import SkillBank      # type: ignore[import-untyped]
        _SKILL_BANK_DIR = _find_skills_dir()
        _SKILL_BANK = SkillBank(_SKILL_BANK_DIR)
        _SKILL_BANK.scan_directory()
        _SKILL_ENGINE_AVAILABLE = True
        return True
    except ImportError:
        _SKILL_ENGINE_AVAILABLE = False
        return False


JSONRPC_VERSION = "2.0"
PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "trinity-lite-mcp"
SERVER_VERSION = __version__

# ---------------------------------------------------------------------------
# Tool definitions (MCP schema)
# ---------------------------------------------------------------------------


def _tool_def(name, description, properties, required, annotations=None):
    tool = {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }
    if annotations:
        tool["annotations"] = annotations
    return tool


READ_ONLY_TOOL = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


STATEFUL_LOCAL_TOOL = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": False,
}


AGENT_EXECUTION_TOOL = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": True,
}


def _desc(*parts):
    return " ".join(part.strip() for part in parts)


TOOL_DEFINITIONS = [
    _tool_def(
        "trinity_dispatch",
        _desc(
            "Create a durable task for one explicit Trinity agent and run one worker cycle for that agent.",
            "Use this when the caller already knows the target agent; use trinity_dispatch_auto when routing should choose the agent.",
            "This writes to the local task database and may execute the configured agent command; with wait=true it returns the final compact task or a timeout error.",
        ),
        {
            "target_agent": {"type": "string", "description": "Exact recipient agent id, such as codex, claude_code, or hermes."},
            "task": {"type": "string", "description": "Task prompt to persist and deliver to the target agent."},
            "source_agent": {"type": "string", "description": "Originating agent id recorded on the task; defaults to mcp."},
            "cwd": {"type": "string", "description": "Working directory passed to the task; defaults to the user's home directory."},
            "task_type": {"type": "string", "description": "Optional task type metadata for routing and audit records."},
            "wait": {"type": "boolean", "description": "If true, block until the task reaches a terminal state or wait_timeout expires."},
            "wait_timeout": {"type": "number", "description": "Maximum seconds to wait when wait=true; defaults to the server wait timeout."},
        },
        ["target_agent", "task"],
        AGENT_EXECUTION_TOOL,
    ),
    _tool_def(
        "trinity_dispatch_auto",
        _desc(
            "Resolve the best Trinity agent with the local route table, create a durable task, and run one worker cycle.",
            "Use this when the caller has a task but should not pick the agent manually; use trinity_dispatch for an explicit target.",
            "This writes route evidence and task state to the local database and may execute the selected agent command; the result includes compact task and route metadata.",
        ),
        {
            "task": {"type": "string", "description": "Task prompt used for route selection and delivery."},
            "source_agent": {"type": "string", "description": "Originating agent id recorded on the task; defaults to mcp."},
            "cwd": {"type": "string", "description": "Working directory passed to the selected agent; defaults to the user's home directory."},
            "task_type": {"type": "string", "description": "Optional task type hint that can override or narrow route matching."},
            "previous_agent": {"type": "string", "description": "Agent id to avoid when resolving opposite-review or retry routes."},
            "wait": {"type": "boolean", "description": "If true, block until the routed task reaches a terminal state or wait_timeout expires."},
            "wait_timeout": {"type": "number", "description": "Maximum seconds to wait when wait=true; defaults to the server wait timeout."},
        },
        ["task"],
        AGENT_EXECUTION_TOOL,
    ),
    _tool_def(
        "trinity_orchestrate",
        _desc(
            "Run a multi-step Trinity workflow from a pipeline file or the built-in implement-then-review flow.",
            "Use this for work that needs sequencing, review gates, or multiple task records; use dispatch tools for a single agent task.",
            "This creates and updates local task records and may execute one or more configured agent commands; it returns pipeline or review-flow evidence.",
        ),
        {
            "task": {"type": "string", "description": "Top-level task prompt for the pipeline or review flow."},
            "source_agent": {"type": "string", "description": "Originating agent id recorded on created tasks; defaults to mcp."},
            "cwd": {"type": "string", "description": "Working directory used by pipeline steps or review flow; defaults to home."},
            "task_type": {"type": "string", "description": "Optional task type hint for the default review flow route."},
            "previous_agent": {"type": "string", "description": "Agent id to avoid when resolving reviewer or retry routes."},
            "pipeline": {"type": "string", "description": "Path to a YAML pipeline file; omit to run the default review flow."},
            "wait": {"type": "boolean", "description": "Reserved for wait-aware clients; pipeline workers run in-process."},
            "wait_timeout": {"type": "number", "description": "Reserved wait timeout in seconds for wait-aware orchestration clients."},
        },
        ["task"],
        AGENT_EXECUTION_TOOL,
    ),
    _tool_def(
        "trinity_status",
        _desc(
            "Read the current state, result, route evidence, and acceptance metadata for one task id.",
            "Use this after dispatch or orchestration to poll progress or recover a result after a timeout.",
            "This is read-only and does not run workers or mark messages as read; it returns a compact task object or task-not-found error.",
        ),
        {
            "task_id": {"type": "string", "description": "Task identifier returned by dispatch, orchestration, or task listing."},
        },
        ["task_id"],
        READ_ONLY_TOOL,
    ),
    _tool_def(
        "trinity_latest",
        _desc(
            "Recover the newest task submitted by one source agent when the task id is unknown.",
            "Use this after an interrupted MCP wait or lost client response, then call trinity_status for the returned primary task id.",
            "By default it skips secondary review children so the returned task is the user-facing parent; set include_reviews=true to inspect review tasks.",
        ),
        {
            "agent": {"type": "string", "description": "Source agent id whose latest submitted task should be returned."},
            "include_reviews": {"type": "boolean", "description": "When true, include secondary review child tasks; defaults to false."},
        },
        ["agent"],
        READ_ONLY_TOOL,
    ),
    _tool_def(
        "trinity_tasks",
        _desc(
            "List recent durable task records, optionally filtered by source or target agent.",
            "Use this to inspect queue history or find a task id before calling trinity_status.",
            "This is read-only, does not run workers, and returns compact task objects in recent-first order.",
        ),
        {
            "agent": {"type": "string", "description": "Optional agent id to match against source_agent or target_agent."},
            "limit": {"type": "integer", "description": "Maximum tasks to return; defaults to 20 and is capped by the server."},
        },
        [],
        READ_ONLY_TOOL,
    ),
    _tool_def(
        "trinity_worker",
        _desc(
            "Run one local worker cycle for a named agent and process one queued task if available.",
            "Use this to manually drain the queue or retry a specific queued task; use trinity_worker_daemon for a background worker.",
            "This may execute the agent command and update task state; it returns no_task or the compact processed task.",
        ),
        {
            "agent": {"type": "string", "description": "Agent id whose queue should be processed."},
            "task_id": {"type": "string", "description": "Optional specific queued task id to process instead of the next task."},
        },
        ["agent"],
        AGENT_EXECUTION_TOOL,
    ),
    _tool_def(
        "trinity_worker_daemon",
        _desc(
            "Start, stop, or check the local background worker process for one agent.",
            "Use status for a process check, start to keep an agent queue draining, and stop to terminate that daemon.",
            "Start and stop modify local process state and PID files; responses include running, started, stopped, pid, and pid_file fields.",
        ),
        {
            "agent": {"type": "string", "description": "Agent id whose worker daemon should be controlled."},
            "action": {"type": "string", "enum": ["start", "stop", "status"], "description": "Daemon action: status checks process state, start launches, stop terminates."},
        },
        ["agent", "action"],
        STATEFUL_LOCAL_TOOL,
    ),
    _tool_def(
        "trinity_doctor",
        _desc(
            "Run Trinity Lite health, configuration, database, publish-readiness, and runtime hygiene checks.",
            "Use this before release, after setup changes, or when routing and worker behavior looks wrong.",
            "This is read-only: it scans configured files, database state, optional repository roots, and retired ports, then returns a structured health report.",
        ),
        {
            "scan_root": {"type": "string", "description": "Optional repository root for publish-readiness and packaging checks."},
            "runtime_root": {"type": "string", "description": "Optional runtime directory to inspect for local hygiene checks."},
            "retired_ports": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Optional TCP ports that should be unused; listening ports are reported as hygiene issues.",
            },
        },
        [],
        READ_ONLY_TOOL,
    ),
    _tool_def(
        "trinity_inbox",
        _desc(
            "Read durable inter-agent messages addressed to one agent from the local Trinity database.",
            "Use this to recover completed work, review notes, or follow-up messages; use trinity_send to create a new message.",
            "By default it reads unread messages, but mark_read=true updates message read state; it returns message records.",
        ),
        {
            "agent": {"type": "string", "description": "Recipient agent id whose inbox should be read."},
            "unread_only": {"type": "boolean", "description": "When true, return only unread messages; defaults to true."},
            "mark_read": {"type": "boolean", "description": "When true, mark returned messages as read after fetching them."},
            "limit": {"type": "integer", "description": "Maximum messages to return; defaults to 20 and is capped by the server."},
        },
        ["agent"],
        STATEFUL_LOCAL_TOOL,
    ),
    _tool_def(
        "trinity_send",
        _desc(
            "Write a durable message from one Trinity agent to another agent's inbox.",
            "Use this for follow-up context, review handoffs, or task-linked notes; use trinity_dispatch to create executable work.",
            "This writes to the local message database, does not run a worker, and returns the stored message record.",
        ),
        {
            "target_agent": {"type": "string", "description": "Recipient agent id that will receive the inbox message."},
            "message": {"type": "string", "description": "Message body to persist in the target inbox."},
            "source_agent": {"type": "string", "description": "Sender agent id recorded on the message; defaults to mcp."},
            "task_id": {"type": "string", "description": "Optional associated task id for threading or audit context."},
        },
        ["target_agent", "message"],
        STATEFUL_LOCAL_TOOL,
    ),
    _tool_def(
        "trinity_skill_search",
        _desc(
            "Search the optional agent-skill-system index for skills relevant to a task or keyword query.",
            "Use this before loading a full skill when the exact skill name is unknown; use trinity_skill_load after selecting a result.",
            "This is read-only and returns ranked skill metadata, or an installation hint if agent-skill-system is not installed.",
        ),
        {
            "query": {"type": "string", "description": "Task description or keywords used to rank matching skills."},
            "limit": {"type": "integer", "description": "Maximum results to return; defaults to 5 and is capped at 20."},
        },
        ["query"],
        READ_ONLY_TOOL,
    ),
    _tool_def(
        "trinity_skill_load",
        _desc(
            "Load the full SKILL.md, memory, schema, keywords, and generated system prompt for one exact skill name.",
            "Use this after trinity_skill_search identifies the correct skill; do not use it for broad discovery.",
            "This is read-only and returns the skill bundle, or a not-found response with available skill names when possible.",
        ),
        {
            "skill_name": {"type": "string", "description": "Exact skill name to load from the local skill bank."},
        },
        ["skill_name"],
        READ_ONLY_TOOL,
    ),
]

TOOLS_BY_NAME = {t["name"]: t for t in TOOL_DEFINITIONS}

# ---------------------------------------------------------------------------
# Resource definitions
# ---------------------------------------------------------------------------

RESOURCE_DEFINITIONS = [
    {
        "uri": "trinity://health",
        "name": "System Health",
        "description": "Trinity Lite system health status",
        "mimeType": "application/json",
    },
    {
        "uri": "trinity://tasks/recent",
        "name": "Recent Tasks",
        "description": "Recent task list (last 20 by default)",
        "mimeType": "application/json",
    },
    {
        "uri": "trinity://tasks/{task_id}",
        "name": "Task Detail",
        "description": "Single task detail by id",
        "mimeType": "application/json",
    },
]

# ---------------------------------------------------------------------------
# Allowed methods
# ---------------------------------------------------------------------------

ALLOWED_METHODS = {
    "initialize",
    "initialized",
    "tools/list",
    "tools/call",
    "resources/list",
    "resources/read",
    "shutdown",
}

RESERVED_AGENT_IDS = {"user", "mcp"}

# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------


def jsonrpc_response(id_, result=None, error=None):
    msg = {"jsonrpc": JSONRPC_VERSION, "id": id_}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    return msg


def jsonrpc_error(id_, code, message, data=None):
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return jsonrpc_response(id_, error=err)


def _compact_task(task):
    """Return a compact representation of a task."""
    keys = [
        "id", "source_agent", "target_agent", "task_type", "prompt",
        "cwd", "status", "depth", "result", "error",
        "created_at", "started_at", "finished_at",
        "parent_task_id", "review_task_id", "gate_status",
        "gate_updated_at", "route_json", "verification_json",
        "acceptance_status", "acceptance_reason", "accepted_at",
    ]
    return {k: task[k] for k in keys if k in task}


def _self_route_result(source, route, task, cwd="", task_type=None):
    return {
        "ok": True,
        "status": "self_route",
        "source_agent": source,
        "target_agent": source,
        "task": task,
        "cwd": cwd,
        "task_type": route.get("task_type") or task_type,
        "route": route,
        "dispatched": False,
        "task_id": None,
        "recommended_action": "execute locally in the current agent, or dispatch explicitly to a different agent for review",
    }


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

_MAX_PROMPT_LENGTH = 100_000
_MAX_MESSAGE_LENGTH = 100_000

# ASCII control characters (0x00-0x1F) except tab, newline, carriage return
_CONTROL_CHARS = set(range(0x20)) - {0x09, 0x0A, 0x0D}


def _validate_task_id(val):
    if not isinstance(val, str) or len(val) != 12:
        raise ValueError("task_id must be a 12-character hex string")
    int(val, 16)  # raises ValueError if not hex
    return val


def _validate_agent_id(val, known_agents):
    if not isinstance(val, str) or not val:
        raise ValueError("agent id must be a non-empty string")
    if len(val) > 128:
        raise ValueError("agent id too long")
    if val not in known_agents and val not in RESERVED_AGENT_IDS:
        raise ValueError("unknown agent id: {}".format(val))
    return val


def _validate_text(val, max_len=_MAX_PROMPT_LENGTH):
    if not isinstance(val, str):
        raise ValueError("must be a string")
    if len(val) > max_len:
        raise ValueError("text too long (max {})".format(max_len))
    if any(ord(ch) in _CONTROL_CHARS for ch in val):
        raise ValueError("text contains control characters")
    return val


def _validate_limit(val, default=20, maximum=100):
    if val is None:
        return default
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        raise ValueError("limit must be a number")
    ival = int(val)
    if ival < 1:
        raise ValueError("limit must be >= 1")
    if ival > maximum:
        raise ValueError("limit must be <= {}".format(maximum))
    return ival


def _validate_timeout(val, default=600):
    if val is None:
        return default
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        raise ValueError("timeout must be a number")
    fval = float(val)
    if fval <= 0:
        raise ValueError("timeout must be positive")
    if fval > 3600:
        raise ValueError("timeout must be <= 3600")
    return fval


def _get_known_agents(bus, agents_path):
    """Return the set of known agent ids from config + reserved."""
    from .adapters import load_specs

    try:
        specs = load_specs(agents_path)
    except Exception:
        specs = {}
    return set(specs.keys()) | RESERVED_AGENT_IDS


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def _handle_trinity_dispatch(params, bus, agents_path, routes_path):
    target = _validate_text(params["target_agent"], 128)
    prompt = _validate_text(params["task"])
    source = params.get("source_agent", "mcp")
    source = _validate_text(source, 128)
    cwd = params.get("cwd", os.environ.get("HOME", str(Path.home())))
    task_type = params.get("task_type", "")
    wait = params.get("wait", False)
    wait_timeout = _validate_timeout(params.get("wait_timeout"))

    known = _get_known_agents(bus, agents_path)
    _validate_agent_id(source, known)
    _validate_agent_id(target, known)

    # Layer 2: self-delegation check
    if source == target:
        return jsonrpc_response(1, _self_route_result(source, {"agent": source}, prompt, cwd, task_type))

    task = bus.submit_task(
        source_agent=source,
        target_agent=target,
        prompt=prompt,
        task_type=task_type if task_type else None,
        cwd=cwd,
    )
    # Run worker once so the task completes in-process
    worker_run_once(target, bus, agents_path, task_id=task["id"])
    task = bus.get_task(task["id"])

    if wait:
        try:
            task = bus.await_task(task["id"], timeout=wait_timeout)
        except TimeoutError:
            return jsonrpc_error(
                1, -32003, "task {} did not finish within {}s".format(task["id"], wait_timeout),
            )

    return jsonrpc_response(1, _compact_task(task))


def _handle_trinity_dispatch_auto(params, bus, agents_path, routes_path):
    prompt = _validate_text(params["task"])
    source = params.get("source_agent", "mcp")
    source = _validate_text(source, 128)
    cwd = params.get("cwd", os.environ.get("HOME", str(Path.home())))
    task_type = params.get("task_type") or None
    previous_agent = params.get("previous_agent") or None
    wait = params.get("wait", False)
    wait_timeout = _validate_timeout(params.get("wait_timeout"))

    known = _get_known_agents(bus, agents_path)
    _validate_agent_id(source, known)
    if previous_agent:
        _validate_agent_id(previous_agent, known)

    route = resolve_route(prompt, task_type, previous_agent, routes_path, agents_path)
    target = route["agent"]

    # Layer 3: route-result check
    if source == target:
        return jsonrpc_response(1, _self_route_result(source, route, prompt, cwd, task_type))

    task = bus.submit_task(
        source_agent=source,
        target_agent=target,
        prompt=prompt,
        task_type=route["task_type"],
        cwd=cwd,
        route=route,
    )
    worker_run_once(target, bus, agents_path, task_id=task["id"])
    task = bus.get_task(task["id"])

    if wait:
        try:
            task = bus.await_task(task["id"], timeout=wait_timeout)
        except TimeoutError:
            return jsonrpc_error(
                1, -32003, "task {} did not finish within {}s".format(task["id"], wait_timeout),
            )

    result = _compact_task(task)
    result["route"] = route
    return jsonrpc_response(1, result)


def _handle_trinity_status(params, bus, agents_path, routes_path):
    task_id = _validate_task_id(params["task_id"])
    try:
        task = bus.get_task(task_id)
    except KeyError:
        return jsonrpc_error(1, -32002, "task not found: {}".format(task_id))
    return jsonrpc_response(1, _compact_task(task))


def _handle_trinity_tasks(params, bus, agents_path, routes_path):
    agent = params.get("agent", "")
    limit = _validate_limit(params.get("limit"))
    known = _get_known_agents(bus, agents_path)
    if agent:
        _validate_agent_id(agent, known)
        agent_arg = agent
    else:
        agent_arg = None
    tasks = bus.list_tasks(agent_arg, limit)
    return jsonrpc_response(1, [_compact_task(t) for t in tasks])


def _handle_trinity_latest(params, bus, agents_path, routes_path):
    agent = _validate_text(params["agent"], 128)
    include_reviews = params.get("include_reviews", False)
    if not isinstance(include_reviews, bool):
        raise ValueError("include_reviews must be a boolean")

    known = _get_known_agents(bus, agents_path)
    _validate_agent_id(agent, known)

    task = bus.latest_source_task(agent, include_reviews=include_reviews)
    return jsonrpc_response(1, _compact_task(task) if task else None)


def _handle_trinity_worker(params, bus, agents_path, routes_path):
    agent = _validate_text(params["agent"], 128)
    task_id = params.get("task_id") or None
    if task_id is not None:
        task_id = _validate_task_id(task_id)

    known = _get_known_agents(bus, agents_path)
    _validate_agent_id(agent, known)

    result = worker_run_once(agent, bus, agents_path, task_id=task_id)
    if result is None:
        return jsonrpc_response(
            1, {"status": "no_task", "message": "no queued task for {}".format(agent)}
        )
    return jsonrpc_response(1, _compact_task(result))


def _handle_trinity_doctor(params, bus, agents_path, routes_path):
    scan_root = params.get("scan_root") or None
    runtime_root = params.get("runtime_root") or None
    retired_ports = params.get("retired_ports", []) or []

    health = run_doctor(
        db_path=str(bus.db_path),
        routes_path=routes_path,
        agents_path=agents_path,
        scan_root=scan_root,
        runtime_root=runtime_root,
        retired_ports=retired_ports,
    )
    return jsonrpc_response(1, health)


def _handle_trinity_inbox(params, bus, agents_path, routes_path):
    agent = _validate_text(params["agent"], 128)
    unread_only = params.get("unread_only", True)
    mark_read = params.get("mark_read", False)
    limit = _validate_limit(params.get("limit"))

    known = _get_known_agents(bus, agents_path)
    _validate_agent_id(agent, known)

    messages = bus.inbox(
        agent, unread_only=unread_only, mark_read=mark_read, limit=limit
    )
    return jsonrpc_response(1, messages)


def _handle_trinity_send(params, bus, agents_path, routes_path):
    target = _validate_text(params["target_agent"], 128)
    message = _validate_text(params["message"], _MAX_MESSAGE_LENGTH)
    source = params.get("source_agent", "mcp")
    source = _validate_text(source, 128)
    task_id = params.get("task_id") or None
    if task_id is not None:
        task_id = _validate_task_id(task_id)

    known = _get_known_agents(bus, agents_path)
    _validate_agent_id(source, known)
    _validate_agent_id(target, known)

    if source == target:
        return jsonrpc_error(1, -32000, "self-messaging is not allowed")

    msg = bus.send_message(source, target, message, task_id)
    return jsonrpc_response(1, msg)


def _handle_trinity_skill_search(params, bus, agents_path, routes_path):
    query = _validate_text(params.get("query", ""), max_len=1000)
    if not query.strip():
        return jsonrpc_error(1, -32602, "query must not be empty")
    limit = _validate_limit(params.get("limit"), default=5, maximum=20)

    if not _init_skill_engine():
        return jsonrpc_response(1, {
            "error": "agent-skill-system not installed",
            "hint": "pip install agent-skill-system",
            "skills": [],
        })

    try:
        from engine.searcher import SkillSearcher  # type: ignore[import-untyped]
        searcher = SkillSearcher(_SKILL_BANK_DIR)
        results = searcher.search(query, _SKILL_BANK.index, top_n=limit)
    except Exception as exc:
        return jsonrpc_response(1, {
            "error": "skill search failed: {}".format(exc),
            "skills": [],
        })

    skills = []
    for entry, cfg, score in results:
        skills.append({
            "name": entry.name,
            "description": cfg.description,
            "version": entry.version,
            "success_rate": entry.success_rate,
            "use_count": entry.use_count,
            "score": score,
            "tags": cfg.tags,
            "trigger_keywords": cfg.trigger_keywords[:8],
        })

    return jsonrpc_response(1, {"skills": skills})


def _handle_trinity_skill_load(params, bus, agents_path, routes_path):
    skill_name = _validate_text(params.get("skill_name", ""), max_len=128)
    if not skill_name.strip():
        return jsonrpc_error(1, -32602, "skill_name must not be empty")

    if not _init_skill_engine():
        return jsonrpc_response(1, {
            "error": "agent-skill-system not installed",
            "hint": "pip install agent-skill-system",
        })

    try:
        from engine.loader import SkillLoader  # type: ignore[import-untyped]
        entry = _SKILL_BANK.get(skill_name)
        if entry is None:
            return jsonrpc_response(1, {
                "error": "skill not found: {}".format(skill_name),
                "available_skills": [s.name for s in _SKILL_BANK.list_active()],
            })
        loader = SkillLoader(_SKILL_BANK_DIR)
        bundle = loader.load(entry)
        if bundle is None:
            return jsonrpc_error(1, -32002, "failed to load skill: {}".format(skill_name))

        memory_entries_serialised = []
        for mem in bundle.memory_entries:
            memory_entries_serialised.append({
                "date": mem.date,
                "type": mem.type.value,
                "title": mem.title,
                "scene": mem.scene,
                "detail": mem.detail,
            })

        return jsonrpc_response(1, {
            "name": bundle.config.name,
            "version": bundle.config.version,
            "description": bundle.config.description,
            "skill_md": bundle.skill_md,
            "memory_md": bundle.memory_md,
            "memory_entries": memory_entries_serialised,
            "input_schema": bundle.config.input_schema,
            "trigger_keywords": bundle.config.trigger_keywords,
            "system_prompt": loader.build_system_prompt(bundle),
        })
    except Exception as exc:
        return jsonrpc_response(1, {
            "error": "skill load failed: {}".format(exc),
        })



def _handle_trinity_orchestrate(params, bus, agents_path, routes_path):
    """Handle trinity_orchestrate: orchestrate pipeline or review flow."""
    prompt = _validate_text(params["task"])
    source = params.get("source_agent", "mcp")
    source = _validate_text(source, 128)
    cwd = params.get("cwd", os.environ.get("HOME", str(Path.home())))
    task_type = params.get("task_type") or None
    previous_agent = params.get("previous_agent") or None
    pipeline_path = params.get("pipeline") or None
    wait = params.get("wait", False)
    wait_timeout = _validate_timeout(params.get("wait_timeout"))

    known = _get_known_agents(bus, agents_path)
    _validate_agent_id(source, known)

    if pipeline_path:
        pipeline = load_pipeline(pipeline_path)
        result = run_pipeline(
            pipeline,
            prompt,
            bus,
            routes_path=routes_path,
            agents_path=agents_path,
            source_agent=source,
            cwd=cwd,
            run_workers=True,
        )
        return jsonrpc_response(1, result)
    else:
        from .orchestrator import run_review_flow
        result = run_review_flow(
            prompt,
            bus,
            routes_path=routes_path,
            agents_path=agents_path,
            source_agent=source,
            task_type=task_type,
            previous_agent=previous_agent,
            cwd=cwd,
            run_workers=True,
        )
        return jsonrpc_response(1, result)
def _handle_trinity_worker_daemon(params, bus, agents_path, routes_path):
    """Handle trinity_worker_daemon: start/stop/status a daemon worker."""
    import subprocess as _sp
    import time as _time

    agent = _validate_text(params["agent"], 128)
    action = params.get("action", "status")

    if action not in ("start", "stop", "status"):
        return jsonrpc_error(1, -32602, "action must be one of: start, stop, status")

    pid_path = _default_pid_path(agent)

    if action == "status":
        pid = _read_pid_file(pid_path)
        if pid is not None:
            try:
                os.kill(pid, 0)
                return jsonrpc_response(1, {"running": True, "pid": pid, "pid_file": str(pid_path)})
            except OSError:
                pass
        return jsonrpc_response(1, {"running": False, "pid_file": str(pid_path)})

    if action == "stop":
        pid = _read_pid_file(pid_path)
        if pid is None:
            # Clean up stale pid file if exists
            try:
                pid_path.unlink(missing_ok=True)
            except OSError:
                pass
            return jsonrpc_response(1, {"stopped": True, "message": "no running daemon found"})
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pid_path.unlink(missing_ok=True)
            return jsonrpc_response(1, {"stopped": True, "message": "stale PID cleaned up"})

        # Wait up to 5s for graceful shutdown
        deadline = _time.monotonic() + 5
        while _time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                break
            _time.sleep(0.1)
        else:
            # Force kill
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

        # Clean PID file
        try:
            pid_path.unlink(missing_ok=True)
        except OSError:
            pass

        return jsonrpc_response(1, {"stopped": True, "pid": pid})

    if action == "start":
        # Check if already running
        pid = _read_pid_file(pid_path)
        if pid is not None:
            try:
                os.kill(pid, 0)
                return jsonrpc_error(1, -32000,
                    "worker daemon for '{}' is already running (PID {})".format(agent, pid))
            except OSError:
                pid_path.unlink(missing_ok=True)

        # Spawn daemon via subprocess (non-blocking)
        try:
            cmd = [sys.executable, "-m", "trinity_lite", "worker", agent, "--daemon"]
            proc = _sp.Popen(cmd, stdin=_sp.DEVNULL, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
            # Give it a moment to acquire PID lock
            _time.sleep(0.3)
            pid = _read_pid_file(pid_path)
            return jsonrpc_response(1, {
                "started": True,
                "pid": pid or proc.pid,
                "pid_file": str(pid_path),
            })
        except Exception as exc:
            return jsonrpc_error(1, -32603, "failed to start daemon: {}".format(exc))


TOOL_HANDLERS = {
    "trinity_dispatch": _handle_trinity_dispatch,
    "trinity_dispatch_auto": _handle_trinity_dispatch_auto,
    "trinity_status": _handle_trinity_status,
    "trinity_latest": _handle_trinity_latest,
    "trinity_tasks": _handle_trinity_tasks,
    "trinity_worker": _handle_trinity_worker,
    "trinity_worker_daemon": _handle_trinity_worker_daemon,
    "trinity_doctor": _handle_trinity_doctor,
    "trinity_inbox": _handle_trinity_inbox,
    "trinity_send": _handle_trinity_send,
    "trinity_skill_search": _handle_trinity_skill_search,
    "trinity_skill_load": _handle_trinity_skill_load,
    "trinity_orchestrate": _handle_trinity_orchestrate,
}


def _handle_tool_call(id_, params, bus, agents_path, routes_path):
    name = params.get("name", "")
    arguments = params.get("arguments", {})
    if not isinstance(arguments, dict):
        return jsonrpc_error(id_, -32602, "arguments must be an object")

    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return jsonrpc_error(id_, -32602, "unknown tool: {}".format(name))

    try:
        result = handler(arguments, bus, agents_path, routes_path)
        # Rebuild response with correct request id
        result["id"] = id_
        return result
    except (ValueError, KeyError) as exc:
        return jsonrpc_error(id_, -32602, str(exc))
    except GuardError as exc:
        return jsonrpc_error(id_, -32004, str(exc))
    except Exception:
        tb = traceback.format_exc()
        print("[mcp] internal error in tool {}:\n{}".format(name, tb), file=sys.stderr, flush=True)
        return jsonrpc_error(id_, -32603, "internal server error")


# ---------------------------------------------------------------------------
# Resource handlers
# ---------------------------------------------------------------------------

RESOURCE_URI_HEALTH = "trinity://health"
RESOURCE_URI_TASKS_RECENT = "trinity://tasks/recent"
_RESOURCE_URI_TASK_PREFIX = "trinity://tasks/"

_RE_TASK_URI = re.compile(r"^trinity://tasks/([a-fA-F0-9]{12})$")


def _handle_resource_read(id_, params, bus, agents_path, routes_path):
    uri = params.get("uri", "")
    if not uri:
        return jsonrpc_error(id_, -32602, "uri is required")

    try:
        if uri == RESOURCE_URI_HEALTH:
            return _resource_health(id_, bus, agents_path, routes_path)
        if uri == RESOURCE_URI_TASKS_RECENT:
            return _resource_tasks_recent(id_, bus, agents_path)
        match = _RE_TASK_URI.match(uri)
        if match:
            return _resource_task(id_, bus, match.group(1))
        return jsonrpc_error(id_, -32002, "unknown resource: {}".format(uri))
    except Exception:
        tb = traceback.format_exc()
        print("[mcp] internal error reading resource {}:\n{}".format(uri, tb), file=sys.stderr, flush=True)
        return jsonrpc_error(id_, -32603, "internal server error")


def _resource_health(id_, bus, agents_path, routes_path):
    try:
        bus.list_tasks(limit=1)
        bus_connected = True
    except Exception:
        bus_connected = False

    health_data = {
        "status": "ok" if bus_connected else "degraded",
        "bus": "connected" if bus_connected else "error",
        "tools": len(TOOL_DEFINITIONS),
        "resources": len(RESOURCE_DEFINITIONS),
    }
    return jsonrpc_response(id_, {
        "contents": [
            {
                "uri": RESOURCE_URI_HEALTH,
                "mimeType": "application/json",
                "text": json.dumps(health_data),
            }
        ],
    })


def _resource_tasks_recent(id_, bus, agents_path):
    tasks = bus.list_tasks(limit=20)
    data = [_compact_task(t) for t in tasks]
    return jsonrpc_response(id_, {
        "contents": [
            {
                "uri": RESOURCE_URI_TASKS_RECENT,
                "mimeType": "application/json",
                "text": json.dumps(data),
            }
        ],
    })


def _resource_task(id_, bus, task_id):
    try:
        task = bus.get_task(task_id)
    except KeyError:
        return jsonrpc_error(id_, -32002, "task not found: {}".format(task_id))
    data = _compact_task(task)
    return jsonrpc_response(id_, {
        "contents": [
            {
                "uri": "trinity://tasks/{}".format(task_id),
                "mimeType": "application/json",
                "text": json.dumps(data),
            }
        ],
    })


# ---------------------------------------------------------------------------
# Request handler (dispatches methods)
# ---------------------------------------------------------------------------


def handle_request(msg, bus, agents_path, routes_path):
    """Process a single JSON-RPC message and return the response (or None)."""
    method = msg.get("method", "")
    id_ = msg.get("id")
    params = msg.get("params", {})

    if method not in ALLOWED_METHODS:
        return jsonrpc_error(id_, -32601, "method not found: {}".format(method))

    if method == "initialize":
        return jsonrpc_response(id_, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })

    if method == "initialized":
        return None

    if method == "tools/list":
        return jsonrpc_response(id_, {"tools": TOOL_DEFINITIONS})

    if method == "tools/call":
        return _handle_tool_call(id_, params, bus, agents_path, routes_path)

    if method == "resources/list":
        return jsonrpc_response(id_, {"resources": RESOURCE_DEFINITIONS})

    if method == "resources/read":
        return _handle_resource_read(id_, params, bus, agents_path, routes_path)

    if method == "shutdown":
        return jsonrpc_response(id_, {})

    return jsonrpc_error(id_, -32601, "method not found: {}".format(method))


# ---------------------------------------------------------------------------
# STDIO serve loop
# ---------------------------------------------------------------------------


def serve(bus, agents_path=None, routes_path=None):
    """Run JSON-RPC 2.0 loop on stdio.

    Reads line-delimited JSON from stdin, writes responses to stdout.
    All diagnostic output goes to stderr.
    """
    print("[mcp] Trinity Lite MCP v{} on stdio".format(SERVER_VERSION), file=sys.stderr, flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        # Parse message
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            error_resp = jsonrpc_error(None, -32700, "parse error")
            sys.stdout.write(json.dumps(error_resp) + "\n")
            sys.stdout.flush()
            continue

        if not isinstance(msg, dict):
            error_resp = jsonrpc_error(None, -32600, "invalid request")
            sys.stdout.write(json.dumps(error_resp) + "\n")
            sys.stdout.flush()
            continue

        # Process message
        try:
            response = handle_request(msg, bus, agents_path, routes_path)
        except Exception:
            tb = traceback.format_exc()
            print("[mcp] unhandled exception:\n{}".format(tb), file=sys.stderr, flush=True)
            error_resp = jsonrpc_error(msg.get("id"), -32603, "internal server error")
            sys.stdout.write(json.dumps(error_resp) + "\n")
            sys.stdout.flush()
            continue

        # Write response
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

        if msg.get("method") == "shutdown":
            break

    print("[mcp] server exiting", file=sys.stderr, flush=True)
