import threading
import unittest
from http.server import HTTPServer

from cognicloud import CogniCloud
from test_browser import Stub

BASE = "/api/v1/marketplace"
TEMPLATE = {
    "slug": "web-researcher",
    "kind": "cognicloud",
    "version": 1,
    "language": "en",
    "name": "Web researcher",
    "summary": "Finds facts",
    "description": "Finds facts on the web.",
    "category": "research",
    "publisher": {"name": "CogniCloud", "workspace": "cognicloud"},
    "tools": ["browser"],
    "instructions": "Research.",
    "maxSteps": 20,
    "timeoutSeconds": 300,
    "skills": [{"name": "Cite", "description": "Cite sources", "body": "Cite every fact."}],
}


class MarketplaceTest(unittest.TestCase):
    def setUp(self):
        Stub.routes = {}
        Stub.seen = []
        self.server = HTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}{BASE}"
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def client(self):
        return CogniCloud("session-token", tenant="acme", marketplace_base_url=self.base, max_retries=0)

    def test_lists_templates_by_category_and_reads_one(self):
        Stub.routes[("GET", f"{BASE}/templates")] = (200, [TEMPLATE])
        Stub.routes[("GET", f"{BASE}/templates/web-researcher")] = (200, {**TEMPLATE, "publisher": {"name": "Ada"}})
        marketplace = self.client().marketplace
        listed = marketplace.list_templates(category="research")
        self.assertEqual(listed[0].publisher.workspace, "cognicloud")
        self.assertEqual(listed[0].skills[0].body, "Cite every fact.")
        self.assertEqual(Stub.seen[-1]["path"], f"{BASE}/templates?category=research")
        self.assertEqual(Stub.seen[-1]["headers"]["tenant_id"], "acme")
        marketplace.list_templates()
        self.assertEqual(Stub.seen[-1]["path"], f"{BASE}/templates")
        template = marketplace.get_template("web-researcher")
        self.assertEqual((template.max_steps, template.timeout_seconds), (20, 300))
        self.assertIsNone(template.publisher.workspace)

    def test_pages_through_actions(self):
        action = {
            "id": "a1",
            "action": "template.read",
            "subjectId": "web-researcher",
            "startedAt": "2026-11-03T10:00:00Z",
            "finishedAt": None,
            "durationMs": None,
            "outcome": "started",
            "errorCode": None,
        }
        Stub.routes[("GET", f"{BASE}/actions")] = (200, {"items": [action], "nextCursor": None})
        page = self.client().marketplace.actions(limit=5)
        self.assertEqual(page.items[0].action, "template.read")
        self.assertIsNone(page.next_cursor)
        self.assertEqual(Stub.seen[-1]["path"], f"{BASE}/actions?limit=5")


if __name__ == "__main__":
    unittest.main()
