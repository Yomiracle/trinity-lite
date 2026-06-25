import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from trinity_lite import __version__
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

    def test_dispatch_wait_blocks_until_complete(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as tmp:
            root = Path(tmp)
            output = io.StringIO()
            with redirect_stdout(output):
                code = main([
                    "dispatch",
                    "codex",
                    "implement hello world",
                    "--db",
                    str(root / "bus.db"),
                    "--cwd",
                    str(root),
                    "--wait",
                    "--wait-timeout",
                    "5",
                ])
            self.assertEqual(code, 0)
            data = json.loads(output.getvalue())
            self.assertEqual(data["status"], "completed")
            self.assertIn("target_agent", data)
            self.assertEqual(data["target_agent"], "codex")

    def test_dispatch_auto_wait_blocks_until_complete(self):
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
                    "--wait",
                    "--wait-timeout",
                    "5",
                ])
            self.assertEqual(code, 0)
            data = json.loads(output.getvalue())
            self.assertEqual(data["status"], "completed")
            self.assertEqual(data["target_agent"], "qwen_cli")

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

    def test_orchestrate_uses_capability_routes_and_agents(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "qwen_cli": {
                        "mode": "mock",
                        "capabilities": ["code_edit"],
                    },
                    "gemini_cli": {
                        "mode": "mock",
                        "capabilities": ["code_review"],
                    },
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "implementation": {
                        "requires": ["code_edit"],
                        "review_required": True,
                    },
                    "code_review": {
                        "requires": ["code_review"],
                    },
                },
                "opposites": {}
            }), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main([
                    "orchestrate",
                    "implement parser",
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
            text = output.getvalue()
            self.assertIn('"target_agent": "qwen_cli"', text)
            self.assertIn('"target_agent": "gemini_cli"', text)
            self.assertIn('"acceptance_status": "accepted"', text)

    def test_orchestrate_wait_runs_workers_and_completes(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "qwen_cli": {
                        "mode": "mock",
                        "capabilities": ["code_edit"],
                    },
                    "gemini_cli": {
                        "mode": "mock",
                        "capabilities": ["code_review"],
                    },
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "implementation": {
                        "requires": ["code_edit"],
                        "review_required": True,
                    },
                    "code_review": {
                        "requires": ["code_review"],
                    },
                },
                "opposites": {}
            }), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main([
                    "orchestrate",
                    "implement parser",
                    "--db",
                    str(root / "bus.db"),
                    "--cwd",
                    str(root),
                    "--agents",
                    str(agents_path),
                    "--routes",
                    str(routes_path),
                    "--wait",
                    "--wait-timeout",
                    "10",
                ])
            self.assertEqual(code, 0)
            text = output.getvalue()
            self.assertIn('"acceptance_status": "accepted"', text)
            self.assertIn('"verification"', text)
            self.assertIn('"accepted_at"', text)


    def test_demo_command_produces_friendly_output(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as tmp:
            root = Path(tmp)
            output = io.StringIO()
            with redirect_stdout(output):
                code = main([
                    "demo",
                    "--db",
                    str(root / "bus.db"),
                ])
            self.assertEqual(code, 0)
            text = output.getvalue()
            self.assertIn("Trinity Lite Demo", text)
            self.assertIn("Next steps:", text)
            self.assertIn("trinity-lite tasks", text)
            self.assertIn("docs/REAL_AGENTS.md", text)

    def test_version_command_prints_version(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["version"])
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue().strip(), f"trinity-lite {__version__}")

    def test_version_flag_prints_version(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--version"])
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue().strip(), f"trinity-lite {__version__}")

    def test_no_args_shows_banner(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main([])
        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertIn("Trinity Lite", text)
        self.assertIn("Quick demo", text)
        self.assertIn("trinity-lite demo", text)

    def test_help_flag_works(self):
        import sys
        output = io.StringIO()
        with redirect_stdout(output):
            try:
                main(["--help"])
            except SystemExit as e:
                self.assertEqual(e.code, 0)
        text = output.getvalue()
        self.assertIn("demo", text)
        self.assertIn("version", text)


if __name__ == "__main__":
    unittest.main()
