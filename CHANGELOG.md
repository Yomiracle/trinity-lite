# Changelog

All notable changes to Trinity Lite are documented here.

## v0.1.1 - 2026-06-21

### Added

- Optional doctor runtime hygiene checks for writable `metrics.jsonl`, retired runtime artifacts, and retired TCP ports.
- Operations guide covering public source vs local runtime boundaries, review attention semantics, and upgrade hygiene.
- Agent metadata for roles, capabilities, and priority.
- Capability-based routing with `requires`, `prefer`, and `avoid` route fields.
- Route results now include `selection` to distinguish explicit-agent and capability-match routing while preserving the existing `source` field.
- Generic CLI agent examples for Qwen, Gemini, Aider, and custom reviewers.
- Agent capabilities documentation and an ADR for capability routing.
- Doctor schema validation for agent and route config files.
- Optional `orchestrate` command for a local primary-task plus review flow.

### Hardened

- Public tree scan now blocks retired runtime artifacts such as `codeproxy.pid` and `trinity_learn.db-wal`.
- Codex, Claude Code, and Hermes are documented as presets rather than requirements.
- Doctor config validation reports structured issue lists in `detail` when route or agent schema checks fail.

### Known Limits

- Not published to PyPI yet.
- The orchestrator is a minimal local review flow; persistent review gates and retries are planned for v0.3.

## v0.1.0 - 2026-06-19

Initial public release.

### Added

- SQLite task bus with task and message storage.
- CLI commands for routing, dispatch, worker execution, task status, messages, inbox, and doctor checks.
- Mock agent adapters for `codex`, `claude_code`, and `hermes`.
- Command adapter support with JSON-array commands and `shell=False`.
- Default routing for implementation, testing, project audit, architecture, review, orchestration, and acceptance tasks.
- Safety checks for self-delegation, delegation depth, allowed working directories, private files, likely secrets, logs, databases, and symlinks.
- English and Chinese README files.
- Architecture, security, and tutorial documentation.
- GitHub Actions test workflow.

### Hardened

- Public tree scan does not follow directory symlinks.
- Worker does not swallow `KeyboardInterrupt`, `SystemExit`, or `MemoryError`.
- Chinese secondary-review routing recognizes short `二审` and `复核` prompts.
- Tests cover rollback behavior, command adapter failures, route errors, symlink scans, private-file scans, and mock worker completion.

### Known Limits

- No MCP server yet.
- No orchestrator yet.
- Not published to PyPI yet.
- Real agent commands require local user configuration.
