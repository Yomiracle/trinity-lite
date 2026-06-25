# Operations Guide

Trinity Lite is public and local-first, but real deployments still need a small
operational baseline. This guide keeps those checks portable and avoids copying
private runtime state into the repository.

## Two Separate Surfaces

Keep these surfaces separate:

| Surface | Belongs in Git | Examples |
|---------|----------------|----------|
| Product source | Yes | Python package, tests, docs, examples |
| Local runtime | No | `.env`, logs, SQLite state, metrics, snapshots, agent credentials |

The public repository should capture reusable checks and lessons. It should not
contain a user's live `~/.trinity-lite`, agent-specific home directories, or
local agent configuration.

## Routine Checks

Run these before publishing a change:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q trinity_lite
trinity-lite doctor --scan-root .
git status --short
```

`doctor --scan-root .` is a publish-readiness check. It looks for files that do
not belong in a public repository, including `.env`, runtime databases, logs,
metrics files, likely secrets, symlinks, and retired runtime artifacts.

## PyPI Publishing

Trinity Lite publishes releases to PyPI. Release artifacts should be built from
the tagged source, checked with `twine check`, and uploaded only after tests pass.

Manual fallback:

```bash
python3 -m build
python3 -m twine check dist/*
python3 -m twine upload dist/*
```

The repository also includes a Trusted Publishing workflow. To use it, configure
the existing PyPI project `trinity-lite` with this GitHub publisher:

| Field | Value |
|-------|-------|
| Owner | `Yomiracle` |
| Repository | `trinity-lite` |
| Workflow | `publish.yml` |
| Environment | `pypi` |

After that, publishing a GitHub Release will build the distribution and publish
it to PyPI without a long-lived API token.

## Runtime Hygiene Profile

For long-running local installations that maintain a metrics log, use the
optional runtime checks:

```bash
trinity-lite doctor --runtime-root ~/.trinity-lite --retired-port 9797
```

The runtime profile checks:

- `metrics.jsonl` exists and is writable under the runtime root.
- Retired runtime artifacts are absent.
- Retired TCP ports are not listening.

This profile is intentionally opt-in. The 30-second demo and public CI do not
require a metrics log.

## Retired Components

Retired components should fail health checks instead of quietly staying alive.
The current public denylist includes:

- `codeproxy.pid`
- `codeproxy.log`
- `trinity_learn.db`
- `trinity_learn.db-wal`
- `trinity_learn.db-shm`

If a deployment retires another process, add its state files to the denylist and
run `trinity-lite doctor --retired-port <port>` for any released port.

## Review Gate Semantics

The orchestrator keeps review and acceptance states explicit:

- `accepted`: primary work, required review, and local verification passed.
- `review_passed`: secondary review passed; `acceptance_status` becomes `accepted` only after local verification also passes.
- `review_attention`: review completed and found P0/P1 issues that need action.
- `verification_failed`: review passed but local verification failed.
- `blocked`: verification could not complete or a required dependency is absent.

`review_attention` is not a stuck task. It is an actionable state that preserves
the reviewer's finding until someone fixes or explicitly accepts the risk.

## Upgrade Rule

To upgrade an existing install:

```bash
python3 -m pip install --upgrade trinity-lite
trinity-lite doctor
```

Trinity Lite follows semantic versioning. Existing SQLite task databases from
the public v0.1+ schema are migrated in place when `TrinityBus` opens them. The
v0.5 acceptance-evidence columns are additive and nullable.

For a real local runtime with long-running workers or state, follow these
additional steps:

1. Stop any running workers or orchestrators.
2. Snapshot your runtime state outside the public repository:
   ```bash
   cp -r ~/.trinity-lite ~/.trinity-lite.bak.$(date +%Y%m%d)
   ```
3. Upgrade the tool:
   ```bash
   python3 -m pip install --upgrade trinity-lite
   ```
4. Verify:
   ```bash
   trinity-lite doctor --runtime-root ~/.trinity-lite
   trinity-lite worker codex --once
   ```
5. If all checks pass, restart your workers and orchestrator.
6. After a few successful runs, remove old backups.

Update public docs or tests only with reusable lessons. Never commit the
snapshot itself.
