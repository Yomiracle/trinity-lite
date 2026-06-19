# Changelog

All notable changes to Trinity Lite are documented here.

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
