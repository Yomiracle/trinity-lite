import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

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

    def test_command_adapter_failure_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "codex": {
                        "mode": "command",
                        "command": ["definitely-not-a-real-trinity-lite-command"]
                    }
                }
            }), encoding="utf-8")
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            task = bus.submit_task("user", "codex", "work", cwd=root)
            done = run_once("codex", bus, str(agents_path))
            self.assertEqual(done["id"], task["id"])
            self.assertEqual(done["status"], "failed")
            self.assertIn("executable not found", done["error"])

    def test_memory_error_is_not_swallowed(self):
        class OomAdapter:
            def run(self, task):
                raise MemoryError("oom")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            task = bus.submit_task("user", "codex", "work", cwd=root)
            with patch("trinity_lite.worker.build_adapter", return_value=OomAdapter()):
                with self.assertRaises(MemoryError):
                    run_once("codex", bus)
            self.assertEqual(bus.get_task(task["id"])["status"], "running")


if __name__ == "__main__":
    unittest.main()
