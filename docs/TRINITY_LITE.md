# Trinity Lite Tutorial

## 1. Install

```bash
python3 -m pip install trinity-lite
```

For local source development, clone the repository and run
`python3 -m pip install -e .`.

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

## 5. Run a Review Flow

The optional orchestrator dispatches the primary task, runs the selected worker
once, and runs a required review once:

```bash
trinity-lite orchestrate "implement a parser"
```

It uses the same routes and agent configs as `dispatch-auto`.

## 6. Switch to Real Commands

```bash
cp examples/agents.command.example.json agents.local.json
```

Edit `agents.local.json` for your local tools, then pass it to workers:

```bash
trinity-lite worker codex --once --agents agents.local.json
```

Keep local command config out of git.

## 7. Route by Capabilities

For arbitrary CLI agents, copy the generic capability examples:

```bash
cp examples/agents.generic.example.json agents.local.json
cp examples/routes.capabilities.example.json routes.local.json
```

Then dispatch with both files:

```bash
trinity-lite dispatch-auto "fix the parser bug" \
  --agents agents.local.json \
  --routes routes.local.json
```

Or run a full primary-plus-review flow:

```bash
trinity-lite orchestrate "fix the parser bug" \
  --agents agents.local.json \
  --routes routes.local.json
```

Trinity Lite will select an agent whose declared capabilities satisfy the route.

## 8. Optional Runtime Hygiene

For a long-running local install, keep runtime files outside the repository and
check them explicitly:

```bash
trinity-lite doctor --runtime-root ~/.trinity-lite --retired-port 9797
```

Skip this step for the default mock demo. It is for installations that maintain a
metrics log and retire local helper services over time.
