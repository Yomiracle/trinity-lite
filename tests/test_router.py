import unittest

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

    def test_opposite_requires_previous_agent(self):
        with self.assertRaises(RouteError):
            resolve_route("review patch", task_type="code_review")


if __name__ == "__main__":
    unittest.main()
