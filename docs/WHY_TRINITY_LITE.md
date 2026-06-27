# Why Trinity Lite?

Most agent frameworks start by asking you to build agents inside their runtime.
Trinity Lite starts from a different reality: you already have CLI agents on
your machine, and you need them to hand work to each other with durable state.

## The Job

Trinity Lite coordinates local CLI agents through a SQLite task bus:

```text
prompt -> route -> queued task -> worker -> CLI command -> result -> review -> verification -> acceptance evidence
```

It is deliberately small:

- no server required;
- no model-provider abstraction in the core package;
- no credentials in project config;
- no shell string execution for agent commands;
- no need to rewrite existing CLI agents as framework objects.

## Comparison

| Project | Primary job | Best for | Trinity Lite difference |
|---------|-------------|----------|--------------------------|
| LangGraph | Build resilient graph-based agents | Stateful agent applications, graph workflows, production agent control flow | Trinity Lite coordinates already-installed CLI agents instead of defining agents inside a graph runtime. |
| CrewAI | Build role-based multi-agent crews | Autonomous role-play style teams and task delegation | Trinity Lite focuses on local CLI handoff, SQLite audit state, and explicit acceptance evidence. |
| AutoGen | Build programmable multi-agent conversations | Research and application frameworks for agentic workflows | Trinity Lite is a smaller operational bus for command-line tools, not a general conversation framework. |
| OpenHands | Run an AI software engineering agent environment | End-to-end autonomous coding in a managed workspace | Trinity Lite does not replace a coding agent; it lets multiple local agents coordinate and review each other. |

## When Trinity Lite Fits

Use Trinity Lite when you want to:

- connect Codex, Claude Code, Hermes, or custom CLI tools on one machine;
- keep every task, result, error, and review link in local SQLite;
- run a mock demo before configuring real agents;
- route by capability instead of hardcoded agent names;
- prove that work was reviewed and verified before acceptance;
- expose the same bus to MCP clients.

## When It Does Not Fit

Do not start with Trinity Lite if you need:

- a hosted cloud agent platform;
- a full graph runtime with complex branching and streaming state;
- managed browsers, sandboxes, and remote execution;
- a provider-specific model API wrapper;
- a UI-first product.

Those can be layered around the bus later, but they are not the core package.

## The Position

Trinity Lite sits between single-agent CLIs and full agent frameworks:

```text
Codex / Claude Code / Hermes / custom CLI
        |
        v
Trinity Lite: local routing, task bus, review, verification, acceptance evidence
        |
        v
Optional layers: MCP clients, dashboards, docs sites, CI checks
```

That narrow scope is the product: a developer can install it, run the mock flow,
then wire in one real CLI at a time.
