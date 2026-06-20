import io
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


if __name__ == "__main__":
    unittest.main()
