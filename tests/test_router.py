import unittest
import json
import tempfile
from pathlib import Path

from trinity_lite.router import RouteError, resolve_route


class RouterTest(unittest.TestCase):
    def test_pattern_routes_to_codex_primary(self):
        route = resolve_route("audit this project")
        self.assertEqual(route["agent"], "codex")
        self.assertEqual(route["task_type"], "project_audit")
        self.assertTrue(route["review_required"])

    def test_opposite_review_route(self):
        route = resolve_route(
            "review patch from Codex",
            task_type="code_review",
            previous_agent="codex",
        )
        self.assertEqual(route["agent"], "claude_code")
        self.assertEqual(route["task_type"], "code_review")

    def test_chinese_secondary_review_routes_to_opposite(self):
        route = resolve_route("二审", previous_agent="codex")
        self.assertEqual(route["agent"], "claude_code")
        self.assertEqual(route["task_type"], "code_review")

    def test_opposite_requires_previous_agent(self):
        with self.assertRaises(RouteError):
            resolve_route("review patch", task_type="code_review")

    def test_custom_routes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            routes_path = Path(tmp) / "routes.json"
            routes_path.write_text(json.dumps({
                "routes": {
                    "custom": {"agent": "hermes", "review_required": False}
                },
                "opposites": {}
            }), encoding="utf-8")
            route = resolve_route("anything", task_type="custom", routes_path=str(routes_path))
            self.assertEqual(route["agent"], "hermes")

    def test_capability_route_selects_custom_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "qwen_cli": {
                        "mode": "mock",
                        "roles": ["primary_engineer"],
                        "capabilities": ["code_edit", "test_run"],
                        "priority": 80,
                    },
                    "gemini_cli": {
                        "mode": "mock",
                        "roles": ["reviewer"],
                        "capabilities": ["code_review", "research"],
                        "priority": 70,
                    },
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "implementation": {
                        "requires": ["code_edit"],
                        "prefer": ["primary_engineer"],
                        "review_required": True,
                    }
                },
                "opposites": {}
            }), encoding="utf-8")
            route = resolve_route(
                "implement a parser",
                routes_path=str(routes_path),
                agents_path=str(agents_path),
            )
            self.assertEqual(route["agent"], "qwen_cli")
            self.assertTrue(route["review_required"])
            self.assertEqual(route["source"], "pattern/default")
            self.assertEqual(route["selection"], "capability_match")

    def test_explicit_agent_wins_over_capability_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "qwen_cli": {
                        "mode": "mock",
                        "capabilities": ["code_edit"],
                        "priority": 90,
                    },
                    "codex": {
                        "mode": "mock",
                        "capabilities": ["documentation"],
                        "priority": 1,
                    },
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "implementation": {
                        "agent": "codex",
                        "requires": ["code_edit"],
                        "prefer": ["qwen_cli"],
                    }
                },
                "opposites": {}
            }), encoding="utf-8")
            route = resolve_route(
                "implement a parser",
                routes_path=str(routes_path),
                agents_path=str(agents_path),
            )
            self.assertEqual(route["agent"], "codex")
            self.assertEqual(route["source"], "pattern/default")
            self.assertEqual(route["selection"], "explicit_agent")

    def test_capability_route_uses_priority_after_preference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "low_priority": {
                        "mode": "mock",
                        "roles": ["primary_engineer"],
                        "capabilities": ["code_edit"],
                        "priority": 10,
                    },
                    "high_priority": {
                        "mode": "mock",
                        "roles": ["primary_engineer"],
                        "capabilities": ["code_edit"],
                        "priority": 90,
                    },
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "implementation": {
                        "requires": ["code_edit"],
                        "prefer": ["primary_engineer"],
                    }
                },
                "opposites": {}
            }), encoding="utf-8")
            route = resolve_route(
                "fix bug",
                routes_path=str(routes_path),
                agents_path=str(agents_path),
            )
            self.assertEqual(route["agent"], "high_priority")

    def test_capability_route_can_prefer_agent_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "qwen_cli": {
                        "mode": "mock",
                        "capabilities": ["code_edit"],
                        "priority": 10,
                    },
                    "aider": {
                        "mode": "mock",
                        "capabilities": ["code_edit"],
                        "priority": 90,
                    },
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "implementation": {
                        "requires": ["code_edit"],
                        "prefer": ["qwen_cli"],
                    }
                },
                "opposites": {}
            }), encoding="utf-8")
            route = resolve_route(
                "fix bug",
                routes_path=str(routes_path),
                agents_path=str(agents_path),
            )
            self.assertEqual(route["agent"], "qwen_cli")

    def test_capability_route_preserves_config_order_for_ties(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "first": {
                        "mode": "mock",
                        "capabilities": ["code_edit"],
                        "priority": 10,
                    },
                    "second": {
                        "mode": "mock",
                        "capabilities": ["code_edit"],
                        "priority": 10,
                    },
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "implementation": {"requires": ["code_edit"]}
                },
                "opposites": {}
            }), encoding="utf-8")
            route = resolve_route(
                "fix bug",
                routes_path=str(routes_path),
                agents_path=str(agents_path),
            )
            self.assertEqual(route["agent"], "first")

    def test_capability_route_avoid_excludes_matching_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "fast_reviewer": {
                        "mode": "mock",
                        "roles": ["reviewer"],
                        "capabilities": ["code_review", "low_cost"],
                        "priority": 90,
                    },
                    "deep_reviewer": {
                        "mode": "mock",
                        "roles": ["reviewer"],
                        "capabilities": ["code_review", "long_context"],
                        "priority": 10,
                    },
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "code_review": {
                        "requires": ["code_review"],
                        "avoid": ["low_cost"],
                    }
                },
                "opposites": {}
            }), encoding="utf-8")
            route = resolve_route(
                "review patch",
                task_type="code_review",
                routes_path=str(routes_path),
                agents_path=str(agents_path),
            )
            self.assertEqual(route["agent"], "deep_reviewer")

    def test_capability_route_can_avoid_agent_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "qwen_cli": {
                        "mode": "mock",
                        "capabilities": ["code_edit"],
                        "priority": 90,
                    },
                    "aider": {
                        "mode": "mock",
                        "capabilities": ["code_edit"],
                        "priority": 10,
                    },
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "implementation": {
                        "requires": ["code_edit"],
                        "avoid": ["qwen_cli"],
                    }
                },
                "opposites": {}
            }), encoding="utf-8")
            route = resolve_route(
                "fix bug",
                routes_path=str(routes_path),
                agents_path=str(agents_path),
            )
            self.assertEqual(route["agent"], "aider")

    def test_capability_route_can_avoid_previous_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "primary": {
                        "mode": "mock",
                        "capabilities": ["code_review"],
                        "priority": 90,
                    },
                    "reviewer": {
                        "mode": "mock",
                        "capabilities": ["code_review"],
                        "priority": 10,
                    },
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "code_review": {"requires": ["code_review"]}
                },
                "opposites": {}
            }), encoding="utf-8")
            route = resolve_route(
                "review this patch",
                task_type="code_review",
                previous_agent="primary",
                routes_path=str(routes_path),
                agents_path=str(agents_path),
            )
            self.assertEqual(route["agent"], "reviewer")

    def test_capability_route_uses_default_specs_without_agents_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            routes_path = Path(tmp) / "routes.json"
            routes_path.write_text(json.dumps({
                "routes": {
                    "implementation": {
                        "requires": ["code_edit"],
                        "prefer": ["primary_engineer"],
                    }
                },
                "opposites": {}
            }), encoding="utf-8")
            route = resolve_route("fix bug", routes_path=str(routes_path))
            self.assertEqual(route["agent"], "codex")

    def test_capability_route_errors_when_no_agent_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_path = root / "agents.json"
            routes_path = root / "routes.json"
            agents_path.write_text(json.dumps({
                "agents": {
                    "writer": {
                        "mode": "mock",
                        "capabilities": ["documentation"],
                    }
                }
            }), encoding="utf-8")
            routes_path.write_text(json.dumps({
                "routes": {
                    "implementation": {"requires": ["code_edit"]}
                },
                "opposites": {}
            }), encoding="utf-8")
            with self.assertRaises(RouteError):
                resolve_route(
                    "implement a parser",
                    routes_path=str(routes_path),
                    agents_path=str(agents_path),
                )


if __name__ == "__main__":
    unittest.main()
