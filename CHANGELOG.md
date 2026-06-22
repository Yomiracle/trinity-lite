# Changelog

All notable changes to Trinity Lite are documented here.

## v0.1.2 - 2026-06-22

### P1 (Critical)

- **orchestrator**: fix `run_once` to process the exact submitted task by passing `task_id`, preventing the orchestrator from picking the wrong queued task.

### P2 (High)

- **adapters**: replace sequential `.replace()` calls with regex-based single-pass placeholder substitution to prevent corrupted prompts.
- **cli**: remove dead `--db`/`--routes`/`--agents` from the main parser (never parsed due to required subparsers).
- **ci**: add Python 3.13 to the test matrix.
- **bus**: add `AND status = 'running'` guard to `finish_worker` UPDATE; raise `ValueError` if rowcount is 0.
- **worker**: import `traceback` and include `traceback.format_exc()` in error strings.
- **doctor**: fix `_is_writable` to use `os.access()` instead of opening the file.

### P3 (Medium)

- **packaging**: add `trinity_lite/py.typed` marker for PEP 561 compliance.
- **gitignore**: add `*.db-shm` and `*.db-wal` patterns.
- **bus**: rename `utc_now()` to `utc_now_iso()` with docstring.
- **ci**: add `timeout-minutes: 10` to the test job.
- **cli**: wrap `__main__.py` in `if __name__ == "__main__":` guard.
- **docs**: update README and ROADMAP to reflect that orchestrator already ships in v0.1.x.

## v0.1.1 - 2026-06-21

### Published

- Published to PyPI as `trinity-lite==0.1.1`.
- Added GitHub Actions Trusted Publishing workflow for future PyPI releases.
- Updated package license metadata to SPDX-style `MIT`.

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
- Real agent commands require local user configuration.
