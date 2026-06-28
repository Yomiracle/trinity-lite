# Trinity Lite Architecture

Trinity Lite is intentionally small. It is not a model gateway and not a full agent platform. It is a task coordination layer.

## Components

| Module | Responsibility |
|--------|----------------|
| `trinity_lite.bus` | SQLite task queue and durable messages |
| `trinity_lite.router` | `task_type`, pattern, explicit-agent, and capability routing |
| `trinity_lite.adapters` | mock and command-based agent adapters plus agent metadata |
| `trinity_lite.worker` | pulls queued tasks and executes an adapter |
| `trinity_lite.orchestrator` | optional primary task plus review flow |
| `trinity_lite.worktree` | managed git worktree lifecycle and diff evidence |
| `trinity_lite.cli` | command line interface |
| `trinity_lite.guard` | path and secret-scan safety helpers |
| `trinity_lite.doctor` | environment, publish-readiness, and optional runtime hygiene checks |

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

The optional `orchestrate` command composes the same pieces:

```text
route primary -> submit -> run primary worker once
              -> if review_required, route code_review
              -> submit -> run reviewer once
              -> run local verifier
              -> persist gate_status, verification_json, acceptance_status, accepted_at
```

## Acceptance Gate

The bus stores lightweight acceptance evidence on task rows:

- `route_json`: JSON-encoded route decision used for dispatch
- `parent_task_id` / `review_task_id`: review linkage
- `gate_status` and `gate_updated_at`: current review or acceptance state
- `verification_json`: JSON-encoded local verifier output
- `acceptance_status` and `acceptance_reason`: accepted, blocked, queued, needs_review, or review_attention
- `accepted_at`: set only after required review and verification pass

The default verifier calls `trinity_lite.doctor.run_doctor()` against the same
bus, routes, and agents config. Applications can pass a custom verifier to
`run_review_flow()` when they need project-specific checks. Supported verifier
signatures are `verifier()`, `verifier(context)`, and `verifier(bus, task_id)`.
The context contains `bus`, `task`, `task_id`, `routes_path`, and `agents_path`.

## Why SQLite

SQLite keeps the public MVP easy to run:

- no server setup
- works offline
- transactional task claiming
- easy to inspect
- enough for one local machine

## Adapter Boundary

Real agent tools are not hardcoded. Public users configure command arrays and
optional routing metadata:

```json
{
  "agents": {
    "implementation_cli": {
      "mode": "command",
      "command": ["my-implementation-cli", "--cwd", "{cwd}", "{prompt}"],
      "roles": ["primary_engineer"],
      "capabilities": ["code_edit", "test_run"],
      "priority": 80
    }
  }
}
```

Commands are executed with `shell=False`. If no `{prompt}` placeholder is present, the prompt is passed on stdin.

## Routing Boundary

Routes can still name an agent explicitly:

```json
{"implementation": {"agent": "codex", "review_required": true}}
```

They can also select by capability:

```json
{
  "implementation": {
    "requires": ["code_edit"],
    "prefer": ["primary_engineer"],
    "review_required": true
  }
}
```

The router does not inspect model providers, keys, or API endpoints. Those
details belong to the CLI agent or local wrapper. Trinity Lite only chooses a
configured worker and records the result.

## Worktree Boundary

`trinity-lite worktree` manages isolated git worktrees for agent work. The
preview command creates branches named `trinity/<task_id>/<agent_id>`, records
their base commit, lists managed worktrees, returns diff evidence, and removes
worktrees during cleanup.

This layer is intentionally separate from `orchestrate` for now. It does not
merge branches, delete branches by default, create pull requests, or run agents
automatically. Those behaviors need explicit review and acceptance integration
before they become part of the default flow.

## Non-Goals

- No private model router
- No bundled credentials
- No remote task execution
- No automatic internet access
- No production deployment assumptions
- No built-in model-provider API abstraction

## Health Boundaries

`doctor --scan-root .` checks the public source tree before release. It should
fail on private files, secrets, runtime databases, logs, metrics, symlinks, and
known retired runtime artifacts.

`doctor --runtime-root <dir>` checks a local runtime directory. This is optional
because the public demo does not require long-running metrics, but deployed
installations can use it to require a writable `metrics.jsonl` and reject retired
state files.

`doctor --retired-port <port>` asserts that a retired local service port is no
longer listening.
