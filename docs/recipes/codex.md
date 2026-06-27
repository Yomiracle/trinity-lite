# Codex Recipe

This recipe wires Codex in as a primary implementation agent.

## Prerequisites

Confirm Codex works outside Trinity Lite first:

```bash
codex --version
```

If your Codex CLI uses a different non-interactive command shape, adjust the
`command` array below. Keep the file local.

## Configure

```bash
cp examples/agents.command.example.json agents.local.json
```

Minimal Codex-only config:

```json
{
  "agents": {
    "codex": {
      "mode": "command",
      "command": ["codex", "exec", "-C", "{cwd}", "{prompt}"],
      "roles": ["primary_engineer"],
      "capabilities": ["architecture_design", "code_edit", "documentation", "project_audit", "test_run"],
      "priority": 80,
      "timeout": 1800
    },
    "claude_code": {
      "mode": "mock",
      "roles": ["reviewer"],
      "capabilities": ["code_review", "risk_check"],
      "timeout": 1800
    },
    "hermes": {
      "mode": "mock",
      "roles": ["orchestrator", "acceptance"],
      "capabilities": ["acceptance", "orchestration", "verification"],
      "timeout": 1800
    }
  }
}
```

## Run

Dispatch work:

```bash
trinity-lite dispatch-auto "write a unit test" --agents agents.local.json
```

Run one Codex worker cycle:

```bash
trinity-lite worker codex --once --agents agents.local.json
```

Inspect the result:

```bash
trinity-lite tasks
```

## Notes

- Commands are JSON arrays and run with `shell=False`.
- Do not put tokens or API keys in `agents.local.json`.
- `agents.local.json` is ignored by git.
- Start with `dispatch-auto` before using full `orchestrate`; it is easier to debug one worker at a time.
