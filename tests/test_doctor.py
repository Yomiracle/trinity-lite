import socket
import json
import tempfile
import unittest
from pathlib import Path

from trinity_lite.bus import TrinityBus
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
            details = {check["name"]: check for check in report["checks"]}
            self.assertEqual(details["acceptance_schema"]["detail"], "schema ok")
            self.assertEqual(details["acceptance_consistency"]["detail"], "ok")

    def test_doctor_rejects_inconsistent_acceptance_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            task = bus.submit_task("user", "codex", "build it", cwd=root)
            bus.update_task_evidence(
                task["id"],
                gate_status="review_passed",
                verification_json={"status": "passed", "checks": []},
                acceptance_status="accepted",
                accepted_at=None,
            )

            report = run_doctor(db_path=str(root / "bus.db"))

            self.assertEqual(report["status"], "unhealthy")
            consistency = next(
                check for check in report["checks"]
                if check["name"] == "acceptance_consistency"
            )
            self.assertFalse(consistency["ok"])
            self.assertEqual(consistency["detail"][0]["id"], task["id"])

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

    def test_doctor_validates_capability_config_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "qwen_cli": {
                        "mode": "mock",
                        "roles": ["primary_engineer"],
                        "capabilities": ["code_edit"],
                        "priority": 80,
                    }
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "implementation": {
                        "requires": ["code_edit"],
                        "prefer": ["primary_engineer"],
                    }
                },
                "opposites": {}
            }), encoding="utf-8")
            report = run_doctor(
                db_path=str(root / "bus.db"),
                routes_path=str(routes_path),
                agents_path=str(agents_path),
            )
            self.assertEqual(report["status"], "healthy")

    def test_doctor_rejects_route_to_unknown_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "qwen_cli": {"mode": "mock"}
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "implementation": {"agent": "codex"}
                },
                "opposites": {}
            }), encoding="utf-8")
            report = run_doctor(
                db_path=str(root / "bus.db"),
                routes_path=str(routes_path),
                agents_path=str(agents_path),
            )
            self.assertEqual(report["status"], "unhealthy")
            routes = next(check for check in report["checks"] if check["name"] == "routes")
            self.assertTrue(any("unknown agent" in issue for issue in routes["detail"]))

    def test_doctor_rejects_unresolvable_capability_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "writer": {
                        "mode": "mock",
                        "capabilities": ["documentation"],
                    }
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "implementation": {"requires": ["code_edit"]}
                },
                "opposites": {}
            }), encoding="utf-8")
            report = run_doctor(
                db_path=str(root / "bus.db"),
                routes_path=str(routes_path),
                agents_path=str(agents_path),
            )
            self.assertEqual(report["status"], "unhealthy")
            routes = next(check for check in report["checks"] if check["name"] == "routes")
            self.assertTrue(any("cannot resolve" in issue for issue in routes["detail"]))

    def test_doctor_rejects_bad_opposites_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "qwen_cli": {"mode": "mock"},
                    "gemini_cli": {"mode": "mock"},
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "code_review": {"agent": "opposite"}
                },
                "opposites": {
                    "qwen_cli": "missing_reviewer"
                }
            }), encoding="utf-8")
            report = run_doctor(
                db_path=str(root / "bus.db"),
                routes_path=str(routes_path),
                agents_path=str(agents_path),
            )
            self.assertEqual(report["status"], "unhealthy")
            routes = next(check for check in report["checks"] if check["name"] == "routes")
            self.assertTrue(any("unknown target agent" in issue for issue in routes["detail"]))

    def test_doctor_rejects_opposite_route_without_opposites(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "qwen_cli": {"mode": "mock"}
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "code_review": {"agent": "opposite"}
                },
                "opposites": {}
            }), encoding="utf-8")
            report = run_doctor(
                db_path=str(root / "bus.db"),
                routes_path=str(routes_path),
                agents_path=str(agents_path),
            )
            self.assertEqual(report["status"], "unhealthy")
            routes = next(check for check in report["checks"] if check["name"] == "routes")
            self.assertTrue(any("no opposites" in issue for issue in routes["detail"]))

    def test_doctor_rejects_bad_agent_field_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "bad": {
                        "mode": "mock",
                        "capabilities": {"code_edit": True},
                    }
                }
            }), encoding="utf-8")
            report = run_doctor(db_path=str(root / "bus.db"), agents_path=str(agents_path))
            self.assertEqual(report["status"], "unhealthy")
            agents = next(check for check in report["checks"] if check["name"] == "agents")
            self.assertTrue(any("capabilities" in issue for issue in agents["detail"]))

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
