import threading
import unittest
from http.server import HTTPServer

from cognicloud import CogniCloud, CogniCloudError
from test_browser import Stub

ID = "7c1f0c2e-6a5b-4d3e-9f10-1a2b3c4d5e6f"
APPLICATION = {
    "id": ID,
    "subdomain": "shop",
    "url": "https://shop.cognicloud.dev",
    "status": "building",
    "repoUrl": None,
    "branch": None,
    "buildCommand": "npm run build",
    "outputDir": "dist",
    "createdAt": "2026-11-01T10:00:00Z",
}


class WebBuilderTest(unittest.TestCase):
    def setUp(self):
        Stub.routes = {}
        Stub.seen = []
        self.server = HTTPServer(("127.0.0.1", 0), Stub)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}/api/v1/web-builder"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def client(self):
        return CogniCloud("session-token", tenant="acme", web_builder_base_url=self.base, max_retries=0)

    def test_creates_an_application_with_the_session_and_tenant(self):
        Stub.routes[("POST", "/api/v1/web-builder/applications")] = (201, APPLICATION)
        created = self.client().web_builder.create("shop", repo_url="https://github.com/acme/shop")
        self.assertEqual(created.url, "https://shop.cognicloud.dev")
        self.assertIsNone(created.branch)
        sent = Stub.seen[0]
        self.assertEqual(sent["body"], {"subdomain": "shop", "repoUrl": "https://github.com/acme/shop"})
        self.assertEqual(sent["headers"]["authorization"], "Bearer session-token")
        self.assertEqual(sent["headers"]["tenant_id"], "acme")

    def test_lists_reads_redeploys_and_reads_logs(self):
        Stub.routes[("GET", "/api/v1/web-builder/applications")] = (200, {"items": [APPLICATION]})
        Stub.routes[("GET", f"/api/v1/web-builder/applications/{ID}")] = (200, APPLICATION)
        Stub.routes[("POST", f"/api/v1/web-builder/applications/{ID}/redeploy")] = (200, APPLICATION)
        Stub.routes[("GET", f"/api/v1/web-builder/applications/{ID}/logs")] = (200, {"logs": "built"})
        api = self.client().web_builder
        self.assertEqual(api.list()[0].id, ID)
        self.assertEqual(api.get(ID).subdomain, "shop")
        self.assertEqual(api.redeploy(ID).status, "building")
        self.assertEqual(api.logs(ID), "built")

    def test_controls_an_application(self):
        one = f"/api/v1/web-builder/applications/{ID}"
        Stub.routes[("PATCH", one)] = (200, APPLICATION)
        Stub.routes[("POST", f"{one}/pause")] = (200, {**APPLICATION, "status": "paused"})
        Stub.routes[("POST", f"{one}/resume")] = (200, APPLICATION)
        Stub.routes[("GET", f"{one}/runtime-logs")] = (200, {"logs": "GET /"})
        Stub.routes[("POST", f"{one}/repository")] = (200, APPLICATION)
        Stub.routes[("PUT", f"{one}/auto-deploy")] = (200, {**APPLICATION, "autoDeploy": True})
        Stub.routes[("DELETE", f"{one}/auto-deploy")] = (200, APPLICATION)
        api = self.client().web_builder
        api.update(ID, branch="next")
        self.assertEqual(Stub.seen[0]["body"], {"branch": "next"})
        self.assertEqual(api.pause(ID).status, "paused")
        api.resume(ID)
        self.assertEqual(api.runtime_logs(ID), "GET /")
        api.create_repository(ID, "shop")
        self.assertEqual(Stub.seen[-1]["body"], {"name": "shop"})
        self.assertTrue(api.enable_auto_deploy(ID).auto_deploy)
        self.assertFalse(api.disable_auto_deploy(ID).auto_deploy)

    def test_lists_actions_and_uses_github(self):
        action = {
            "id": "a1",
            "action": "build_from_push",
            "applicationId": ID,
            "name": "shop",
            "startedAt": "2026-11-02T10:00:00Z",
            "finishedAt": None,
            "durationMs": None,
            "outcome": "succeeded",
            "errorCode": None,
        }
        repository = {"fullName": "acme/shop", "url": "https://github.com/acme/shop", "defaultBranch": "main", "private": False}
        Stub.routes[("GET", "/api/v1/web-builder/actions")] = (200, {"items": [action], "nextCursor": None})
        Stub.routes[("POST", "/api/v1/web-builder/github/authorize")] = (200, {"authorizeUrl": "https://github.com/login"})
        Stub.routes[("POST", "/api/v1/web-builder/github/connect")] = (200, {"login": "acme"})
        Stub.routes[("GET", "/api/v1/web-builder/github/repositories")] = (200, {"login": "acme", "items": [repository]})
        Stub.routes[("DELETE", "/api/v1/web-builder/github")] = (204, None)
        api = self.client().web_builder
        self.assertEqual(api.actions().items[0].application_id, ID)
        self.assertEqual(api.authorize_github("https://app.test/back"), "https://github.com/login")
        self.assertEqual(api.connect_github("code", "state"), "acme")
        self.assertEqual(api.github_repositories().items[0].default_branch, "main")
        api.disconnect_github()

    def test_reports_a_taken_subdomain(self):
        Stub.routes[("POST", "/api/v1/web-builder/applications")] = (409, {"error": "conflict", "message": "taken"})
        with self.assertRaises(CogniCloudError) as caught:
            self.client().web_builder.create("shop")
        self.assertEqual(caught.exception.code, "conflict")
        self.assertEqual(len(Stub.seen), 1)


if __name__ == "__main__":
    unittest.main()
