# Trinity Lite

[![Tests](https://github.com/Yomiracle/trinity-lite/actions/workflows/test.yml/badge.svg)](https://github.com/Yomiracle/trinity-lite/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/Yomiracle/trinity-lite)](https://github.com/Yomiracle/trinity-lite/releases)
[![PyPI](https://img.shields.io/pypi/v/trinity-lite.svg)](https://pypi.org/project/trinity-lite/)

**Local-first multi-agent workflow infrastructure for CLI-based AI agents.**

Trinity Lite gives Codex, Claude Code, Hermes, Qwen, Gemini, Aider, and any CLI-based agent a shared task bus: route work, persist state in SQLite, run workers, capture results, and inspect the whole workflow from the command line.

[中文 README](README_zh.md)

## Why Trinity Lite

AI coding agents are powerful on their own, but multi-agent work is often still coordinated by hand:

| Manual workflow | Trinity Lite workflow |
|-----------------|----------------------|
| Copy results between tools | Dispatch tasks through a shared bus |
| Remember task state yourself | Store task status and results in SQLite |
| Decide handoffs manually | Route by task type or explicit agent |
| Lose failure context | Keep errors, results, and messages queryable |
| Demo depends on installed real agents | Mock agents run the full workflow locally |

Trinity Lite turns "several AI tools on one machine" into a small, reproducible agent workflow layer.

## Who It Is For

| User | What Trinity Lite helps with |
|------|------------------------------|
| AI developers | Prototype multi-agent coding workflows without building a platform first |
| Agent workflow builders | Test routing, task persistence, review handoffs, and worker execution |
| Indie hackers and small teams | Coordinate local CLI agents without server infrastructure |
| Technical creators and educators | Demonstrate real multi-agent flow with commands people can run |

## 30-Second Demo

```bash
python3 -m pip install trinity-lite
trinity-lite doctor
trinity-lite dispatch-auto "implement a hello-world function"
trinity-lite worker codex --once
trinity-lite tasks
```

The default agents are mock agents, so this demo works even if Codex, Claude Code, or Hermes are not installed.

## How It Works

```text
                  +----------------+
user task ------> | router         |
                  +-------+--------+
                          |
                          v
                  +-------+--------+
                  | SQLite task bus|
                  +-------+--------+
                          |
          +---------------+----------------+
          v                                v
   +------+-------+                 +------+-------+
   | Codex worker |                 | review worker|
   +------+-------+                 +------+-------+
          |                                |
          v                                v
   agent adapter                    agent adapter
          |                                |
          +---------------+----------------+
                          v
                  status / result / inbox
```

Codex, Claude Code, and Hermes are default presets, not requirements. Roles are configurable:

| Agent | Default Role |
|-------|--------------|
| `codex` | primary implementation, testing, project audit |
| `claude_code` | secondary review and cross-check |
| `hermes` | orchestration and acceptance |

## Core Capabilities

- **Routing**: resolve task types to explicit agents or agents selected by declared capabilities.
- **Durable bus**: store tasks, status, results, errors, and messages in SQLite.
- **Worker model**: pull queued tasks and execute mock agents or real local CLIs.
- **Command adapters**: connect Codex, Claude Code, Hermes, Qwen, Gemini, Aider, or any CLI through JSON-array commands.
- **Local health checks**: verify Python, SQLite, route config, agent config, publish readiness, and optional runtime hygiene.
- **Safety boundaries**: block self-delegation, cap delegation depth, enforce allowed working directories, and scan public trees.

## Technical Highlights

- **Zero runtime dependencies**: standard-library Python package.
- **SQLite-first state**: local, inspectable, transactional task storage.
- **Shell-safe command execution**: command adapters use JSON arrays and `shell=False`.
- **Mock-to-real upgrade path**: run the full demo before installing real agent CLIs.
- **Capability routing**: agents can declare roles, capabilities, and priority for name-agnostic routing.
- **CI-backed public release**: tests, compile checks, doctor checks, and a PyPI publish workflow run in GitHub Actions.
- **Designed for extension**: MCP server and orchestrator are planned as optional layers, not required for the core bus.

## Product Positioning

Trinity Lite sits between "single-agent CLI tools" and "full agent frameworks":

```text
Codex / Claude Code / custom CLI
        |
        v
Trinity Lite: route -> bus -> worker -> result
        |
        v
future layers: MCP server, orchestrator, tracing, dashboard
```

It does not try to replace agent frameworks. It provides a lightweight coordination layer for the AI tools developers already use.

## Quick Start

```bash
python3 -m pip install trinity-lite

# Run a local health check
trinity-lite doctor

# Dispatch a task using the built-in route resolver
trinity-lite dispatch-auto "implement a hello-world function"

# Run one mock Codex worker cycle
trinity-lite worker codex --once

# Check recent tasks
trinity-lite tasks
```

For local development from source:

```bash
git clone https://github.com/Yomiracle/trinity-lite.git
cd trinity-lite
python3 -m pip install -e .

# Run a source-tree health check
trinity-lite doctor --scan-root .

# Dispatch a task using the built-in route resolver
trinity-lite dispatch-auto "implement a hello-world function"

# Run one mock Codex worker cycle
trinity-lite worker codex --once

# Check recent tasks
trinity-lite tasks
```

## Use Real Agent Commands

Copy the command example and edit it for your machine:

```bash
cp examples/agents.command.example.json agents.local.json
trinity-lite dispatch-auto "write a unit test"
trinity-lite worker codex --once --agents agents.local.json
```

Agent commands are configured as JSON arrays and run with `shell=False`.

See [docs/REAL_AGENTS.md](docs/REAL_AGENTS.md) for Codex, Claude Code, and generic CLI examples.

For name-agnostic routing, copy the generic capability examples:

```bash
cp examples/agents.generic.example.json agents.local.json
cp examples/routes.capabilities.example.json routes.local.json
trinity-lite dispatch-auto "fix the parser bug" --agents agents.local.json --routes routes.local.json
```

## Roadmap

- **v0.1.x**: harden the public local bus, docs, examples, and tests.
- **v0.2**: add a minimal MCP server so AI clients can call Trinity Lite directly.
- **v0.3**: add an optional orchestrator for primary work -> review -> doctor/tests -> acceptance.
- **v1.0**: stabilize CLI, schema, and packaging.

See [ROADMAP.md](ROADMAP.md).

## Core Commands

```bash
trinity-lite route "review this patch" --previous-agent codex
trinity-lite dispatch codex "implement X"
trinity-lite dispatch-auto "audit this project"
trinity-lite status <task_id>
trinity-lite tasks
trinity-lite worker codex --once
trinity-lite send claude_code "please review task abc"
trinity-lite inbox claude_code
trinity-lite orchestrate "implement X"
trinity-lite doctor --scan-root .
```

For long-running local installs that maintain a metrics log, add runtime hygiene
checks:

```bash
trinity-lite doctor --runtime-root ~/.trinity-lite --retired-port 9797
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Project Docs

- [Trinity Lite tutorial](docs/TRINITY_LITE.md)
- [Real agent command setup](docs/REAL_AGENTS.md)
- [Agent capabilities](docs/CAPABILITIES.md)
- [Product positioning](docs/PRODUCT.md)
- [Operations guide](docs/OPERATIONS.md)
- [Security notes](docs/SECURITY.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT
