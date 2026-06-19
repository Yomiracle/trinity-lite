# Trinity Lite

**A minimal public three-agent task bus for Codex, Claude Code, Hermes, or any CLI-based agent.**

Trinity Lite is the safe, public version of a private three-agent workflow. It keeps the useful parts: persistent dispatch, routing, workers, durable messages, mock agents, and safety checks. It does not include private keys, local logs, model gateways, personal memories, or machine-specific configuration.

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

The default agents are mock agents, so the demo works even if Codex, Claude Code, or Hermes are not installed.

## Use Real Agent Commands

Copy the command example and edit it for your machine:

```bash
cp examples/agents.command.example.json agents.local.json
trinity-lite dispatch-auto "write a unit test"
trinity-lite worker codex --once --agents agents.local.json
```

Agent commands are configured as JSON arrays and run with `shell=False`.

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

## License

MIT
