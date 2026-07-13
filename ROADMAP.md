# Roadmap

Trinity Lite is intentionally small: a local AgentOps control plane for
cross-vendor CLI agents. The roadmap prioritizes operational trust before a
larger connector or UI surface.

## Shipped

### v0.1-v0.2: Local Bus and MCP

- SQLite task and message bus.
- CLI routing, dispatch, workers, status, inbox, and doctor.
- Mock-agent demo and command adapters.
- MCP tools and read-only resources.

### v0.3-v0.5: Orchestration and Acceptance

- YAML pipelines and primary-to-review orchestration.
- Optional task-aware model selection from a user-defined pool.
- Durable route, review, verification, and acceptance evidence.
- Local acceptance gate that records why work passed or stopped.

### v0.6: Worktree and Recovery Preview

- Managed git worktree create/list/diff/cleanup commands.
- Recorded base commit, branch, worktree path, agent id, and diff evidence.
- `trinity_latest` recovery after an interrupted client response.
- Structured `self_route` results that keep local work out of delegation loops.

Automatic merge, conflict resolution, and branch deletion remain out of scope
for the preview.

## Next

### v0.7: Proof Bundles and Five-Minute Onboarding

- Export one task's route, result, review, verification, and acceptance data as
  a portable JSON and Markdown proof bundle.
- Auto-detect supported local agent CLIs and generate a safe starter config.
- Add an onboarding doctor that distinguishes optional agents from blockers.
- Keep the mock-to-real-agent path usable without a hosted account.

### v0.8: Operational Visibility and Recovery

- Add a compact local task/review/test/cost console.
- Record token, cost, latency, retry, and success metadata when adapters expose
  it; mark unavailable data explicitly instead of estimating it.
- Add explicit cancellation, retry, and resumable workflow checkpoints.
- Preserve SQLite inspectability and stable CLI/JSON output.

## v1.0: Stable Local AgentOps Contract

- Freeze the core CLI command shape and MCP task contract.
- Stabilize the SQLite schema with documented migrations.
- Publish a supported adapter contract for custom CLI agents.
- Keep package, release, documentation, and acceptance evidence synchronized.

## Later, Not Committed

- Safe JSON command connectors for GitHub, PyPI, and local filesystems.
- Remote workers and encrypted synchronization.
- Team policy packs and role-based controls.

These layers must not weaken the local-first core or turn Trinity Lite into a
provider-specific model wrapper.

## Non-Goals

- No bundled credentials or private model gateway configuration.
- No hosted remote-code-execution service in the core package.
- No universal agent framework or provider API abstraction.
- No claim that routing heuristics automatically choose the globally best or
  cheapest model.
