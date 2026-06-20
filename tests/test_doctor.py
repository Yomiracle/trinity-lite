import socket
import tempfile
import unittest
from pathlib import Path

from trinity_lite.doctor import run_doctor


class DoctorTest(unittest.TestCase):
    def test_doctor_healthy_on_clean_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            state = root / "state"
            repo.mkdir()
            state.mkdir()
            report = run_doctor(db_path=str(state / "bus.db"), scan_root=str(repo))
            self.assertEqual(report["status"], "healthy")

    def test_doctor_unhealthy_on_private_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            state = root / "state"
            repo.mkdir()
            state.mkdir()
            (repo / ".env").write_text("empty example", encoding="utf-8")
            report = run_doctor(db_path=str(state / "bus.db"), scan_root=str(repo))
            self.assertEqual(report["status"], "unhealthy")

    def test_runtime_checks_require_metrics_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            runtime = root / "runtime"
            state.mkdir()
            runtime.mkdir()
            report = run_doctor(db_path=str(state / "bus.db"), runtime_root=str(runtime))
            self.assertEqual(report["status"], "unhealthy")
            details = {check["name"]: check["detail"] for check in report["checks"]}
            self.assertIn("missing", details["runtime_metrics"])

    def test_runtime_checks_reject_retired_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            runtime = root / "runtime"
            state.mkdir()
            runtime.mkdir()
            (runtime / "metrics.jsonl").write_text("", encoding="utf-8")
            (runtime / "codeproxy.pid").write_text("123", encoding="utf-8")
            (runtime / "trinity_learn.db-wal").write_text("", encoding="utf-8")
            report = run_doctor(db_path=str(state / "bus.db"), runtime_root=str(runtime))
            self.assertEqual(report["status"], "unhealthy")
            details = {check["name"]: check["detail"] for check in report["checks"]}
            self.assertIn("codeproxy.pid", details["retired_runtime_artifacts"])
            self.assertIn("trinity_learn.db-wal", details["retired_runtime_artifacts"])

    def test_runtime_checks_healthy_when_metrics_exists_and_retired_artifacts_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            runtime = root / "runtime"
            state.mkdir()
            runtime.mkdir()
            (runtime / "metrics.jsonl").write_text("", encoding="utf-8")
            report = run_doctor(db_path=str(state / "bus.db"), runtime_root=str(runtime))
            self.assertEqual(report["status"], "healthy")

    def test_retired_port_check_rejects_listener(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            state.mkdir()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(("127.0.0.1", 0))
                except PermissionError:
                    self.skipTest("local socket bind is not allowed in this environment")
                sock.listen(1)
                port = sock.getsockname()[1]
                report = run_doctor(db_path=str(state / "bus.db"), retired_ports=[port])
            self.assertEqual(report["status"], "unhealthy")
            details = {check["name"]: check["detail"] for check in report["checks"]}
            self.assertIn("listening", details[f"retired_port:{port}"])

    def test_retired_port_check_rejects_invalid_port(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            state.mkdir()
            report = run_doctor(db_path=str(state / "bus.db"), retired_ports=[70000])
            self.assertEqual(report["status"], "unhealthy")
            details = {check["name"]: check["detail"] for check in report["checks"]}
            self.assertIn("invalid", details["retired_port:70000"])


if __name__ == "__main__":
    unittest.main()
