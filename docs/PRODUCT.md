# Trinity Lite Product Positioning

Trinity Lite is a local AgentOps control plane for cross-vendor CLI coding
agents. It connects tools developers already use so work can be routed,
recovered, independently reviewed, locally verified, and accepted with durable
evidence.

It is not a chatbot, a hosted SaaS, or another framework for defining agents.
It is the operations and acceptance layer around existing agent CLIs.

## Category

```text
Local AgentOps for CLI agents
```

The short product line is:

> The local control plane for cross-vendor coding agents: route work, recover
> state, and accept only with evidence.

## Primary Users

| User | Need |
|------|------|
| Advanced solo developers using two or more agent CLIs | Stop copying work between terminals and recover long-running task state |
| Small AI-native engineering teams | Separate implementation, review, verification, and acceptance without deploying a control server |
| Local-first or privacy-sensitive developers | Keep task state and evidence in an inspectable local SQLite database |
| Agent-tool integrators | Coordinate existing CLIs through a neutral task bus and MCP surface |

Technical educators and workflow researchers can use the mock flow, but they
are a secondary audience rather than the primary product buyer.

## The Job to Be Done

> I already have capable coding agents. Make their handoffs reliable, preserve
> the truth when a client disconnects, and do not call work complete until a
> separate review and local verification have produced evidence.

Without an operations layer, multi-agent CLI work often means:

- copying prompts and results between terminals;
- losing task ids or results when a client disconnects;
- dispatching the same work twice because status is unclear;
- letting the implementing agent declare its own work complete;
- relying on chat history instead of an inspectable acceptance record.

## Product Workflow

```text
task -> route -> durable queue -> worker -> result
     -> independent review -> local verification -> acceptance evidence
```

The core contract is not merely "agents can talk." It is that each transition
has durable state and that acceptance is backed by recorded evidence.

## Competitive Wedge

- **Existing-agent adoption:** connect Codex, Claude Code, Hermes, or a custom
  command adapter without rebuilding them as framework objects.
- **Durable operational truth:** persist tasks, status, results, errors,
  messages, review links, and acceptance state in SQLite.
- **Failure recovery:** recover the latest submitted task after an interrupted
  MCP response instead of creating a duplicate.
- **Separation of duties:** route implementation and review to different roles
  and run a local verifier before acceptance.
- **Local-first inspectability:** no hosted control plane is required for the
  core workflow.

Parallel agents, worktrees, subagents, cross-provider access, and model
selection are useful capabilities, but they are not durable differentiators on
their own. Trinity Lite should compete on reliable handoff, recovery, and
evidence rather than the number of agents it can launch.

## Value

Trinity Lite does not claim that every task becomes 10x faster. Its value
compounds across repeated implementation, review, and verification loops:

- less terminal-to-terminal coordination;
- fewer lost or duplicate tasks;
- faster recovery after client failures;
- independent review before acceptance;
- a portable record of why work passed or stopped;
- incremental adoption through mock agents and one real adapter at a time.

## Technical Pillars

- SQLite task and message bus.
- Capability and task-type routing.
- Mock and shell-safe JSON-array command adapters.
- MCP tools plus a CLI fallback.
- Review, verification, and acceptance evidence.
- Worktree isolation preview and diff evidence.
- Guardrails for self-routes, delegation depth, allowed roots, and public tree
  scanning.
- Doctor checks and release CI.

## Current Scope

Trinity Lite v0.6.1 is a single-machine, local-first package with a CLI, MCP
server, mock and command workers, YAML pipelines, optional model selection,
worktree preview, task recovery, and an acceptance gate.

It is not yet:

- a distributed execution engine;
- a hosted collaboration platform;
- an enterprise RBAC or compliance product;
- a managed browser or sandbox service;
- a universal model-cost optimizer;
- a UI-first product.

Those boundaries should remain explicit until the corresponding capability is
implemented and verified.

## Product Priorities

1. Exportable proof bundles for route, result, review, verification, and
   acceptance.
2. Five-minute onboarding and local CLI auto-detection.
3. A compact task, review, test, failure, latency, and cost console.
4. Explicit cancellation, retry, and resumable checkpoints.
5. A stable adapter contract before team or remote-worker features.

## 中文定位

Trinity Lite 是面向跨厂商 CLI 编程 Agent 的本地 AgentOps 控制平面。它不替
用户重新创建 Agent，而是连接已经在使用的 Codex、Claude Code、Hermes 或
自定义 CLI，让任务可路由、状态可恢复、结果可二审、变更可验证，并且只有在
留下持久验收证据后才算完成。

它的主要用户是已经同时使用两个以上 AI 编程工具的高级个人开发者和小型
AI 工程团队。它的竞争力不是“能同时运行多个 Agent”，而是跨厂商、本地优先、
持久状态、失败恢复、职责分离和证据化验收。
