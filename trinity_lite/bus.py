"""SQLite task and message bus for Trinity Lite."""

from __future__ import annotations

import os
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .guard import GuardError, ensure_inside_roots
from .paths import default_allowed_roots, default_db_path


MAX_DEPTH = 2
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
TASK_EVIDENCE_COLUMNS = {
    "parent_task_id": "TEXT",
    "review_task_id": "TEXT",
    "gate_status": "TEXT",
    "gate_updated_at": "TEXT",
    "route_json": "TEXT",
    "verification_json": "TEXT",
    "acceptance_status": "TEXT",
    "acceptance_reason": "TEXT",
    "accepted_at": "TEXT",
}


def utc_now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def json_dumps(value: Any) -> str:
    """Serialize evidence JSON deterministically."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class TrinityBus:
    """Persistent task bus backed by SQLite."""

    def __init__(
        self,
        db_path: str | os.PathLike[str] | None = None,
        allowed_roots: list[Path] | None = None,
    ) -> None:
        self.db_path = Path(db_path).expanduser() if db_path else default_db_path()
        self.allowed_roots = allowed_roots or default_allowed_roots()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    source_agent TEXT NOT NULL,
                    target_agent TEXT NOT NULL,
                    task_type TEXT,
                    prompt TEXT NOT NULL,
                    cwd TEXT NOT NULL,
                    status TEXT NOT NULL,
                    depth INTEGER NOT NULL DEFAULT 0,
                    result TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    heartbeat_at TEXT,
                    parent_task_id TEXT,
                    review_task_id TEXT,
                    gate_status TEXT,
                    gate_updated_at TEXT,
                    route_json TEXT,
                    verification_json TEXT,
                    acceptance_status TEXT,
                    acceptance_reason TEXT,
                    accepted_at TEXT
                )
                """
            )
            self._ensure_task_columns(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    source_agent TEXT NOT NULL,
                    target_agent TEXT NOT NULL,
                    task_id TEXT,
                    message TEXT NOT NULL,
                    read INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )

    def _ensure_task_columns(self, conn: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
        }
        for name, column_type in TASK_EVIDENCE_COLUMNS.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE tasks ADD COLUMN {name} {column_type}")

    def submit_task(
        self,
        source_agent: str,
        target_agent: str,
        prompt: str,
        task_type: str | None = None,
        cwd: str | os.PathLike[str] | None = None,
        depth: int = 0,
        parent_task_id: str | None = None,
        route: dict[str, Any] | None = None,
        gate_status: str | None = None,
        acceptance_status: str | None = None,
        acceptance_reason: str | None = None,
    ) -> dict[str, Any]:
        if source_agent == target_agent:
            raise GuardError("self-delegation is not allowed")
        if depth > MAX_DEPTH:
            raise GuardError(f"delegation depth exceeds max depth {MAX_DEPTH}")
        workdir = ensure_inside_roots(cwd or os.getcwd(), self.allowed_roots)
        task_id = uuid.uuid4().hex[:12]
        now = utc_now_iso()
        route_json = json_dumps(route) if route is not None else None
        # Keep the initial gate timestamp visible until the orchestrator advances it.
        gate_updated_at = now if gate_status else None
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    id, source_agent, target_agent, task_type, prompt, cwd,
                    status, depth, created_at, heartbeat_at, parent_task_id,
                    route_json, gate_status, gate_updated_at, acceptance_status,
                    acceptance_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    source_agent,
                    target_agent,
                    task_type,
                    prompt,
                    str(workdir),
                    depth,
                    now,
                    now,
                    parent_task_id,
                    route_json,
                    gate_status,
                    gate_updated_at,
                    acceptance_status,
                    acceptance_reason,
                ),
            )
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"task not found: {task_id}")
        return dict(row)

    def list_tasks(self, agent: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        sql = "SELECT * FROM tasks"
        params: list[Any] = []
        if agent:
            sql += " WHERE source_agent = ? OR target_agent = ?"
            params.extend([agent, agent])
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def task_for_worker(self, target_agent: str, task_id: str | None = None) -> dict[str, Any] | None:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if task_id is not None:
                row = conn.execute(
                    """
                    SELECT * FROM tasks
                    WHERE id = ? AND status = 'queued'
                    """,
                    (task_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT * FROM tasks
                    WHERE target_agent = ? AND status = 'queued'
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (target_agent,),
                ).fetchone()
            if row is None:
                conn.commit()
                return None
            conn.execute(
                """
                UPDATE tasks
                SET status = 'running', started_at = ?, heartbeat_at = ?
                WHERE id = ? AND status = 'queued'
                """,
                (now, now, row["id"]),
            )
            conn.commit()
        return self.get_task(row["id"])

    def finish_worker(
        self,
        task_id: str,
        result: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        status = "failed" if error else "completed"
        now = utc_now_iso()
        with self.connect() as conn:
            cur = conn.execute(
                """
                UPDATE tasks
                SET status = ?, result = ?, error = ?, finished_at = ?, heartbeat_at = ?
                WHERE id = ? AND status = 'running'
                """,
                (status, result, error, now, now, task_id),
            )
            if cur.rowcount == 0:
                raise ValueError(f"task {task_id} is not in running state")
        return self.get_task(task_id)

    def update_task_evidence(self, task_id: str, **fields: Any) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in TASK_EVIDENCE_COLUMNS:
                raise ValueError(f"unsupported task evidence column: {key}")
            if key in {"route_json", "verification_json"} and value is not None and not isinstance(value, str):
                value = json_dumps(value)
            updates[key] = value
        if not updates:
            return self.get_task(task_id)

        assignments = ", ".join(f"{key} = ?" for key in updates)
        with self.connect() as conn:
            cur = conn.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ?",
                (*updates.values(), task_id),
            )
            if cur.rowcount == 0:
                raise KeyError(f"task not found: {task_id}")
        return self.get_task(task_id)

    def send_message(
        self,
        source_agent: str,
        target_agent: str,
        message: str,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        if source_agent == target_agent:
            raise GuardError("self-messaging is not allowed")
        msg_id = uuid.uuid4().hex[:12]
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    id, source_agent, target_agent, task_id, message, read, created_at
                )
                VALUES (?, ?, ?, ?, ?, 0, ?)
                """,
                (msg_id, source_agent, target_agent, task_id, message, utc_now_iso()),
            )
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)).fetchone()
        return dict(row)

    def await_task(self, task_id: str, timeout: float = 300) -> dict[str, Any]:
        """Block until task reaches terminal status or timeout."""
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            task = self.get_task(task_id)
            if task["status"] in TERMINAL_STATUSES:
                return task
            time.sleep(0.2)
        raise TimeoutError(f"task {task_id} did not finish within {timeout}s")

    def inbox(
        self,
        agent: str,
        unread_only: bool = True,
        mark_read: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM messages WHERE target_agent = ?"
        params: list[Any] = [agent]
        if unread_only:
            sql += " AND read = 0"
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            messages = [dict(r) for r in rows]
            if mark_read and messages:
                for message in messages:
                    conn.execute(
                        "UPDATE messages SET read = 1 WHERE id = ?",
                        (message["id"],),
                    )
        return messages
