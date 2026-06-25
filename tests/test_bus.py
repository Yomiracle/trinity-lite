import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from trinity_lite.bus import TrinityBus
from trinity_lite.guard import GuardError


class BusTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "bus.db"
        self.bus = TrinityBus(self.db, allowed_roots=[self.root])

    def tearDown(self):
        self.temp.cleanup()

    def test_task_round_trip(self):
        route = {"agent": "codex", "task_type": "implementation", "review_required": True}
        task = self.bus.submit_task(
            "user",
            "codex",
            "build it",
            "implementation",
            cwd=self.root,
            route=route,
            acceptance_status="queued",
        )
        self.assertEqual(task["status"], "queued")
        self.assertEqual(json.loads(task["route_json"]), route)
        self.assertEqual(task["acceptance_status"], "queued")
        claimed = self.bus.task_for_worker("codex")
        self.assertEqual(claimed["id"], task["id"])
        self.assertEqual(claimed["status"], "running")
        done = self.bus.finish_worker(task["id"], result="ok")
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["result"], "ok")

    def test_rejects_self_delegation_depth_and_cwd_escape(self):
        with self.assertRaises(GuardError):
            self.bus.submit_task("codex", "codex", "loop", cwd=self.root)
        with self.assertRaises(GuardError):
            self.bus.submit_task("user", "codex", "too deep", cwd=self.root, depth=3)
        with self.assertRaises(GuardError):
            self.bus.submit_task("user", "codex", "escape", cwd="/")

    def test_connection_context_rolls_back_on_exception(self):
        with self.assertRaises(RuntimeError):
            with self.bus.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO tasks (
                        id, source_agent, target_agent, prompt, cwd,
                        status, depth, created_at, heartbeat_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "rollback-test",
                        "user",
                        "codex",
                        "work",
                        str(self.root),
                        "queued",
                        0,
                        "2026-01-01T00:00:00+00:00",
                        "2026-01-01T00:00:00+00:00",
                    ),
                )
                raise RuntimeError("force rollback")
        with self.assertRaises(KeyError):
            self.bus.get_task("rollback-test")

    def test_update_task_evidence_round_trip(self):
        task = self.bus.submit_task("user", "codex", "build it", "implementation", cwd=self.root)
        updated = self.bus.update_task_evidence(
            task["id"],
            gate_status="review_passed",
            gate_updated_at="2026-01-01T00:00:00+00:00",
            verification_json={"status": "passed", "checks": []},
            acceptance_status="accepted",
            acceptance_reason="verified",
            accepted_at="2026-01-01T00:00:01+00:00",
        )

        self.assertEqual(updated["gate_status"], "review_passed")
        self.assertEqual(json.loads(updated["verification_json"])["status"], "passed")
        self.assertEqual(updated["acceptance_status"], "accepted")
        self.assertEqual(updated["accepted_at"], "2026-01-01T00:00:01+00:00")

    def test_schema_migration_adds_acceptance_columns(self):
        legacy_db = self.root / "legacy.db"
        with sqlite3.connect(legacy_db) as conn:
            conn.execute(
                """
                CREATE TABLE tasks (
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
                    heartbeat_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE messages (
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

        migrated = TrinityBus(legacy_db, allowed_roots=[self.root])
        task = migrated.submit_task("user", "codex", "build it", cwd=self.root)

        self.assertIn("route_json", task)
        self.assertIn("verification_json", task)
        self.assertIn("acceptance_status", task)
        self.assertIn("accepted_at", task)

    def test_await_task_returns_on_completion(self):
        task = self.bus.submit_task("user", "codex", "build it", "implementation", cwd=self.root)
        self.bus.task_for_worker("codex")
        self.bus.finish_worker(task["id"], result="ok")
        result = self.bus.await_task(task["id"], timeout=5)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["result"], "ok")

    def test_await_task_timeout_raises(self):
        task = self.bus.submit_task("user", "codex", "slow task", "implementation", cwd=self.root)
        with self.assertRaises(TimeoutError):
            self.bus.await_task(task["id"], timeout=0.1)

    def test_message_round_trip(self):
        msg = self.bus.send_message("codex", "claude_code", "please review")
        self.assertEqual(msg["read"], 0)
        inbox = self.bus.inbox("claude_code", mark_read=True)
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]["message"], "please review")
        self.assertEqual(self.bus.inbox("claude_code"), [])


if __name__ == "__main__":
    unittest.main()
