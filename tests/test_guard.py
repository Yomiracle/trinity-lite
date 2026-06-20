import tempfile
import unittest
from pathlib import Path

from trinity_lite.guard import GuardError, ensure_inside_roots, redact_secrets, scan_public_tree


class GuardTest(unittest.TestCase):
    def test_redacts_likely_secrets(self):
        fake_value = "s" + "k-" + "abcdefghijklmnopqrstuvwxyz"
        text = "OPENAI_" + "API" + "_KEY" + "=" + fake_value
        self.assertNotIn(fake_value, redact_secrets(text))

    def test_does_not_redact_github_actions_oidc_permission(self):
        text = "permissions:\n  id-token: write\n"
        self.assertEqual(text, redact_secrets(text))

    def test_redacts_env_style_secret_names(self):
        text = "SERVICE_" + "TOKEN=public-looking-but-sensitive"
        self.assertEqual("[REDACTED]", redact_secrets(text))

    def test_scan_public_tree_blocks_private_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_value = "s" + "k-" + "abcdefghijklmnopqrstuvwxyz"
            (root / ".env").write_text("TO" + "KEN=" + fake_value, encoding="utf-8")
            (root / "README.md").write_text("hello", encoding="utf-8")
            issues = scan_public_tree(root)
            self.assertTrue(any("blocked runtime/private file" in i for i in issues))
            self.assertTrue(any("possible secret" in i for i in issues))

    def test_scan_public_tree_blocks_retired_runtime_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "codeproxy.pid").write_text("123", encoding="utf-8")
            (root / "trinity_learn.db-wal").write_text("", encoding="utf-8")
            issues = scan_public_tree(root)
            self.assertTrue(any("codeproxy.pid" in i for i in issues))
            self.assertTrue(any("trinity_learn.db-wal" in i for i in issues))

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

    def test_scan_public_tree_does_not_follow_directory_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as external:
            root = Path(tmp)
            outside = Path(external)
            fake_value = "s" + "k-" + "abcdefghijklmnopqrstuvwxyz"
            (outside / "secret.txt").write_text("TO" + "KEN=" + fake_value, encoding="utf-8")
            try:
                (root / "linked_dir").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("symlinks are not available on this filesystem")
            issues = scan_public_tree(root)
            self.assertTrue(any("symlink is not allowed" in i for i in issues))
            self.assertFalse(any("possible secret" in i for i in issues))

    def test_scan_public_tree_skips_pycache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "__pycache__"
            cache.mkdir()
            (cache / "module.pyc").write_bytes(b"\x00\x01not-text")
            self.assertEqual(scan_public_tree(root), [])

    def test_ensure_inside_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child"
            child.mkdir()
            self.assertEqual(ensure_inside_roots(child, [root]), child.resolve())
            with self.assertRaises(GuardError):
                ensure_inside_roots("/", [root])


if __name__ == "__main__":
    unittest.main()
