import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from trinity_lite.cli import main


class CliTest(unittest.TestCase):
    def test_global_options_work_after_subcommand(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as tmp:
            root = Path(tmp)
            db = root / "bus.db"
            output = io.StringIO()
            with redirect_stdout(output):
                code = main([
                    "dispatch-auto",
                    "implement a parser",
                    "--db",
                    str(db),
                    "--cwd",
                    str(root),
                ])
                self.assertEqual(code, 0)
                code = main(["worker", "codex", "--once", "--db", str(db)])
                self.assertEqual(code, 0)

    def test_route_errors_are_structured(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["route", "review this patch"])
        self.assertEqual(code, 2)
        self.assertIn('"error"', output.getvalue())

    def test_doctor_accepts_runtime_hygiene_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / "runtime"
            runtime.mkdir()
            (runtime / "metrics.jsonl").write_text("", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main([
                    "doctor",
                    "--db",
                    str(root / "bus.db"),
                    "--runtime-root",
                    str(runtime),
                    "--retired-port",
                    "70000",
                ])
            self.assertEqual(code, 0)
            self.assertIn('"runtime_metrics"', output.getvalue())
            self.assertIn('"retired_port:70000"', output.getvalue())

    def test_dispatch_auto_uses_capability_routes_and_agents(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as tmp:
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
            output = io.StringIO()
            with redirect_stdout(output):
                code = main([
                    "dispatch-auto",
                    "implement a parser",
                    "--db",
                    str(root / "bus.db"),
                    "--cwd",
                    str(root),
                    "--agents",
                    str(agents_path),
                    "--routes",
                    str(routes_path),
                ])
            self.assertEqual(code, 0)
            self.assertIn('"target_agent": "qwen_cli"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
