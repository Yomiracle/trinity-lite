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

- **Route tasks between your agents.** *"Send implementation to Codex, reviews to Claude Code — automatically."*
- **Remember everything.** Tasks, results, errors, and messages all land in a local SQLite database you can query anytime.
- **Run workers that pull and execute.** Each agent gets a worker that picks up queued tasks, runs them, and writes results back.
- **Keep things safe.** Self-delegation is blocked. Delegation depth is capped. Working directories are allowlisted. No surprises.

## Quick start

30 seconds, works without any real agents installed:

```bash
pip install trinity-lite
trinity-lite doctor
trinity-lite dispatch-auto "implement a hello-world function"
trinity-lite worker codex --once
trinity-lite tasks
```

Mock agents ship with the package, so the full workflow runs out of the box.

## Why not another framework

Trinity Lite doesn't build agents. It connects the agents you already have.

LangGraph and CrewAI give you primitives to build new agents from scratch. Trinity Lite assumes your agents already exist — Codex in one terminal, Claude Code in another — and gives them a shared task bus, durable state, and safety boundaries. No SDK to learn, no new agent abstraction.

## Who this is for

| You are... | Trinity Lite helps you... |
|------------|---------------------------|
| Running 2+ CLI agents and tired of copy-pasting between terminals | Dispatch tasks through a shared bus and read results in one place |
| Prototyping multi-agent workflows before committing to a platform | Test routing, persistence, and review handoffs with mock agents first |
| Coordinating agents on a single machine without server infrastructure | Keep everything local: SQLite state, stdlib-only runtime, no daemons |
| Demonstrating multi-agent systems to others | Ship a reproducible workflow that anyone can run with five commands |

## Features

- **Route by task type or agent capability.** Declare what each agent can do, and the router picks the right one — or dispatch directly to a named agent.
- **Persist everything in SQLite.** Tasks, statuses, results, errors, and inter-agent messages are all queryable from a single local database.
- **Run workers that execute real CLIs.** Workers pull tasks from the bus, invoke Codex, Claude Code, Hermes, or any CLI agent, and write results back.
- **Use name-agnostic capability routing.** Agents declare capabilities like `implement`, `review`, `audit` — the router matches tasks without hardcoding agent names.
- **Test without real agents.** Mock agents simulate the full dispatch → worker → result cycle, so you can prototype before wiring up live CLIs.
- **Block dangerous patterns before they happen.** Self-delegation is rejected. Delegation depth is capped. Working directories must be in the allowlist.
- **Check health with one command.** `trinity-lite doctor` verifies Python, SQLite, route config, agent config, and publish readiness in a single pass.
- **Execute commands safely.** All agent commands are JSON arrays running with `shell=False` — no shell injection surface.
- **Extend with zero friction.** Zero runtime dependencies. Standard library only. The MCP server is one optional pip extra away.

## Install

```bash
pip install trinity-lite
```

Requires Python 3.10+. Zero runtime dependencies — just the standard library.

### Optional extras

```bash
pip install trinity-lite[mcp]          # MCP server
pip install trinity-lite[agent-skill]   # agent-skill-system integration
```

## Example workflow

Here's how three agents collaborate on a single feature:

```bash
# 1. Run health check to confirm everything is wired up
trinity-lite doctor

# 2. Hermes routes the task — the router picks the right agent automatically
trinity-lite dispatch-auto "implement a rate limiter for the API" --source-agent hermes

# 3. Codex picks up and implements
trinity-lite worker codex --once --agents agents.local.json

# 4. Claude Code reviews the implementation
trinity-lite send claude_code "please review task <task_id>" --source-agent hermes
trinity-lite worker claude_code --once --agents agents.local.json

# 5. Inspect the full trail
trinity-lite tasks
trinity-lite status <task_id>
```

The first two steps work immediately with mock agents. Wire up real CLIs by copying the example config:

```bash
cp examples/agents.command.example.json agents.local.json
```

## MCP server

Trinity Lite ships as an MCP server — let your AI clients control the task bus directly.

```bash
pip install trinity-lite[mcp]
trinity-lite mcp serve
```

**10 tools available:**

| Tool | What it does |
|------|--------------|
| `trinity_dispatch` | Dispatch a task to a specific agent |
| `trinity_dispatch_auto` | Let the router pick the right agent |
| `trinity_status` | Get state and result of any task |
| `trinity_tasks` | List recent tasks, filterable by agent |
| `trinity_worker` | Run one worker cycle for an agent |
| `trinity_doctor` | Run health and diagnostic checks |
| `trinity_inbox` | Read durable messages for an agent |
| `trinity_send` | Send a message to another agent |
| `trinity_skill_search` | Search agent-skill-system for relevant skills |
| `trinity_skill_load` | Load full content of a named skill |

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
