import tempfile
import unittest
from pathlib import Path

from trinity_lite.bus import TrinityBus
from trinity_lite.worker import run_once


class WorkerTest(unittest.TestCase):
    def test_mock_worker_completes_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            task = bus.submit_task("user", "codex", "implement hello", cwd=root)
            done = run_once("codex", bus)
            self.assertEqual(done["id"], task["id"])
            self.assertEqual(done["status"], "completed")
            self.assertIn("[mock:codex]", done["result"])

    def test_missing_configured_agent_fails_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            task = bus.submit_task("user", "unknown", "work", cwd=root)
            done = run_once("unknown", bus)
            self.assertEqual(done["id"], task["id"])
            self.assertEqual(done["status"], "failed")
            self.assertIn("agent not configured", done["error"])


if __name__ == "__main__":
    unittest.main()
