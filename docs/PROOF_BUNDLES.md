# Proof Bundles

A proof bundle exports one task's full evidence chain — route, work result,
review, verification, and acceptance — as portable files you can archive,
attach to a change request, or hand to another tool.

## Exporting

```bash
trinity-lite proof <task_id>                     # writes JSON + Markdown to the current directory
trinity-lite proof <task_id> --out bundles/      # choose an output directory
trinity-lite proof <task_id> --format json       # or: md, both (default)
```

Files are named `proof-<task_id>.json` and `proof-<task_id>.md`. Bundles are
export artifacts, so the default output directory is the current working
directory, not the managed state directory under `~/.trinity-lite`.

MCP clients can read the same structure without writing files through the
read-only `trinity_proof` tool.

## JSON Structure

The JSON bundle is versioned so consumers can evolve with the schema:

```json
{
  "proof_bundle_version": 1,
  "generated_at": "2026-09-22T05:18:18+00:00",
  "generator": "trinity-lite 0.7.0",
  "task": { "id": "...", "prompt": "...", "status": "completed", "...": "..." },
  "route": { "agent": "codex", "task_type": "implementation", "...": "..." },
  "work": { "status": "completed", "result": "...", "error": null, "...": "..." },
  "review": { "task_id": "...", "task": { "...": "..." } },
  "verification": { "status": "passed", "checks": [ "..." ] },
  "acceptance": { "status": "accepted", "reason": "...", "accepted_at": "..." },
  "timeline": [ { "stage": "route", "at": "...", "actor": "...", "detail": "..." } ]
}
```

## Missing Stages

Proof bundles never fabricate evidence. A task that only reached part of the
flow exports the stages that exist and marks the rest explicitly:

- JSON: the stage field is `null` (for example `"review": null` when no
  secondary review was dispatched).
- Markdown: the stage section shows "_Not recorded._".

An unknown task id returns a structured error and writes no files.

## Markdown Summary

The Markdown file mirrors the workflow order — Route, Work, Review,
Verification, Acceptance — and ends with a timeline table built from the
recorded timestamps (`created_at`, `started_at`, `finished_at`,
`gate_updated_at`, `accepted_at`). It is meant for humans; the JSON file is
meant for tools.
