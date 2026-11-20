import os
import tempfile
import threading
import unittest
from http.server import HTTPServer
from io import BytesIO
from pathlib import Path

from _keys import KEY, PRODUCT_KEYS
from cognicloud import (
    Bucket,
    CogniCloud,
    CogniCloudError,
    ObjectList,
    ObjectMetadata,
    check_keys,
    parse_key,
)
from test_browser import Stub

STORAGE_KEY = PRODUCT_KEYS["storage"]

BASE = "/api/v1/storage"
BUCKET = {
    "id": "b1",
    "name": "photos",
    "visibility": "private",
    "description": None,
    "objectCount": 2,
    "totalSize": 2048,
    "createdAt": "2026-11-20T10:00:00Z",
}
METADATA = {
    "key": "reports/q 1/a#b?.txt",
    "size": 11,
    "contentType": "text/plain",
    "etag": "e1",
    "lastModified": "2026-11-20T10:01:00Z",
}
OBJECT = {"key": "reports/a.txt", "size": 11, "etag": "e2", "lastModified": "2026-11-20T10:02:00Z"}
CONFLICT = {"error": "conflict", "message": "The bucket is not empty. Delete its objects first, or pass force=true."}


class StorageTest(unittest.TestCase):
    def setUp(self):
        Stub.routes = {}
        Stub.seen = []
        self.server = HTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}{BASE}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def storage(self, max_retries=0):
        client = CogniCloud(KEY, PRODUCT_KEYS, storage_base_url=self.base, max_retries=max_retries)
        return client.storage

    def test_refuses_storage_without_a_storage_key(self):
        client = CogniCloud(KEY, {"database": PRODUCT_KEYS["database"]}, storage_base_url=self.base)
        with self.assertRaises(CogniCloudError) as caught:
            _ = client.storage
        self.assertEqual(caught.exception.code, "missing_product_key")

    def test_reads_the_storage_key_kind_and_refuses_it_elsewhere(self):
        self.assertEqual(parse_key(STORAGE_KEY).kind, "storage")
        with self.assertRaises(CogniCloudError) as caught:
            check_keys(KEY, {"mail": STORAGE_KEY})
        self.assertEqual(caught.exception.code, "invalid_key")

    def test_sends_the_storage_key_paired_with_the_account_key(self):
        Stub.routes[("GET", f"{BASE}/buckets")] = (200, {"buckets": [BUCKET]})
        buckets = self.storage().buckets.list()
        self.assertIsInstance(buckets[0], Bucket)
        sent = Stub.seen[0]
        self.assertEqual(sent["headers"]["authorization"], f"Bearer {STORAGE_KEY}")
        self.assertEqual(sent["headers"]["x-cognicloud-account-key"], KEY)
        self.assertNotIn("tenant_id", sent["headers"])

    def test_lists_creates_gets_and_updates_buckets(self):
        Stub.routes[("POST", f"{BASE}/buckets")] = (201, BUCKET)
        Stub.routes[("GET", f"{BASE}/buckets/photos")] = (200, BUCKET)
        Stub.routes[("PATCH", f"{BASE}/buckets/photos")] = (200, dict(BUCKET, visibility="public_read", description=None))
        storage = self.storage()
        self.assertEqual(storage.buckets.create("photos", description="Shots").id, "b1")
        self.assertEqual(storage.buckets.get("photos").object_count, 2)
        updated = storage.buckets.update("photos", visibility="public_read")
        self.assertEqual(updated.visibility, "public_read")
        self.assertIsNone(updated.description)
        self.assertEqual(Stub.seen[0]["body"], {"name": "photos", "description": "Shots"})
        self.assertEqual(Stub.seen[2]["body"], {"visibility": "public_read"})

    def test_creates_a_bucket_without_a_description(self):
        Stub.routes[("POST", f"{BASE}/buckets")] = (201, BUCKET)
        self.storage().buckets.create("photos")
        self.assertEqual(Stub.seen[0]["body"], {"name": "photos"})

    def test_update_sends_a_null_description_to_clear_it_and_leaves_out_what_is_not_passed(self):
        Stub.routes[("PATCH", f"{BASE}/buckets/photos")] = (200, BUCKET)
        storage = self.storage()
        storage.buckets.update("photos", description=None)
        storage.buckets.update("photos", description="New")
        storage.buckets.update("photos")
        self.assertEqual(Stub.seen[0]["body"], {"description": None})
        self.assertEqual(Stub.seen[1]["body"], {"description": "New"})
        self.assertEqual(Stub.seen[2]["body"], {})

    def test_encodes_the_bucket_name_in_its_path(self):
        Stub.routes[("GET", f"{BASE}/buckets/my%20photos%2Fold")] = (200, BUCKET)
        self.storage().buckets.get("my photos/old")
        self.assertEqual(Stub.seen[0]["path"], f"{BASE}/buckets/my%20photos%2Fold")

    def test_refuses_to_delete_a_bucket_with_objects_unless_forced(self):
        Stub.routes[("DELETE", f"{BASE}/buckets/photos")] = [(409, CONFLICT), (204, None)]
        storage = self.storage(max_retries=2)
        with self.assertRaises(CogniCloudError) as caught:
            storage.buckets.delete("photos")
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(caught.exception.code, "conflict")
        self.assertEqual(len(Stub.seen), 1)
        storage.buckets.delete("photos", force=True)
        self.assertEqual(Stub.seen[1]["path"], f"{BASE}/buckets/photos?force=true")

    def test_deletes_an_empty_bucket(self):
        Stub.routes[("DELETE", f"{BASE}/buckets/photos")] = (204, None)
        self.storage().buckets.delete("photos")
        self.assertEqual(Stub.seen[0]["path"], f"{BASE}/buckets/photos")

    def test_lists_one_page_with_every_query_option(self):
        page = {"folders": ["reports/"], "objects": [OBJECT], "nextCursor": "next"}
        Stub.routes[("GET", f"{BASE}/buckets/photos/objects")] = (200, page)
        result = self.storage().objects.list(
            "photos", prefix="reports/", delimiter="/", cursor="abc", limit=5
        )
        self.assertIsInstance(result, ObjectList)
        self.assertEqual(result.folders, ["reports/"])
        self.assertEqual(result.objects[0].etag, "e2")
        self.assertEqual(result.next_cursor, "next")
        self.assertEqual(
            Stub.seen[0]["path"],
            f"{BASE}/buckets/photos/objects?prefix=reports%2F&delimiter=%2F&cursor=abc&limit=5",
        )

    def test_lists_flat_when_the_delimiter_is_empty(self):
        Stub.routes[("GET", f"{BASE}/buckets/photos/objects")] = (200, {"folders": [], "objects": [], "nextCursor": None})
        result = self.storage().objects.list("photos", delimiter="")
        self.assertIsNone(result.next_cursor)
        self.assertEqual(Stub.seen[0]["path"], f"{BASE}/buckets/photos/objects?delimiter=")

    def test_lists_without_options_or_with_no_query(self):
        Stub.routes[("GET", f"{BASE}/buckets/photos/objects")] = (200, {"folders": [], "objects": [], "nextCursor": None})
        self.storage().objects.list("photos")
        self.assertEqual(Stub.seen[0]["path"], f"{BASE}/buckets/photos/objects")

    def test_iterates_over_every_page_following_the_cursor(self):
        first = {"folders": [], "objects": [OBJECT], "nextCursor": "c2"}
        second = {"folders": [], "objects": [dict(OBJECT, key="reports/b.txt")], "nextCursor": None}
        Stub.routes[("GET", f"{BASE}/buckets/photos/objects")] = [(200, first), (200, second)]
        pages = self.storage().objects.pages("photos", prefix="reports/", limit=1)
        self.assertEqual(Stub.seen, [])
        self.assertEqual(next(pages).objects[0].key, "reports/a.txt")
        self.assertEqual(len(Stub.seen), 1)
        self.assertEqual(next(pages).objects[0].key, "reports/b.txt")
        self.assertEqual(list(pages), [])
        self.assertEqual(
            [item["path"] for item in Stub.seen],
            [f"{BASE}/buckets/photos/objects?prefix=reports%2F&limit=1", f"{BASE}/buckets/photos/objects?prefix=reports%2F&cursor=c2&limit=1"],
        )

    def test_iterates_a_single_page_bucket_once(self):
        Stub.routes[("GET", f"{BASE}/buckets/photos/objects")] = (200, {"folders": [], "objects": [], "nextCursor": None})
        self.assertEqual(len(list(self.storage().objects.pages("photos"))), 1)
        self.assertEqual(len(Stub.seen), 1)

    def test_uploads_bytes_as_octet_stream_with_each_segment_encoded(self):
        Stub.routes[("PUT", f"{BASE}/buckets/photos/objects/reports/q%201/a%23b%3F.txt")] = (200, METADATA)
        stored = self.storage().objects.upload("photos", "reports/q 1/a#b?.txt", b"hello world")
        self.assertIsInstance(stored, ObjectMetadata)
        self.assertEqual(stored.content_type, "text/plain")
        sent = Stub.seen[0]
        self.assertEqual(sent["body"], b"hello world")
        self.assertEqual(sent["headers"]["content-type"], "application/octet-stream")
        self.assertEqual(sent["headers"]["content-length"], "11")
        self.assertEqual(sent["headers"]["authorization"], f"Bearer {STORAGE_KEY}")

    def test_uploads_a_file_with_the_content_type_from_its_name(self):
        Stub.routes[("PUT", f"{BASE}/buckets/photos/objects/doc.pdf")] = (200, dict(METADATA, key="doc.pdf"))
        Stub.routes[("PUT", f"{BASE}/buckets/photos/objects/data.unknownext")] = (200, dict(METADATA, key="data.unknownext"))
        Stub.routes[("PUT", f"{BASE}/buckets/photos/objects/doc.bin")] = (200, dict(METADATA, key="doc.bin"))
        storage = self.storage()
        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder, "doc.pdf")
            unknown = Path(folder, "data.unknownext")
            pdf.write_bytes(b"%PDF-1.4 hello")
            unknown.write_bytes(b"hello world")
            storage.objects.upload("photos", "doc.pdf", pdf)
            storage.objects.upload("photos", "data.unknownext", unknown)
            storage.objects.upload("photos", "doc.bin", pdf, content_type="application/x-custom")
        self.assertEqual(Stub.seen[0]["headers"]["content-type"], "application/pdf")
        self.assertEqual(Stub.seen[0]["body"], b"%PDF-1.4 hello")
        self.assertEqual(Stub.seen[1]["headers"]["content-type"], "application/octet-stream")
        self.assertEqual(Stub.seen[2]["headers"]["content-type"], "application/x-custom")

    def test_uploads_bytes_like_content_without_a_file(self):
        Stub.routes[("PUT", f"{BASE}/buckets/photos/objects/a.txt")] = (200, dict(METADATA, key="a.txt"))
        storage = self.storage()
        storage.objects.upload("photos", "a.txt", bytearray(b"one"))
        storage.objects.upload("photos", "a.txt", memoryview(b"two"))
        self.assertEqual([item["body"] for item in Stub.seen], [b"one", b"two"])
        self.assertEqual(Stub.seen[0]["headers"]["content-type"], "application/octet-stream")

    def test_uploads_an_open_binary_file_named_by_its_path(self):
        Stub.routes[("PUT", f"{BASE}/buckets/photos/objects/notes.txt")] = (200, dict(METADATA, key="notes.txt"))
        Stub.routes[("PUT", f"{BASE}/buckets/photos/objects/raw")] = (200, dict(METADATA, key="raw"))
        storage = self.storage()
        with tempfile.TemporaryDirectory() as folder:
            named = Path(folder, "notes.txt")
            named.write_bytes(b"# hi")
            with named.open("rb") as file:
                storage.objects.upload("photos", "notes.txt", file)
            with BytesIO(b"raw bytes") as buffer:
                storage.objects.upload("photos", "raw", buffer)
        self.assertEqual(Stub.seen[0]["body"], b"# hi")
        self.assertEqual(Stub.seen[0]["headers"]["content-type"], "text/plain")
        self.assertEqual(Stub.seen[1]["body"], b"raw bytes")
        self.assertEqual(Stub.seen[1]["headers"]["content-type"], "application/octet-stream")

    def test_refuses_a_str_body_before_any_request(self):
        storage = self.storage()
        with self.assertRaises(TypeError) as caught:
            storage.objects.upload("photos", "notes.txt", "hello")
        self.assertIn("Path(...)", str(caught.exception))
        self.assertIn(".encode()", str(caught.exception))
        self.assertEqual(Stub.seen, [])

    def test_refuses_a_text_file_and_other_bodies(self):
        storage = self.storage()
        with tempfile.TemporaryDirectory() as folder:
            text = Path(folder, "t.txt")
            text.write_text("hello")
            with text.open("r") as file:
                with self.assertRaises(TypeError):
                    storage.objects.upload("photos", "t.txt", file)
        with self.assertRaises(TypeError):
            storage.objects.upload("photos", "t.txt", 42)
        self.assertEqual(Stub.seen, [])

    def test_does_not_repeat_an_upload(self):
        Stub.routes[("PUT", f"{BASE}/buckets/photos/objects/a.txt")] = (503, {"error": "service_unavailable", "message": "No."})
        with self.assertRaises(CogniCloudError):
            self.storage(max_retries=2).objects.upload("photos", "a.txt", b"x")
        self.assertEqual(len(Stub.seen), 1)

    def test_downloads_the_bytes_of_an_object(self):
        Stub.routes[("GET", f"{BASE}/buckets/photos/objects/reports/a.txt")] = (200, b"hello world")
        content = self.storage().objects.download("photos", "reports/a.txt")
        self.assertEqual(content, b"hello world")
        self.assertNotIn("range", Stub.seen[0]["headers"])
        self.assertEqual(Stub.seen[0]["headers"]["accept"], "*/*")

    def test_downloads_an_empty_object(self):
        Stub.routes[("GET", f"{BASE}/buckets/photos/objects/empty.txt")] = (200, b"")
        self.assertEqual(self.storage().objects.download("photos", "empty.txt"), b"")

    def test_downloads_a_range(self):
        Stub.routes[("GET", f"{BASE}/buckets/photos/objects/reports/a.txt")] = (206, b"hello")
        content = self.storage().objects.download("photos", "reports/a.txt", range_="bytes=0-4")
        self.assertEqual(content, b"hello")
        self.assertEqual(Stub.seen[0]["headers"]["range"], "bytes=0-4")

    def test_reads_the_metadata_of_an_object(self):
        Stub.routes[("GET", f"{BASE}/buckets/photos/objects/reports/a.txt")] = (200, dict(METADATA, key="reports/a.txt"))
        metadata = self.storage().objects.metadata("photos", "reports/a.txt")
        self.assertEqual(metadata.content_type, "text/plain")
        self.assertEqual(Stub.seen[0]["path"], f"{BASE}/buckets/photos/objects/reports/a.txt?metadata=true")

    def test_deletes_an_object(self):
        Stub.routes[("DELETE", f"{BASE}/buckets/photos/objects/reports/q%201/a.txt")] = (204, None)
        self.storage().objects.delete("photos", "reports/q 1/a.txt")
        self.assertEqual(Stub.seen[0]["path"], f"{BASE}/buckets/photos/objects/reports/q%201/a.txt")

    def test_creates_a_folder(self):
        Stub.routes[("POST", f"{BASE}/buckets/photos/folders")] = (201, None)
        self.assertIsNone(self.storage().folders.create("photos", "reports/2026/"))
        self.assertEqual(Stub.seen[0]["body"], {"prefix": "reports/2026/"})

    def test_refuses_object_keys_that_url_handling_would_collapse_before_any_request(self):
        storage = self.storage()
        bad_keys = ["", "a//b", "a//", "a/./b", "a/../b", "x/../y", "../x", "a/..", "/a", "a\nb", "a\x00b", "a\x7fb", "a\x85b"]
        calls = {
            "upload": lambda key: storage.objects.upload("photos", key, b"x"),
            "download": lambda key: storage.objects.download("photos", key),
            "metadata": lambda key: storage.objects.metadata("photos", key),
            "delete": lambda key: storage.objects.delete("photos", key),
        }
        for name, call in calls.items():
            for key in bad_keys:
                with self.subTest(method=name, key=key):
                    with self.assertRaises(CogniCloudError) as caught:
                        call(key)
                    self.assertEqual(caught.exception.code, "invalid_key")
                    self.assertEqual(caught.exception.status, 0)
        self.assertEqual(Stub.seen, [])

    def test_refuses_a_bad_key_in_an_upload_before_reading_the_file(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = os.path.join(folder, "missing.bin")
            with self.assertRaises(CogniCloudError) as caught:
                self.storage().objects.upload("photos", "x/../y", missing)
        self.assertEqual(caught.exception.code, "invalid_key")
        self.assertEqual(Stub.seen, [])

    def test_refuses_bad_prefixes_for_listing_and_folders_before_any_request(self):
        storage = self.storage()
        for prefix in ["/reports", "a//b", "a/../b", "reports/./x", "a\nb", "", "/"]:
            with self.subTest(method="folders.create", prefix=prefix):
                with self.assertRaises(CogniCloudError) as caught:
                    storage.folders.create("photos", prefix)
                self.assertEqual(caught.exception.code, "invalid_key")
        for prefix in ["/reports/", "a//b/", "a/../b/", "a/../", "a//"]:
            with self.subTest(method="objects.list", prefix=prefix):
                with self.assertRaises(CogniCloudError) as caught:
                    storage.objects.list("photos", prefix=prefix)
                self.assertEqual(caught.exception.code, "invalid_key")
        self.assertEqual(Stub.seen, [])

    def test_accepts_one_trailing_slash_empty_listing_prefix_and_plain_dots(self):
        Stub.routes[("POST", f"{BASE}/buckets/photos/folders")] = (201, None)
        Stub.routes[("GET", f"{BASE}/buckets/photos/objects")] = (200, {"folders": [], "objects": [], "nextCursor": None})
        Stub.routes[("GET", f"{BASE}/buckets/photos/objects/.hidden/..name")] = (200, b"ok")
        Stub.routes[("PUT", f"{BASE}/buckets/photos/objects/folder/")] = (200, dict(METADATA, key="folder/"))
        storage = self.storage()
        storage.folders.create("photos", "reports/2026/")
        storage.folders.create("photos", "reports")
        storage.objects.list("photos", prefix="reports/")
        storage.objects.list("photos")
        self.assertEqual(storage.objects.download("photos", ".hidden/..name"), b"ok")
        storage.objects.upload("photos", "folder/", b"")
        self.assertEqual(len(Stub.seen), 6)

    def test_retries_reads_but_not_writes(self):
        Stub.routes[("GET", f"{BASE}/buckets")] = (503, {"error": "service_unavailable", "message": "later"})
        with self.assertRaises(CogniCloudError):
            self.storage(max_retries=2).buckets.list()
        self.assertEqual(len(Stub.seen), 3)
        Stub.seen = []
        Stub.routes[("POST", f"{BASE}/buckets")] = (503, {"error": "service_unavailable", "message": "later"})
        with self.assertRaises(CogniCloudError):
            self.storage(max_retries=2).buckets.create("photos")
        self.assertEqual(len(Stub.seen), 1)


if __name__ == "__main__":
    unittest.main()
