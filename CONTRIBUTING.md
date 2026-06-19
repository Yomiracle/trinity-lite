# Contributing

Thanks for considering a contribution. Trinity Lite is a small local tool, so changes should keep it easy to understand and safe to publish.

## Development Setup

```bash
git clone https://github.com/Yomiracle/trinity-lite.git
cd trinity-lite
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
python3 -m trinity_lite doctor --scan-root .
```

## Before Opening a Pull Request

Run:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q trinity_lite
python3 -m trinity_lite doctor --scan-root .
git status --short
```

The working tree should not contain runtime files such as `.env`, `.db`, `.sqlite`, `.log`, or private local command configs.

## Design Rules

- Keep runtime dependencies at zero unless there is a strong reason to add one.
- Keep agent commands as JSON arrays and execute them with `shell=False`.
- Do not add private machine paths, credentials, prompts, logs, or local databases.
- Add focused tests for routing, bus invariants, worker failure paths, and safety checks.
- Prefer small changes that preserve the current CLI.

## Security

Do not report secrets or private credentials in public issues. If you find a sensitive leak, contact the maintainer privately first.

See [docs/SECURITY.md](docs/SECURITY.md) for the public-release safety model.
