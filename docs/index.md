# Trinity Lite Documentation

Trinity Lite is a local-first orchestration layer for CLI AI agents.

It gives existing tools such as Codex, Claude Code, Hermes, or your own CLI a
shared workflow:

```text
route -> work -> review -> verify -> accept
```

The default demo uses mock agents, so you can try the full flow before wiring in
real commands.

## Start Here

```bash
python3 -m pip install trinity-lite
trinity-lite doctor
trinity-lite orchestrate "implement a hello-world function"
```

For source development:

```bash
git clone https://github.com/Yomiracle/trinity-lite.git
cd trinity-lite
python3 -m pip install -e ".[yaml]"
python3 -m unittest discover -s tests -v
```

## Core Docs

- [Why Trinity Lite?](WHY_TRINITY_LITE.md)
- [Tutorial](TRINITY_LITE.md)
- [Real Agent Setup](REAL_AGENTS.md)
- [Agent Capabilities](CAPABILITIES.md)
- [Worktree Parallelism Preview](WORKTREE_PARALLELISM.md)
- [Architecture](ARCHITECTURE.md)
- [Operations](OPERATIONS.md)
- [Security](SECURITY.md)
- [MCP Server Design](MCP_SERVER_DESIGN.md)
- [Product Positioning](PRODUCT.md)

## Recipes

- [Codex](recipes/codex.md)
- [Claude Code](recipes/claude-code.md)
- [Hermes and private Trinity boundaries](recipes/hermes-private-trinity.md)
- [Generic CLI agent](recipes/generic-cli.md)

## Optional Extras

```bash
python3 -m pip install "trinity-lite[yaml]"          # YAML pipeline files
python3 -m pip install "trinity-lite[mcp]"           # MCP server
python3 -m pip install "trinity-lite[agent-skill]"   # agent-skill-system integration
```

## What Trinity Lite Is Not

Trinity Lite is not a hosted agent platform, a model gateway, or a replacement
for a full agent framework. It is a small local coordination layer for existing
CLI agents.
