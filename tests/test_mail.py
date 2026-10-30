import json
import threading
import unittest
from http.server import HTTPServer

from cognicloud import CogniCloud, CogniCloudError
from test_browser import Stub

MAILBOX = {
    "id": "7c1f0c2e-6a5b-4d3e-9f10-1a2b3c4d5e6f",
    "address": "support@mail.example.com",
    "localPart": "support",
    "domain": "mail.example.com",
    "createdAt": "2026-10-29T10:00:00Z",
    "updatedAt": "2026-10-29T10:00:00Z",
}


class MailTest(unittest.TestCase):
    def setUp(self):
        Stub.routes = {}
        Stub.seen = []
        self.server = HTTPServer(("127.0.0.1", 0), Stub)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}/api/v1/mail"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def client(self):
        return CogniCloud("session-token", tenant="acme", mail_base_url=self.base, max_retries=0)

    def test_creates_a_mailbox_and_returns_the_password_once(self):
        Stub.routes[("POST", "/api/v1/mail/mailboxes")] = (201, {"mailbox": MAILBOX, "password": "Vf9!mQ2xTr7#pL4wNz8K"})
        created = self.client().mail.create("support")
        self.assertEqual(created.mailbox.address, "support@mail.example.com")
        self.assertEqual(created.password, "Vf9!mQ2xTr7#pL4wNz8K")
        sent = Stub.seen[0]
        self.assertEqual(sent["body"], {"localPart": "support"})
        self.assertEqual(sent["headers"]["authorization"], "Bearer session-token")
        self.assertEqual(sent["headers"]["tenant_id"], "acme")

    def test_lists_with_paging_and_reads_connection_settings(self):
        Stub.routes[("GET", "/api/v1/mail/mailboxes")] = (200, {"items": [MAILBOX], "total": 1, "limit": 5, "offset": 0})
        Stub.routes[("GET", "/api/v1/mail/mailboxes/settings")] = (
            200,
            {
                "usernameFormat": "full mailbox address",
                "imap": {"host": "mail.example.com", "port": 993, "security": "ssl"},
                "smtp": {"host": "mail.example.com", "port": 465, "security": "ssl"},
            },
        )
        client = self.client()
        self.assertEqual(client.mail.list(limit=5).total, 1)
        self.assertEqual(Stub.seen[0]["path"], "/api/v1/mail/mailboxes?limit=5")
        self.assertEqual(client.mail.connection_settings().imap.port, 993)

    def test_deletes_and_rotates(self):
        Stub.routes[("DELETE", f"/api/v1/mail/mailboxes/{MAILBOX['id']}")] = (204, None)
        Stub.routes[("POST", f"/api/v1/mail/mailboxes/{MAILBOX['id']}/password/rotate")] = (200, {"password": "new-pass-1!"})
        client = self.client()
        client.mail.delete(MAILBOX["id"])
        self.assertEqual(client.mail.rotate_password(MAILBOX["id"]), "new-pass-1!")

    def test_reports_unknown_mailboxes(self):
        with self.assertRaises(CogniCloudError) as caught:
            self.client().mail.get("missing")
        self.assertEqual(caught.exception.status, 404)


if __name__ == "__main__":
    unittest.main()


DOMAIN = {
    "id": "d1",
    "name": "yourcompany.com",
    "status": "pending",
    "records": [
        {"type": "TXT", "host": "_cognicloud.yourcompany.com", "value": "cognicloud-verify=abc", "purpose": "ownership", "ok": None}
    ],
    "otherMx": ["relay1.netnames.net"],
    "createdAt": "2026-10-30T10:00:00Z",
    "verifiedAt": None,
    "lastCheckedAt": None,
}


class MailDomainsTest(MailTest):
    def test_adds_verifies_lists_and_deletes_a_domain_and_creates_a_mailbox_on_it(self):
        Stub.routes[("POST", "/api/v1/mail/domains")] = (201, DOMAIN)
        Stub.routes[("POST", "/api/v1/mail/domains/d1/verify")] = (200, {**DOMAIN, "status": "verified"})
        Stub.routes[("GET", "/api/v1/mail/domains")] = (200, {"items": [{**DOMAIN, "status": "verified"}]})
        Stub.routes[("POST", "/api/v1/mail/mailboxes")] = (
            201,
            {"mailbox": {**MAILBOX, "address": "ceo@yourcompany.com", "domain": "yourcompany.com"}, "password": "pw"},
        )
        Stub.routes[("DELETE", "/api/v1/mail/domains/d1")] = (204, None)
        client = self.client()
        added = client.mail.domains.add("yourcompany.com")
        self.assertEqual(added.status, "pending")
        self.assertEqual(added.other_mx, ["relay1.netnames.net"])
        self.assertIsNone(added.records[0].ok)
        self.assertEqual(client.mail.domains.verify("d1").status, "verified")
        self.assertEqual(len(client.mail.domains.list()), 1)
        created = client.mail.create("ceo", domain="yourcompany.com")
        self.assertEqual(created.mailbox.address, "ceo@yourcompany.com")
        client.mail.domains.delete("d1")
        self.assertEqual(Stub.seen[0]["body"], {"name": "yourcompany.com"})
        self.assertEqual(Stub.seen[3]["body"], {"localPart": "ceo", "domain": "yourcompany.com"})
        self.assertEqual(Stub.seen[4]["method"], "DELETE")
