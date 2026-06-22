# Trinity Lite v0.2 - MCP Server Design

> **Status:** Draft  
> **Target:** Trinity Lite v0.2  
> **Principle:** Optional layer -- the core bus works without it

---

## Table of Contents

1. [Architecture](#1-architecture)
2. [Tools](#2-tools)
3. [Resources](#3-resources)
4. [Security](#4-security)
5. [Implementation Plan](#5-implementation-plan)
6. [Usage Example](#6-usage-example)
7. [Comparison with Internal Server](#7-comparison)
8. [Appendices](#appendices)

---

## 1. Architecture

### 1.1 Process Model

The MCP server runs as a standalone subprocess launched by the AI coding agent.
This is the standard MCP model used by Claude Code and Codex.

    Agent launches:  trinity-lite mcp serve
    Agent <--> STDIO <--> trinity-lite mcp server process

Why a separate command, not embedded in every CLI call:

- MCP servers are long-running; agent starts them once and holds the pipe.
- Embedding MCP into every CLI call would add startup latency.
- The mcp subcommand extends the existing CLI naturally.

What the server does NOT do:

- Does NOT run the worker loop (workers run via separate CLI).
- Does NOT fork subprocesses. Delegates to existing worker model.

### 1.2 Transport: STDIO vs HTTP

| Criterion | STDIO | HTTP (SSE) |
|-----------|-------|------------|
| Client support | Universal (Codex, Claude Code) | Some clients |
| Complexity | Minimal (stdin/stdout) | HTTP server + SSE |
| Dependencies | Zero (stdlib only) | http.server or framework |
| Security | Inherited from parent | Port binding + auth |
| Multi-client | One per process | Multiple clients |

Decision: STDIO first. Zero-dependency, matches how Codex/Claude Code invoke
MCP servers. HTTP added later for multi-client scenarios.

### 1.3 Zero-Dependency Approach

Trinity Lite v0.1.x has zero runtime dependencies. We preserve that.

MCP is JSON-RPC 2.0 over STDIO. Minimal stdlib implementation needs:

1. JSON-RPC dispatcher (json module)
2. STDIO line I/O (sys.stdin/stdout); sys.stderr for logging
3. MCP lifecycle: initialize, tools/list, tools/call, resources/*, shutdown

~300-400 lines of stdlib Python.

Alternative: mcp PyPI package (FastMCP). Rejected as default but available
via pip install trinity-lite[mcp] with auto-detection.

---

## 2. Tools (MCP Tools = Functions Agents Can Call)

Each tool returns JSON-formatted strings matching existing CLI output.

### 2.1 trinity_dispatch

Submit a task to an explicitly named agent. Returns task record with ID.

Parameters: target_agent (string, required) - Agent ID to dispatch to. task (string, required) - Task prompt. source_agent (string, opt) - Caller, defaults to TRINITY_AGENT. cwd (string, opt) - Working dir in allowed roots. task_type (string, opt) - Explicit type. wait (boolean, opt) - Block until terminal. wait_timeout (number, opt) - Timeout sec, default 300.

### 2.2 trinity_dispatch_auto

Infer task type from prompt, resolve target via pattern+capability routing, dispatch. Primary delegation tool.

Parameters: task (string, required) - Task prompt, type inferred. source_agent (string, opt) - Caller, defaults TRINITY_AGENT. cwd (string, opt) - Working dir. task_type (string, opt) - Override inferred type. previous_agent (string, opt) - For review handoffs. wait (boolean, opt) - Block until terminal. wait_timeout (number, opt) - Timeout, default 300.

### 2.3 trinity_status

Get current state, result, or error of a task by its 12-character ID.

Parameters: task_id (string, required) - The 12-char task ID.

### 2.4 trinity_tasks

List recent tasks, optionally filtered by agent.

Parameters: agent (string, opt) - Filter by source/target. limit (int, opt, 1-100) - Max tasks, default 20.

### 2.5 trinity_worker

Claim and execute the next queued task for an agent. Runs claim, execute adapter, record result. Returns updated task or null if nothing queued. NOTE: This closes the MCP loop -- dispatch, then worker, then status -- all within the MCP session.

Parameters: agent (string, required) - Agent to pull work for. task_id (string, opt) - Claim a specific task.

### 2.6 trinity_doctor

Run environment checks: Python version, SQLite bus, routes, agents, optional tree scan.
Returns health report with status and checks array.

Parameters: scan_root (string, opt) - Scan directory for private files/secrets.

### 2.7 trinity_inbox

Read durable messages sent to an agent via the message bus.

Parameters: agent (string, opt) - Default TRINITY_AGENT. unread_only (boolean, opt) - Only unread, default true. mark_read (boolean, opt) - Mark as read, default false. limit (int, opt, 1-100) - Max messages, default 20.

### 2.8 trinity_send

Send a durable message to another Trinity agent. Persists in SQLite.

Parameters: target_agent (string, required) - Agent to send to. message (string, required) - Message body. source_agent (string, opt) - Sender, defaults TRINITY_AGENT. task_id (string, opt) - Task association.

### 2.9 Tool-to-CLI Map

| MCP Tool | Equivalent CLI |
|----------|---------------|
| trinity_dispatch | trinity-lite dispatch agent task |
| trinity_dispatch_auto | trinity-lite dispatch-auto task |
| trinity_status | trinity-lite status task_id |
| trinity_tasks | trinity-lite tasks |
| trinity_worker | trinity-lite worker agent --once |
| trinity_doctor | trinity-lite doctor |
| trinity_inbox | trinity-lite inbox agent |
| trinity_send | trinity-lite send agent message |

---

## 3. Resources (MCP Resources = Data Agents Can Read)

MCP resources are URI-addressable read-only data. They complement tools: tools mutate state, resources inspect state.

### 3.1 trinity://tasks/{task_id}

- MIME: application/json
- Full task detail: prompt, status, result, error, timestamps
- Implementation: TrinityBus.get_task(task_id)

### 3.2 trinity://tasks/recent

- MIME: application/json
- 20 most recent tasks (compact records)
- Implementation: TrinityBus.list_tasks(limit=20)

### 3.3 trinity://health

- MIME: application/json
- Doctor health report, same as trinity_doctor tool but no params
- Implementation: run_doctor() with defaults

---

## 4. Security

Inherits all Trinity Lite v0.1.x boundaries plus MCP-specific guards.

### 4.1 Self-Delegation Prevention

Critical MCP risk: agent delegating a task that routes back to itself.

Multi-layer defense:

1. **source==target check** - TrinityBus.submit_task() rejects source==target (bus-level).
2. **dispatch_auto self-route check** - Verifies target_agent != source after routing.
3. **Depth limit** - depth > MAX_DEPTH (2) rejected. TRINITY_DEPTH env tracked.
4. **previous_agent exclusion** - Router excludes previous_agent from capability matches.

What this prevents:

- codex -> dispatch_auto -> resolves to codex (self) -> REJECTED
- codex -> dispatch_auto(review, previous_agent=codex) -> opposite -> OK depth=1
- claude_code re-delegates -> codex -> OK depth=2
- codex tries again -> depth > 2 -> REJECTED

### 4.2 Allowed Roots

Every cwd validated via ensure_inside_roots(). TRINITY_LITE_ALLOWED_ROOTS controls.

### 4.3 No Credential Exposure

- No API keys, tokens, or secrets read/stored/transmitted
- Agent responsible if writing secrets to task results
- Only TRINITY_AGENT and TRINITY_DEPTH env vars read (no secrets)

### 4.4 Process Isolation

- Subprocess of AI agent; same FS permissions
- No network (STDIO only Phase 1); no fork; no shell

### 4.5 Input Validation

- JSON Schema validation before dispatch
- Task IDs: 12-char hex. Agent: from config. Prompts: ~100KB max.

---

## 5. Implementation Plan

### Phase 1: Minimal STDIO Server (v0.2.0)

- New module: trinity_lite/mcp_server.py (~400 lines)
- New CLI subcommand: trinity-lite mcp serve
- MCP protocol: JSON-RPC 2.0 over stdin/stdout (stdlib only)
- Lifecycle: initialize, tools/list, tools/call, shutdown
- Tools: trinity_dispatch_auto, trinity_status
- Logging to stderr

| File | Action |
|------|--------|
| trinity_lite/mcp_server.py | Create (~400 lines) |
| trinity_lite/cli.py | Modify - add mcp subcommand |
| tests/test_mcp_server.py | Create (~200 lines) |

### Phase 2: Full Tools + Resources (v0.2.1)

- All 8 tools + 3 resources
- --wait support (runs worker cycles internally)
- resources/list and resources/read handlers
- JSON-RPC error codes (-32600 through -32603)
- Input validation

### Phase 3: HTTP Transport (v0.2.2)

- trinity-lite mcp serve --transport http --port 8099
- Python stdlib http.server + SSE framing
- Localhost-only by default

### Dependency Decision

Primary path (zero-dependency): stdlib only (json, sys.stdin/stdout/stderr).
Optional: pip install trinity-lite[mcp] for mcp PyPI FastMCP.
Auto-detection at import time: try import FastMCP, fallback to hand-rolled.

---

## 6. Usage Example

### 6.1 MCP Client Configuration

Claude Code (.mcp.json):
```json
{
  "mcpServers": {
    "trinity-lite": {
      "command": "trinity-lite",
      "args": ["mcp", "serve"],
      "env": { "TRINITY_AGENT": "claude_code" }
    }
  }
}
```

Codex (MCP config):
```json
{
  "mcpServers": {
    "trinity-lite": {
      "command": "trinity-lite",
      "args": ["mcp", "serve"],
      "env": { "TRINITY_AGENT": "codex" }
    }
  }
}
```

### 6.2 Example Session

```
User: audit this project for security issues

Claude Code:
  -> trinity_dispatch_auto({"task":"audit project","wait":true})
  <- {"id":"abc123","status":"completed","result":"Found 3 issues:..."}

Claude Code:
  Audit complete. Found 3 issues:
  1. Hardcoded secret in config.py:42
  2. SQL injection in query_builder.py:87
  3. Missing CSRF on /api/upload

  Would you like me to dispatch fix tasks?
```

### 6.3 Orchestration with Wait

```
User: implement auth, have another agent review

Claude Code:
  Step 1: dispatch_auto({"task":"implement JWT auth","wait":true})
         -> task abc123 completed
  Step 2: dispatch_auto({"task":"review JWT auth","previous_agent":"codex","wait":true})
         -> def456 completed. Review passed with 2 suggestions.

  Acceptance: ACCEPTED_WITH_SUGGESTIONS
```

---

## 7. Comparison with Internal Trinity MCP Server

The internal server at ~/.hermes/trinity_mcp.py serves full Trinity. Trinity Lite MCP is a simplified, public-friendly adaptation.

### 7.1 Side-by-Side

| Aspect | Internal (~/.hermes/) | Trinity Lite v0.2 |
|--------|----------------------|-------------------|
| Dependency | mcp PyPI (FastMCP) | Zero-dep, optional mcp extra |
| Agents | Fixed: hermes,claude_code,codex | Configurable: any |
| Router | importlib.reload() hot-reload | Direct resolve_route() |
| Self-delegation | Manual check | Same + bus-level guard |
| trinity_route | Separate dry-run tool | In dispatch_auto response |
| trinity_agents | Bus topology tool | Replaced by trinity_doctor |
| trinity_worker | Not present | NEW - execute in MCP session |
| trinity_doctor | Not present | NEW - health from MCP |
| Resources | None | 3: tasks/{id}, recent, health |
| Transport | STDIO only | STDIO + HTTP later |
| Module path | ~/.hermes/ (private) | trinity_lite/ (public, PyPI) |
| CLI | Standalone script | trinity-lite mcp serve |

### 7.2 What is Simplified

1. **No hardcoded agent list.** Internal: fixed 3 agents. Public: loaded from config (agents.local.json) or defaults.
2. **No router reload hack.** Internal: importlib.reload() for live edits. Public: fresh load each call.
3. **trinity_agents -> trinity_doctor.** Internal exposes bus topology. Public uses doctor for setup validation.
4. **trinity_worker added.** Internal assumes persistent workers. Public may not have them, so worker tool closes the loop inline.
5. **Resources added.** Internal has none. Public adds read-only inspection.
6. **Ephemeral design.** Internal has persistent workers, learning DBs, metrics. Trinity Lite is ephemeral by design.

### 7.3 What is the Same

- Core bus operations: submit_task, get_task, list_tasks, send_message, inbox
- Routing semantics: task_type inference, pattern matching, capability, opposite
- Depth and self-delegation guards
- STDIO JSON-RPC 2.0 framing
- TRINITY_AGENT env var identity
- Compact task serialization
- --wait semantics with configurable timeout

---

## Appendix A: MCP Startup Sequence

```
1. Agent spawns:   trinity-lite mcp serve
2. Server logs:    "Trinity Lite MCP server starting..." (stderr)
3. Server waits for initialize on stdin
4. Client:  {"jsonrpc":"2.0","id":1,"method":"initialize",...}
5. Server:  {"jsonrpc":"2.0","id":1,"result":{
     "protocolVersion":"2024-11-05",
     "capabilities":{"tools":{},"resources":{}},
     "serverInfo":{"name":"trinity-lite","version":"0.2.0"}}}
6. Client:  {"jsonrpc":"2.0","method":"notifications/initialized"}
7. Server accepts (no response for notification)
8. Normal operation: tools/call, resources/read/list
9. Client:  {"jsonrpc":"2.0","id":N,"method":"shutdown"}
10. Server responds, exits 0
```

## Appendix B: Protocol Implementation Sketch

```python
# trinity_lite/mcp_server.py (sketch, ~300 lines)
import json, sys

TOOLS = { ... }
RESOURCES = [ ... ]

def read_message():
    line = sys.stdin.readline()
    if not line: return None
    return json.loads(line)

def write_message(msg):
    sys.stdout.write(json.dumps(msg) + chr(10))
    sys.stdout.flush()

def handle_request(req):
    method, req_id = req.get("method"), req.get("id")
    if method == "initialize":
        return {"jsonrpc":"2.0","id":req_id,"result":{
            "protocolVersion":"2024-11-05",
            "capabilities":{"tools":{},"resources":{}},
            "serverInfo":{"name":"trinity-lite","version":"0.2.0"}}}
    elif method == "tools/list":
        return resp(req_id, {"tools":list(TOOLS.values())})
    elif method == "tools/call":
        return call_tool(req_id, req["params"])
    elif method == "shutdown":
        return resp(req_id, {})

def serve():
    while True:
        req = read_message()
        if req is None: break
        resp = handle_request(req)
        if resp: write_message(resp)
```

---

*Document version: 1.0 - 2026-06-22*
