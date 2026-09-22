# Changelog

## v0.7.1 - 2026-09-22

### Added

- Added `trinity-lite init [--out PATH] [--force]` to detect supported local
  agent CLIs (Codex, Claude Code, Hermes) on PATH and write a safe starter
  `agents.local.json`: detected CLIs become command-mode agents with the
  documented JSON-array commands, undetected presets stay in mock mode, and
  no credentials are ever written. An existing config is never overwritten
  unless `--force` is given; when no CLI is found the command still succeeds
  and writes a mock-only config.
- Added `trinity_lite.init` with `detect_agent_clis()`,
  `build_starter_config()`, and `run_init()`.
- Added `trinity-lite doctor --onboarding`: every doctor check now carries a
  `level` field (`blocker` or `optional`), onboarding mode additionally
  probes for supported agent CLIs as an optional check with a remediation
  hint, and the CLI exits non-zero only when a blocker check fails. The
  report also lists `blockers_failed` and `optional_failed` explicitly.

### Changed

- Default `trinity-lite doctor` behavior is unchanged: it still exits 0 and
  computes `status` from all checks, so existing MCP and acceptance-gate
  callers are unaffected.

## v0.7.0 - 2026-09-22

### Added

- Added `trinity-lite proof <task_id> [--out DIR] [--format json|md|both]` to
  export one task's route, work result, review, verification, and acceptance
  evidence as a portable proof bundle: a structured JSON file with a
  `proof_bundle_version` field and a human-readable Markdown file with stage
  sections and a timeline table.
- Added `trinity_lite.proof` with `build_proof_bundle()`, `render_markdown()`,
  and `export_proof_bundle()`. Stages without recorded evidence are exported
  as explicit nulls and marked "Not recorded" in Markdown; no data is
  fabricated for incomplete tasks.
- Added the read-only `trinity_proof` MCP tool that returns the same proof
  bundle structure to MCP clients without writing files.

### Changed

- The MCP server now exposes 14 tools; README, MCP design documentation, and
  tool-count assertions were updated accordingly.

## v0.6.1 - 2026-07-13

### Added

- Added `trinity-lite latest` and the `trinity_latest` MCP tool to recover the
  latest primary task submitted by a source agent when a client loses the task
  id before displaying the result.

### Fixed

- Return a structured `self_route` result instead of an MCP/CLI error when a
  dispatch resolves to the source agent itself.
- Synchronized the GitHub README, package metadata, and published command/tool
  surface so `trinity_latest` is available to users who install from PyPI.

### Changed

- Positioned Trinity Lite as a local AgentOps control plane for cross-vendor
  CLI agents, centered on durable recovery and evidence-based acceptance.
- Added a macOS CI smoke job and Dependabot configuration for Python and
  GitHub Actions dependencies.
- Updated supported-version, roadmap, product, and MCP design documentation.

## v0.6.0 - 2026-06-29

### Added

- Added `trinity-lite worktree create/list/diff/cleanup` as a preview for
  isolated git worktree lifecycle management.
- Added `trinity_lite.worktree` with metadata stored outside agent checkouts and
  diff evidence based on the recorded base commit.
- Added worktree preview documentation and tests.

### Fixed

- Removed empty managed worktree root directories after cleanup.

### Changed

- Ignored local `marketing/` drafts so release checks stay focused on source,
  package, and documentation files.

## v0.5.3 - 2026-06-27

### Changed

- Added Glama registry and Docker evaluation metadata.
- Improved MCP tool descriptions and annotations for read-only, stateful, and
  agent-execution tools.
- Added the GitHub Pages documentation workflow and public agent recipes.

## v0.5.2 - 2026-06-27

### Fixed

- Fixed `trinity-lite orchestrate --pipeline ... --wait` so YAML pipeline runs do not enter the review-flow wait path.

## v0.5.1 - 2026-06-27

### Added

- Added the optional `yaml` extra: `pip install "trinity-lite[yaml]"` installs `PyYAML` for YAML pipeline files.

### Changed

- GitHub Tests and Publish workflows now install the package with `.[yaml]` so pipeline YAML tests run in clean CI environments.
- README and Chinese README now document the YAML, MCP, and agent-skill optional extras.

## v0.5.0 - 2026-06-26

### Added

- **Persistent Acceptance Evidence**: `TrinityBus` task rows now store route decisions, review links, gate state, verification output, acceptance reasons, and `accepted_at`.
- **Local Acceptance Gate**: `run_review_flow()` accepts work only after the primary task completes, required review passes, and the local verifier passes. The default verifier runs `trinity-lite doctor`; applications can pass a custom verifier.
- **Doctor Consistency Checks**: `trinity-lite doctor` validates acceptance schema migration and flags inconsistent accepted or verification-failed rows.
- **MCP Evidence Output**: task resources and tool responses include acceptance evidence fields.

### Changed

- `dispatch-auto` persists `route_json` instead of returning route decisions only in memory.
- CLI and MCP server versions now read from package `__version__`, avoiding stale installed metadata when running from source.
- Existing SQLite databases are migrated in place with additive nullable acceptance columns.

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

## Earlier releases

- `v0.2.3`: documentation refresh.
- `v0.2.2`: optional `agent-skill-system` dependency.
- `v0.2.1`: agent skill integration.
- `v0.2.0`: initial MCP server.
- `v0.1.4`: synchronous dispatch with `--wait`.
- `v0.1.3`: guided demo and first-run UX.
- `v0.1.0` through `v0.1.2`: initial local bus, CLI, packaging, and hardening.

Full release notes remain available on the
[GitHub Releases page](https://github.com/Yomiracle/trinity-lite/releases).
