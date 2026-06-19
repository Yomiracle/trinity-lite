# Trinity Lite Architecture

Trinity Lite is intentionally small. It is not a model gateway and not a full agent platform. It is a task coordination layer.

## Components

| Module | Responsibility |
|--------|----------------|
| `trinity_lite.bus` | SQLite task queue and durable messages |
| `trinity_lite.router` | `task_type` and pattern routing |
| `trinity_lite.adapters` | mock and command-based agent adapters |
| `trinity_lite.worker` | pulls queued tasks and executes an adapter |
| `trinity_lite.cli` | command line interface |
| `trinity_lite.guard` | path and secret-scan safety helpers |
| `trinity_lite.doctor` | environment and publish-readiness checks |

## Data Flow

```text
1. User runs dispatch-auto
2. Router resolves target agent and task type
3. Bus writes queued task to SQLite
4. Worker claims the next queued task for its agent
5. Adapter runs a mock response or configured command
6. Bus stores completed result or failure error
7. User reads status/tasks/inbox
```

## Why SQLite

SQLite keeps the public MVP easy to run:

- no server setup
- works offline
- transactional task claiming
- easy to inspect
- enough for one local machine

## Adapter Boundary

Real agent tools are not hardcoded. Public users configure command arrays:

```json
{
  "agents": {
    "codex": {
      "mode": "command",
      "command": ["codex", "exec", "-C", "{cwd}", "{prompt}"]
    }
  }
}
```

Commands are executed with `shell=False`. If no `{prompt}` placeholder is present, the prompt is passed on stdin.

## Non-Goals

- No private model router
- No bundled credentials
- No remote task execution
- No automatic internet access
- No production deployment assumptions
