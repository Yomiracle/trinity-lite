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


if __name__ == "__main__":
    unittest.main()
