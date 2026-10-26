import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from cognicloud import CogniCloud, CogniCloudError

SESSION = {
    "id": "b903c5d0",
    "status": "active",
    "cdpUrl": "wss://cognicloud.flippi.co/api/v1/browser/sessions/b903c5d0/cdp?token=t",
    "liveUrl": "https://cognicloud.flippi.co/api/v1/browser/sessions/b903c5d0/live?token=t",
    "profileId": None,
    "proxyCountryCode": None,
    "solveCaptchas": False,
    "recording": False,
    "screen": None,
    "timeoutAt": "2026-10-22T10:15:00Z",
    "startedAt": "2026-10-22T10:00:00Z",
    "finishedAt": None,
}


class Stub(BaseHTTPRequestHandler):
    """Answers from `routes[(method, path)]` as (status, body) and records every request."""

    routes: dict = {}
    seen: list = []

    def _answer(self):
        length = int(self.headers.get("content-length", 0))
        body = self.rfile.read(length) if length else b""
        Stub.seen.append(
            {
                "method": self.command,
                "path": self.path,
                "headers": {key.lower(): value for key, value in self.headers.items()},
                "body": json.loads(body) if body else None,
            }
        )
        status, payload = Stub.routes.get((self.command, self.path.split("?")[0]), (404, {"error": "not_found", "message": "No route matches this path."}))
        raw = b"" if payload is None else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    do_GET = _answer
    do_POST = _answer
    do_DELETE = _answer

    def log_message(self, *args):
        pass


class BrowserTests(unittest.TestCase):
    def setUp(self):
        Stub.routes = {}
        Stub.seen = []
        self.server = HTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}/v1/browser"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def client(self, **options):
        return CogniCloud("amadeus-token", tenant="acme", browser_base_url=self.base, **options)

    def test_creates_a_session_at_the_browser_base_with_the_session_headers(self):
        Stub.routes[("POST", "/v1/browser/sessions")] = (201, SESSION)
        session = self.client().browser.sessions.create(timeout_minutes=15)
        self.assertEqual(session.id, "b903c5d0")
        self.assertEqual(session.status, "active")
        self.assertTrue(session.cdp_url.startswith("wss://"))
        request = Stub.seen[0]
        self.assertEqual(request["body"], {"timeoutMinutes": 15})
        self.assertEqual(request["headers"]["authorization"], "Bearer amadeus-token")
        self.assertEqual(request["headers"]["tenant_id"], "acme")

    def test_lists_reads_and_stops_sessions(self):
        stopped = dict(SESSION, status="stopped", cdpUrl=None, liveUrl=None, finishedAt="2026-10-22T10:05:00Z")
        Stub.routes[("GET", "/v1/browser/sessions")] = (200, {"items": [SESSION], "concurrency": {"active": 1, "limit": 2}})
        Stub.routes[("GET", "/v1/browser/sessions/b903c5d0")] = (200, SESSION)
        Stub.routes[("POST", "/v1/browser/sessions/b903c5d0/stop")] = (200, stopped)
        browser = self.client().browser
        listed = browser.sessions.list()
        self.assertEqual((listed.concurrency.active, listed.concurrency.limit), (1, 2))
        self.assertEqual(browser.sessions.get("b903c5d0").status, "active")
        after = browser.sessions.stop("b903c5d0")
        self.assertEqual(after.status, "stopped")
        self.assertIsNone(after.cdp_url)
        self.assertEqual(Stub.seen[2]["method"], "POST")

    def test_raises_the_service_error_code_when_the_workspace_is_full(self):
        Stub.routes[("POST", "/v1/browser/sessions")] = (
            429,
            {"error": "concurrency_limit", "message": "Stop a session before starting another."},
        )
        with self.assertRaises(CogniCloudError) as caught:
            self.client().browser.sessions.create()
        self.assertEqual(caught.exception.status, 429)
        self.assertEqual(caught.exception.code, "concurrency_limit")

    def test_saves_a_session_as_a_profile_and_starts_from_it(self):
        profile = {
            "id": "5f1c9a2e",
            "name": "shop login",
            "sizeBytes": 20480,
            "createdAt": "2026-10-21T10:20:00Z",
            "lastUsedAt": None,
            "expiresAt": "2027-01-19T10:20:00Z",
        }
        Stub.routes[("POST", "/v1/browser/sessions/b903c5d0/profile")] = (201, profile)
        Stub.routes[("POST", "/v1/browser/sessions")] = (201, SESSION)
        browser = self.client().browser
        saved = browser.sessions.save_profile("b903c5d0", "shop login")
        self.assertEqual(saved.id, "5f1c9a2e")
        self.assertEqual(saved.size_bytes, 20480)
        self.assertEqual(saved.expires_at, "2027-01-19T10:20:00Z")
        self.assertEqual(Stub.seen[0]["body"], {"name": "shop login"})
        browser.sessions.create(profile_id=saved.id)
        self.assertEqual(Stub.seen[1]["body"], {"profileId": "5f1c9a2e"})

    def test_countries_and_profiles_are_empty_until_they_exist(self):
        Stub.routes[("GET", "/v1/browser/countries")] = (200, [])
        Stub.routes[("GET", "/v1/browser/profiles")] = (200, [])
        browser = self.client().browser
        self.assertEqual(browser.countries(), [])
        self.assertEqual(browser.profiles(), [])

    def test_retries_reads_but_not_starts(self):
        Stub.routes[("GET", "/v1/browser/sessions")] = (503, {"error": "service_unavailable", "message": "later"})
        with self.assertRaises(CogniCloudError):
            self.client(max_retries=2).browser.sessions.list()
        self.assertEqual(len(Stub.seen), 3)
        Stub.seen = []
        Stub.routes[("POST", "/v1/browser/sessions")] = (503, {"error": "service_unavailable", "message": "later"})
        with self.assertRaises(CogniCloudError):
            self.client(max_retries=2).browser.sessions.create()
        self.assertEqual(len(Stub.seen), 1)

    def test_reports_an_unreachable_service_as_a_network_error(self):
        probe = HTTPServer(("127.0.0.1", 0), Stub)
        closed_port = probe.server_address[1]
        probe.server_close()
        client = CogniCloud("amadeus-token", browser_base_url=f"http://127.0.0.1:{closed_port}/v1/browser", max_retries=0)
        with self.assertRaises(CogniCloudError) as caught:
            client.browser.sessions.list()
        self.assertEqual(caught.exception.status, 0)
        self.assertEqual(caught.exception.code, "network_error")


if __name__ == "__main__":
    unittest.main()


class TokenRequiredTest(unittest.TestCase):
    def test_refuses_a_missing_or_blank_token_before_any_request(self):
        for token in ["", "   ", None]:
            with self.subTest(token=token), self.assertRaises(CogniCloudError) as raised:
                CogniCloud(token)
            self.assertEqual(raised.exception.code, "missing_token")


class BrowserKeyClientTest(unittest.TestCase):
    def setUp(self):
        Stub.routes = {}
        Stub.seen = []
        self.server = HTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}/v1/browser"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_refuses_a_missing_or_blank_key_before_any_request(self):
        from cognicloud import CogniCloudBrowser

        for key in ["", "   ", None]:
            with self.subTest(key=key), self.assertRaises(CogniCloudError) as raised:
                CogniCloudBrowser(key)
            self.assertEqual(raised.exception.code, "missing_key")

    def test_sends_only_the_key_with_no_tenant_header(self):
        from cognicloud import CogniCloudBrowser

        Stub.routes[("GET", "/v1/browser/profiles")] = (200, [])
        browser = CogniCloudBrowser("cgb_abc", browser_base_url=self.base).browser
        self.assertEqual(browser.profiles(), [])
        request = Stub.seen[0]
        self.assertEqual(request["headers"]["authorization"], "Bearer cgb_abc")
        self.assertNotIn("tenant_id", request["headers"])
