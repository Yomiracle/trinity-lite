# Roadmap

Trinity Lite is intentionally small. The public project should stay easy to install, inspect, and modify before adding larger orchestration features.

## v0.1.x: Public MVP Hardening

- Keep the mock-agent demo stable.
- Improve README, Chinese docs, and first-run instructions.
- Expand tests around routing, worker failures, and publish safety checks.
- Keep private Trinity runtime state out of the public repository.
- Keep capability-based routing simple, explicit, and backward-compatible.
- Keep PyPI release automation and packaging metadata healthy.
- Ship the optional local orchestrator for primary-work-plus-review flows.

## v0.2: MCP Server

- Add a minimal MCP server for agent tools:
  - `trinity_dispatch_auto`
  - `trinity_status`
  - `trinity_tasks`
  - `trinity_send`
  - `trinity_inbox`
  - `trinity_doctor`
- Keep the CLI as the fallback path.
- Document Codex and Claude Code client setup.
- Document generic CLI agent setup as the default mental model.

## v1.0: Stable Local Agent Bus

- Freeze the CLI command shape.
- Freeze the SQLite schema or add migrations.
- Keep PyPI packaging and release automation stable.
- Add stable documentation for real-world Codex, Claude Code, and generic CLI setups.

## Non-Goals

- No bundled credentials.
- No private model gateway configuration.
- No provider-specific API abstraction in the core package.
- No remote code execution service.
- No dependency on a specific commercial model provider.
