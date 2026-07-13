# Trinity Lite

[![Tests](https://github.com/Yomiracle/trinity-lite/actions/workflows/test.yml/badge.svg)](https://github.com/Yomiracle/trinity-lite/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/Yomiracle/trinity-lite)](https://github.com/Yomiracle/trinity-lite/releases)
[![PyPI](https://img.shields.io/pypi/v/trinity-lite.svg)](https://pypi.org/project/trinity-lite/)
[![Yomiracle/trinity-lite MCP server](https://glama.ai/mcp/servers/Yomiracle/trinity-lite/badges/score.svg)](https://glama.ai/mcp/servers/Yomiracle/trinity-lite/score)

**面向跨厂商 CLI 编程 Agent 的本地 AgentOps 控制平面：路由任务、恢复状态、拿证据验收。**

Trinity Lite 连接你已经在使用的 Codex、Claude Code、Hermes 和任意自定义 CLI agent，不要求把它们重写进另一个框架。它把路由、执行、二审、本地验证和验收证据放进同一条可恢复的本地工作流，并用 SQLite 保存运行事实。

[English README](README.md) · [文档首页](docs/index.md) · [为什么选择 Trinity Lite?](docs/WHY_TRINITY_LITE.md) · [接入教程](docs/recipes/generic-cli.md)

## 为什么需要 Trinity Lite

单个 AI 编程 agent 已经很强。真正困难的是跨工具保存任务事实、在客户端断开后恢复结果、避免重复派发，并确定一项工作是否真的通过了独立审查和本地验证：

| 手工协作方式 | Trinity Lite 方式 |
|--------------|-------------------|
| 在多个工具之间复制结果 | 用 `orchestrate` 跑完整主任务和二审流程 |
| 靠人脑记任务状态 | SQLite 保存状态、结果和验收证据 |
| 手动决定谁做、谁审 | 按任务类型、能力或指定 agent 路由 |
| 失败原因容易丢失 | error、result、message、verification 都可查询 |
| demo 依赖已安装的真实 agent | mock agent 本地即可跑完整流程 |

Trinity Lite 把“同一台机器上的多个 AI 工具”变成一个小型、可复现、可扩展、可验收的 agent 工作流层。

## 面向谁

| 用户 | Trinity Lite 帮你做什么 |
|------|--------------------------|
| 同时使用两个以上 Agent CLI 的高级个人开发者 | 用持久工作流替代多个终端之间的手工交接 |
| AI 原生小团队 | 分离实现、二审、验证和验收，不必先部署控制服务器 |
| 本地优先或隐私敏感的开发者 | 把任务状态和验收证据留在本机 SQLite 中 |
| Agent 工具集成者 | 通过中立任务总线和 MCP 接入已有 CLI |

## 30 秒跑通

```bash
python3 -m pip install trinity-lite
trinity-lite doctor
trinity-lite orchestrate "implement a hello-world function"
```

默认 agent 是 mock 模式，所以别人没有安装 Codex、Claude Code、Hermes，也能先跑通“路由 -> 主任务 -> 二审 -> 本地验证 -> 验收”的完整 demo。

## 工作方式

```text
                  +----------------+
用户任务 -------> | router         |
                  +-------+--------+
                          |
                          v
                  +-------+--------+
                  | SQLite task bus|
                  +-------+--------+
                          |
          +---------------+----------------+
          v                                v
   +------+-------+                 +------+-------+
   | Codex worker |                 | 二审 worker |
   +------+-------+                 +------+-------+
          |                                |
          v                                v
   agent adapter                    agent adapter
          |                                |
          +---------------+----------------+
                          v
              status / result / review / acceptance
```

Codex、Claude Code、Hermes 是默认 preset，不是使用前提。角色可以配置：

| Agent | 默认职责 |
|-------|----------|
| `codex` | 实现、测试、项目审查 |
| `claude_code` | 二审、复核、交叉检查 |
| `hermes` | 编排、验收 |

## 核心能力

- **任务路由**：根据任务类型交给显式 agent，或按声明的能力自动选择 agent。
- **持久化总线**：SQLite 保存任务、状态、结果、错误和消息。
- **Worker 模型**：worker 拉取 queued task，执行 mock agent 或真实本地 CLI。
- **验收证据链**：orchestrator 会持久化 `route_json`、二审关联、`verification_json`、验收原因和 `accepted_at`。
- **Worktree 隔离**：v0.6 preview；`trinity-lite worktree` 可以为 agent 创建独立 git worktree，记录 base commit、branch、路径和 diff 证据。
- **命令适配器**：通过 JSON array command 接入 Codex、Claude Code、Hermes 或任意自定义 CLI。
- **本地健康检查**：检查 Python、SQLite、routes、agents、发布扫描状态和可选运行态卫生。
- **安全边界**：自路由不会创建循环任务，同时限制派发深度、cwd 范围并扫描公开发布目录。

## 技术亮点

- **零核心运行时依赖**：默认只依赖 Python 标准库；YAML pipeline 通过可选 extra 启用。
- **SQLite-first 状态层**：本地、可检查、事务化的任务存储。
- **shell-safe 命令执行**：命令使用 JSON array，并通过 `shell=False` 执行。
- **mock 到真实 agent 的升级路径**：先跑通完整流程，再接真实 CLI agent。
- **能力路由**：agent 可以声明角色、能力和优先级，路由不再依赖固定 agent 名字。
- **CI 支撑的公开发布**：GitHub Actions 运行测试、编译检查、doctor 和 PyPI 发布 workflow。
- **为扩展预留边界**：MCP server、orchestrator、tracing、dashboard 都可以作为后续层添加。

## 产品定位

Trinity Lite 位于“单个 agent CLI 工具”和“完整 agent 框架”之间，产品类别是本地 AgentOps：

```text
Codex / Claude Code / custom CLI
        |
        v
Trinity Lite: route -> work -> review -> verify -> accept
        |
        v
后续层：tracing、dashboard、更强的生产级编排
```

它不是要替代 agent 框架，而是给开发者已经在用的 AI 工具加一层本地运行、故障恢复、职责分离和证据化验收能力。并行 Agent、worktree 和模型选择是功能，但不是产品壁垒本身。

## 快速开始

```bash
python3 -m pip install trinity-lite

# 本地健康检查
trinity-lite doctor

# 自动路由、执行、二审、验证、验收
trinity-lite orchestrate "implement a hello-world function"

# 查看任务和验收证据
trinity-lite tasks
```

### 可选 extra

```bash
python3 -m pip install "trinity-lite[yaml]"          # YAML pipeline 文件
python3 -m pip install "trinity-lite[mcp]"           # MCP server
python3 -m pip install "trinity-lite[agent-skill]"   # agent-skill-system 集成
```

## 升级

```bash
python3 -m pip install --upgrade trinity-lite
```

Trinity Lite 遵循[语义化版本](https://semver.org/lang/zh-CN/)。同一 minor 系列内的补丁版本保持向后兼容，升级后通常无需迁移数据或修改配置。查看当前版本：

```bash
trinity-lite doctor
# 或
python3 -m pip show trinity-lite | grep Version
```

版本变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 从源码开始

```bash
git clone https://github.com/Yomiracle/trinity-lite.git
cd trinity-lite
python3 -m pip install -e .
trinity-lite doctor --scan-root .
```

如果长期运行的本地安装维护了 metrics log，可以增加运行态卫生检查：

```bash
trinity-lite doctor --runtime-root ~/.trinity-lite --retired-port 9797
```

## 接入真实 Agent

复制示例配置：

```bash
cp examples/agents.command.example.json agents.local.json
```

编辑 `agents.local.json` 后运行：

```bash
trinity-lite orchestrate "write a unit test" --agents agents.local.json
```

命令用 JSON array 配置，并用 `shell=False` 执行，避免 shell 注入。

真实 Codex / Claude Code / Hermes / 通用 CLI 接入方式见：[docs/REAL_AGENTS.md](docs/REAL_AGENTS.md) 和 [docs/recipes/](docs/recipes/generic-cli.md)。

如果要按能力而不是固定 agent 名字路由，可以复制通用示例：

```bash
cp examples/agents.generic.example.json agents.local.json
cp examples/routes.capabilities.example.json routes.local.json
trinity-lite orchestrate "fix the parser bug" --agents agents.local.json --routes routes.local.json
```

## Worktree Preview

这是 v0.6 preview。它负责管理独立 worktree 生命周期和 diff 证据，但暂不自动合并回主工作区。

为某个 agent 创建独立代码工作区：

```bash
trinity-lite worktree create "fix parser bug" --repo . --agent codex
trinity-lite worktree list
trinity-lite worktree diff <task_id>
trinity-lite worktree cleanup <task_id>
```

当前 preview 只负责创建、列出、查看 diff 和清理 worktree；不会自动合并，也不会默认删除分支。详见：[Worktree Parallelism Preview](docs/WORKTREE_PARALLELISM.md)。

## 路线图

- **v0.1.x**：本地任务总线、CLI、文档、示例和测试。
- **v0.2**：最小 MCP server，让 AI 客户端能直接调用 Trinity Lite。
- **v0.3**：YAML pipeline，支持可配置多步顺序编排。
- **v0.4**：模型选择器，按任务复杂度和模型能力选择后端。
- **v0.5**：完整本地验收链路，持久化 `route_json`、`verification_json`、`acceptance_status` 和 `accepted_at`。
- **v0.6**：Worktree 与恢复 preview，提供独立工作区、diff 证据、`trinity_latest` 任务恢复和结构化 `self_route`。
- **v0.7**：验收证据包和五分钟接入，支持导出 JSON/Markdown 证据并自动发现本地 Agent CLI。
- **v0.8**：本地任务/二审/测试/成本控制台，以及显式取消、重试和可恢复检查点。
- **v1.0**：稳定 CLI、SQLite schema 和包发布流程。

GitHub、PyPI、filesystem 等安全连接器属于后续候选层，目前不承诺具体版本。

见：[ROADMAP.md](ROADMAP.md)。

## 文档

- [架构](docs/ARCHITECTURE.md)
- [安全说明](docs/SECURITY.md)
- [教程](docs/TRINITY_LITE.md)
- [真实 Agent 接入](docs/REAL_AGENTS.md)
- [Agent 能力路由](docs/CAPABILITIES.md)
- [Worktree Parallelism Preview](docs/WORKTREE_PARALLELISM.md)
- [产品定位](docs/PRODUCT.md)
- [运维指南](docs/OPERATIONS.md)
- [路线图](ROADMAP.md)
- [变更日志](CHANGELOG.md)
- [贡献指南](CONTRIBUTING.md)
