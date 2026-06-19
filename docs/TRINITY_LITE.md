# Trinity Lite Tutorial

## 1. Install

```bash
python3 -m pip install -e .
```

## 2. Dispatch a Task

```bash
trinity-lite dispatch-auto "implement a parser"
```

This creates a queued task in the local SQLite bus.

## 3. Run a Worker

```bash
trinity-lite worker codex --once
```

The default Codex adapter is a mock adapter, so it returns a deterministic result.

## 4. Read Status

```bash
trinity-lite tasks
trinity-lite status <task_id>
```

## 5. Switch to Real Commands

```bash
cp examples/agents.command.example.json agents.local.json
```

Edit `agents.local.json` for your local tools, then pass it to workers:

```bash
trinity-lite worker codex --once --agents agents.local.json
```

Keep local command config out of git.
