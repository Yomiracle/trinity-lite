# Security Notes

Trinity Lite is designed as a public, sanitized MVP. Treat it as a local development tool unless you harden it further.

## Never Commit

- `.env`
- API keys, OAuth tokens, cookies, passwords
- private task databases
- personal memories or shell history
- machine-specific process reports
- private model gateway configuration
- retired runtime files such as `codeproxy.pid` or `trinity_learn.db-wal`

## Built-In Safety

- Tasks cannot be delegated from an agent to itself.
- Delegation depth is capped at `2`.
- Task working directories must be inside allowed roots.
- Agent commands are JSON arrays and run with `shell=False`.
- `doctor --scan-root .` checks for common private files, retired runtime artifacts, and likely secrets.
- `doctor --runtime-root <dir> --retired-port <port>` can check a long-running local runtime without committing it.

## Allowed Roots

By default, task `cwd` must be inside `$HOME`. Override this only when needed:

```bash
export TRINITY_LITE_ALLOWED_ROOTS="$HOME/projects:/tmp/demo"
```

## Public Release Checklist

Run before publishing:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q trinity_lite
trinity-lite doctor --scan-root .
git status --short
```

Then manually inspect:

- No `.env`
- No `.db`, `.sqlite`, `.log`
- No `codeproxy.pid` or `trinity_learn.db*`
- No real API keys
- No hardcoded user home path
- No private task prompt or result history
