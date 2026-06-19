## Summary

What changed?

## Verification

Run before submitting:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q trinity_lite
python3 -m trinity_lite doctor --scan-root .
```

## Safety Checklist

- [ ] No `.env`, API keys, OAuth tokens, local databases, logs, or private paths.
- [ ] Agent commands remain JSON arrays and use `shell=False`.
- [ ] Routing, bus, worker, or guard changes include focused tests.
- [ ] Docs are updated when CLI behavior changes.
