import json
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

    def test_review_flow_no_run_only_queues_primary_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            result = run_review_flow("implement hello", bus, cwd=str(root), run_workers=False)
            self.assertEqual(result["primary_task"]["target_agent"], "codex")
            self.assertEqual(result["primary_task"]["status"], "queued")
            self.assertIsNone(result["review_task"])
            self.assertEqual(result["acceptance_status"], "queued")


if __name__ == "__main__":
    unittest.main()
