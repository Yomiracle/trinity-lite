# Real Agent Command Setup

Trinity Lite runs mock agents by default. That is intentional: anyone can test the bus without installing Codex, Claude Code, Hermes, Qwen, Gemini, Aider, or another agent CLI.

When you are ready to run real tools, create a local command config that is not committed to git.

## 1. Copy the Example

```bash
cp examples/agents.command.example.json agents.local.json
```

`agents.local.json` is ignored by git.

## 2. Configure Commands

Commands are JSON arrays. Trinity Lite executes them with `shell=False`, so shell features such as pipes, redirects, aliases, and inline environment variable assignments are not expanded.

Good:

```json
{
  "agents": {
    "codex": {
      "mode": "command",
      "command": ["codex", "exec", "-C", "{cwd}", "{prompt}"],
      "timeout": 1800
    }
  }
}
```

Avoid:

```json
{
  "command": ["zsh", "-lc", "source ~/.zshrc; codex exec -C {cwd} {prompt}"]
}
```

Use a shell wrapper only when the tool truly requires shell startup behavior, and keep that wrapper local.

Agent metadata can also declare workflow roles, capabilities, and priority:

```json
{
  "agents": {
    "qwen_cli": {
      "mode": "command",
      "command": ["qwen", "run", "{prompt}"],
      "roles": ["primary_engineer"],
      "capabilities": ["code_edit", "test_run", "long_context"],
      "priority": 80,
      "timeout": 1800
    }
  }
}
```

See [Agent capabilities](CAPABILITIES.md) for capability-based routing.

## 3. Codex Example

```json
{
  "agents": {
    "codex": {
      "mode": "command",
      "command": ["codex", "exec", "-C", "{cwd}", "{prompt}"],
      "timeout": 1800
    },
    "claude_code": {
      "mode": "mock",
      "timeout": 1800
    },
    "hermes": {
      "mode": "mock",
      "timeout": 1800
    }
  }
}
```

Run:

```bash
trinity-lite dispatch-auto "write a unit test"
trinity-lite worker codex --once --agents agents.local.json
trinity-lite tasks
```

## 4. Claude Code Example

```json
{
  "agents": {
    "codex": {
      "mode": "mock",
      "timeout": 1800
    },
    "claude_code": {
      "mode": "command",
      "command": ["claude", "-p", "{prompt}"],
      "timeout": 1800
    },
    "hermes": {
      "mode": "mock",
      "timeout": 1800
    }
  }
}
```

Run a review route:

```bash
trinity-lite dispatch codex "implement something"
trinity-lite route "二审" --previous-agent codex
trinity-lite dispatch-auto "二审" --previous-agent codex
trinity-lite worker claude_code --once --agents agents.local.json
```

## 5. Generic CLI Agent

Any local command can be used if it accepts either:

- the prompt as a command argument through `{prompt}`, or
- the prompt on stdin when `{prompt}` is not present.

Example using stdin:

```json
{
  "agents": {
    "assistant": {
      "mode": "command",
      "command": ["my-agent-cli", "--cwd", "{cwd}"],
      "timeout": 600
    }
  }
}
```

## 6. Capability-Based Routing

Copy the generic examples:

```bash
cp examples/agents.generic.example.json agents.local.json
cp examples/routes.capabilities.example.json routes.local.json
```

Route by declared capabilities:

```bash
trinity-lite dispatch-auto "fix the parser bug" \
  --agents agents.local.json \
  --routes routes.local.json
```

Run the selected worker:

```bash
trinity-lite worker qwen_cli --once --agents agents.local.json
```

Codex, Claude Code, and Hermes are presets, not requirements. If your agent uses
a different API provider or a local model, keep that setup inside the CLI or a
local wrapper.

## 7. Placeholders

Supported placeholders:

| Placeholder | Meaning |
|-------------|---------|
| `{prompt}` | Task prompt |
| `{cwd}` | Task working directory |
| `{task_id}` | Trinity Lite task id |
| `{task_type}` | Resolved task type |

## 8. Safety Notes

- Keep `agents.local.json` out of git.
- Do not put API keys in command arrays.
- Prefer environment variables managed by the agent tool itself.
- Run `trinity-lite doctor --scan-root .` before publishing a repository.

## 中文说明

默认 mock agent 是为了让任何人都能先跑通流程。接入真实 Codex、Claude Code、Qwen、Gemini、Aider 或自定义 CLI 时，只需要复制示例到本地的 `agents.local.json`，然后按自己的机器修改命令。

关键规则：

- 命令必须是 JSON array。
- Trinity Lite 使用 `shell=False` 执行命令。
- 不要把 API key、OAuth token、本机私有路径提交到仓库。
- 本地配置文件使用 `agents.local.json`，不要 commit。
- 如果不同 agent 使用不同 API，把这些差异留在 CLI 或本地 wrapper 内，Trinity Lite 只负责路由和记录。
