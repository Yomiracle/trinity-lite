# Hermes and Private Trinity Boundaries

This public package is `trinity-lite`.

The maintainer may also have a private `~/.hermes` Trinity runtime on their own
machine. That private runtime is not part of the public package and is not
required to use Trinity Lite.

## Keep the Boundary Clear

| Layer | Purpose | Should be committed? |
|-------|---------|----------------------|
| `trinity-lite` package | Public local task bus, CLI, MCP server, docs, examples | Yes |
| `agents.local.json` | Local command wiring for your machine | No |
| `~/.hermes` private runtime | Maintainer-specific orchestration, health checks, gateway config | No |
| API keys and provider routing | Belongs to the underlying CLI tools or local wrappers | No |

## Using Hermes as a Command Agent

If you have a `hermes` CLI installed and it supports a non-interactive prompt,
you can wire it as a command agent:

```json
{
  "agents": {
    "hermes": {
      "mode": "command",
      "command": ["hermes", "-z", "{prompt}"],
      "roles": ["orchestrator", "acceptance"],
      "capabilities": ["acceptance", "orchestration", "verification"],
      "priority": 60,
      "timeout": 1800
    }
  }
}
```

Check your local Hermes help output before using this exact command:

```bash
hermes --help
```

## Using Private Trinity to QA the Public Package

The maintainer can use a private Trinity runtime to check the public package,
but the check must install `trinity-lite` into a temporary virtualenv. That
proves the PyPI artifact works for a clean user and avoids accidentally testing
against a global local install.

Recommended release QA shape:

```text
private ~/.hermes Trinity -> GitHub/PyPI check -> temp venv install -> trinity-lite doctor -> orchestrate --wait -> SQLite evidence query
```

Do not copy private databases, gateway configs, model routing files, or message
logs into this repository.
