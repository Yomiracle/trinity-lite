import json
import sys
import tempfile
import unittest
from pathlib import Path

from trinity_lite.bus import TrinityBus
from trinity_lite.orchestrator import run_review_flow


class OrchestratorTest(unittest.TestCase):
    def test_review_flow_uses_default_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            result = run_review_flow("implement hello", bus, cwd=str(root))
            self.assertEqual(result["primary_task"]["target_agent"], "codex")
            self.assertEqual(result["primary_task"]["status"], "completed")
            self.assertEqual(result["review_task"]["target_agent"], "claude_code")
            self.assertEqual(result["review_task"]["status"], "completed")
            self.assertEqual(result["acceptance_status"], "accepted")
            self.assertEqual(result["primary_task"]["acceptance_status"], "accepted")
            self.assertEqual(result["primary_task"]["gate_status"], "review_passed")
            self.assertIsNotNone(result["primary_task"]["accepted_at"])
            self.assertEqual(json.loads(result["primary_task"]["verification_json"])["status"], "passed")
            self.assertEqual(json.loads(result["primary_task"]["route_json"])["agent"], "codex")
            self.assertEqual(result["review_task"]["parent_task_id"], result["primary_task"]["id"])

    def test_review_flow_uses_capability_routes(self):
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
                    },
                    "gemini_cli": {
                        "mode": "mock",
                        "roles": ["reviewer"],
                        "capabilities": ["code_review"],
                        "priority": 70,
                    },
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "implementation": {
                        "requires": ["code_edit"],
                        "prefer": ["primary_engineer"],
                        "review_required": True,
                    },
                    "code_review": {
                        "requires": ["code_review"],
                        "prefer": ["reviewer"],
                    },
                },
                "opposites": {}
            }), encoding="utf-8")
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            result = run_review_flow(
                "implement parser",
                bus,
                routes_path=str(routes_path),
                agents_path=str(agents_path),
                cwd=str(root),
            )
            self.assertEqual(result["primary_task"]["target_agent"], "qwen_cli")
            self.assertEqual(result["review_task"]["target_agent"], "gemini_cli")
            self.assertEqual(result["acceptance_status"], "accepted")
            self.assertEqual(result["primary_task"]["gate_status"], "review_passed")

    def test_review_flow_no_run_only_queues_primary_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            result = run_review_flow("implement hello", bus, cwd=str(root), run_workers=False)
            self.assertEqual(result["primary_task"]["target_agent"], "codex")
            self.assertEqual(result["primary_task"]["status"], "queued")
            self.assertIsNone(result["review_task"])
            self.assertEqual(result["acceptance_status"], "queued")
            self.assertEqual(result["primary_task"]["gate_status"], "primary_pending")

    def test_review_attention_blocks_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "codex": {"mode": "mock"},
                    "claude_code": {
                        "mode": "command",
                        "command": [sys.executable, "-c", "print('P1: missing guard')"],
                    },
                }
            }), encoding="utf-8")
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])

            result = run_review_flow(
                "implement parser",
                bus,
                agents_path=str(agents_path),
                cwd=str(root),
            )

            self.assertEqual(result["acceptance_status"], "review_attention")
            self.assertEqual(result["primary_task"]["gate_status"], "review_attention")
            self.assertIsNone(result["primary_task"]["accepted_at"])

    def test_verification_failure_blocks_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])

            result = run_review_flow(
                "implement hello",
                bus,
                cwd=str(root),
                verifier=lambda: {"status": "failed", "checks": [{"name": "custom", "ok": False}]},
            )

            self.assertEqual(result["acceptance_status"], "blocked")
            self.assertEqual(result["primary_task"]["gate_status"], "verification_failed")
            self.assertIsNone(result["primary_task"]["accepted_at"])
            self.assertEqual(json.loads(result["primary_task"]["verification_json"])["status"], "failed")

    def test_custom_verifier_receives_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            seen = {}

            def verifier(context):
                seen["task_id"] = context["task_id"]
                seen["bus_path"] = str(context["bus"].db_path)
                return {"status": "passed", "checks": [{"name": "custom", "ok": True}]}

            result = run_review_flow(
                "implement hello",
                bus,
                cwd=str(root),
                verifier=verifier,
            )

            self.assertEqual(result["acceptance_status"], "accepted")
            self.assertEqual(seen["task_id"], result["primary_task"]["id"])
            self.assertEqual(seen["bus_path"], str(root / "bus.db"))

    def test_custom_verifier_can_accept_bus_and_task_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            seen = {}

            def verifier(verifier_bus, task_id):
                seen["task_id"] = task_id
                seen["task"] = verifier_bus.get_task(task_id)["id"]
                return {"status": "passed", "checks": [{"name": "custom", "ok": True}]}

            result = run_review_flow(
                "implement hello",
                bus,
                cwd=str(root),
                verifier=verifier,
            )

            self.assertEqual(result["acceptance_status"], "accepted")
            self.assertEqual(seen["task_id"], result["primary_task"]["id"])
            self.assertEqual(seen["task"], result["primary_task"]["id"])


if __name__ == "__main__":
    unittest.main()
