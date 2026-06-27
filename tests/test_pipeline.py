"""Tests for pipeline orchestration."""

import json
import tempfile
import unittest
from pathlib import Path

from trinity_lite.bus import TrinityBus
from trinity_lite.pipeline import (
    load_pipeline,
    resolve_step_prompt,
    run_pipeline,
)


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=str(Path.home()))
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_yaml(self, name, content):
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return str(path)

    def test_load_valid_pipeline(self):
        yaml_text = "name: test-pipeline\nsteps:\n  - id: step1\n    agent: codex\n    task_type: implementation\n    prompt_template: 'Implement: {task}'\n"
        yaml_path = self._write_yaml("test.yaml", yaml_text)
        p = load_pipeline(yaml_path)
        self.assertEqual(p["name"], "test-pipeline")
        self.assertEqual(len(p["steps"]), 1)
        self.assertEqual(p["steps"][0]["id"], "step1")

    def test_load_invalid_yaml_raises(self):
        json_path = self._write_yaml("bad.json", "not valid json{{{")
        with self.assertRaises(ValueError):
            load_pipeline(json_path)

    def test_missing_required_field_raises(self):
        yaml_text = "name: bad\nsteps:\n  - id: step1\n    task_type: implementation\n    prompt_template: 'ok'\n"
        yaml_path = self._write_yaml("bad.yaml", yaml_text)
        with self.assertRaises(ValueError):
            load_pipeline(yaml_path)

    def test_empty_steps_raises(self):
        yaml_path = self._write_yaml("empty.yaml", "name: empty\nsteps: []")
        with self.assertRaises(ValueError):
            load_pipeline(yaml_path)

    def test_duplicate_step_ids_raises(self):
        yaml_text = "name: dup\nsteps:\n  - id: step1\n    agent: codex\n    task_type: implementation\n    prompt_template: 'ok'\n  - id: step1\n    agent: codex\n    task_type: implementation\n    prompt_template: 'ok'\n"
        yaml_path = self._write_yaml("dup.yaml", yaml_text)
        with self.assertRaises(ValueError):
            load_pipeline(yaml_path)

    def test_unknown_step_reference_raises(self):
        yaml_text = "name: badref\nsteps:\n  - id: step1\n    agent: codex\n    task_type: implementation\n    prompt_template: 'Result: {steps.nonexistent.result}'\n"
        yaml_path = self._write_yaml("badref.yaml", yaml_text)
        with self.assertRaises(ValueError):
            load_pipeline(yaml_path)

    def test_prompt_template_rendering_task_only(self):
        step = {"prompt_template": "Do: {task}"}
        result = resolve_step_prompt(step, "write tests", {})
        self.assertEqual(result, "Do: write tests")

    def test_prompt_template_rendering_with_step_result(self):
        step = {"prompt_template": "Result was: {steps.step1.result}"}
        step_results = {"step1": {"result": "all done", "status": "completed"}}
        result = resolve_step_prompt(step, "task", step_results)
        self.assertEqual(result, "Result was: all done")

    def test_prompt_template_rendering_with_missing_step(self):
        step = {"prompt_template": "Got: {steps.missing.result}"}
        result = resolve_step_prompt(step, "task", {})
        self.assertEqual(result, "Got: ")

    def test_prompt_template_rendering_with_error(self):
        step = {"prompt_template": "Error: {steps.step1.result}"}
        step_results = {"step1": {"error": "failed hard", "status": "failed"}}
        result = resolve_step_prompt(step, "task", step_results)
        self.assertEqual(result, "Error: failed hard")

    def test_run_single_step_pipeline(self):
        bus = TrinityBus(self.root / "bus.db", allowed_roots=[self.root])
        pipeline = {
            "name": "test-single",
            "steps": [
                {"id": "implement", "agent": "codex", "task_type": "implementation",
                 "prompt_template": "Implement: {task}"}
            ],
        }
        result = run_pipeline(pipeline, "hello world", bus, cwd=str(self.root))
        self.assertEqual(result["pipeline_name"], "test-single")
        self.assertEqual(result["overall_status"], "completed")
        self.assertEqual(len(result["steps"]), 1)
        self.assertEqual(result["steps"][0]["status"], "completed")

    def test_run_two_step_pipeline(self):
        bus = TrinityBus(self.root / "bus.db", allowed_roots=[self.root])
        pipeline = {
            "name": "test-two",
            "steps": [
                {"id": "implement", "agent": "codex", "task_type": "implementation",
                 "prompt_template": "Implement: {task}"},
                {"id": "review", "agent": "claude_code", "task_type": "code_review",
                 "prompt_template": "Review: {task}\nResult: {steps.implement.result}"},
            ],
        }
        result = run_pipeline(pipeline, "hello", bus, cwd=str(self.root))
        self.assertEqual(result["overall_status"], "completed")
        self.assertEqual(len(result["steps"]), 2)
        self.assertEqual(result["steps"][0]["status"], "completed")
        self.assertEqual(result["steps"][1]["status"], "completed")

    def test_pipeline_step_results_accessible(self):
        bus = TrinityBus(self.root / "bus.db", allowed_roots=[self.root])
        pipeline = {
            "name": "test-ref",
            "steps": [
                {"id": "step1", "agent": "codex", "task_type": "implementation",
                 "prompt_template": "Task: {task}"},
                {"id": "step2", "agent": "claude_code", "task_type": "code_review",
                 "prompt_template": "Previous result was: {steps.step1.result}"},
            ],
        }
        result = run_pipeline(pipeline, "check refs", bus, cwd=str(self.root))
        self.assertEqual(result["overall_status"], "completed")
        step2 = bus.get_task(result["steps"][1]["task_id"])
        self.assertIn("Previous result was:", step2["prompt"])

    def test_pipeline_no_run_workers(self):
        bus = TrinityBus(self.root / "bus.db", allowed_roots=[self.root])
        pipeline = {
            "name": "test-no-run",
            "steps": [
                {"id": "step1", "agent": "codex", "task_type": "implementation",
                 "prompt_template": "{task}"}
            ],
        }
        result = run_pipeline(pipeline, "stuff", bus, cwd=str(self.root), run_workers=False)
        self.assertEqual(result["overall_status"], "queued")

    def test_pipeline_fail_fast(self):
        bus = TrinityBus(self.root / "bus.db", allowed_roots=[self.root])
        pipeline = {
            "name": "test-fail",
            "steps": [
                {"id": "step1", "agent": "no_such_agent", "task_type": "implementation",
                 "prompt_template": "{task}"},
                {"id": "step2", "agent": "codex", "task_type": "implementation",
                 "prompt_template": "{task}"},
            ],
        }
        result = run_pipeline(pipeline, "stuff", bus, cwd=str(self.root))
        self.assertEqual(result["overall_status"], "failed")
        self.assertEqual(len(result["steps"]), 1)

    def test_cli_orchestrate_with_pipeline_flag(self):
        import io as _io
        import json as _json
        from contextlib import redirect_stdout as _redirect_stdout
        from trinity_lite.cli import main
        yaml_text = "name: cli-pipe\nsteps:\n  - id: step1\n    agent: codex\n    task_type: implementation\n    prompt_template: 'ok'\n"
        pipeline_path = self._write_yaml("cli_test.yaml", yaml_text)
        output = _io.StringIO()
        with _redirect_stdout(output):
            code = main([
                "orchestrate",
                "test task",
                "--pipeline", pipeline_path,
                "--db", str(self.root / "cli_bus.db"),
                "--cwd", str(self.root),
            ])
        self.assertEqual(code, 0)
        data = _json.loads(output.getvalue())
        self.assertEqual(data["pipeline_name"], "cli-pipe")
        self.assertEqual(data["overall_status"], "completed")

    def test_cli_orchestrate_with_pipeline_wait_flag(self):
        import io as _io
        import json as _json
        from contextlib import redirect_stdout as _redirect_stdout
        from trinity_lite.cli import main
        yaml_text = "name: cli-pipe\nsteps:\n  - id: step1\n    agent: codex\n    task_type: implementation\n    prompt_template: 'ok'\n"
        pipeline_path = self._write_yaml("cli_wait_test.yaml", yaml_text)
        output = _io.StringIO()
        with _redirect_stdout(output):
            code = main([
                "orchestrate",
                "test task",
                "--pipeline", pipeline_path,
                "--db", str(self.root / "cli_wait_bus.db"),
                "--cwd", str(self.root),
                "--wait",
                "--wait-timeout", "10",
            ])
        self.assertEqual(code, 0)
        data = _json.loads(output.getvalue())
        self.assertEqual(data["pipeline_name"], "cli-pipe")
        self.assertEqual(data["overall_status"], "completed")


if __name__ == "__main__":
    unittest.main()
