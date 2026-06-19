# Trinity Lite

**一个可公开、可复现、已脱敏的三 Agent 任务总线。**

Trinity Lite 是 Trinity 私有系统的公开最小版。它保留三 Agent 协作里最有价值的部分：任务派发、路由、SQLite 总线、worker、mock agent、消息、doctor 和安全检查；同时剥离私有 token、真实数据库、本机路径、模型网关、日志和个人记忆。

[English README](README.md)

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

默认 agent 是 mock 模式，所以别人没有安装 Codex、Claude Code、Hermes，也能先跑通 demo。

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

## 绝不公开的东西

这个公开版不包含：

- API key / OAuth token
- `.env`
- 真实任务数据库
- 个人记忆和日志
- SmartRouter / PM2 / 私有模型网关配置
- `/Users/...` 这种本机路径
- 私有 Hermes 身份文件

发布前运行：

```bash
trinity-lite doctor --scan-root .
python3 -m unittest discover -s tests -v
```

## 文档

- [架构](docs/ARCHITECTURE.md)
- [安全说明](docs/SECURITY.md)
- [教程](docs/TRINITY_LITE.md)
