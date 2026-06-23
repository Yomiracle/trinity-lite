# Trinity Lite

[![Tests](https://github.com/Yomiracle/trinity-lite/actions/workflows/test.yml/badge.svg)](https://github.com/Yomiracle/trinity-lite/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/trinity-lite.svg)](https://pypi.org/project/trinity-lite/)

**The bus that lets your AI agents talk to each other.**

[中文 README](README_zh.md)

## The problem

You already use Claude Code. Maybe you just installed Codex. You want them to collaborate — but there's no built-in way to route tasks between them, remember who did what, or stop them from stepping on each other. Trinity Lite is the missing layer.

## What it does

- **Route by capability, not name.** You describe the task. The router matches it to the right agent — no hardcoded agent names, no fragile dispatch logic. *"Implement a rate limiter" lands on the agent you tagged `implement`. "Review the auth module" goes to the agent tagged `review`.*
- **Give every agent a pull queue.** Workers read pending tasks from the shared bus, execute them via CLI, and write results back. Each agent polls on its own schedule. You never copy-paste an output between terminals again.
- **Remember every decision.** Every task, status change, result, error, and inter-agent message lands in a local SQLite database. Query who did what, when, and what happened — without setting up a logging pipeline.
- **Block footguns before they fire.** Self-delegation loops are rejected. Delegation depth has a hard cap. Working directories must be in the allowlist. You ship features, not incident reports.

## Quick start

30 seconds, no agents required:

```bash
pip install trinity-lite
trinity-lite doctor
trinity-lite dispatch-auto "implement a hello-world function"
trinity-lite worker codex --once
trinity-lite tasks
```

Mock agents are built in. You see the full dispatch → execute → result cycle before you wire up anything real.

## Not another framework

Trinity Lite doesn't build agents. It connects the agents you already have.

LangGraph and CrewAI give you primitives for building agents from scratch — graph definitions, role abstractions, tool wrappers. Trinity Lite starts from the opposite end: Claude Code is running in one terminal, Codex is running in another, and they need a shared task bus, durable state, and safety boundaries. No SDK to learn. No new agent abstraction. Just a bus that works with the CLIs you already use.

## Who this is for

| You are... | Trinity Lite helps you... |
|------------|---------------------------|
| Copy-pasting prompts and outputs between two agent terminals all day | Dispatch once to the bus and let agents pull their own work |
| Prototyping a multi-agent pipeline before committing infrastructure | Run the full flow with mock agents — no API keys, no provisioning |
| Running everything on a single machine with zero server setup | Keep your state in SQLite, your runtime in stdlib, your daemon count at zero |
| Showing a colleague how multi-agent collaboration works | `pip install` → five commands → they see it run. No explanation needed. |

## Features

- **Route by capability.** Tag agents with `implement`, `review`, `audit` — the router matches tasks to the agent that can do them. No agent names in your dispatch logic.
- **Dispatch directly when you need control.** Bypass the router and send a task straight to `claude_code` or `codex`. Best of both worlds.
- **Persist everything in SQLite.** Tasks, statuses, results, errors, and messages in one local file. Query it with `sqlite3` or any tool that speaks SQL.
- **Run CLI workers on demand.** `trinity-lite worker codex --once` pulls one queued task, executes the agent's command, and writes the result. Run it in a loop, in cron, or by hand.
- **Execute safely, no shell injection.** Agent commands are JSON arrays run with `shell=False`. No string interpolation into a shell. No surprises.
- **Test with mock agents.** Mock agents simulate the full cycle without real CLIs. Prototype routing, persistence, and review handoffs first. Wire up real agents later.
- **Guard against runaway delegation.** Self-delegation is blocked. Delegation depth is capped. Working directories are allowlisted. Safe by default.
- **Check health in one pass.** `trinity-lite doctor` verifies Python, SQLite, route config, agent config, and publish readiness.
- **Zero dependencies.** Runtime is Python standard library only. Nothing to install but Python 3.10+.
- **109 tests guarding the surface area.** Mock workflows, safety checks, routing, persistence — all covered.

## Install

```bash
pip install trinity-lite
```

Python 3.10+. Zero runtime dependencies. Standard library only.

### Optional extras

```bash
pip install trinity-lite[mcp]           # MCP server — 10 tools + 3 resources
pip install trinity-lite[agent-skill]   # agent-skill-system integration
```

## Workflow example

Hermes routes → Codex implements → Claude Code reviews. Five commands, one audit trail.

```bash
# Hermes sends the task. The router picks Codex automatically.
trinity-lite dispatch-auto "implement a rate limiter for the API" --source-agent hermes

# Codex pulls the task and runs it.
trinity-lite worker codex --once --agents agents.local.json

# Claude Code reviews the result.
trinity-lite send claude_code "please review task <task_id>" --source-agent hermes
trinity-lite worker claude_code --once --agents agents.local.json

# Read the full trail.
trinity-lite status <task_id>
```

Works immediately with mock agents. Ready for real CLIs when you are:

```bash
cp examples/agents.command.example.json agents.local.json
```

## MCP server

Turn the task bus into an MCP server. Let any MCP client dispatch, query, and route tasks.

```bash
pip install trinity-lite[mcp]
trinity-lite mcp serve
```

**10 tools:**

| Tool | What it does |
|------|--------------|
| `trinity_dispatch` | Dispatch a task to a specific agent |
| `trinity_dispatch_auto` | Dispatch and let the capability router pick the agent |
| `trinity_status` | Get the state and result of any task by ID |
| `trinity_tasks` | List recent tasks, filterable by agent |
| `trinity_worker` | Run one worker cycle for an agent |
| `trinity_doctor` | Run health and diagnostic checks |
| `trinity_inbox` | Read durable messages for an agent |
| `trinity_send` | Send a message from one agent to another |
| `trinity_skill_search` | Search agent-skill-system for relevant skills |
| `trinity_skill_load` | Load the full content of a named skill |

**3 resources:** `trinity://health`, `trinity://tasks/recent`, `trinity://tasks/{task_id}`

## Links

- [PyPI](https://pypi.org/project/trinity-lite/)
- [Documentation](docs/)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Real agent setup](docs/REAL_AGENTS.md)

## License

MIT
