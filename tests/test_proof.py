import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from trinity_lite.bus import TrinityBus
from trinity_lite.cli import main
from trinity_lite.orchestrator import run_review_flow
from trinity_lite.proof import (
    PROOF_BUNDLE_VERSION,
    build_proof_bundle,
    export_proof_bundle,
    render_markdown,
)


class ProofBundleTest(unittest.TestCase):
    def _full_flow(self, root: Path) -> tuple[TrinityBus, dict]:
        bus = TrinityBus(root / "bus.db", allowed_roots=[root])
        result = run_review_flow("implement hello", bus, cwd=str(root))
        return bus, result

    def test_full_evidence_chain_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus, result = self._full_flow(root)
            bundle = build_proof_bundle(bus, result["primary_task"]["id"])

            self.assertEqual(bundle["proof_bundle_version"], PROOF_BUNDLE_VERSION)
            self.assertEqual(bundle["task"]["id"], result["primary_task"]["id"])
            self.assertEqual(bundle["route"]["agent"], "codex")
            self.assertEqual(bundle["work"]["status"], "completed")
            self.assertIsNotNone(bundle["work"]["result"])
            self.assertEqual(bundle["review"]["task_id"], result["review_task"]["id"])
            self.assertEqual(bundle["review"]["task"]["target_agent"], "claude_code")
            self.assertEqual(bundle["verification"]["status"], "passed")
            self.assertEqual(bundle["acceptance"]["status"], "accepted")
            self.assertIsNotNone(bundle["acceptance"]["accepted_at"])

            stages = [event["stage"] for event in bundle["timeline"]]
            self.assertIn("route", stages)
            self.assertIn("work", stages)
            self.assertIn("review", stages)
            self.assertIn("accept", stages)

    def test_partial_task_marks_missing_stages_as_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            task = bus.submit_task(
                source_agent="user",
                target_agent="codex",
                prompt="queued only",
                cwd=str(root),
            )
            bundle = build_proof_bundle(bus, task["id"])

            self.assertIsNone(bundle["route"])
            self.assertIsNone(bundle["review"])
            self.assertIsNone(bundle["verification"])
            self.assertIsNone(bundle["acceptance"])
            self.assertEqual(bundle["work"]["status"], "queued")
            self.assertIsNone(bundle["work"]["result"])

    def test_missing_task_id_raises_key_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            with self.assertRaises(KeyError):
                build_proof_bundle(bus, "000000000000")

    def test_markdown_renders_all_stage_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus, result = self._full_flow(root)
            bundle = build_proof_bundle(bus, result["primary_task"]["id"])
            markdown = render_markdown(bundle)

            for section in ("## Route", "## Work", "## Review", "## Verification",
                            "## Acceptance", "## Timeline"):
                self.assertIn(section, markdown)
            self.assertIn("| Stage | At | Actor | Detail |", markdown)
            self.assertIn("accepted", markdown)

    def test_markdown_marks_missing_stages_not_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = TrinityBus(root / "bus.db", allowed_roots=[root])
            task = bus.submit_task(
                source_agent="user",
                target_agent="codex",
                prompt="queued only",
                cwd=str(root),
            )
            markdown = render_markdown(build_proof_bundle(bus, task["id"]))
            self.assertIn("_Not recorded._", markdown)

    def test_export_writes_json_and_markdown_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus, result = self._full_flow(root)
            out_dir = root / "bundles"
            task_id = result["primary_task"]["id"]
            summary = export_proof_bundle(bus, task_id, out_dir=out_dir)

            self.assertEqual(summary["task_id"], task_id)
            self.assertEqual(summary["proof_bundle_version"], PROOF_BUNDLE_VERSION)
            json_path = Path(summary["files"]["json"])
            md_path = Path(summary["files"]["md"])
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())

            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(data["proof_bundle_version"], PROOF_BUNDLE_VERSION)
            self.assertEqual(data["task"]["id"], task_id)
            self.assertIn("## Acceptance", md_path.read_text(encoding="utf-8"))

    def test_export_single_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus, result = self._full_flow(root)
            summary = export_proof_bundle(
                bus, result["primary_task"]["id"], out_dir=root, formats=("json",)
            )
            self.assertIn("json", summary["files"])
            self.assertNotIn("md", summary["files"])


class ProofCliTest(unittest.TestCase):
    def test_proof_command_writes_both_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "bus.db"
            bus = TrinityBus(db, allowed_roots=[root])
            result = run_review_flow("implement hello", bus, cwd=str(root))
            task_id = result["primary_task"]["id"]
            out_dir = root / "out"

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["proof", task_id, "--db", str(db), "--out", str(out_dir)])
            self.assertEqual(code, 0)
            data = json.loads(output.getvalue())
            self.assertEqual(data["task_id"], task_id)
            self.assertTrue((out_dir / f"proof-{task_id}.json").exists())
            self.assertTrue((out_dir / f"proof-{task_id}.md").exists())

    def test_proof_command_json_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "bus.db"
            bus = TrinityBus(db, allowed_roots=[root])
            task = bus.submit_task(
                source_agent="user",
                target_agent="codex",
                prompt="queued only",
                cwd=str(root),
            )
            out_dir = root / "out"

            output = io.StringIO()
            with redirect_stdout(output):
                code = main([
                    "proof", task["id"], "--db", str(db),
                    "--out", str(out_dir), "--format", "json",
                ])
            self.assertEqual(code, 0)
            self.assertTrue((out_dir / f"proof-{task['id']}.json").exists())
            self.assertFalse((out_dir / f"proof-{task['id']}.md").exists())

    def test_proof_command_unknown_task_returns_structured_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "bus.db"
            TrinityBus(db, allowed_roots=[root])
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["proof", "000000000000", "--db", str(db), "--out", str(root)])
            self.assertEqual(code, 2)
            self.assertIn('"error"', output.getvalue())
            self.assertFalse((root / "proof-000000000000.json").exists())


if __name__ == "__main__":
    unittest.main()
