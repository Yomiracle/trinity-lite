import tempfile
import unittest
from pathlib import Path

from trinity_lite.cli import main


class CliTest(unittest.TestCase):
    def test_global_options_work_after_subcommand(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as tmp:
            root = Path(tmp)
            db = root / "bus.db"
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


if __name__ == "__main__":
    unittest.main()
