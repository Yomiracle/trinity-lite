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

    def test_message_round_trip(self):
        msg = self.bus.send_message("codex", "claude_code", "please review")
        self.assertEqual(msg["read"], 0)
        inbox = self.bus.inbox("claude_code", mark_read=True)
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]["message"], "please review")
        self.assertEqual(self.bus.inbox("claude_code"), [])


if __name__ == "__main__":
    unittest.main()
