import io
import json
import os
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from trinity_lite.cli import main
from trinity_lite.doctor import run_doctor
from trinity_lite.init import (
    AGENT_CLI_PRESETS,
    build_starter_config,
    detect_agent_clis,
    run_init,
)


def _fake_path(dir_path: Path, names: list[str]) -> str:
    """Create executable stubs for the given CLI names in dir_path."""
    for name in names:
        stub = dir_path / name
        stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(dir_path)


class DetectAgentClisTest(unittest.TestCase):
    def test_detects_present_clis(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _fake_path(Path(tmp), ["codex", "claude"])
            with mock.patch.dict(os.environ, {"PATH": path}):
                detected = detect_agent_clis()
            self.assertTrue(detected["codex"].endswith("codex"))
            self.assertTrue(detected["claude_code"].endswith("claude"))
            self.assertIsNone(detected["hermes"])

    def test_detects_nothing_on_empty_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"PATH": str(Path(tmp))}):
                detected = detect_agent_clis()
            self.assertTrue(all(exe is None for exe in detected.values()))
            self.assertEqual(set(detected), set(AGENT_CLI_PRESETS))


class BuildStarterConfigTest(unittest.TestCase):
    def test_detected_agents_use_command_mode(self):
        config = build_starter_config({"codex": "/usr/bin/codex", "claude_code": None, "hermes": None})
        agents = config["agents"]
        self.assertEqual(agents["codex"]["mode"], "command")
        self.assertEqual(agents["codex"]["command"], ["codex", "exec", "-C", "{cwd}", "{prompt}"])
        self.assertEqual(agents["claude_code"]["mode"], "mock")
        self.assertEqual(agents["hermes"]["mode"], "mock")

    def test_commands_are_json_arrays_without_credentials(self):
        config = build_starter_config({agent: f"/usr/bin/{agent}" for agent in AGENT_CLI_PRESETS})
        text = json.dumps(config).lower()
        for spec in config["agents"].values():
            self.assertIsInstance(spec["command"], list)
            self.assertTrue(all(isinstance(part, str) for part in spec["command"]))
        for forbidden in ("api_key", "apikey", "token", "secret", "password"):
            self.assertNotIn(forbidden, text)


class RunInitTest(unittest.TestCase):
    def test_writes_starter_config_with_detected_clis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bin").mkdir()
            path = _fake_path(root / "bin", ["codex"])
            out = root / "agents.local.json"
            with mock.patch.dict(os.environ, {"PATH": path}):
                result = run_init(out_path=str(out))
            self.assertTrue(result["written"])
            self.assertFalse(result["skipped"])
            self.assertFalse(result["mock_only"])
            self.assertEqual([d["agent"] for d in result["detected"]], ["codex"])
            self.assertEqual(result["missing"], ["claude_code", "hermes"])
            config = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(config["agents"]["codex"]["mode"], "command")
            self.assertEqual(config["agents"]["claude_code"]["mode"], "mock")

    def test_mock_only_config_when_no_cli_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "agents.local.json"
            with mock.patch.dict(os.environ, {"PATH": str(root)}):
                result = run_init(out_path=str(out))
            self.assertTrue(result["written"])
            self.assertTrue(result["mock_only"])
            self.assertEqual(result["detected"], [])
            config = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(all(s["mode"] == "mock" for s in config["agents"].values()))

    def test_never_overwrites_existing_config_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "agents.local.json"
            out.write_text('{"agents": {"custom": {"mode": "mock"}}}\n', encoding="utf-8")
            with mock.patch.dict(os.environ, {"PATH": str(Path(tmp))}):
                result = run_init(out_path=str(out))
            self.assertFalse(result["written"])
            self.assertTrue(result["skipped"])
            self.assertIn("exists", result["reason"])
            self.assertIn("custom", out.read_text(encoding="utf-8"))

    def test_force_overwrites_existing_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "agents.local.json"
            out.write_text('{"agents": {"custom": {"mode": "mock"}}}\n', encoding="utf-8")
            with mock.patch.dict(os.environ, {"PATH": str(Path(tmp))}):
                result = run_init(out_path=str(out), force=True)
            self.assertTrue(result["written"])
            self.assertTrue(result["forced"])
            config = json.loads(out.read_text(encoding="utf-8"))
            self.assertNotIn("custom", config["agents"])


class InitCliTest(unittest.TestCase):
    def test_cli_init_writes_config_and_prints_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "agents.local.json"
            output = io.StringIO()
            with mock.patch.dict(os.environ, {"PATH": str(Path(tmp))}):
                with redirect_stdout(output):
                    code = main(["init", "--out", str(out)])
            self.assertEqual(code, 0)
            result = json.loads(output.getvalue())
            self.assertTrue(result["written"])
            self.assertTrue(out.exists())

    def test_cli_init_skips_existing_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "agents.local.json"
            out.write_text("{}", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["init", "--out", str(out)])
            self.assertEqual(code, 0)
            result = json.loads(output.getvalue())
            self.assertTrue(result["skipped"])
            self.assertEqual(out.read_text(encoding="utf-8"), "{}")


class OnboardingDoctorTest(unittest.TestCase):
    def test_run_doctor_marks_levels_on_all_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_doctor(db_path=str(Path(tmp) / "bus.db"))
            self.assertTrue(report["checks"])
            for check in report["checks"]:
                self.assertIn(check["level"], ("blocker", "optional"))
            self.assertEqual(report["blockers_failed"], [])
            self.assertEqual(report["optional_failed"], [])

    def test_onboarding_adds_agent_cli_check_as_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"PATH": str(Path(tmp))}):
                report = run_doctor(db_path=str(Path(tmp) / "bus.db"), onboarding=True)
            cli_check = next(c for c in report["checks"] if c["name"] == "agent_clis")
            self.assertEqual(cli_check["level"], "optional")
            self.assertFalse(cli_check["ok"])
            self.assertIn("hint", cli_check)
            # Optional failure alone does not make onboarding unhealthy.
            self.assertEqual(report["status"], "healthy")
            self.assertEqual(report["blockers_failed"], [])
            self.assertEqual(report["optional_failed"], ["agent_clis"])

    def test_onboarding_unhealthy_only_on_blocker_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            agents_path.write_text(json.dumps({"agents": {"bad": {"mode": "nope"}}}), encoding="utf-8")
            with mock.patch.dict(os.environ, {"PATH": str(root)}):
                report = run_doctor(
                    db_path=str(root / "bus.db"),
                    agents_path=str(agents_path),
                    onboarding=True,
                )
            self.assertEqual(report["status"], "unhealthy")
            self.assertIn("agents", report["blockers_failed"])
            self.assertIn("agent_clis", report["optional_failed"])

    def test_default_doctor_status_unchanged_by_optional_failures(self):
        # Default (non-onboarding) mode keeps the old semantics: any failed
        # check makes the report unhealthy.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / "runtime"
            runtime.mkdir()
            report = run_doctor(db_path=str(root / "bus.db"), runtime_root=str(runtime))
            self.assertEqual(report["status"], "unhealthy")
            self.assertIn("runtime_metrics", report["optional_failed"])

    def test_cli_doctor_onboarding_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Healthy blockers + missing CLIs (optional) -> exit 0.
            output = io.StringIO()
            with mock.patch.dict(os.environ, {"PATH": str(root)}):
                with redirect_stdout(output):
                    code = main(["doctor", "--onboarding", "--db", str(root / "bus.db")])
            self.assertEqual(code, 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["status"], "healthy")

            # Blocker failure -> exit 1.
            bad_agents = root / "agents.json"
            bad_agents.write_text(json.dumps({"agents": {"bad": {"mode": "nope"}}}), encoding="utf-8")
            output = io.StringIO()
            with mock.patch.dict(os.environ, {"PATH": str(root)}):
                with redirect_stdout(output):
                    code = main([
                        "doctor", "--onboarding",
                        "--db", str(root / "bus.db"),
                        "--agents", str(bad_agents),
                    ])
            self.assertEqual(code, 1)
            report = json.loads(output.getvalue())
            self.assertIn("agents", report["blockers_failed"])

    def test_cli_doctor_default_still_exits_zero_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_agents = root / "agents.json"
            bad_agents.write_text(json.dumps({"agents": {"bad": {"mode": "nope"}}}), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main([
                    "doctor",
                    "--db", str(root / "bus.db"),
                    "--agents", str(bad_agents),
                ])
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
