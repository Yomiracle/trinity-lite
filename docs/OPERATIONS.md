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

Future orchestrator work should keep review states explicit:

- `accepted`: primary work and required review passed.
- `review_attention`: review completed and found P0/P1 issues that need action.
- `blocked`: verification could not complete or a required dependency is absent.

`review_attention` is not a stuck task. It is an actionable state that preserves
the reviewer's finding until someone fixes or explicitly accepts the risk.

## Upgrade Rule

Before upgrading a real local runtime:

1. Export or snapshot runtime state outside the public repository.
2. Run doctor and tests on the source tree.
3. Upgrade the tool.
4. Re-run doctor, worker smoke tests, and any gateway or scheduler checks used by
   that deployment.
5. Update public docs or tests only with reusable lessons.

Never commit the snapshot itself.
