# Changelog

## v0.4.0 - 2026-06-24

### Added

- **Model Selector**: Automatically picks the best LLM backend for each task based on complexity and required capabilities. No hardcoded model names — users define their own pool with tiers (budget/standard/premium) and strength tags (coding/reasoning/security/...).
  - `trinity_lite/model_selector.py`: Core selection engine with 4-layer decision logic (bypass → hard signal → task-type map → SC complexity classification).
  - `trinity_lite/model_autodetect.py`: Zero-config environment scanner — detects available backends from environment variables, key files, and local endpoints (Ollama). Runs `init()` on first import.
  - `trinity_lite/model_pool_wizard.py`: Interactive setup wizard — no JSON knowledge needed. Asks simple questions and generates `model_pool.json`.
- **New CLI commands**:
  - `trinity-lite setup-models`: Run the interactive model pool wizard.
  - `trinity-lite detect-models`: Auto-detect available LLM backends and save to `~/.trinity/model_pool.json`.
- Model pool config at `~/.trinity/model_pool.json` is auto-loaded by the selector. Set `TRINITY_MODEL_POOL` env var to use a custom path.
- Agent-aware filtering: `available_to` field on models restricts which agents can use them (optional).

## v0.3.1 - 2026-06-23

### Added

- **YAML Pipeline Orchestration**: N-step sequential pipelines defined in YAML files, enabling multi-agent workflows beyond the built-in review flow.
  - New `pipelines/` directory with example pipelines (`implement-review.yaml`, `implement-only.yaml`).
  - `trinity_lite/pipeline.py`: `load_pipeline()`, `resolve_step_prompt()`, `run_pipeline()`.
  - `--pipeline` flag on `orchestrate` CLI subcommand: `trinity-lite orchestrate "task" --pipeline pipelines/implement-review.yaml`
  - `trinity_orchestrate` MCP tool: orchestrate pipelines from any MCP client.
  - Pipeline step prompts support `{task}` and `{steps.X.result}` variable substitution.
  - 16 new tests covering pipeline loading, validation, rendering, and execution.

### Changed

- `run_review_flow()` gains a `BUILTIN_REVIEW_PIPELINE` constant documenting the review flow structure (backwards compatible).
- MCP server tool count updated from 11 to 12 (new trinity_orchestrate tool).
