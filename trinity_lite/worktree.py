"""Git worktree lifecycle helpers for Trinity Lite."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import default_worktree_root


class WorktreeError(ValueError):
    """Raised when a managed worktree operation cannot be completed."""


@dataclass(frozen=True)
class WorktreeRef:
    """A managed git worktree and its metadata."""

    task_id: str
    agent_id: str
    prompt: str
    repo_path: Path
    worktree_path: Path
    branch: str
    base_ref: str
    base_commit: str
    created_at: str
    dirty_at_create: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "prompt": self.prompt,
            "repo_path": str(self.repo_path),
            "worktree_path": str(self.worktree_path),
            "branch": self.branch,
            "base_ref": self.base_ref,
            "base_commit": self.base_commit,
            "created_at": self.created_at,
            "dirty_at_create": self.dirty_at_create,
        }


def create_worktree(
    prompt: str,
    repo_path: str | Path = ".",
    agent_id: str = "agent",
    task_id: str | None = None,
    base_ref: str = "HEAD",
    worktree_root: str | Path | None = None,
) -> dict[str, Any]:
    """Create a managed git worktree and persist metadata outside it."""

    _require_git()
    repo = repo_root(repo_path)
    agent = _safe_id(agent_id, label="agent_id")
    task = _safe_id(task_id or uuid.uuid4().hex[:12], label="task_id")
    root = _resolve_worktree_root(worktree_root)
    repo_key = _repo_key(repo)
    path = root / repo_key / f"{task}-{agent}"
    branch = f"trinity/{task}/{agent}"

    if path.exists():
        raise WorktreeError(f"worktree path already exists: {path}")
    if _metadata_path(root, task, agent).exists():
        raise WorktreeError(f"managed worktree metadata already exists for {task}/{agent}")
    if _branch_exists(repo, branch):
        raise WorktreeError(f"branch already exists: {branch}")

    base_commit = _git(["rev-parse", base_ref], cwd=repo)
    dirty = bool(_git(["status", "--porcelain"], cwd=repo, allow_empty=True))

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _git(["worktree", "add", "-b", branch, str(path), base_ref], cwd=repo)
    except WorktreeError:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        raise

    ref = WorktreeRef(
        task_id=task,
        agent_id=agent,
        prompt=prompt,
        repo_path=repo,
        worktree_path=path.resolve(),
        branch=branch,
        base_ref=base_ref,
        base_commit=base_commit,
        created_at=_utc_now(),
        dirty_at_create=dirty,
    )
    _write_metadata(root, ref)
    data = ref.as_dict()
    data["status"] = "created"
    return data


def list_managed_worktrees(
    worktree_root: str | Path | None = None,
    repo_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """List Trinity Lite managed worktrees from metadata."""

    root = _resolve_worktree_root(worktree_root)
    repo_filter = repo_root(repo_path) if repo_path is not None else None
    items: list[dict[str, Any]] = []
    for path in sorted(_index_dir(root).glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if repo_filter is not None and Path(data.get("repo_path", "")).resolve() != repo_filter:
            continue
        worktree_path = Path(data.get("worktree_path", ""))
        data["exists"] = worktree_path.exists()
        data["metadata_path"] = str(path)
        items.append(data)
    return items


def diff_worktree(
    ref: str | Path,
    worktree_root: str | Path | None = None,
    base_ref: str | None = None,
    stat_only: bool = False,
) -> dict[str, Any]:
    """Return a diff summary for a managed worktree or worktree path."""

    meta = _resolve_metadata_or_path(ref, worktree_root)
    path = Path(meta["worktree_path"]).expanduser().resolve()
    if not path.exists():
        raise WorktreeError(f"worktree path does not exist: {path}")
    base = base_ref or meta.get("base_commit") or "HEAD"
    stat = _git(["diff", "--stat", base, "--"], cwd=path, allow_empty=True)
    status = _git(["status", "--short"], cwd=path, allow_empty=True)
    untracked = _git(
        ["ls-files", "--others", "--exclude-standard"],
        cwd=path,
        allow_empty=True,
    ).splitlines()
    patch = "" if stat_only else _git(["diff", base, "--"], cwd=path, allow_empty=True)
    return {
        "task_id": meta.get("task_id"),
        "agent_id": meta.get("agent_id"),
        "worktree_path": str(path),
        "branch": meta.get("branch"),
        "base": base,
        "stat": stat,
        "status": status,
        "untracked_files": untracked,
        "patch": patch,
    }


def cleanup_worktree(
    ref: str | Path,
    worktree_root: str | Path | None = None,
    force: bool = False,
    delete_branch: bool = False,
) -> dict[str, Any]:
    """Remove a managed worktree and optionally delete its branch."""

    root = _resolve_worktree_root(worktree_root)
    meta = _resolve_metadata_or_path(ref, root)
    worktree_path = Path(meta["worktree_path"]).expanduser().resolve()
    repo = Path(meta["repo_path"]).expanduser().resolve()
    branch = meta.get("branch")
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(worktree_path))

    removed = False
    if worktree_path.exists():
        _git(args, cwd=repo)
        removed = True
    elif not force:
        raise WorktreeError(f"worktree path does not exist: {worktree_path}")

    branch_deleted = False
    if delete_branch and branch:
        branch_args = ["branch", "-d", branch]
        try:
            _git(branch_args, cwd=repo)
            branch_deleted = True
        except WorktreeError:
            if not force:
                raise
            _git(["branch", "-D", branch], cwd=repo)
            branch_deleted = True

    metadata_path = _metadata_path(root, meta["task_id"], meta["agent_id"])
    metadata_removed = False
    if metadata_path.exists():
        metadata_path.unlink()
        metadata_removed = True
    _git(["worktree", "prune"], cwd=repo, allow_empty=True)
    _remove_empty_child_dirs(root, worktree_path.parent)
    _remove_empty_child_dirs(root, metadata_path.parent)
    return {
        "task_id": meta.get("task_id"),
        "agent_id": meta.get("agent_id"),
        "worktree_path": str(worktree_path),
        "branch": branch,
        "removed": removed,
        "metadata_removed": metadata_removed,
        "branch_deleted": branch_deleted,
    }


def repo_root(path: str | Path = ".") -> Path:
    """Resolve the git repository root for a path."""

    candidate = Path(path).expanduser().resolve()
    if not candidate.exists():
        raise WorktreeError(f"repo path does not exist: {candidate}")
    if not candidate.is_dir():
        raise WorktreeError(f"repo path is not a directory: {candidate}")
    try:
        root = _git(["rev-parse", "--show-toplevel"], cwd=candidate)
    except WorktreeError as exc:
        raise WorktreeError(f"not a git repository: {candidate}") from exc
    return Path(root).resolve()


def _resolve_metadata_or_path(ref: str | Path, worktree_root: str | Path | None) -> dict[str, Any]:
    raw = str(ref)
    path = Path(raw).expanduser()
    if path.exists() and path.is_dir():
        return _metadata_for_path(path.resolve(), worktree_root)
    return _metadata_for_ref(raw, worktree_root)


def _metadata_for_ref(ref: str, worktree_root: str | Path | None) -> dict[str, Any]:
    root = _resolve_worktree_root(worktree_root)
    exact_matches = sorted(_index_dir(root).glob(f"{ref}-*.json"))
    direct = sorted(_index_dir(root).glob(f"*{_safe_filename(ref)}*.json"))
    matches = exact_matches or direct
    if not matches:
        raise WorktreeError(f"managed worktree not found: {ref}")
    if len(matches) > 1:
        names = ", ".join(path.stem for path in matches)
        raise WorktreeError(f"managed worktree reference is ambiguous: {ref} ({names})")
    return json.loads(matches[0].read_text(encoding="utf-8"))


def _metadata_for_path(path: Path, worktree_root: str | Path | None) -> dict[str, Any]:
    root = _resolve_worktree_root(worktree_root)
    matches = []
    for item in _index_dir(root).glob("*.json"):
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if Path(data.get("worktree_path", "")).expanduser().resolve() == path:
            matches.append(data)
    if not matches:
        raise WorktreeError(f"managed metadata not found for worktree path: {path}")
    if len(matches) > 1:
        raise WorktreeError(f"multiple metadata records found for worktree path: {path}")
    return matches[0]


def _write_metadata(root: Path, ref: WorktreeRef) -> None:
    path = _metadata_path(root, ref.task_id, ref.agent_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ref.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _metadata_path(root: Path, task_id: str, agent_id: str) -> Path:
    return _index_dir(root) / f"{_safe_filename(task_id)}-{_safe_filename(agent_id)}.json"


def _index_dir(root: Path) -> Path:
    return root / "_index"


def _resolve_worktree_root(path: str | Path | None) -> Path:
    return (Path(path).expanduser() if path else default_worktree_root()).resolve()


def _remove_empty_child_dirs(root: Path, path: Path) -> None:
    root = root.resolve()
    current = path.resolve()
    while current != root and root in current.parents:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _repo_key(repo: Path) -> str:
    digest = hashlib.sha1(str(repo).encode("utf-8")).hexdigest()[:8]
    return f"{_safe_filename(repo.name)}-{digest}"


def _safe_id(value: str, label: str) -> str:
    safe = _safe_filename(value.strip())
    if not safe:
        raise WorktreeError(f"{label} must contain at least one safe character")
    return safe[:80]


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-._")


def _branch_exists(repo: Path, branch: str) -> bool:
    return bool(_git(["branch", "--list", branch], cwd=repo, allow_empty=True))


def _git(args: list[str], cwd: Path, allow_empty: bool = False) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        shell=False,
        check=False,
    )
    output = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if completed.returncode != 0:
        detail = stderr or output or f"git {' '.join(args)} exited {completed.returncode}"
        raise WorktreeError(detail)
    if not output and not allow_empty:
        return ""
    return output


def _require_git() -> None:
    if shutil.which("git") is None:
        raise WorktreeError("git executable not found")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
