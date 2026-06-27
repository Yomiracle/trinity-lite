# Agent Capabilities

Trinity Lite is agent-agnostic. Codex, Claude Code, and Hermes are default
presets, not requirements.

The core contract is:

```text
task -> route requirements -> agent capabilities -> worker command -> result
```

Trinity Lite does not need to know which API or model a CLI agent uses. It only
needs a command to run and enough metadata to route tasks.

## Agent Metadata

Agents can declare roles, capabilities, and priority in `agents.local.json`:

```json
{
  "agents": {
    "implementation_cli": {
      "mode": "command",
      "command": ["my-implementation-cli", "--cwd", "{cwd}", "{prompt}"],
      "roles": ["primary_engineer"],
      "capabilities": ["code_edit", "test_run", "long_context"],
      "priority": 80,
      "timeout": 1800
    }
  }
}
```

| Field | Meaning |
|-------|---------|
| `agent_id` | The JSON object key, such as `implementation_cli` |
| `mode` | `mock` or `command` |
| `command` | JSON-array command for command agents |
| `roles` | Human workflow roles such as `primary_engineer` or `reviewer` |
| `capabilities` | Concrete things the agent can do, such as `code_edit` |
| `priority` | Tie-breaker when multiple agents match |
| `timeout` | Command timeout in seconds |

## Route Rules

Legacy explicit-agent routes still work:

```json
{
  "implementation": {"agent": "codex", "review_required": true}
}
```

Capability routes select from configured agents:

```json
{
  "implementation": {
    "requires": ["code_edit"],
    "prefer": ["primary_engineer"],
    "review_required": true
  }
}
```

Route fields:

| Field | Meaning |
|-------|---------|
| `agent` | Explicit agent id, or `opposite` for opposite-agent review |
| `requires` | Capabilities every candidate must have |
| `prefer` | Ordered labels to prefer; labels may be agent ids, roles, or capabilities |
| `avoid` | Agent ids, roles, or capabilities to exclude |
| `review_required` | Whether a later orchestrator should request review |

Selection order:

1. If `agent` is `opposite`, use the configured opposite of `previous_agent`.
2. If `agent` names a concrete agent id, use it.
3. Otherwise, load agents and keep candidates with every required capability.
4. Exclude candidates matching any `avoid` label.
5. Prefer matches in `prefer`, then higher `priority`.

`previous_agent` is also excluded from capability matching so review routes do
not return work to the same agent.

Route results keep `source` compatible with earlier releases and add `selection`
to show whether the route used `explicit_agent` or `capability_match`.

## Example

```bash
cp examples/agents.generic.example.json agents.local.json
cp examples/routes.capabilities.example.json routes.local.json

trinity-lite dispatch-auto "fix the parser bug" \
  --agents agents.local.json \
  --routes routes.local.json
```

The selected worker still runs normally:

```bash
trinity-lite worker implementation_cli --once --agents agents.local.json
```

The optional orchestrator uses the same capability routes for primary work and
review:

```bash
trinity-lite orchestrate "fix the parser bug" \
  --agents agents.local.json \
  --routes routes.local.json
```

## API Differences

Different CLI agents may use different APIs, keys, tools, model families, or
context windows. Keep those details inside the CLI agent or a local wrapper.

Trinity Lite should not store API keys, model-provider configuration, OAuth
tokens, or private endpoint URLs in the public repository.

If an API requires special setup, wrap it locally:

```json
{
  "agents": {
    "internal_agent": {
      "mode": "command",
      "command": ["internal-agent-wrapper", "{prompt}"],
      "capabilities": ["code_edit"],
      "timeout": 1800
    }
  }
}
```

## Common Capability Names

Suggested names:

| Capability | Use For |
|------------|---------|
| `code_edit` | Implementing or modifying code |
| `code_review` | Reviewing patches or agent output |
| `test_run` | Running or writing tests |
| `project_audit` | Repository-wide audit tasks |
| `architecture_design` | Architecture and design work |
| `documentation` | Writing docs or changelogs |
| `research` | Source gathering and synthesis |
| `long_context` | Large-repository or large-document tasks |
| `orchestration` | Dispatching or workflow control |
| `acceptance` | Final acceptance checks |
| `verification` | Independent validation |
| `risk_check` | Security, reliability, or regression checks |

These are conventions, not a closed enum. Use stable names in your own routes
and agent configs.

## Validation

Trinity Lite does not enforce a closed capability vocabulary, but `doctor`
validates config structure and route resolvability:

```bash
trinity-lite doctor --agents agents.local.json --routes routes.local.json
```

This catches invalid field types, unknown explicit agents, broken `opposites`
entries, and capability routes that cannot match any configured agent.
