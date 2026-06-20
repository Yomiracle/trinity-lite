# ADR-001: Agent Capability Routing

## Status

Accepted

## Context

Trinity Lite started with Codex, Claude Code, and Hermes as default agent names.
That is useful for the maintainer's own workflow, but public users may run Qwen,
Gemini, Aider, OpenHands, local wrappers, or other CLI agents with different API
providers and model capabilities.

The public project needs to route tasks without knowing or storing those API
details.

## Decision

Add optional `roles`, `capabilities`, and `priority` metadata to agent specs.
Route rules may keep using explicit `agent` values or switch to capability
matching with `requires`, `prefer`, and `avoid`.

Trinity Lite will not call model APIs directly. CLI agents and local wrappers own
provider-specific setup.

## Rationale

This keeps the v0.1.x package small and dependency-free while making it useful
for users who do not run Codex, Claude Code, or Hermes.

Capability matching also keeps routing explainable:

```text
required capabilities -> preferred labels -> priority
```

## Trade-offs

- No automatic capability discovery.
- No cost or quality scoring engine.
- No model-provider adapters in core.
- Users must maintain honest local capability metadata.

These trade-offs are acceptable for a local-first MVP. More advanced scoring can
be added later if real usage shows it is needed.

## Consequences

- Existing explicit-agent routes remain compatible.
- Public examples can show generic CLI agents without private API details.
- Future orchestrator work can use `review_required` and capability labels
  without hardcoding agent names.
