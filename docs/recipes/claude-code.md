# Claude Code Recipe

This recipe wires Claude Code in as a secondary reviewer.

## Prerequisites

Confirm Claude Code works outside Trinity Lite first:

```bash
claude --version
claude -p "Reply with OK"
```

If your local Claude Code command uses a different non-interactive flag, update
the `command` array below.

## Configure

Create `agents.local.json`:

```json
{
  "agents": {
    "codex": {
      "mode": "mock",
      "roles": ["primary_engineer"],
      "capabilities": ["code_edit", "test_run"],
      "timeout": 1800
    },
    "claude_code": {
      "mode": "command",
      "command": ["claude", "-p", "{prompt}"],
      "roles": ["reviewer"],
      "capabilities": ["code_review", "risk_check", "source_scan"],
      "priority": 70,
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

## Run a Review Task

Create a primary task with the mock Codex agent:

```bash
trinity-lite dispatch codex "implement a parser" --agents agents.local.json
trinity-lite worker codex --once --agents agents.local.json
```

Route a review to Claude Code:

```bash
trinity-lite dispatch-auto "review the parser implementation" \
  --type code_review \
  --previous-agent codex \
  --agents agents.local.json
```

Run the Claude Code worker:

```bash
trinity-lite worker claude_code --once --agents agents.local.json
```

## Use in an Orchestrated Flow

For an implementation route that requires review, configure routes so primary
work goes to the implementation agent and `code_review` goes to `claude_code`.
Then run:

```bash
trinity-lite orchestrate "implement a rate limiter" --agents agents.local.json
```

The accepted primary task will include `review_task_id`, `verification_json`,
`acceptance_status`, and `accepted_at`.
