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
        task = self.bus.submit_task("user", "codex", "build it", "implementation", cwd=self.root)
        self.assertEqual(task["status"], "queued")
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
