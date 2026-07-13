# Trinity Lite

[![Tests](https://github.com/Yomiracle/trinity-lite/actions/workflows/test.yml/badge.svg)](https://github.com/Yomiracle/trinity-lite/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/Yomiracle/trinity-lite)](https://github.com/Yomiracle/trinity-lite/releases)
[![PyPI](https://img.shields.io/pypi/v/trinity-lite.svg)](https://pypi.org/project/trinity-lite/)
[![Yomiracle/trinity-lite MCP server](https://glama.ai/mcp/servers/Yomiracle/trinity-lite/badges/score.svg)](https://glama.ai/mcp/servers/Yomiracle/trinity-lite/score)

**Local AgentOps for cross-vendor CLI coding agents. Route work, recover state, and accept only with evidence.**

Trinity Lite is a local control plane for Codex, Claude Code, Hermes, and custom
CLI agents. It connects the tools you already use; it does not ask you to
rebuild them inside another framework.

[中文 README](README_zh.md) · [Docs](docs/index.md) · [Why Trinity Lite?](docs/WHY_TRINITY_LITE.md) · [Recipes](docs/recipes/generic-cli.md)

## The problem

You already use more than one capable coding agent. The hard part is no longer
starting another agent; it is preserving task truth across tools, recovering
after a client disconnects, preventing duplicate work, and deciding when a
result is actually accepted. Trinity Lite is that local operations layer.

## What it does

- **Route by capability, not name.** You describe the task. The router matches it to the right agent — no hardcoded agent names, no fragile dispatch logic. *"Implement a rate limiter" lands on the agent you tagged `implement`. "Review the auth module" goes to the agent tagged `review`.*
- **Give every agent a pull queue.** Workers read pending tasks from the shared bus, execute them via CLI, and write results back. Each agent polls on its own schedule. You never copy-paste an output between terminals again.
- **Remember every decision.** Every task, status change, result, error, and inter-agent message lands in a local SQLite database. Query who did what, when, and what happened — without setting up a logging pipeline.
- **Review, verify, then accept.** `orchestrate` runs primary work, routes the required review, runs local verification, and writes acceptance evidence back to SQLite.
- **Block footguns before they fire.** Self-routes become explicit local-work decisions instead of creating loops. Delegation depth has a hard cap. Working directories must be in the allowlist.

## Quick start

30 seconds, no agents required:

```bash
pip install trinity-lite
trinity-lite doctor
trinity-lite orchestrate "implement a hello-world function"
```

Mock agents are built in. You see the full route → work → review → verify → accept cycle before you wire up anything real.

## Not another framework

Trinity Lite does not build agents. It operates the agents you already have.

LangGraph and CrewAI give you primitives for building agents from scratch — graph definitions, role abstractions, and tool wrappers. Trinity Lite starts from the opposite end: Claude Code is running in one terminal, Codex is running in another, and their work needs reliable handoff, recovery, independent review, and an acceptance trail. No new agent abstraction. Just local AgentOps for the CLIs you already use.

## Who this is for

| You are... | Trinity Lite helps you... |
|------------|---------------------------|
| An advanced solo developer using two or more agent CLIs | Replace manual terminal handoffs with one durable workflow and evidence trail |
| A small AI-native engineering team | Separate implementation, review, verification, and acceptance without deploying a control server |
| A local-first or privacy-sensitive developer | Keep task state in an inspectable SQLite database on your machine |
| An agent-tool integrator | Connect existing CLIs through a neutral bus and MCP surface |

## Features

- **Route by capability.** Tag agents with `implement`, `review`, `audit` — the router matches tasks to the agent that can do them. No agent names in your dispatch logic.
- **Dispatch directly when you need control.** Bypass the router and send a task straight to `claude_code` or `codex`. Best of both worlds.
- **Persist everything in SQLite.** Tasks, statuses, results, errors, and messages in one local file. Query it with `sqlite3` or any tool that speaks SQL.
- **Accept with evidence, not vibes.** The review flow records route decisions, review links, verification results, acceptance reasons, and `accepted_at` in SQLite. A reviewed task is accepted only after the local verifier passes.
- **Isolate agent code edits with git worktrees.** Released as a v0.6 preview: `trinity-lite worktree` creates managed branches and checkouts, records the base commit, and returns diff evidence without touching your main checkout.
- **Run CLI workers on demand.** `trinity-lite worker codex --once` pulls one queued task, executes the agent's command, and writes the result. Run it in a loop, in cron, or by hand.
- **Execute safely, no shell injection.** Agent commands are JSON arrays run with `shell=False`. No string interpolation into a shell. No surprises.
- **Test with mock agents.** Mock agents simulate the full cycle without real CLIs. Prototype routing, persistence, and review handoffs first. Wire up real agents later.
- **Guard against runaway delegation.** Self-delegation is blocked. Delegation depth is capped. Working directories are allowlisted. Safe by default.
- **Check health in one pass.** `trinity-lite doctor` verifies Python, SQLite, route config, agent config, and publish readiness.
- **Zero core dependencies.** The default runtime is Python standard library only. YAML pipelines are available through an optional extra.
- **150+ tests guarding the surface area.** Mock workflows, safety checks, routing, persistence, MCP, and acceptance gates — all covered.
- **Optional model selection hints.** Select from your declared model pool with transparent task, tier, and capability rules; no claim of a universal best or cheapest model.

## Install

```bash
pip install trinity-lite
```

Python 3.10+. Zero core runtime dependencies. Standard library only unless an optional extra is installed.

### Optional extras

```bash
pip install "trinity-lite[yaml]"          # YAML pipeline files
pip install "trinity-lite[mcp]"           # MCP server — 13 tools + 3 resources
pip install "trinity-lite[agent-skill]"   # agent-skill-system integration
```

## Workflow example

Route primary work → run the worker → run the reviewer → verify → accept. One command, one audit trail.

```bash
trinity-lite orchestrate "implement a rate limiter for the API"
```

The primary task row records `route_json`, `review_task_id`, `verification_json`, `acceptance_status`, `acceptance_reason`, and `accepted_at`.

Ready for real CLIs when you are:

```bash
cp examples/agents.command.example.json agents.local.json
trinity-lite orchestrate "implement a rate limiter for the API" --agents agents.local.json
```

Prefer manual control? Use the lower-level bus commands:

```bash
trinity-lite dispatch-auto "implement a parser"
trinity-lite worker codex --once
trinity-lite tasks
```

## Worktree Preview

This is a v0.6 preview. It manages isolated worktree lifecycle and diff
evidence while keeping automatic merge-back out of scope.

Create an isolated checkout for an agent:

```bash
trinity-lite worktree create "fix parser bug" --repo . --agent codex
trinity-lite worktree list
trinity-lite worktree diff <task_id>
trinity-lite worktree cleanup <task_id>
```

Worktree preview records branch, base commit, path, agent id, task id, and diff
evidence. It does not merge branches or delete branches by default. See
[Worktree Parallelism Preview](docs/WORKTREE_PARALLELISM.md).

## MCP server

Turn the task bus into an MCP server. Let any MCP client dispatch, query, and route tasks.

```bash
pip install trinity-lite[mcp]
trinity-lite mcp serve
```

**13 tools:**

| Tool | What it does |
|------|--------------|
| `trinity_dispatch` | Dispatch a task to a specific agent |
| `trinity_dispatch_auto` | Dispatch and let the capability router pick the agent |
| `trinity_orchestrate` | Run the default review flow or a YAML pipeline |
| `trinity_status` | Get the state and result of any task by ID |
| `trinity_latest` | Recover the latest task submitted by an agent |
| `trinity_tasks` | List recent tasks, filterable by agent |
| `trinity_worker` | Run one worker cycle for an agent |
| `trinity_worker_daemon` | Start, stop, or inspect a daemon worker |
| `trinity_doctor` | Run health and diagnostic checks |
| `trinity_inbox` | Read durable messages for an agent |
| `trinity_send` | Send a message from one agent to another |
| `trinity_skill_search` | Search agent-skill-system for relevant skills |
| `trinity_skill_load` | Load the full content of a named skill |

**3 resources:** `trinity://health`, `trinity://tasks/recent`, `trinity://tasks/{task_id}`

If an MCP client disconnects or times out before it displays the task id, call
`trinity_latest` for the source agent, then call `trinity_status` with the
returned primary task id. By default `trinity_latest` skips secondary review
children so recovery lands on the user-facing task.

## Acceptance Evidence

`trinity-lite orchestrate` now writes a local acceptance trail to the task row:

- `route_json`: JSON-encoded route decision used for primary dispatch
- `review_task_id` and `parent_task_id`: links between primary work and secondary review
- `gate_status`: `primary_pending`, `review_pending`, `review_passed`, `review_attention`, `verification_failed`, or `accepted`
- `verification_json`: JSON-encoded local verifier result, defaulting to `trinity-lite doctor`
- `acceptance_status`, `acceptance_reason`, and `accepted_at`

If the reviewer reports P0/P1 findings, the flow stops at `review_attention`. If local verification fails, it stops at `verification_failed`. `accepted_at` is written only after the required review and verification pass.

## Optional Model Selector

Select from a model pool you control using task complexity and declared
capabilities. This is a transparent routing helper, not a universal cost
optimizer:

```bash
# Auto-detect your available models (zero config)
trinity-lite detect-models

# Or set up interactively (no JSON needed)
trinity-lite setup-models
```

**How it works**: Define your model pool with tiers (`budget` / `standard` / `premium`) and strength tags. The selector picks automatically:

| Task | → Tier | → Model |
|---|---|---|
| "Fix typo in README" | budget | cheap model |
| "Add search endpoint" | budget | cheap model |
| "Refactor auth module" | standard | mid-tier |
| "Design microservice architecture" | premium | strongest |

**Manual call** (API usage):

```python
from trinity_lite.model_selector import select_model

result = select_model("Design a rate limiter", task_type="architecture_design")
print(result["model"])  # → a premium model from your configured pool
print(result["reason"]) # → hard_signal:architecture
```

**Custom pool** — create `~/.trinity/model_pool.json`:

```json
{
  "your-cheap-model": {"tier": "budget", "strengths": ["coding"], "api_type": "anthropic"},
  "your-strong-model": {"tier": "premium", "strengths": ["reasoning", "architecture"], "api_type": "openai"}
}
```

Works with 1 model, 2 models, or 10 models. No agent names hardcoded.

## Links

- [PyPI](https://pypi.org/project/trinity-lite/)
- [Documentation](https://yomiracle.github.io/trinity-lite/)
- [Why Trinity Lite?](docs/WHY_TRINITY_LITE.md)
- [Recipes](docs/recipes/generic-cli.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Real agent setup](docs/REAL_AGENTS.md)

## License

MIT
