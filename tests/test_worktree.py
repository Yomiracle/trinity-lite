import io
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from trinity_lite.cli import main
from trinity_lite.worktree import (
    WorktreeError,
    cleanup_worktree,
    create_worktree,
    diff_worktree,
    list_managed_worktrees,
    repo_root,
)


def _git(args, cwd):
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        shell=False,
        check=True,
    )


@unittest.skipIf(shutil.which("git") is None, "git executable not available")
class WorktreeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        _git(["init"], self.repo)
        _git(["config", "user.email", "trinity-lite@example.invalid"], self.repo)
        _git(["config", "user.name", "Trinity Lite Tests"], self.repo)
        (self.repo / "README.md").write_text("hello\n", encoding="utf-8")
        _git(["add", "README.md"], self.repo)
        _git(["commit", "-m", "initial"], self.repo)
        self.worktree_root = self.root / "state" / "worktrees"

    def tearDown(self):
        self.temp.cleanup()

    def test_repo_root_rejects_non_git_directory(self):
        non_repo = self.root / "plain"
        non_repo.mkdir()
        with self.assertRaises(WorktreeError):
            repo_root(non_repo)

    def test_create_list_diff_and_cleanup_worktree(self):
        created = create_worktree(
            "fix parser bug",
            repo_path=self.repo,
            agent_id="codex",
            task_id="task123",
            worktree_root=self.worktree_root,
        )

        worktree_path = Path(created["worktree_path"])
        self.assertTrue(worktree_path.exists())
        self.assertEqual(created["task_id"], "task123")
        self.assertEqual(created["agent_id"], "codex")
        self.assertEqual(created["branch"], "trinity/task123/codex")

        managed = list_managed_worktrees(self.worktree_root)
        self.assertEqual(len(managed), 1)
        self.assertTrue(managed[0]["exists"])

        (worktree_path / "README.md").write_text("hello\nupdated\n", encoding="utf-8")
        (worktree_path / "new_file.txt").write_text("new\n", encoding="utf-8")
        diff = diff_worktree("task123", worktree_root=self.worktree_root)

        self.assertEqual(diff["task_id"], "task123")
        self.assertIn("README.md", diff["stat"])
        self.assertIn("README.md", diff["patch"])
        self.assertIn("new_file.txt", diff["untracked_files"])
        self.assertIn("M README.md", diff["status"])

        cleaned = cleanup_worktree("task123", worktree_root=self.worktree_root, force=True)
        self.assertTrue(cleaned["removed"])
        self.assertTrue(cleaned["metadata_removed"])
        self.assertFalse(worktree_path.exists())
        self.assertFalse(worktree_path.parent.exists())
        self.assertEqual(list_managed_worktrees(self.worktree_root), [])
        self.assertEqual(list(self.worktree_root.iterdir()), [])

    def test_duplicate_task_id_is_rejected(self):
        create_worktree(
            "first",
            repo_path=self.repo,
            agent_id="codex",
            task_id="dup",
            worktree_root=self.worktree_root,
        )
        with self.assertRaises(WorktreeError):
            create_worktree(
                "second",
                repo_path=self.repo,
                agent_id="codex",
                task_id="dup",
                worktree_root=self.worktree_root,
            )

    def test_cli_worktree_round_trip(self):
        output = io.StringIO()
        db = self.root / "bus.db"
        with redirect_stdout(output):
            code = main([
                "worktree",
                "create",
                "write tests",
                "--db",
                str(db),
                "--repo",
                str(self.repo),
                "--agent",
                "codex",
                "--task-id",
                "cli123",
                "--worktree-root",
                str(self.worktree_root),
            ])
        self.assertEqual(code, 0)
        created = json.loads(output.getvalue())
        worktree_path = Path(created["worktree_path"])
        self.assertTrue(worktree_path.exists())
        self.assertFalse(db.exists())

        (worktree_path / "README.md").write_text("cli change\n", encoding="utf-8")

        output = io.StringIO()
        with redirect_stdout(output):
            code = main([
                "worktree",
                "diff",
                "cli123",
                "--db",
                str(self.root / "bus.db"),
                "--worktree-root",
                str(self.worktree_root),
                "--stat-only",
            ])
        self.assertEqual(code, 0)
        diff = json.loads(output.getvalue())
        self.assertIn("README.md", diff["stat"])
        self.assertEqual(diff["patch"], "")

        output = io.StringIO()
        with redirect_stdout(output):
            code = main([
                "worktree",
                "cleanup",
                "cli123",
                "--db",
                str(self.root / "bus.db"),
                "--worktree-root",
                str(self.worktree_root),
                "--force",
            ])
        self.assertEqual(code, 0)
        cleaned = json.loads(output.getvalue())
        self.assertTrue(cleaned["removed"])


if __name__ == "__main__":
    unittest.main()
