# Trinity Lite

[![Tests](https://github.com/Yomiracle/trinity-lite/actions/workflows/test.yml/badge.svg)](https://github.com/Yomiracle/trinity-lite/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/trinity-lite.svg)](https://pypi.org/project/trinity-lite/)
[![Yomiracle/trinity-lite MCP server](https://glama.ai/mcp/servers/Yomiracle/trinity-lite/badges/score.svg)](https://glama.ai/mcp/servers/Yomiracle/trinity-lite/score)

**Local-first multi-agent orchestration for CLI AI agents.**

[中文 README](README_zh.md) · [Docs](docs/index.md) · [Why Trinity Lite?](docs/WHY_TRINITY_LITE.md) · [Recipes](docs/recipes/generic-cli.md)

## The problem

You already use Claude Code. Maybe you just installed Codex. You want them to collaborate, review each other, and leave an audit trail you can inspect later. But there is no built-in way to route tasks between local CLI agents, remember who did what, or decide when work is actually accepted. Trinity Lite is the missing layer.

## What it does

- **Route by capability, not name.** You describe the task. The router matches it to the right agent — no hardcoded agent names, no fragile dispatch logic. *"Implement a rate limiter" lands on the agent you tagged `implement`. "Review the auth module" goes to the agent tagged `review`.*
- **Give every agent a pull queue.** Workers read pending tasks from the shared bus, execute them via CLI, and write results back. Each agent polls on its own schedule. You never copy-paste an output between terminals again.
- **Remember every decision.** Every task, status change, result, error, and inter-agent message lands in a local SQLite database. Query who did what, when, and what happened — without setting up a logging pipeline.
- **Review, verify, then accept.** `orchestrate` runs primary work, routes the required review, runs local verification, and writes acceptance evidence back to SQLite.
- **Block footguns before they fire.** Self-delegation loops are rejected. Delegation depth has a hard cap. Working directories must be in the allowlist. You ship features, not incident reports.

## Quick start

30 seconds, no agents required:

```bash
pip install trinity-lite
trinity-lite doctor
trinity-lite orchestrate "implement a hello-world function"
```

Mock agents are built in. You see the full route → work → review → verify → accept cycle before you wire up anything real.

## Not another framework

Trinity Lite doesn't build agents. It connects the agents you already have.

LangGraph and CrewAI give you primitives for building agents from scratch — graph definitions, role abstractions, tool wrappers. Trinity Lite starts from the opposite end: Claude Code is running in one terminal, Codex is running in another, and they need routing, review handoff, durable state, and an acceptance trail. No SDK to learn. No new agent abstraction. Just a local workflow layer for the CLIs you already use.

## Who this is for

| You are... | Trinity Lite helps you... |
|------------|---------------------------|
| Copy-pasting prompts and outputs between two agent terminals all day | Run one orchestrated flow and inspect the evidence afterward |
| Prototyping a multi-agent pipeline before committing infrastructure | Run the full flow with mock agents — no API keys, no provisioning |
| Running everything on a single machine with zero server setup | Keep your state in SQLite, your runtime in stdlib, your daemon count at zero |
| Showing a colleague how multi-agent collaboration works | `pip install` → `trinity-lite orchestrate` → they see it run. No explanation needed. |

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
- **130+ tests guarding the surface area.** Mock workflows, safety checks, routing, persistence, MCP, and acceptance gates — all covered.
- **Smart model selection.** Automatically picks the right LLM for each task. Simple CRUD → cheap model. Architecture design → strong reasoning model. Define your own model pool with tiers and strength tags.

## Install

```bash
pip install trinity-lite
```

Python 3.10+. Zero core runtime dependencies. Standard library only unless an optional extra is installed.

### Optional extras

```bash
pip install "trinity-lite[yaml]"          # YAML pipeline files
pip install "trinity-lite[mcp]"           # MCP server — 12 tools + 3 resources
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

**12 tools:**

| Tool | What it does |
|------|--------------|
| `trinity_dispatch` | Dispatch a task to a specific agent |
| `trinity_dispatch_auto` | Dispatch and let the capability router pick the agent |
| `trinity_orchestrate` | Run the default review flow or a YAML pipeline |
| `trinity_status` | Get the state and result of any task by ID |
| `trinity_tasks` | List recent tasks, filterable by agent |
| `trinity_worker` | Run one worker cycle for an agent |
| `trinity_worker_daemon` | Start, stop, or inspect a daemon worker |
| `trinity_doctor` | Run health and diagnostic checks |
| `trinity_inbox` | Read durable messages for an agent |
| `trinity_send` | Send a message from one agent to another |
| `trinity_skill_search` | Search agent-skill-system for relevant skills |
| `trinity_skill_load` | Load the full content of a named skill |

**3 resources:** `trinity://health`, `trinity://tasks/recent`, `trinity://tasks/{task_id}`

## Acceptance Evidence

`trinity-lite orchestrate` now writes a local acceptance trail to the task row:

- `route_json`: JSON-encoded route decision used for primary dispatch
- `review_task_id` and `parent_task_id`: links between primary work and secondary review
- `gate_status`: `primary_pending`, `review_pending`, `review_passed`, `review_attention`, `verification_failed`, or `accepted`
- `verification_json`: JSON-encoded local verifier result, defaulting to `trinity-lite doctor`
- `acceptance_status`, `acceptance_reason`, and `accepted_at`

If the reviewer reports P0/P1 findings, the flow stops at `review_attention`. If local verification fails, it stops at `verification_failed`. `accepted_at` is written only after the required review and verification pass.

## Model Selector (NEW in v0.4.0)

Auto-pick the best LLM for each task based on complexity:

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
print(result["model"])  # → gpt-5.5
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
- [Documentation](docs/)
- [Why Trinity Lite?](docs/WHY_TRINITY_LITE.md)
- [Recipes](docs/recipes/generic-cli.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Real agent setup](docs/REAL_AGENTS.md)

## License

MIT
