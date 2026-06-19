# Trinity Lite

[![Tests](https://github.com/Yomiracle/trinity-lite/actions/workflows/test.yml/badge.svg)](https://github.com/Yomiracle/trinity-lite/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/Yomiracle/trinity-lite)](https://github.com/Yomiracle/trinity-lite/releases)

**一个可公开、可复现、可扩展的三 Agent 任务总线。**

Trinity Lite 把多 Agent 协作变成一个可检查、可运行的本地工程流程：router 判断任务给谁，SQLite bus 持久化任务，worker 执行 agent，最后可以查询状态和结果。默认 mock agent 能让任何人先跑通完整链路，再逐步接入真实 Codex、Claude Code、Hermes 或其他 CLI agent。

[English README](README.md)

## 30 秒跑通

```bash
git clone https://github.com/Yomiracle/trinity-lite.git
cd trinity-lite
python3 -m pip install -e .
trinity-lite doctor --scan-root .
trinity-lite dispatch-auto "implement a hello-world function"
trinity-lite worker codex --once
trinity-lite tasks
```

默认 agent 是 mock 模式，所以别人没有安装 Codex、Claude Code、Hermes，也能先跑通 demo。

## 它解决什么问题

普通多 Agent 很容易变成“几个 AI 互相聊天”。Trinity Lite 做的是更工程化的协作：

```text
用户任务 -> router 判断谁做 -> SQLite task bus 持久化 -> worker 执行 -> 结果可查询
```

默认角色：

| Agent | 默认职责 |
|-------|----------|
| `codex` | 实现、测试、项目审查 |
| `claude_code` | 二审、复核、交叉检查 |
| `hermes` | 编排、验收 |

## 核心能力

- **自动路由**：根据任务类型决定交给哪个 agent。
- **SQLite 任务总线**：持久化任务、状态、结果和错误。
- **Worker 执行模型**：支持 mock agent，也支持真实本地 CLI agent。
- **跨 Agent 消息**：通过 inbox/message 做持久化沟通。
- **Doctor 检查**：检查运行环境和公开发布状态。
- **真实 Agent 接入**：不用改源码，通过本地 JSON 配置接入 Codex、Claude Code、Hermes 或任意 CLI。

## 适合展示什么

Trinity Lite 适合用来展示：

- 多 Agent 不是互相聊天，而是有路由、有任务、有状态的工程流程；
- Codex / Claude Code / Hermes 可以通过共享 bus 协作；
- 复杂 agent 系统可以抽出一个公开、可复现、可学习的 Lite 版本；
- 从 mock demo 到真实 agent 接入的完整升级路径。

## 快速开始

```bash
git clone https://github.com/Yomiracle/trinity-lite.git
cd trinity-lite
python3 -m pip install -e .

# 本地健康检查
trinity-lite doctor --scan-root .

# 自动路由并派发任务
trinity-lite dispatch-auto "implement a hello-world function"

# mock Codex worker 执行一次
trinity-lite worker codex --once

# 查看任务
trinity-lite tasks
```

## 接入真实 Agent

复制示例配置：

```bash
cp examples/agents.command.example.json agents.local.json
```

编辑 `agents.local.json` 后运行：

```bash
trinity-lite dispatch-auto "write a unit test"
trinity-lite worker codex --once --agents agents.local.json
```

命令用 JSON array 配置，并用 `shell=False` 执行，避免 shell 注入。

真实 Codex / Claude Code / 通用 CLI 接入方式见：[docs/REAL_AGENTS.md](docs/REAL_AGENTS.md)。

## 文档

- [架构](docs/ARCHITECTURE.md)
- [安全说明](docs/SECURITY.md)
- [教程](docs/TRINITY_LITE.md)
- [真实 Agent 接入](docs/REAL_AGENTS.md)
- [路线图](ROADMAP.md)
- [变更日志](CHANGELOG.md)
- [贡献指南](CONTRIBUTING.md)
