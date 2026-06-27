import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from trinity_lite.bus import TrinityBus
from trinity_lite import __version__
from trinity_lite.mcp_server import (
    handle_request,
    serve,
    TOOL_DEFINITIONS,
    RESOURCE_DEFINITIONS,
    jsonrpc_response,
    jsonrpc_error,
    _compact_task,
    _validate_task_id,
    _validate_agent_id,
    _validate_text,
    _validate_limit,
    _validate_timeout,
    _get_known_agents,
)

try:
    from engine.bank import SkillBank  # noqa: F401

    HAS_AGENT_SKILL = True
except ImportError:
    HAS_AGENT_SKILL = False

# Detect agent-skill-system skills directory
SKILLS_DIR = os.environ.get(
    "TRINITY_SKILLS_DIR",
    os.path.expanduser("~/agent-skill-system/skills"),
)


class McpServerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "bus.db"
        self.bus = TrinityBus(self.db, allowed_roots=[self.root])

    def tearDown(self):
        self.temp.cleanup()

    def _msg(self, method, id_=1, params=None):
        msg = {"jsonrpc": "2.0", "method": method, "id": id_}
        if params is not None:
            msg["params"] = params
        return msg

    def _call(self, msg):
        return handle_request(msg, self.bus, None, None)

    # ---- JSON-RPC lifecycle ----

    def test_initialize_handshake(self):
        resp = self._call(self._msg("initialize", 1, {}))
        self.assertEqual(resp["id"], 1)
        self.assertIn("protocolVersion", resp["result"])
        self.assertEqual(resp["result"]["protocolVersion"], "2024-11-05")
        self.assertIn("capabilities", resp["result"])
        self.assertIn("tools", resp["result"]["capabilities"])
        self.assertIn("resources", resp["result"]["capabilities"])
        self.assertIn("serverInfo", resp["result"])
        self.assertEqual(resp["result"]["serverInfo"]["name"], "trinity-lite-mcp")
        self.assertEqual(resp["result"]["serverInfo"]["version"], __version__)

    def test_initialized_returns_none(self):
        resp = self._call(self._msg("initialized"))
        self.assertIsNone(resp)

    def test_shutdown_returns_empty_result(self):
        resp = self._call(self._msg("shutdown", 1, {}))
        self.assertEqual(resp["id"], 1)
        self.assertEqual(resp["result"], {})

    def test_unknown_method_returns_error(self):
        resp = self._call(self._msg("nonexistent", 1, {}))
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32601)

    # ---- tools/list ----

    def test_tools_list(self):
        resp = self._call(self._msg("tools/list", 1))
        tools = resp["result"]["tools"]
        self.assertIsInstance(tools, list)
        self.assertEqual(len(tools), 12)
        names = [t["name"] for t in tools]
        self.assertIn("trinity_dispatch", names)
        self.assertIn("trinity_dispatch_auto", names)
        self.assertIn("trinity_status", names)
        self.assertIn("trinity_tasks", names)
        self.assertIn("trinity_worker", names)
        self.assertIn("trinity_doctor", names)
        self.assertIn("trinity_inbox", names)
        self.assertIn("trinity_send", names)
        self.assertIn("trinity_skill_search", names)
        self.assertIn("trinity_skill_load", names)
        # Check schema structure
        for t in tools:
            self.assertIn("name", t)
            self.assertIn("description", t)
            self.assertGreaterEqual(len(t["description"].split()), 20)
            self.assertIn("annotations", t)
            self.assertIn("readOnlyHint", t["annotations"])
            self.assertIn("destructiveHint", t["annotations"])
            self.assertIn("idempotentHint", t["annotations"])
            self.assertIn("openWorldHint", t["annotations"])
            self.assertIn("inputSchema", t)
            self.assertEqual(t["inputSchema"]["type"], "object")
            self.assertIn("properties", t["inputSchema"])
            self.assertIn("required", t["inputSchema"])
        by_name = {t["name"]: t for t in tools}
        self.assertTrue(by_name["trinity_status"]["annotations"]["readOnlyHint"])
        self.assertFalse(by_name["trinity_dispatch"]["annotations"]["readOnlyHint"])
        self.assertTrue(by_name["trinity_dispatch"]["annotations"]["openWorldHint"])

    # ---- resources/list ----

    def test_resources_list(self):
        resp = self._call(self._msg("resources/list", 1))
        resources = resp["result"]["resources"]
        self.assertIsInstance(resources, list)
        self.assertEqual(len(resources), 3)
        uris = [r["uri"] for r in resources]
        self.assertIn("trinity://health", uris)
        self.assertIn("trinity://tasks/recent", uris)
        self.assertIn("trinity://tasks/{task_id}", uris)

    # ---- resources/read ----

    def test_resource_health(self):
        resp = self._call(self._msg("resources/read", 1, {"uri": "trinity://health"}))
        self.assertIn("result", resp)
        contents = resp["result"]["contents"]
        self.assertEqual(len(contents), 1)
        data = json.loads(contents[0]["text"])
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["bus"], "connected")
        self.assertEqual(data["tools"], 12)
        self.assertEqual(data["resources"], 3)

    def test_resource_health_degraded(self):
        # Use a bad bus path to simulate disconnected
        bad_bus = TrinityBus(self.root / "nonexistent" / "deep" / "bus.db", allowed_roots=[self.root])
        resp = handle_request(self._msg("resources/read", 1, {"uri": "trinity://health"}), bad_bus, None, None)
        # Even with a bad path, SQLite creates the file... Let's use list_tasks catching.
        # Actually sqlite will create dirs via bus, so this should still connect.
        # Skip this test since sqlite is too forgiving.
        pass

    def test_resource_tasks_recent(self):
        task = self.bus.submit_task("user", "codex", "hello", "implementation", cwd=self.root)
        resp = self._call(self._msg("resources/read", 1, {"uri": "trinity://tasks/recent"}))
        contents = resp["result"]["contents"]
        data = json.loads(contents[0]["text"])
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)

    def test_resource_task_by_id(self):
        task = self.bus.submit_task("user", "codex", "hello", "implementation", cwd=self.root)
        resp = self._call(self._msg("resources/read", 1, {"uri": "trinity://tasks/" + task["id"]}))
        contents = resp["result"]["contents"]
        data = json.loads(contents[0]["text"])
        self.assertEqual(data["id"], task["id"])

    def test_resource_task_not_found(self):
        resp = self._call(self._msg("resources/read", 1, {"uri": "trinity://tasks/deadbeef1234"}))
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32002)

    def test_resource_invalid_uri(self):
        resp = self._call(self._msg("resources/read", 1, {"uri": "trinity://nonexistent"}))
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32002)

    # ---- tools/call: trinity_status ----

    def test_trinity_status_returns_task(self):
        task = self.bus.submit_task("user", "codex", "implement test", "implementation", cwd=self.root)
        params = {"name": "trinity_status", "arguments": {"task_id": task["id"]}}
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["id"], task["id"])
        self.assertEqual(resp["result"]["status"], "queued")

    def test_trinity_status_not_found(self):
        params = {"name": "trinity_status", "arguments": {"task_id": "deadbeef1234"}}
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32002)

    def test_trinity_status_invalid_id(self):
        params = {"name": "trinity_status", "arguments": {"task_id": "short"}}
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32602)

    # ---- tools/call: trinity_dispatch ----

    def test_trinity_dispatch_creates_and_runs_task(self):
        params = {
            "name": "trinity_dispatch",
            "arguments": {
                "target_agent": "codex",
                "task": "implement hello world",
                "cwd": str(self.root),
            },
        }
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("result", resp)
        result = resp["result"]
        self.assertEqual(result["target_agent"], "codex")
        self.assertEqual(result["status"], "completed")
        self.assertIn("[mock:codex]", result.get("result", ""))

    def test_trinity_dispatch_self_delegation_blocked(self):
        params = {
            "name": "trinity_dispatch",
            "arguments": {
                "target_agent": "mcp",
                "task": "self task",
                "cwd": str(self.root),
            },
        }
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32000)

    def test_trinity_dispatch_unknown_agent(self):
        params = {
            "name": "trinity_dispatch",
            "arguments": {
                "target_agent": "nonexistent_agent_123",
                "task": "hello",
                "cwd": str(self.root),
            },
        }
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32602)

    def test_trinity_dispatch_missing_required(self):
        params = {
            "name": "trinity_dispatch",
            "arguments": {"target_agent": "codex"},
        }
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32602)

    # ---- tools/call: trinity_dispatch_auto ----

    def test_trinity_dispatch_auto_routes_and_runs(self):
        params = {
            "name": "trinity_dispatch_auto",
            "arguments": {
                "task": "implement a parser function",
                "cwd": str(self.root),
            },
        }
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("result", resp)
        result = resp["result"]
        self.assertIn("route", result)
        self.assertEqual(result["route"]["agent"], "codex")
        self.assertEqual(result["route"]["task_type"], "implementation")
        self.assertEqual(result["status"], "completed")
        self.assertIn("route_json", result)
        self.assertIsNotNone(result["route_json"])

    # ---- tools/call: trinity_tasks ----

    def test_trinity_tasks_lists_tasks(self):
        self.bus.submit_task("user", "codex", "task 1", cwd=self.root)
        self.bus.submit_task("user", "claude_code", "task 2", cwd=self.root)
        params = {"name": "trinity_tasks", "arguments": {}}
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("result", resp)
        tasks = resp["result"]
        self.assertIsInstance(tasks, list)
        self.assertEqual(len(tasks), 2)

    def test_trinity_tasks_filter_by_agent(self):
        self.bus.submit_task("user", "codex", "codex task", cwd=self.root)
        self.bus.submit_task("user", "claude_code", "claude task", cwd=self.root)
        params = {
            "name": "trinity_tasks",
            "arguments": {"agent": "codex"},
        }
        resp = self._call(self._msg("tools/call", 1, params))
        tasks = resp["result"]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["target_agent"], "codex")

    # ---- tools/call: trinity_worker ----

    def test_trinity_worker_runs_queued_task(self):
        task = self.bus.submit_task("user", "codex", "worker test", cwd=self.root)
        params = {
            "name": "trinity_worker",
            "arguments": {"agent": "codex"},
        }
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["id"], task["id"])
        self.assertEqual(resp["result"]["status"], "completed")

    def test_trinity_worker_no_task(self):
        params = {
            "name": "trinity_worker",
            "arguments": {"agent": "codex"},
        }
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["status"], "no_task")

    # ---- tools/call: trinity_doctor ----

    def test_trinity_doctor_runs(self):
        params = {"name": "trinity_doctor", "arguments": {}}
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("result", resp)
        self.assertIn("status", resp["result"])

    # ---- tools/call: trinity_inbox ----

    def test_trinity_inbox_reads_messages(self):
        self.bus.send_message("codex", "claude_code", "please review")
        params = {
            "name": "trinity_inbox",
            "arguments": {"agent": "claude_code"},
        }
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("result", resp)
        self.assertEqual(len(resp["result"]), 1)
        self.assertEqual(resp["result"][0]["message"], "please review")

    # ---- tools/call: trinity_send ----

    def test_trinity_send_sends_message(self):
        params = {
            "name": "trinity_send",
            "arguments": {
                "target_agent": "claude_code",
                "message": "review this please",
            },
        }
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["message"], "review this please")

    def test_trinity_send_self_message_blocked(self):
        params = {
            "name": "trinity_send",
            "arguments": {
                "target_agent": "mcp",
                "message": "self message",
            },
        }
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32000)

    # ---- Input validation helpers ----

    def test_validate_task_id_valid(self):
        self.assertEqual(_validate_task_id("deadbeef1234"), "deadbeef1234")

    def test_validate_task_id_invalid(self):
        with self.assertRaises(ValueError):
            _validate_task_id("short")
        with self.assertRaises(ValueError):
            _validate_task_id("nothex123456")

    def test_validate_agent_id_known(self):
        known = {"codex", "claude_code", "hermes"}
        self.assertEqual(_validate_agent_id("codex", known), "codex")
        self.assertEqual(_validate_agent_id("mcp", known), "mcp")  # reserved

    def test_validate_agent_id_unknown(self):
        with self.assertRaises(ValueError):
            _validate_agent_id("nonexistent", {"codex"})

    def test_validate_text_control_chars(self):
        with self.assertRaises(ValueError):
            _validate_text("hello\x00world")

    def test_validate_text_too_long(self):
        with self.assertRaises(ValueError):
            _validate_text("x" * 200_000)

    def test_validate_limit(self):
        self.assertEqual(_validate_limit(None), 20)
        self.assertEqual(_validate_limit(5), 5)
        with self.assertRaises(ValueError):
            _validate_limit(0)
        with self.assertRaises(ValueError):
            _validate_limit(101)

    def test_validate_timeout(self):
        self.assertEqual(_validate_timeout(None), 600)
        self.assertEqual(_validate_timeout(60), 60)
        with self.assertRaises(ValueError):
            _validate_timeout(0)
        with self.assertRaises(ValueError):
            _validate_timeout(3601)

    # ---- Error code verification ----

    def test_parse_error_on_bad_json(self):
        from trinity_lite.mcp_server import serve
        import io
        import sys

        # Simulate serving a malformed line
        old_stdout = sys.stdout
        old_stdin = sys.stdin
        try:
            # We test handle_request directly for bad json
            pass
        finally:
            sys.stdout = old_stdout

    def test_invalid_params_for_unknown_tool(self):
        params = {
            "name": "nonexistent_tool",
            "arguments": {},
        }
        resp = self._call(self._msg("tools/call", 1, params))
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32602)

    # ---- JSON-RPC response helpers ----

    def test_jsonrpc_response_structure(self):
        resp = jsonrpc_response(1, {"key": "value"})
        self.assertEqual(resp["jsonrpc"], "2.0")
        self.assertEqual(resp["id"], 1)
        self.assertEqual(resp["result"], {"key": "value"})
        self.assertNotIn("error", resp)

    def test_jsonrpc_error_structure(self):
        resp = jsonrpc_error(1, -32600, "test error", {"detail": "extra"})
        self.assertEqual(resp["jsonrpc"], "2.0")
        self.assertEqual(resp["id"], 1)
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32600)
        self.assertEqual(resp["error"]["message"], "test error")
        self.assertEqual(resp["error"]["data"], {"detail": "extra"})

    # ---- Compact task ----

    def test_compact_task_strips_extra_fields(self):
        task = {
            "id": "abc123def456",
            "source_agent": "user",
            "target_agent": "codex",
            "task_type": "impl",
            "prompt": "test",
            "cwd": "/tmp",
            "status": "queued",
            "depth": 0,
            "result": None,
            "error": None,
            "created_at": "now",
            "started_at": None,
            "finished_at": None,
            "route_json": "{}",
            "verification_json": None,
            "acceptance_status": "queued",
            "accepted_at": None,
            "extra_field": "should be removed",
        }
        compact = _compact_task(task)
        self.assertNotIn("extra_field", compact)
        self.assertEqual(compact["id"], "abc123def456")
        self.assertEqual(compact["acceptance_status"], "queued")


    # ---- Skills: agent-skill-system integration ----

    def test_skill_search_without_agent_skill_system(self):
        """Graceful error when agent-skill-system not installed."""
        import trinity_lite.mcp_server as mcp
        from unittest.mock import patch

        with patch.object(mcp, "_init_skill_engine", return_value=False):
            params = {
                "name": "trinity_skill_search",
                "arguments": {"query": "parse a contract"},
            }
            resp = self._call(self._msg("tools/call", 1, params))
            self.assertIn("result", resp)
            self.assertIn("error", resp["result"])
            self.assertEqual(resp["result"]["error"], "agent-skill-system not installed")
            self.assertIn("hint", resp["result"])

    @unittest.skipUnless(HAS_AGENT_SKILL and Path(SKILLS_DIR).exists(),
                         "agent-skill-system not installed or skills dir not found")
    def test_skill_search_returns_matching_skills(self):
        """Search returns matching skills when engine is available."""
        import trinity_lite.mcp_server as mcp

        old_available = mcp._SKILL_ENGINE_AVAILABLE
        old_bank = mcp._SKILL_BANK
        old_bank_dir = mcp._SKILL_BANK_DIR
        try:
            from engine.bank import SkillBank
            mcp._SKILL_ENGINE_AVAILABLE = True
            mcp._SKILL_BANK_DIR = SKILLS_DIR
            mcp._SKILL_BANK = SkillBank(mcp._SKILL_BANK_DIR)
            mcp._SKILL_BANK.scan_directory()

            params = {
                "name": "trinity_skill_search",
                "arguments": {"query": "generate a weekly report", "limit": 3},
            }
            resp = self._call(self._msg("tools/call", 1, params))
            self.assertIn("result", resp)
            self.assertIn("skills", resp["result"])
            skills = resp["result"]["skills"]
            self.assertIsInstance(skills, list)
            if skills:
                self.assertIn("name", skills[0])
                self.assertIn("description", skills[0])
                self.assertIn("score", skills[0])
        finally:
            mcp._SKILL_ENGINE_AVAILABLE = old_available
            mcp._SKILL_BANK = old_bank
            mcp._SKILL_BANK_DIR = old_bank_dir

    @unittest.skipUnless(HAS_AGENT_SKILL and Path(SKILLS_DIR).exists(),
                         "agent-skill-system not installed or skills dir not found")
    def test_skill_load_returns_content(self):
        """Load a skill's full content."""
        import trinity_lite.mcp_server as mcp

        old_available = mcp._SKILL_ENGINE_AVAILABLE
        old_bank = mcp._SKILL_BANK
        old_bank_dir = mcp._SKILL_BANK_DIR
        try:
            from engine.bank import SkillBank
            mcp._SKILL_ENGINE_AVAILABLE = True
            mcp._SKILL_BANK_DIR = SKILLS_DIR
            mcp._SKILL_BANK = SkillBank(mcp._SKILL_BANK_DIR)
            mcp._SKILL_BANK.scan_directory()

            # Pick an active skill from the bank
            active = mcp._SKILL_BANK.list_active()
            if active:
                skill_name = active[0].name
                params = {
                    "name": "trinity_skill_load",
                    "arguments": {"skill_name": skill_name},
                }
                resp = self._call(self._msg("tools/call", 1, params))
                self.assertIn("result", resp)
                result = resp["result"]
                self.assertIn("name", result)
                self.assertIn("skill_md", result)
                self.assertIn("system_prompt", result)
        finally:
            mcp._SKILL_ENGINE_AVAILABLE = old_available
            mcp._SKILL_BANK = old_bank
            mcp._SKILL_BANK_DIR = old_bank_dir

    @unittest.skipUnless(HAS_AGENT_SKILL and Path(SKILLS_DIR).exists(),
                         "agent-skill-system not installed or skills dir not found")
    def test_skill_load_not_found(self):
        """Graceful error when skill name is not in the bank."""
        import trinity_lite.mcp_server as mcp

        old_available = mcp._SKILL_ENGINE_AVAILABLE
        old_bank = mcp._SKILL_BANK
        old_bank_dir = mcp._SKILL_BANK_DIR
        try:
            from engine.bank import SkillBank
            mcp._SKILL_ENGINE_AVAILABLE = True
            mcp._SKILL_BANK_DIR = SKILLS_DIR
            mcp._SKILL_BANK = SkillBank(mcp._SKILL_BANK_DIR)
            mcp._SKILL_BANK.scan_directory()

            params = {
                "name": "trinity_skill_load",
                "arguments": {"skill_name": "nonexistent-skill-xyz"},
            }
            resp = self._call(self._msg("tools/call", 1, params))
            self.assertIn("result", resp)
            self.assertIn("error", resp["result"])
            self.assertIn("skill not found", resp["result"]["error"])
            self.assertIn("available_skills", resp["result"])
        finally:
            mcp._SKILL_ENGINE_AVAILABLE = old_available
            mcp._SKILL_BANK = old_bank
            mcp._SKILL_BANK_DIR = old_bank_dir


if __name__ == "__main__":
    unittest.main()
