# Trinity Lite

[![Tests](https://github.com/Yomiracle/trinity-lite/actions/workflows/test.yml/badge.svg)](https://github.com/Yomiracle/trinity-lite/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/Yomiracle/trinity-lite)](https://github.com/Yomiracle/trinity-lite/releases)

**A minimal public three-agent task bus for Codex, Claude Code, Hermes, or any CLI-based agent.**

Trinity Lite is the safe, public version of a private three-agent workflow. It keeps the useful parts: persistent dispatch, routing, workers, durable messages, mock agents, and safety checks. It does not include private keys, local logs, model gateways, personal memories, or machine-specific configuration.

[中文 README](README_zh.md)

## 30-Second Demo

```bash
git clone https://github.com/Yomiracle/trinity-lite.git
cd trinity-lite
python3 -m pip install -e .
trinity-lite doctor --scan-root .
trinity-lite dispatch-auto "implement a hello-world function"
trinity-lite worker codex --once
trinity-lite tasks
```

The default agents are mock agents, so this demo works even if Codex, Claude Code, or Hermes are not installed.

## What It Does

```text
user task -> router -> SQLite task bus -> worker -> agent adapter -> result
```

Default roles are configurable:

| Agent | Default Role |
|-------|--------------|
| `codex` | primary implementation, testing, project audit |
| `claude_code` | secondary review and cross-check |
| `hermes` | orchestration and acceptance |

## Quick Start

```bash
git clone https://github.com/Yomiracle/trinity-lite.git
cd trinity-lite
python3 -m pip install -e .

# Run a local health check
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
trinity-lite doctor --scan-root .
```

## Safety Rules

Trinity Lite intentionally excludes private runtime state:

- no `.env`
- no API keys or OAuth tokens
- no local SmartRouter or PM2 config
- no private SQLite task databases
- no personal memories, logs, or shell history
- no hardcoded `/Users/...` paths

See [docs/SECURITY.md](docs/SECURITY.md).

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Project Docs

- [Trinity Lite tutorial](docs/TRINITY_LITE.md)
- [Real agent command setup](docs/REAL_AGENTS.md)
- [Security notes](docs/SECURITY.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT
