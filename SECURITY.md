# Security Policy

Trinity Lite is a local development tool. It should never contain private keys, OAuth tokens, local task databases, logs, shell history, model gateway configuration, or machine-specific paths.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x | Yes |

## Reporting a Vulnerability

Do not open a public issue that includes credentials, tokens, private prompts, or machine-specific files.

For public hardening issues without sensitive data, open a GitHub issue with reproduction steps.

For sensitive leaks, contact the maintainer privately before posting details.

## Local Checks

Run before publishing changes:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q trinity_lite
python3 -m trinity_lite doctor --scan-root .
```

For a long-running local runtime, add:

```bash
python3 -m trinity_lite doctor --runtime-root ~/.trinity-lite --retired-port 9797
```

See [docs/SECURITY.md](docs/SECURITY.md) for implementation details.
