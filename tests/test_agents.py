import threading
import unittest
from http.server import HTTPServer

from cognicloud import CogniCloud, CogniCloudError
from test_browser import Stub

AGENT_ID = "0f9a7c1e-3b2d-4e5f-8a6b-7c8d9e0f1a2b"
SKILL_ID = "5d4c3b2a-1f0e-4d9c-8b7a-6f5e4d3c2b1a"
RUN_ID = "9e8d7c6b-5a4f-4e3d-2c1b-0a9f8e7d6c5b"
BASE = "/api/v1/agents"
AGENT = {
    "id": AGENT_ID,
    "name": "Researcher",
    "description": "Finds facts",
    "endpointId": "ep_1",
    "instructions": "Answer briefly.",
    "tools": ["browser"],
    "databaseId": None,
    "maxSteps": 20,
    "timeoutSeconds": 300,
    "status": "active",
    "invokeUrl": f"https://cognicloud.dev/api/v1/agents/agents/{AGENT_ID}/runs",
    "credentialPrefix": "ccag_6163_ab12",
    "templateSlug": None,
    "skillIds": [SKILL_ID],
    "visibility": "private",
    "listingSlug": None,
    "publishedVersion": None,
    "hasUnpublishedChanges": False,
    "createdAt": "2026-11-03T10:00:00Z",
}
SKILL = {
    "id": SKILL_ID,
    "name": "Cite sources",
    "description": "Always cite",
    "body": "Cite every fact.",
    "version": 2,
    "createdAt": "2026-11-03T10:00:00Z",
    "updatedAt": "2026-11-03T11:00:00Z",
}
RUNNING = {
    "id": RUN_ID,
    "agentId": AGENT_ID,
    "status": "running",
    "input": "What is CogniCloud?",
    "output": None,
    "steps": [],
    "errorCode": None,
    "errorMessage": None,
    "maxSteps": 20,
    "timeoutSeconds": 300,
    "createdAt": "2026-11-03T10:00:00Z",
    "finishedAt": None,
}
COMPLETED = {
    **RUNNING,
    "status": "completed",
    "output": "A foundation service.",
    "steps": [
        {"number": 1, "thought": "Look it up", "tool": "browser", "summary": "Tool refused", "error": "tool_unavailable"},
        {"number": 2, "thought": "Answer", "tool": None, "summary": "Answered", "error": None},
    ],
    "finishedAt": "2026-11-03T10:00:05Z",
}
ACTION = {
    "id": "a1",
    "action": "agent.create",
    "subjectId": AGENT_ID,
    "startedAt": "2026-11-03T10:00:00Z",
    "finishedAt": "2026-11-03T10:00:00Z",
    "durationMs": 12,
    "outcome": "succeeded",
    "errorCode": None,
}


class AgentsTestCase(unittest.TestCase):
    def setUp(self):
        Stub.routes = {}
        Stub.seen = []
        self.server = HTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}{BASE}"
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def client(self):
        return CogniCloud("session-token", tenant="acme", agents_base_url=self.base, max_retries=0)


class AgentsTest(AgentsTestCase):
    def test_creates_an_agent_with_the_session_and_tenant_and_returns_its_credential_once(self):
        Stub.routes[("POST", f"{BASE}/agents")] = (201, {"agent": AGENT, "credential": {"secret": "ccag_6163_secret"}})
        created = self.client().agents.create(
            "Researcher",
            "ep_1",
            "Answer briefly.",
            tools=["browser"],
            max_steps=20,
            timeout_seconds=300,
            skill_ids=[SKILL_ID],
        )
        self.assertEqual(created.credential, "ccag_6163_secret")
        self.assertNotIn("ccag_6163_secret", repr(created))
        self.assertEqual(created.agent.endpoint_id, "ep_1")
        self.assertEqual(created.agent.skill_ids, [SKILL_ID])
        self.assertFalse(created.agent.has_unpublished_changes)
        request = Stub.seen[0]
        self.assertEqual(
            request["body"],
            {
                "name": "Researcher",
                "endpointId": "ep_1",
                "instructions": "Answer briefly.",
                "tools": ["browser"],
                "maxSteps": 20,
                "timeoutSeconds": 300,
                "skillIds": [SKILL_ID],
            },
        )
        self.assertEqual(request["headers"]["authorization"], "Bearer session-token")
        self.assertEqual(request["headers"]["tenant_id"], "acme")

    def test_lists_reads_updates_rotates_and_deletes(self):
        one = f"{BASE}/agents/{AGENT_ID}"
        Stub.routes[("GET", f"{BASE}/agents")] = (200, [AGENT])
        Stub.routes[("GET", one)] = (200, AGENT)
        Stub.routes[("PATCH", one)] = (200, {**AGENT, "status": "paused"})
        Stub.routes[("POST", f"{one}/credential/rotate")] = (200, {"secret": "ccag_6163_new"})
        Stub.routes[("DELETE", one)] = (204, None)
        agents = self.client().agents
        self.assertEqual(agents.list()[0].invoke_url, AGENT["invokeUrl"])
        self.assertEqual(agents.get(AGENT_ID).credential_prefix, "ccag_6163_ab12")
        self.assertEqual(agents.update(AGENT_ID, status="paused").status, "paused")
        self.assertEqual(Stub.seen[-1]["body"], {"status": "paused"})
        self.assertEqual(agents.rotate_credential(AGENT_ID), "ccag_6163_new")
        self.assertIsNone(agents.delete(AGENT_ID))
        self.assertEqual(Stub.seen[-1]["method"], "DELETE")

    def test_update_keeps_the_database_unless_given_and_clears_it_with_none(self):
        Stub.routes[("PATCH", f"{BASE}/agents/{AGENT_ID}")] = (200, AGENT)
        agents = self.client().agents
        agents.update(AGENT_ID, name="Renamed")
        self.assertEqual(Stub.seen[-1]["body"], {"name": "Renamed"})
        agents.update(AGENT_ID, database_id=None)
        self.assertEqual(Stub.seen[-1]["body"], {"databaseId": None})
        agents.update(AGENT_ID, database_id="db_1", tools=[])
        self.assertEqual(Stub.seen[-1]["body"], {"tools": [], "databaseId": "db_1"})

    def test_publishing_is_not_available_yet(self):
        unavailable = (503, {"error": "service_unavailable", "message": "Publishing is not available yet."})
        Stub.routes[("POST", f"{BASE}/agents/{AGENT_ID}/publish")] = unavailable
        Stub.routes[("POST", f"{BASE}/agents/{AGENT_ID}/unpublish")] = unavailable
        agents = self.client().agents
        with self.assertRaises(CogniCloudError) as caught:
            agents.publish(AGENT_ID, category="research", publisher_name="Ada Labs", language="en")
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(Stub.seen[-1]["body"], {"category": "research", "publisherName": "Ada Labs", "language": "en"})
        with self.assertRaises(CogniCloudError):
            agents.unpublish(AGENT_ID)

    def test_lists_and_revokes_keys_and_pages_through_actions(self):
        Stub.routes[("GET", f"{BASE}/keys")] = (
            200,
            [{"id": "k1", "name": "CI", "prefix": "cga_6163", "createdAt": "2026-11-03T10:00:00Z", "lastUsedAt": None}],
        )
        Stub.routes[("DELETE", f"{BASE}/keys/k1")] = (204, None)
        Stub.routes[("GET", f"{BASE}/actions")] = (200, {"items": [ACTION], "nextCursor": "c2"})
        agents = self.client().agents
        self.assertEqual(agents.keys.list()[0].prefix, "cga_6163")
        agents.keys.revoke("k1")
        self.assertEqual(Stub.seen[-1]["method"], "DELETE")
        page = agents.actions(limit=1, cursor="c1")
        self.assertEqual(page.next_cursor, "c2")
        self.assertEqual(page.items[0].subject_id, AGENT_ID)
        self.assertEqual(Stub.seen[-1]["path"], f"{BASE}/actions?limit=1&cursor=c1")


class SkillsTest(AgentsTestCase):
    def test_manages_skills_and_reads_their_versions(self):
        one = f"{BASE}/skills/{SKILL_ID}"
        Stub.routes[("POST", f"{BASE}/skills")] = (201, SKILL)
        Stub.routes[("GET", f"{BASE}/skills")] = (200, [SKILL])
        Stub.routes[("GET", one)] = (200, SKILL)
        Stub.routes[("PATCH", one)] = (200, {**SKILL, "version": 3})
        Stub.routes[("DELETE", one)] = (204, None)
        Stub.routes[("GET", f"{one}/versions")] = (
            200,
            [{"version": 1, "name": "Cite", "description": "d", "body": "b", "createdAt": "2026-11-03T10:00:00Z"}],
        )
        skills = self.client().skills
        self.assertEqual(skills.create("Cite sources", "Always cite", "Cite every fact.").version, 2)
        self.assertEqual(Stub.seen[-1]["body"], {"name": "Cite sources", "description": "Always cite", "body": "Cite every fact."})
        self.assertEqual(skills.list()[0].updated_at, "2026-11-03T11:00:00Z")
        self.assertEqual(skills.get(SKILL_ID).body, "Cite every fact.")
        self.assertEqual(skills.update(SKILL_ID, body="New").version, 3)
        self.assertEqual(Stub.seen[-1]["body"], {"body": "New"})
        self.assertEqual(skills.versions(SKILL_ID)[0].version, 1)
        skills.delete(SKILL_ID)
        self.assertEqual(Stub.seen[-1]["method"], "DELETE")


class RunsTest(AgentsTestCase):
    def test_starts_lists_reads_and_stops_runs(self):
        runs_path = f"{BASE}/agents/{AGENT_ID}/runs"
        Stub.routes[("POST", runs_path)] = (202, RUNNING)
        Stub.routes[("GET", runs_path)] = (200, {"items": [COMPLETED], "nextCursor": None})
        Stub.routes[("GET", f"{BASE}/runs/{RUN_ID}")] = (200, COMPLETED)
        Stub.routes[("POST", f"{BASE}/runs/{RUN_ID}/stop")] = (
            200,
            {**RUNNING, "status": "stopped", "errorCode": "stopped", "errorMessage": "Stopped."},
        )
        runs = self.client().runs
        started = runs.start(AGENT_ID, "What is CogniCloud?")
        self.assertEqual(started.status, "running")
        self.assertEqual(Stub.seen[-1]["body"], {"input": "What is CogniCloud?"})
        listed = runs.list(AGENT_ID, limit=10, cursor="c1")
        self.assertIsNone(listed.next_cursor)
        self.assertEqual(Stub.seen[-1]["path"], f"{runs_path}?limit=10&cursor=c1")
        run = runs.get(RUN_ID)
        self.assertEqual(run.output, "A foundation service.")
        self.assertEqual(run.steps[0].tool, "browser")
        self.assertEqual(run.steps[0].error, "tool_unavailable")
        self.assertIsNone(run.steps[1].tool)
        stopped = runs.stop(RUN_ID)
        self.assertEqual((stopped.status, stopped.error_code), ("stopped", "stopped"))

    def test_run_and_wait_polls_until_the_run_finishes(self):
        Stub.routes[("POST", f"{BASE}/agents/{AGENT_ID}/runs")] = (202, RUNNING)
        Stub.routes[("GET", f"{BASE}/runs/{RUN_ID}")] = [(200, RUNNING), (200, RUNNING), (200, COMPLETED)]
        run = self.client().runs.run_and_wait(AGENT_ID, "What is CogniCloud?", poll_interval=0.01, timeout=5)
        self.assertEqual(run.status, "completed")
        self.assertEqual([request["method"] for request in Stub.seen], ["POST", "GET", "GET", "GET"])

    def test_run_and_wait_raises_the_timeout_error_when_time_runs_out(self):
        Stub.routes[("POST", f"{BASE}/agents/{AGENT_ID}/runs")] = (202, RUNNING)
        Stub.routes[("GET", f"{BASE}/runs/{RUN_ID}")] = (200, RUNNING)
        with self.assertRaises(CogniCloudError) as caught:
            self.client().runs.run_and_wait(AGENT_ID, "Go", poll_interval=0.01, timeout=0.05)
        self.assertEqual((caught.exception.status, caught.exception.code), (0, "timeout"))

    def test_run_and_wait_rejects_a_negative_poll_interval_or_timeout_before_starting(self):
        runs = self.client().runs
        for options in ({"poll_interval": -1}, {"timeout": -1}):
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    runs.run_and_wait(AGENT_ID, "Go", **options)
        self.assertEqual(Stub.seen, [])

    def test_raises_the_service_refusals(self):
        cases = [
            (409, "agent_paused"),
            (422, "endpoint_missing"),
            (429, "limit_reached"),
            (503, "service_unavailable"),
        ]
        for status, code in cases:
            with self.subTest(code=code):
                Stub.routes[("POST", f"{BASE}/agents/{AGENT_ID}/runs")] = (status, {"error": code, "message": "No."})
                Stub.seen = []
                with self.assertRaises(CogniCloudError) as caught:
                    CogniCloud("t", agents_base_url=self.base, max_retries=2).runs.start(AGENT_ID, "Go")
                self.assertEqual((caught.exception.status, caught.exception.code), (status, code))
                self.assertEqual(len(Stub.seen), 1)


class AgentCredentialClientTest(AgentsTestCase):
    def test_sends_the_tenant_with_a_workspace_key_only_when_given(self):
        Stub.routes[("GET", f"{BASE}/agents")] = (200, [])
        CogniCloud("cga_6163_key", agents_base_url=self.base).agents.list()
        self.assertNotIn("tenant_id", Stub.seen[-1]["headers"])
        CogniCloud("cga_6163_key", tenant="acme", agents_base_url=self.base).agents.list()
        self.assertEqual(Stub.seen[-1]["headers"]["tenant_id"], "acme")
        CogniCloud("session-token", agents_base_url=self.base).agents.list()
        self.assertEqual(Stub.seen[-1]["headers"]["tenant_id"], "cognicloud")

    def test_runs_with_the_credential_alone_and_gets_forbidden_elsewhere(self):
        Stub.routes[("POST", f"{BASE}/agents/{AGENT_ID}/runs")] = (202, RUNNING)
        Stub.routes[("GET", f"{BASE}/agents")] = (403, {"error": "forbidden", "message": "Runs only."})
        client = CogniCloud("ccag_6163_secret", agents_base_url=self.base, max_retries=0)
        self.assertEqual(client.runs.start(AGENT_ID, "Go").id, RUN_ID)
        request = Stub.seen[0]
        self.assertEqual(request["headers"]["authorization"], "Bearer ccag_6163_secret")
        self.assertNotIn("tenant_id", request["headers"])
        with self.assertRaises(CogniCloudError) as caught:
            client.agents.list()
        self.assertEqual((caught.exception.status, caught.exception.code), (403, "forbidden"))

    def test_still_sends_the_default_tenant_to_other_services(self):
        host = self.base.removesuffix(BASE)
        Stub.routes[("GET", "/v1/browser/countries")] = (200, [])
        Stub.routes[("GET", "/api/v1/mail/mailboxes")] = (200, {"items": [], "total": 0, "limit": 20, "offset": 0})
        client = CogniCloud(
            "ccag_6163_secret",
            browser_base_url=f"{host}/v1/browser",
            mail_base_url=f"{host}/api/v1/mail",
            max_retries=0,
        )
        client.browser.countries()
        client.mail.list()
        self.assertEqual(len(Stub.seen), 2)
        for request in Stub.seen:
            self.assertEqual(request["headers"]["tenant_id"], "cognicloud")


if __name__ == "__main__":
    unittest.main()
