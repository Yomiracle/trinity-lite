import os, signal, tempfile, time, unittest, json
from pathlib import Path
from unittest.mock import patch

from trinity_lite.bus import TrinityBus
from trinity_lite.worker import (
    run_once, run_loop, _acquire_pid_file, _cleanup_pid_file,
    _check_existing_pid, _read_pid_file, _stop_flag,
    _install_signal_handlers, _default_pid_path,
)


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

    # ── New daemon tests ──

    def test_run_loop_stop_flag(self):
        """Start loop, set stop_flag, verify exits cleanly."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            _stop_flag.clear()
            # Set stop flag after a short delay in a separate thread
            import threading
            def set_stop():
                time.sleep(0.15)
                _stop_flag.set()
            t = threading.Thread(target=set_stop)
            t.start()
            exit_code = run_loop("codex", bus, poll_seconds=0.05)
            t.join()
            self.assertEqual(exit_code, 0)

    def test_pid_file_creation(self):
        """Verify PID file created with correct contents."""
        with tempfile.TemporaryDirectory() as tmp:
            pid_path = Path(tmp) / "test.pid"
            _acquire_pid_file(pid_path)
            self.assertTrue(pid_path.exists())
            pid = int(pid_path.read_text().strip())
            self.assertEqual(pid, os.getpid())
            _cleanup_pid_file(pid_path)

    def test_pid_file_cleanup_on_exit(self):
        """Verify PID file created during daemon loop and cleanup works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pid_path = Path(tmp) / "cleanup_test.pid"
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            _stop_flag.clear()
            import threading
            def set_stop():
                time.sleep(0.15)
                _stop_flag.set()
            t = threading.Thread(target=set_stop)
            t.start()
            exit_code = run_loop("codex", bus, poll_seconds=0.05, pid_file=pid_path)
            t.join()
            self.assertEqual(exit_code, 0)
            # PID file was created
            self.assertTrue(pid_path.exists())
            # Manually verify cleanup works (atexit fires at process exit)
            _cleanup_pid_file(pid_path)
            self.assertFalse(pid_path.exists())

    def test_duplicate_daemon_prevented(self):
        """Verify second attempt to acquire PID raises error."""
        with tempfile.TemporaryDirectory() as tmp:
            pid_path = Path(tmp) / "dup.pid"
            # Write our own PID first
            _acquire_pid_file(pid_path)
            self.assertTrue(pid_path.exists())
            # Second attempt should raise
            with self.assertRaises(RuntimeError):
                _check_existing_pid(pid_path)
            _cleanup_pid_file(pid_path)

    def test_stale_pid_cleanup(self):
        """Write fake PID, verify it's treated as stale and can be re-acquired."""
        with tempfile.TemporaryDirectory() as tmp:
            pid_path = Path(tmp) / "stale.pid"
            # Write a PID that doesn't exist
            pid_path.write_text("99999")
            # Should be treated as stale (None returned)
            result = _check_existing_pid(pid_path)
            self.assertIsNone(result)

    def test_read_pid_file(self):
        """Test _read_pid_file returns correct PID."""
        with tempfile.TemporaryDirectory() as tmp:
            pid_path = Path(tmp) / "read.pid"
            pid_path.write_text("42")
            self.assertEqual(_read_pid_file(pid_path), 42)
            # Corrupt file
            pid_path.write_text("not_a_pid")
            self.assertIsNone(_read_pid_file(pid_path))
            # Missing file
            self.assertIsNone(_read_pid_file(Path(tmp) / "nonexistent.pid"))

    def test_default_pid_path(self):
        """Test default PID path resolution."""
        path = _default_pid_path("codex")
        self.assertIn(".trinity", str(path))
        self.assertIn("workers", str(path))
        self.assertTrue(str(path).endswith("codex.pid"))


if __name__ == "__main__":
    unittest.main()
