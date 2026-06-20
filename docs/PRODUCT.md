# Trinity Lite Product Positioning

Trinity Lite is a local-first multi-agent workflow layer for CLI-based AI coding agents.

It is not a chatbot, not a hosted SaaS, and not a replacement for full agent frameworks. It is a small coordination layer that helps existing CLI agents work through a shared, inspectable task bus.

## Category

```text
Local-first multi-agent workflow infrastructure
```

Trinity Lite belongs to the agent orchestration and developer tooling space. Its closest neighbors are multi-agent frameworks and workflow engines, but it is lighter and more CLI-native:

- Full agent frameworks create and run agents inside their own abstractions.
- Trinity Lite coordinates existing agent CLIs through routing, SQLite state, and workers.

## Target Users

| User | Need |
|------|------|
| AI developers | Prototype multi-agent coding workflows without building infrastructure first |
| Agent workflow builders | Test routing, review handoffs, task persistence, and worker execution |
| Indie hackers and small teams | Coordinate local agent tools without deploying a server |
| Technical creators and educators | Demonstrate real multi-agent flow with commands viewers can reproduce |

## Problem

AI coding agents are strong individually, but collaboration between them is often manual:

- copy output from one tool into another;
- decide handoffs by memory;
- lose intermediate task state;
- forget which agent did what;
- rerun work because failures are not persisted;
- struggle to demonstrate a full workflow when real agent CLIs are not installed yet.

This makes multi-agent work hard to inspect, teach, repeat, and improve.

## Solution

Trinity Lite turns agent collaboration into a local workflow:

```text
task -> router -> SQLite bus -> worker -> agent adapter -> result
```

The key product idea is simple: agents do not need to live in the same framework or use the same model API to cooperate. They only need a shared task bus, clear routing, durable state, and a small capability contract.

## Efficiency Gains

Trinity Lite does not claim that every task becomes 10x faster. Its value is reducing coordination overhead:

- less copy-paste between agents;
- fewer lost task states;
- faster review handoffs;
- easier replay and inspection;
- clearer separation between primary work, review, and acceptance;
- faster onboarding through mock agents before real CLI setup.

For one-off tasks, the gain is small. For repeated implementation, review, and verification loops, the gain compounds because the workflow becomes consistent.

## Innovation

Trinity Lite is different from many agent frameworks because it starts from the tools developers already use:

```text
Codex / Claude Code / Hermes / Qwen / Gemini / Aider / custom CLI
        |
        v
shared local bus
```

Instead of requiring users to rebuild agents inside a new framework, it wraps CLI agents with a local coordination layer. This makes it easier to adopt incrementally:

1. run mock agents;
2. configure one real CLI agent;
3. declare capabilities for name-agnostic routing;
4. add MCP server;
5. add orchestrator.

## Technical Pillars

- **SQLite task bus**: durable local state without running a separate server.
- **Router**: explicit-agent, pattern, and capability routing.
- **Worker model**: simple polling execution for queued tasks.
- **Agent adapters**: mock and command modes.
- **Capability metadata**: roles, capabilities, and priority for arbitrary CLI agents.
- **Shell-safe execution**: JSON-array commands with `shell=False`.
- **Guardrails**: self-delegation block, depth limit, allowed cwd roots, public tree scan.
- **Doctor checks**: local health and publish-readiness checks.
- **CI**: tests and doctor run on GitHub Actions.

## Current Scope

Trinity Lite v0.1 is a public local MVP:

- CLI first;
- mock-agent demo first;
- no runtime dependencies;
- no MCP server yet;
- no orchestrator yet;
- not a production distributed execution engine.

## Roadmap Narrative

Trinity Lite grows in layers:

```text
v0.1 local bus + CLI + mock/command workers + capability routing
v0.2 MCP server for direct agent tool calls
v0.3 orchestrator for primary work -> review -> verification
v1.0 stable CLI/schema/package
```

That staged design keeps the first version understandable while leaving a clear path toward a stronger multi-agent system.

## 中文定位

Trinity Lite 是一个本地优先的多 Agent 工作流基础设施。它面向 AI 开发者、agent 工作流构建者、独立开发者、小团队和技术内容创作者，解决多个 CLI 型 AI 编程工具之间缺少任务路由、状态持久化、二审交接和可复现演示的问题。

它的创新点不是重新发明一个 agent 框架，而是给 Codex、Claude Code、Hermes、Qwen、Gemini、Aider 或任意 CLI agent 加一个共享任务总线和能力路由层，让已有工具可以用工程化方式协作。
