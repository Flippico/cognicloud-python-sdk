import threading
import unittest
from http.server import HTTPServer

from cognicloud import CogniCloud, CogniCloudDatabase, CogniCloudError, Statement
from test_browser import Stub

BASE = "/api/v1/database"
RESULT = {"columns": [{"name": "id", "type": "int4"}], "rows": [{"id": 1}], "rowCount": 1, "truncated": False}
DATABASE = {"id": "db1", "name": "Orders", "createdAt": "2026-10-30T10:00:00Z"}


class DatabaseTest(unittest.TestCase):
    def setUp(self):
        Stub.routes = {}
        Stub.seen = []
        self.server = HTTPServer(("127.0.0.1", 0), Stub)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}{BASE}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def db(self, max_retries=0):
        return CogniCloudDatabase("cgd_key", database_base_url=self.base, max_retries=max_retries)

    def client(self):
        return CogniCloud("session", tenant="acme", database_base_url=self.base, max_retries=0)

    def test_refuses_a_missing_key(self):
        with self.assertRaises(CogniCloudError) as caught:
            CogniCloudDatabase(" ")
        self.assertEqual(caught.exception.code, "missing_key")

    def test_runs_sql_with_the_key_and_no_tenant(self):
        Stub.routes[("POST", f"{BASE}/query")] = (200, RESULT)
        result = self.db().query("SELECT id FROM orders WHERE status = $1", ["paid"])
        self.assertEqual(result.rows, [{"id": 1}])
        self.assertEqual(result.columns[0].type, "int4")
        self.assertEqual(result.row_count, 1)
        sent = Stub.seen[0]
        self.assertEqual(sent["body"], {"sql": "SELECT id FROM orders WHERE status = $1", "params": ["paid"]})
        self.assertEqual(sent["headers"]["authorization"], "Bearer cgd_key")
        self.assertNotIn("tenant_id", sent["headers"])

    def test_does_not_repeat_a_query_because_it_may_change_data(self):
        Stub.routes[("POST", f"{BASE}/query")] = (503, {"error": "service_unavailable", "message": "Try again."})
        with self.assertRaises(CogniCloudError):
            self.db(max_retries=2).query("DELETE FROM orders")
        self.assertEqual(len(Stub.seen), 1)

    def test_reports_the_postgres_code_of_a_failed_statement(self):
        failure = {"code": "23505", "error": "query_failed", "message": "duplicate key"}
        Stub.routes[("POST", f"{BASE}/query")] = (400, failure)
        with self.assertRaises(CogniCloudError) as caught:
            self.db().query("INSERT")
        self.assertEqual(caught.exception.code, "query_failed")
        self.assertEqual(caught.exception.query_code, "23505")

    def test_sends_a_transaction(self):
        Stub.routes[("POST", f"{BASE}/transaction")] = (200, {"results": [RESULT, RESULT]})
        results = self.db().transaction([Statement("UPDATE a SET b = 1"), Statement("DELETE FROM a WHERE id = $1", [2])])
        self.assertEqual(len(results), 2)
        self.assertEqual(
            Stub.seen[0]["body"],
            {
                "statements": [
                    {"sql": "UPDATE a SET b = 1", "params": []},
                    {"sql": "DELETE FROM a WHERE id = $1", "params": [2]},
                ]
            },
        )

    def test_lists_tables(self):
        columns = [{"name": "id", "type": "integer", "nullable": False}]
        Stub.routes[("GET", f"{BASE}/tables")] = (200, {"tables": [{"name": "orders", "columns": columns}]})
        table = self.db().tables()[0]
        self.assertEqual(table.name, "orders")
        self.assertFalse(table.columns[0].nullable)

    def test_builds_a_select_with_every_filter(self):
        Stub.routes[("POST", f"{BASE}/tables/order%20items/select")] = (200, RESULT)
        query = (
            self.db()
            .table("order items")
            .select("id", "email")
            .eq("a", 1)
            .neq("b", 2)
            .gt("c", 3)
            .gte("d", 4)
            .lt("e", 5)
            .lte("f", 6)
            .like("g", "%x")
            .ilike("h", "%y")
            .is_("i", None)
            .in_("j", [1, 2])
            .order("id", desc=True)
            .order("email")
            .limit(10)
            .offset(20)
        )
        self.assertEqual(Stub.seen, [])
        query.execute()
        self.assertEqual(
            Stub.seen[0]["body"],
            {
                "columns": ["id", "email"],
                "filters": [
                    {"column": "a", "op": "eq", "value": 1},
                    {"column": "b", "op": "neq", "value": 2},
                    {"column": "c", "op": "gt", "value": 3},
                    {"column": "d", "op": "gte", "value": 4},
                    {"column": "e", "op": "lt", "value": 5},
                    {"column": "f", "op": "lte", "value": 6},
                    {"column": "g", "op": "like", "value": "%x"},
                    {"column": "h", "op": "ilike", "value": "%y"},
                    {"column": "i", "op": "is", "value": None},
                    {"column": "j", "op": "in", "value": [1, 2]},
                ],
                "order": [{"column": "id", "desc": True}, {"column": "email", "desc": False}],
                "limit": 10,
                "offset": 20,
            },
        )

    def test_selects_every_column_by_default(self):
        Stub.routes[("POST", f"{BASE}/tables/orders/select")] = (200, RESULT)
        self.db().table("orders").select().execute()
        self.assertEqual(Stub.seen[0]["body"], {"columns": [], "filters": [], "order": []})

    def test_inserts_one_row_or_many_at_once(self):
        Stub.routes[("POST", f"{BASE}/tables/orders/insert")] = (200, RESULT)
        orders = self.db().table("orders")
        orders.insert({"email": "a"})
        orders.insert([{"email": "b"}, {"email": "c"}])
        self.assertEqual(Stub.seen[0]["body"], {"rows": [{"email": "a"}]})
        self.assertEqual(Stub.seen[1]["body"], {"rows": [{"email": "b"}, {"email": "c"}]})

    def test_updates_and_deletes_with_filters(self):
        Stub.routes[("POST", f"{BASE}/tables/orders/update")] = (200, RESULT)
        Stub.routes[("POST", f"{BASE}/tables/orders/delete")] = (200, RESULT)
        orders = self.db().table("orders")
        orders.update({"total": 5}).eq("id", 1).execute()
        orders.delete().eq("id", 1).execute()
        filters = [{"column": "id", "op": "eq", "value": 1}]
        self.assertEqual(Stub.seen[0]["body"], {"values": {"total": 5}, "filters": filters})
        self.assertEqual(Stub.seen[1]["body"], {"filters": filters})

    def test_manages_databases_as_the_signed_in_person(self):
        Stub.routes[("POST", f"{BASE}/databases")] = (201, DATABASE)
        Stub.routes[("GET", f"{BASE}/databases")] = (200, {"items": [DATABASE]})
        Stub.routes[("GET", f"{BASE}/databases/db1")] = (200, DATABASE)
        Stub.routes[("DELETE", f"{BASE}/databases/db1")] = (204, None)
        database = self.client().database
        self.assertEqual(database.create("Orders").id, "db1")
        self.assertEqual(database.list()[0].created_at, "2026-10-30T10:00:00Z")
        self.assertEqual(database.get("db1").name, "Orders")
        database.delete("db1")
        self.assertEqual(Stub.seen[0]["body"], {"name": "Orders"})
        self.assertEqual(Stub.seen[0]["headers"]["authorization"], "Bearer session")
        self.assertEqual(Stub.seen[0]["headers"]["tenant_id"], "acme")

    def test_lists_and_revokes_keys_and_pages_through_actions(self):
        key = {
            "id": "key1",
            "databaseId": "db1",
            "name": "Agent",
            "access": "read",
            "prefix": "cgd_1234",
            "createdAt": "2026-10-30T10:00:00Z",
            "lastUsedAt": None,
        }
        action = {
            "id": "a1",
            "action": "create_key",
            "databaseId": "db1",
            "name": "Agent",
            "startedAt": "2026-10-30T10:00:00Z",
            "finishedAt": "2026-10-30T10:00:01Z",
            "durationMs": 12,
            "outcome": "succeeded",
            "errorCode": None,
        }
        Stub.routes[("GET", f"{BASE}/databases/db1/keys")] = (200, [key])
        Stub.routes[("DELETE", f"{BASE}/databases/db1/keys/key1")] = (204, None)
        Stub.routes[("GET", f"{BASE}/actions")] = (200, {"items": [action], "nextCursor": "next"})
        database = self.client().database
        self.assertEqual(database.keys.list("db1")[0].access, "read")
        database.keys.revoke("db1", "key1")
        page = database.actions(limit=5, cursor="abc")
        self.assertEqual(page.next_cursor, "next")
        self.assertEqual(page.items[0].duration_ms, 12)
        self.assertEqual(Stub.seen[2]["path"], f"{BASE}/actions?limit=5&cursor=abc")


if __name__ == "__main__":
    unittest.main()
