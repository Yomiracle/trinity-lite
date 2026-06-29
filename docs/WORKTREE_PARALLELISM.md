# Worktree Parallelism Preview

This is a v0.6 preview. It manages isolated worktree lifecycle and diff evidence
while keeping automatic merge-back out of scope.

Trinity Lite can create managed git worktrees for agent work. This is the first
step toward parallel agent execution: each agent gets an isolated checkout, and
Trinity records the worktree path, branch, base commit, and diff evidence.

This preview only manages worktree lifecycle. It does not automatically merge
branches, create pull requests, or run `orchestrate` inside a worktree yet.

## Why Worktrees

Without worktrees, multiple agents have to take turns in the same checkout.
That makes review and rollback harder because local edits overlap.

With managed worktrees:

```text
main repo
  |
  +-- codex worktree       trinity/<task_id>/codex
  +-- reviewer worktree    trinity/<task_id>/reviewer
  +-- verifier worktree    trinity/<task_id>/verifier
```

Each branch starts from the recorded `base_commit`. The diff command compares
the worktree back to that base, so reviewers can inspect exactly what changed.

## Create

```bash
trinity-lite worktree create "fix parser bug" --repo . --agent codex
```

Output includes:

- `task_id`: generated unless `--task-id` is provided
- `worktree_path`: isolated checkout path
- `branch`: managed branch, for example `trinity/<task_id>/codex`
- `base_commit`: commit the branch started from
- `dirty_at_create`: whether the source repo had local changes at creation time

By default, worktrees live under:

```text
~/.trinity-lite/worktrees/
```

Use `--worktree-root` to choose a different managed root.

## List

```bash
trinity-lite worktree list
trinity-lite worktree list --repo .
```

Trinity Lite keeps metadata outside the worktree in an `_index/` directory under
the managed worktree root. This keeps metadata out of the agent diff.

## Diff

```bash
trinity-lite worktree diff <task_id>
trinity-lite worktree diff <task_id> --stat-only
```

The diff response contains:

- `stat`: `git diff --stat <base>`
- `patch`: full tracked-file patch unless `--stat-only` is used
- `status`: `git status --short`
- `untracked_files`: untracked files that are not included in normal git diff

## Cleanup

```bash
trinity-lite worktree cleanup <task_id>
trinity-lite worktree cleanup <task_id> --force
```

Cleanup removes the worktree and its Trinity Lite metadata. It does not delete
the branch by default, because the branch may contain work the user still wants
to inspect.

To also delete the managed branch:

```bash
trinity-lite worktree cleanup <task_id> --delete-branch
```

If the branch is unmerged and you still want to delete it:

```bash
trinity-lite worktree cleanup <task_id> --force --delete-branch
```

## Current Limits

- No automatic merge back to the main checkout.
- No pull request creation.
- No built-in conflict resolution.
- No automatic `orchestrate --worktree` integration yet.
- The command depends on the local `git` executable.

The safe next step is to make `orchestrate --worktree` create a primary-agent
worktree, run the worker inside it, collect diff evidence, then pass that diff
into review and acceptance.
