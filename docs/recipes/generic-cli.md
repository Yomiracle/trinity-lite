# Generic CLI Agent Recipe

Use this recipe for any local CLI that can accept a prompt as an argument or on
stdin.

## Prompt as an Argument

```json
{
  "agents": {
    "implementation_cli": {
      "mode": "command",
      "command": ["my-implementation-cli", "--cwd", "{cwd}", "{prompt}"],
      "roles": ["primary_engineer"],
      "capabilities": ["code_edit", "test_run"],
      "priority": 70,
      "timeout": 1800
    }
  }
}
```

## Prompt on Stdin

If `{prompt}` is not present in the command array, Trinity Lite sends the prompt
to stdin:

```json
{
  "agents": {
    "review_cli": {
      "mode": "command",
      "command": ["my-review-cli", "--format", "text"],
      "roles": ["reviewer"],
      "capabilities": ["code_review", "risk_check"],
      "priority": 60,
      "timeout": 1800
    }
  }
}
```

## Capability Routing

Copy the generic examples:

```bash
cp examples/agents.generic.example.json agents.local.json
cp examples/routes.capabilities.example.json routes.local.json
```

Route and run:

```bash
trinity-lite dispatch-auto "fix the parser bug" \
  --agents agents.local.json \
  --routes routes.local.json

trinity-lite worker implementation_cli --once --agents agents.local.json
```

## Safety Checklist

- Use JSON arrays, not shell strings.
- Keep credentials in the CLI tool's own config or environment.
- Keep `agents.local.json` and `routes.local.json` out of git.
- Run `trinity-lite doctor --agents agents.local.json --routes routes.local.json` after editing config.
- Start with one worker cycle before running daemons or full orchestration.
