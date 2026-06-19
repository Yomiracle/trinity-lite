import tempfile
import unittest
from pathlib import Path

from trinity_lite.guard import redact_secrets, scan_public_tree


class GuardTest(unittest.TestCase):
    def test_redacts_likely_secrets(self):
        fake_value = "s" + "k-" + "abcdefghijklmnopqrstuvwxyz"
        text = "OPENAI_" + "API" + "_KEY" + "=" + fake_value
        self.assertNotIn(fake_value, redact_secrets(text))

    def test_scan_public_tree_blocks_private_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_value = "s" + "k-" + "abcdefghijklmnopqrstuvwxyz"
            (root / ".env").write_text("TO" + "KEN=" + fake_value, encoding="utf-8")
            (root / "README.md").write_text("hello", encoding="utf-8")
            issues = scan_public_tree(root)
            self.assertTrue(any("blocked runtime/private file" in i for i in issues))
            self.assertTrue(any("possible secret" in i for i in issues))

    def test_scan_public_tree_blocks_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.md"
            target.write_text("safe", encoding="utf-8")
            try:
                (root / "linked.md").symlink_to(target)
            except OSError:
                self.skipTest("symlinks are not available on this filesystem")
            issues = scan_public_tree(root)
            self.assertTrue(any("symlink is not allowed" in i for i in issues))


if __name__ == "__main__":
    unittest.main()
