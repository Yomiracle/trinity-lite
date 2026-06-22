# MCP Server Design for Trinity Lite

Trinity Lite v0.1.x provides a CLI interface: users run `trinity-lite dispatch-auto`,
check `trinity-lite tasks`, and poll workers manually. The v0.2 goal is to add an
**MCP (Model Context Protocol) server** so AI coding agents — Codex, Claude Code,
and any MCP-compatible client — can call Trinity Lite directly as a tool within
their session, without leaving the agent interface.

## 1. Architecture

### 1.1 Invocation Model

The MCP server is a **standalone subprocess**, not a background daemon or
in-process library. AI agents launch it on demand:

```text
Claude Code / Codex  --(STDIO JSON-RPC)->  trinity-lite mcp serve
                                                    |
                                                    +-- TrinityBus (SQLite)
                                                    +-- Router
                                                    +-- Worker (once)
                                                    +-- Doctor
```

### 1.2 Transport Strategy

| Phase | Transport | Target | Rationale |
|-------|-----------|--------|-----------|
| Phase 1 (v0.2.0) | STDIO | Minimal server | Matches Codex/Claude Code MCP invocation; zero network surface |
| Phase 2 (v0.2.1) | STDIO | Full tools + resources | All eight tools and three resources |
| Phase 3 (v0.2.2) | HTTP (`--transport http`) | Network-accessible | Optional for remote or containerised use |

STDIO transport is the default and the first transport implemented. The server
reads JSON-RPC 2.0 requests from stdin and writes responses to stdout. All
logging goes to stderr so it does not interfere with the protocol stream.

HTTP transport in Phase 3 will add `--host` and `--port` flags, a simple
`http.server`-based listener, and `--health` endpoint parity with the
`trinity://health` resource.

### 1.3 Dependency Policy

**Phase 1+2: zero new runtime dependencies.** The MCP server implements
JSON-RPC 2.0 over stdio using only the Python standard library (`json`, `sys`,
`asyncio` or synchronous `select`/`io`). The implementation is approximately
300-400 lines in a new `trinity_lite/mcp_server.py` module.

**Optional `mcp` extra:** For users who want richer protocol support (type
validation, server features, proper capability negotiation), `pip install
trinity-lite[mcp]` will pull in the `mcp` PyPI package. The core stdlib
implementation remains the default. When the `mcp` package is installed, the
server delegates transport and lifecycle to it while keeping the tool
implementations shared.

```toml
# pyproject.toml (additions for v0.2)
[project.optional-dependencies]
mcp = ["mcp>=1.0"]
```

### 1.4 CLI Entry Point

```
trinity-lite mcp serve [--db PATH] [--routes PATH] [--agents PATH]
```

The `mcp serve` subcommand:

1. Initialises the `TrinityBus` with the given (or default) database.
2. Loads routes and agent config if provided.
3. Starts the JSON-RPC loop on stdio.
4. Writes all diagnostic output to stderr.
5. Exits cleanly on EOF (stdin close) or a `shutdown` request.

## 2. Tools

Eight tools are exposed via the MCP server. Each tool corresponds to a
`tools/call` JSON-RPC method with a structured return value.

### 2.1 `trinity_dispatch`

Dispatch a task to a specific named agent.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `target_agent` | string | yes | -- | Agent id to receive the task |
| `task` | string | yes | -- | Task prompt |
| `source_agent` | string | no | `"mcp"` | Originating agent id |
| `cwd` | string | no | `$HOME` | Working directory |
| `task_type` | string | no | `""` | Task type for routing |
| `wait` | boolean | no | `false` | Block until task completes |
| `wait_timeout` | number | no | `600` | Timeout in seconds for wait |

**Security:** `source_agent` is validated against known agent ids. If it
matches `target_agent`, the call is rejected with a self-delegation error.

**Return value:** The compact task object (id, status, prompt, agent, timestamps,
result if completed).

### 2.2 `trinity_dispatch_auto`

Resolve the route automatically then dispatch.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task` | string | yes | -- | Task prompt |
| `source_agent` | string | no | `"mcp"` | Originating agent id |
| `cwd` | string | no | `$HOME` | Working directory |
| `task_type` | string | no | `""` | Task type hint |
| `previous_agent` | string | no | `""` | Previous agent for avoidance |
| `wait` | boolean | no | `false` | Block until task completes |
| `wait_timeout` | number | no | `600` | Timeout in seconds for wait |

**Security:** If routing resolves to `source_agent`, the call is rejected
(self-delegation prevention). The resolved route is included in the return
value for auditability.

**Return value:** Compact task object with `route` key showing the resolved
route (`agent`, `task_type`, `selection`, `source`).

### 2.3 `trinity_status`

Get the current state and result of a task.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task_id` | string | yes | -- | Task identifier |

**Return value:** Full task object from the bus.

### 2.4 `trinity_tasks`

List recent tasks, optionally filtered by agent.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `agent` | string | no | `""` | Filter by agent (source or target) |
| `limit` | integer | no | `20` | Maximum tasks to return |

**Return value:** Array of compact task objects, most recent first.

### 2.5 `trinity_worker` (NEW)

Run one worker cycle for a named agent. This is the key innovation for MCP
sessions: the agent can dispatch a task and then execute it immediately within
the same MCP connection, without needing a separate terminal to run `trinity-lite
worker`.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `agent` | string | yes | -- | Agent id to run worker for |
| `task_id` | string | no | `""` | Process a specific queued task |

**Behaviour:**

1. Claims the next queued task for `agent` (or the specific `task_id`).
2. Runs the configured adapter (mock or command).
3. Stores the result in the bus.
4. Returns the updated task object.

**Return value:** Updated task object with `status`, `result`, or `error`.

**Rationale:** In the internal `~/.hermes/trinity_mcp.py`, workers are
long-running processes managed outside the MCP server. For the public Trinity
Lite, `trinity_worker` lets agents close the dispatch->execute->inspect loop
entirely within one MCP session. This is especially important for agents that
do not control their own subprocess lifecycle.

### 2.6 `trinity_doctor` (NEW)

Run health and diagnostic checks. Replaces the internal `trinity_agents` tool
with a broader, release-safe health check.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `scan_root` | string | no | `""` | Repository root for publish-readiness scan |
| `runtime_root` | string | no | `""` | Runtime directory for hygiene checks |
| `retired_ports` | array[int] | no | `[]` | Ports that should not be listening |

**Return value:** Health status object:

```json
{
  "status": "healthy",
  "checks": [
    {"name": "database", "ok": true, "detail": "SQLite at ~/.trinity-lite/bus.db"},
    {"name": "scan_root", "ok": true, "detail": "no private files found"}
  ]
}
```

**Rationale for replacing `trinity_agents`:** The internal MCP server's
`trinity_agents` tool exposed agent identifiers and database paths -- useful in
a controlled environment but a potential information leak in a public tool.
`trinity_doctor` provides equivalent operational insight through a structured
health contract that is both more useful and safer to expose.

### 2.7 `trinity_inbox`

Read durable messages addressed to an agent.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `agent` | string | yes | -- | Agent whose inbox to read |
| `unread_only` | boolean | no | `true` | Return only unread messages |
| `mark_read` | boolean | no | `false` | Mark returned messages as read |
| `limit` | integer | no | `20` | Maximum messages to return |

**Security:** `agent` is validated against known agent ids to prevent
enumeration of arbitrary inboxes.

**Return value:** Array of message objects.

### 2.8 `trinity_send`

Send a durable message to another agent.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `target_agent` | string | yes | -- | Recipient agent id |
| `message` | string | yes | -- | Message body |
| `source_agent` | string | no | `"mcp"` | Sender agent id |
| `task_id` | string | no | `""` | Associated task id |

**Security:** Self-messaging is rejected. `source_agent` must be a known agent id.

**Return value:** The created message object.

## 3. Resources

Three resource URIs provide read-only access to Trinity Lite state. Resources
are served through `resources/read` JSON-RPC requests.

### 3.1 `trinity://tasks/{task_id}`

Single task detail.

**Returns:** Full task object (id, status, source_agent, target_agent, prompt,
cwd, depth, result, error, timestamps).

**Errors:** `-32002` (not found) if `task_id` does not exist.

### 3.2 `trinity://tasks/recent`

Recent task list (last 20 by default).

**Returns:** Array of compact task objects.

### 3.3 `trinity://health`

System health status. Combines database connectivity, agent config validity,
route resolvability, and optional scan/hygiene checks.

**Returns:** Health status object identical to `trinity_doctor` output.

**Why resources and not just tools:** Resources are the MCP idiom for
read-only state access. They are cacheable by clients, appear in the resource
panel of MCP-aware UIs, and separate concerns: tools mutate state, resources
observe it. Providing both gives MCP clients the richest integration surface.

## 4. Security

The MCP server inherits all existing Trinity Lite security properties and adds
server-specific protections.

### 4.1 Self-Delegation Prevention (4-layer defence)

| Layer | Mechanism | Location |
|-------|-----------|----------|
| 1 | Guard error in `TrinityBus.submit_task` | Already in `bus.py` |
| 2 | Pre-dispatch check in `trinity_dispatch` | `mcp_server.py` tool handler |
| 3 | Route-result check in `trinity_dispatch_auto` | `mcp_server.py` tool handler |
| 4 | `source_agent` validated against known ids | `mcp_server.py` input validation |

Layer 1 catches it at the bus level. Layers 2-3 catch it before the bus call
so the error message is tool-specific and actionable. Layer 4 prevents the
client from bypassing validation with unknown agent ids.

### 4.2 Allowed Roots Enforcement

The `cwd` parameter is validated through the existing `guard.ensure_inside_roots()`
function. If the caller supplies a path outside `$HOME` (or the configured
`TRINITY_LITE_ALLOWED_ROOTS`), the call is rejected before any task is created.

### 4.3 Credential Safety

- The MCP server does not read or transmit API keys, OAuth tokens, or environment
  secrets.
- Agent command configs (`agents.local.json`) are loaded as structured data and
  never echoed in tool or resource responses.
- The `trinity_doctor` tool reports on database connectivity and config validity
  without exposing raw config contents.

### 4.4 Process Isolation

- The MCP server runs as a separate OS process from the AI agent.
- Command-mode agents are executed with `shell=False` (JSON arrays), unchanged
  from the CLI worker path.
- If the AI agent process terminates, the MCP server detects stdin EOF and
  shuts down cleanly.

### 4.5 Input Validation

All tool parameters are validated on entry:

- String parameters: length limits, no control characters in task prompts.
- `task_id`: validated as 12-character hex string.
- `agent` ids: validated against the set of known agents (from config and
  reserved ids `"user"`, `"mcp"`).
- Numeric parameters: range-checked (`limit` <= 100, `wait_timeout` <= 3600).
- JSON-RPC method names: allowlisted to the eight tool names plus
  `initialize`, `initialized`, `tools/list`, `resources/list`,
  `resources/read`, `shutdown`.

## 5. Implementation Plan

### Phase 1: Minimal STDIO Server (v0.2.0)

**Scope:**

- New module: `trinity_lite/mcp_server.py` (approx 300-400 lines)
- New CLI subcommand: `trinity-lite mcp serve`
- JSON-RPC 2.0 over stdio with stdlib only
- Three core tools: `trinity_dispatch`, `trinity_dispatch_auto`, `trinity_status`
- Three resources: `trinity://tasks/{task_id}`, `trinity://tasks/recent`, `trinity://health`
- MCP lifecycle: `initialize` -> `initialized` -> serve -> `shutdown`
- All security layers active
- Tests: `tests/test_mcp_server.py`

**Acceptance criteria:**

```bash
# Send initialize to server
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | trinity-lite mcp serve
# Dispatch a task
echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"trinity_dispatch","arguments":{"target_agent":"codex","task":"hello"}}}' | trinity-lite mcp serve
```

### Phase 2: Full Tools + Resources (v0.2.1)

**Scope:**

- Remaining five tools: `trinity_tasks`, `trinity_worker`, `trinity_doctor`,
  `trinity_inbox`, `trinity_send`
- Optional `mcp` extra in `pyproject.toml`
- When `mcp` PyPI package is installed, server delegates transport to it
  while sharing tool implementations
- Full test coverage for all eight tools and three resources
- Documentation updates in `README.md`

**Acceptance criteria:**

- All eight tools respond correctly via JSON-RPC
- Three resources return expected data
- `pip install trinity-lite[mcp]` works and server uses FastMCP transport
- All existing tests pass; new MCP tests >= 90% coverage

### Phase 3: HTTP Transport (v0.2.2)

**Scope:**

- `trinity-lite mcp serve --transport http --host 127.0.0.1 --port 9797`
- Simple HTTP listener using `http.server` (stdlib)
- Same JSON-RPC 2.0 wire protocol over HTTP POST
- `GET /health` endpoint for liveness checks
- Process lifecycle management with graceful shutdown on SIGTERM

**Non-goals for v0.2.x:**

- WebSocket transport
- Streaming responses
- Multi-client concurrency
- Authentication or TLS (users who need these should put a reverse proxy or
  SSH tunnel in front)

## 6. Usage Examples

### 6.1 Claude Code MCP Config

```json
{
  "mcpServers": {
    "trinity-lite": {
      "command": "trinity-lite",
      "args": ["mcp", "serve", "--db", "~/.trinity-lite/bus.db"],
      "env": {
        "TRINITY_LITE_ALLOWED_ROOTS": "/home/user/projects:/tmp"
      }
    }
  }
}
```

After configuration, Claude Code will show `trinity_dispatch`,
`trinity_dispatch_auto`, `trinity_status`, `trinity_tasks`, `trinity_worker`,
`trinity_doctor`, `trinity_inbox`, and `trinity_send` in its tool list.

### 6.2 Codex MCP Config

Codex MCP integration can invoke Trinity Lite directly by defining it as a
tool provider in the Codex MCP server configuration:

```json
{
  "mcp_servers": {
    "trinity-lite": {
      "command": "trinity-lite",
      "args": ["mcp", "serve"],
      "env": {
        "TRINITY_HOME": "~/.trinity-lite"
      }
    }
  }
}
```

The agent writes task prompts and reads results through MCP tool calls without
leaving the Codex session.

### 6.3 Example Audit Flow Session

An agent uses Trinity Lite MCP tools to perform a complete audit-and-fix
cycle:

```text
AGENT: trinity_dispatch(target_agent="auditor", task="audit security of auth.py")
  -> {"id": "a1b2c3d4e5f6", "status": "queued", "target_agent": "auditor"}

AGENT: trinity_worker(agent="auditor")
  -> {"id": "a1b2c3d4e5f6", "status": "completed", "result": "3 issues found: ..."}

AGENT: trinity_dispatch_auto(task="fix the SQL injection in auth.py login",
                              previous_agent="auditor")
  -> {"id": "b2c3d4e5f6a1", "status": "queued", "route": {"agent": "primary_eng", ...}}

AGENT: trinity_worker(agent="primary_eng")
  -> {"id": "b2c3d4e5f6a1", "status": "completed", "result": "Fixed. Updated auth.py:42"}

AGENT: trinity_status(task_id="b2c3d4e5f6a1")
  -> {"id": "b2c3d4e5f6a1", "status": "completed", ...}

AGENT: trinity_tasks(agent="auditor")
  -> [{...}, {...}]  # audit trail

AGENT: trinity_doctor()
  -> {"status": "healthy", ...}
```

### 6.4 Orchestration with `--wait`

The `wait` parameter lets agents block until a task finishes, enabling
synchronous orchestration within a single tool call:

```text
AGENT: trinity_dispatch_auto(
          task="write tests for parser.py",
          wait=true,
          wait_timeout=300
       )
  -> Internal loop: dispatch -> claim worker -> run -> return completed task
  -> {"id": "c3d4e5f6a1b2", "status": "completed", "result": "15 tests written"}
```

The server uses `TrinityBus.await_task()` internally during `wait`, polling
the SQLite bus until the task reaches a terminal state or the timeout expires.

## 7. Comparison with Internal `~/.hermes/trinity_mcp.py`

The internal MCP server used within Hermes influenced the public design but
differs in key areas.

### 7.1 What's Simplified

| Aspect | Internal MCP | Public Trinity Lite MCP |
|--------|-------------|------------------------|
| **Dependencies** | Requires `mcp` (FastMCP) | Zero-dependency stdlib fallback; optional `mcp` extra |
| **Agent set** | Hardcoded AGENTS = {hermes, claude_code, codex} | Dynamic from `agents.local.json` plus reserved ids |
| **Database** | Fixed `DB_PATH` from shared config | Configurable via `--db` flag |
| **Routing** | `importlib.reload(trinity_router)` with module-level state | Stateless `resolve_route()` call per invocation |
| **Depth tracking** | Read from `TRINITY_DEPTH` env var | Passed through task metadata in bus |
| **Tool count** | 7 tools (`trinity_route`, `trinity_agents`) | 8 tools (no route standalone, adds `trinity_worker`, `trinity_doctor`) |
| **Resources** | None | 3 resource URIs |
| **CLI entry** | `python3 trinity_mcp.py` | `trinity-lite mcp serve` |
| **Module path** | `~/.hermes/trinity_mcp.py` (private) | `trinity_lite/mcp_server.py` (package) |

### 7.2 What's Kept the Same

| Aspect | Shared Design |
|--------|---------------|
| **STDIO transport** | JSON-RPC 2.0 over stdin/stdout |
| **Core bus operations** | `submit_task`, `get_task`, `list_tasks`, `send_message`, `inbox`, `await_task` |
| **Self-delegation prevention** | Check `target_agent == source` before dispatch |
| **Compact task representation** | Same subset of fields in tool responses |
| **`wait` semantics** | Block until terminal status or timeout |
| **Agent validation** | `source_agent` must be a known id |
| **Error handling** | ValueError for invalid params, TimeoutError for wait expiry |

### 7.3 Design Decisions

**Removing `trinity_route` as standalone tool:** The internal server exposes
route resolution separately from dispatch. In the public design, routing is
integrated into `trinity_dispatch_auto` and included in its response. A
standalone `route` tool adds complexity without a clear MCP use case; agents
that need route inspection can call `dispatch_auto` and examine the `route`
field without side effects (the task is only submitted if route passes
validation).

**Adding `trinity_worker`:** This is the biggest design departure. The internal
setup assumes workers run as detached CLI processes (`trinity-lite worker codex
--once`). In an MCP session, the agent cannot easily spawn a sibling process
to run a worker. `trinity_worker` brings worker execution into the MCP server
process so the agent can submit and execute tasks in a single session.

**Adding `trinity_doctor`:** The internal `trinity_agents` returned agent ids and
database paths. The public `trinity_doctor` provides structured health
information -- database status, config validity, route resolvability -- without
leaking internal identifiers or file paths unnecessarily.

## 8. Appendices

### A. MCP Startup Sequence

The MCP lifecycle follows this sequence:

```
 1. AI agent launches: trinity-lite mcp serve
 2. Server writes server info to stderr: "Trinity Lite MCP v0.2.0 on stdio"
 3. Client sends: {"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}
 4. Server responds: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"...","capabilities":{...}}}
 5. Client sends: {"jsonrpc":"2.0","method":"initialized"}
 6. Client sends: {"jsonrpc":"2.0","id":2,"method":"tools/list"}
 7. Server responds with all 8 tool definitions
 8. Client sends: {"jsonrpc":"2.0","id":3,"method":"resources/list"}
 9. Server responds with 3 resource definitions
10. Client sends tool calls as {"jsonrpc":"2.0","method":"tools/call","params":{"name":"...","arguments":{...}}}
11. Server processes each call and returns results
12. On session end or stdin EOF: server exits
```

### B. Protocol Implementation Sketch

The minimal JSON-RPC 2.0 implementation in `trinity_lite/mcp_server.py`:

```python
"""MCP server for Trinity Lite. Zero-dependency JSON-RPC 2.0 over stdio."""

import json
import sys
from typing import Any

from .bus import TrinityBus
from .doctor import run_doctor
from .router import resolve_route
from .worker import run_once


JSONRPC_VERSION = "2.0"
PROTOCOL_VERSION = "2024-11-05"

TOOLS = {}
RESOURCES = {}


def jsonrpc_response(id_, result=None, error=None):
    msg = {"jsonrpc": JSONRPC_VERSION, "id": id_}
    if error:
        msg["error"] = error
    else:
        msg["result"] = result
    return msg


def handle_request(msg, bus, agents_path, routes_path):
    method = msg.get("method", "")
    id_ = msg.get("id")

    if method == "initialize":
        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": id_,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "trinity-lite-mcp", "version": "0.2.0"},
            },
        }
    if method == "initialized":
        return None
    if method == "tools/list":
        return jsonrpc_response(id_, {"tools": list(TOOLS.values())})
    if method == "resources/list":
        return jsonrpc_response(id_, {"resources": list(RESOURCES.values())})
    if method == "tools/call":
        return _handle_tool_call(id_, msg.get("params", {}), bus, agents_path, routes_path)
    if method == "resources/read":
        return _handle_resource_read(id_, msg.get("params", {}), bus, agents_path, routes_path)
    if method == "shutdown":
        return jsonrpc_response(id_, {})
    return jsonrpc_response(id_, error={"code": -32601, "message": f"method not found: {method}"})


def serve(bus, agents_path=None, routes_path=None):
    """Run JSON-RPC 2.0 loop on stdio."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            response = jsonrpc_response(None, error={"code": -32700, "message": "parse error"})
            sys.stdout.write(json.dumps(response) + "\\n")
            sys.stdout.flush()
            continue
        response = handle_request(msg, bus, agents_path, routes_path)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\\n")
            sys.stdout.flush()
        if msg.get("method") == "shutdown":
            break
```

The full implementation adds input validation, error handling, and the
`_handle_tool_call` / `_handle_resource_read` dispatch functions (approx 150
additional lines), keeping the total at 300-400 lines.

### C. Tool Schema Reference

Each tool definition follows the MCP tool schema:

```json
{
  "name": "trinity_dispatch",
  "description": "Dispatch an asynchronous task to a specific Trinity agent.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "target_agent": {"type": "string", "description": "Agent id to receive the task"},
      "task": {"type": "string", "description": "Task prompt"},
      "source_agent": {"type": "string", "description": "Originating agent id (default: mcp)"},
      "cwd": {"type": "string", "description": "Working directory (default: $HOME)"},
      "task_type": {"type": "string", "description": "Task type for routing"},
      "wait": {"type": "boolean", "description": "Block until task completes"},
      "wait_timeout": {"type": "number", "description": "Timeout in seconds for wait"}
    },
    "required": ["target_agent", "task"]
  }
}
```

### D. Error Codes

| Code | Meaning | Context |
|------|---------|---------|
| `-32700` | Parse error | Invalid JSON received |
| `-32600` | Invalid request | Malformed JSON-RPC message |
| `-32601` | Method not found | Unknown method name |
| `-32602` | Invalid params | Missing required parameter or wrong type |
| `-32603` | Internal error | Unexpected server failure |
| `-32000` | Self-delegation | Source agent equals target agent |
| `-32001` | Depth exceeded | Delegation depth > 2 |
| `-32002` | Not found | Task or resource not found |
| `-32003` | Timeout | Wait timed out before task completion |
| `-32004` | Root violation | Working directory outside allowed roots |