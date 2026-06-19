---
name: Bug report
about: Report a reproducible Trinity Lite problem
title: "[Bug]: "
labels: bug
assignees: ""
---

## What happened?

Describe the problem clearly.

## Steps to reproduce

```bash

```

## Expected behavior

What did you expect to happen?

## Environment

- OS:
- Python version:
- Trinity Lite version or commit:
- Agent config: mock / Codex / Claude Code / other

## Verification

Please run:

```bash
python3 -m unittest discover -s tests -v
python3 -m trinity_lite doctor --scan-root .
```

Paste the relevant output here. Remove secrets before posting.
