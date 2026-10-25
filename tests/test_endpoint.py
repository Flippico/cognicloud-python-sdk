import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cognicloud import (
    CogniCloudError,
    DeltaEvent,
    DoneEvent,
    EmbeddingsRequest,
    EndpointClient,
    ErrorEvent,
    McpTool,
    ResponsesRequest,
)

ANSWER = {
    "id": "0c4e0e4a-0000-0000-0000-000000000000",
    "model": "gpt-5-mini",
    "output": "Valid.",
    "finishReason": "stop",
    "usage": {"inputTokens": 10, "outputTokens": 3, "totalTokens": 13},
    "responseId": "resp_1",
    "outputItems": [{"type": "mcp_call", "name": "validate_invoice_xml"}],
}
INVOKE_PATH = "/invoke/636f676e69636c6f7564/e1"


class Stub(BaseHTTPRequestHandler):
    """Answers from `routes[path]` as (status, content_type, body) and records each request."""

    routes: dict = {}
    seen: list = []

    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(length)) if length else None
        Stub.seen.append(
            {"path": self.path, "headers": {key.lower(): value for key, value in self.headers.items()}, "body": body}
        )
        status, content_type, raw = Stub.routes[self.path]
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


def json_route(status, payload):
    return (status, "application/json", json.dumps(payload).encode())


def sse_route(text):
    return (200, "text/event-stream", text.encode())


class EndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Stub.routes = {}
        Stub.seen = []

    def client(self, **options):
        return EndpointClient("cc_live_secret", endpoint_id="e1", base_url=self.base, **options)

    def test_invoke_sends_the_credential_and_returns_the_answer(self):
        Stub.routes[INVOKE_PATH] = json_route(200, ANSWER)
        answer = self.client().invoke({"messages": [{"role": "user", "content": "Hi"}]})
        self.assertEqual(answer.output, "Valid.")
        self.assertEqual(answer.usage.total_tokens, 13)
        self.assertEqual(Stub.seen[0]["headers"]["authorization"], "Bearer cc_live_secret")

    def test_responses_sends_mcp_tools_by_label(self):
        Stub.routes[INVOKE_PATH] = json_route(200, ANSWER)
        request = ResponsesRequest(
            input="Check this invoice.",
            instructions="Be brief.",
            tools=[McpTool("ksef", allowed_tools=["validate_invoice_xml"])],
            tool_choice="required",
        )
        answer = self.client().responses(request)
        self.assertEqual(answer.response_id, "resp_1")
        self.assertEqual(len(answer.output_items), 1)
        self.assertEqual(
            Stub.seen[0]["body"],
            {
                "input": "Check this invoice.",
                "instructions": "Be brief.",
                "tools": [{"type": "mcp", "server_label": "ksef", "allowed_tools": ["validate_invoice_xml"]}],
                "tool_choice": "required",
            },
        )

    def test_responses_continues_with_previous_response_id(self):
        Stub.routes[INVOKE_PATH] = json_route(200, {**ANSWER, "responseId": "resp_2"})
        answer = self.client().responses(ResponsesRequest(input="And this one?", previous_response_id="resp_1"))
        self.assertEqual(answer.response_id, "resp_2")
        self.assertEqual(Stub.seen[0]["body"], {"input": "And this one?", "previous_response_id": "resp_1"})

    def test_embeddings_return_one_vector_per_input(self):
        Stub.routes[INVOKE_PATH + "/embeddings"] = json_route(
            200,
            {
                "id": "x",
                "model": "embed-small",
                "data": [{"index": 0, "embedding": [0.1, 0.2]}, {"index": 1, "embedding": [0.3, 0.4]}],
                "usage": {"inputTokens": 12, "outputTokens": 0, "totalTokens": 12},
            },
        )
        result = self.client().embeddings(EmbeddingsRequest(["first", "second"], dimensions=256))
        self.assertEqual(result.data[1].embedding, [0.3, 0.4])
        self.assertEqual(Stub.seen[0]["body"], {"input": ["first", "second"], "dimensions": 256})

    def test_invoke_is_never_retried_on_server_errors(self):
        Stub.routes[INVOKE_PATH] = json_route(503, {"error": "gateway_unavailable", "message": "Try again."})
        with self.assertRaises(CogniCloudError) as caught:
            self.client(max_retries=3).invoke({"input": "Hi"})
        self.assertEqual((caught.exception.status, caught.exception.code), (503, "gateway_unavailable"))
        self.assertEqual(len(Stub.seen), 1)

    def test_stream_yields_deltas_then_the_done_answer(self):
        body = (
            'event: delta\ndata: {"text":"Hel"}\n\n'
            'event: delta\r\ndata: {"text":"lo"}\r\n\r\n'
            f"event: done\ndata: {json.dumps({**ANSWER, 'output': 'Hello'})}\n\n"
        )
        Stub.routes[INVOKE_PATH] = sse_route(body)
        events = list(self.client().stream({"messages": [{"role": "user", "content": "hi"}]}))
        self.assertEqual(events[0], DeltaEvent("Hel"))
        self.assertEqual(events[1], DeltaEvent("lo"))
        self.assertIsInstance(events[2], DoneEvent)
        self.assertEqual(events[2].answer.output, "Hello")
        self.assertEqual(len(events), 3)
        self.assertEqual(Stub.seen[0]["body"], {"messages": [{"role": "user", "content": "hi"}], "stream": True})
        self.assertEqual(Stub.seen[0]["headers"]["accept"], "text/event-stream")

    def test_stream_yields_a_provider_error_and_stops(self):
        Stub.routes[INVOKE_PATH] = sse_route(
            'event: delta\ndata: {"text":"Hi"}\n\n'
            'event: error\ndata: {"code":"upstream_failure","message":"The provider did not finish the answer."}\n\n'
        )
        events = list(self.client().stream_responses(ResponsesRequest("x")))
        self.assertEqual(events[1], ErrorEvent("upstream_failure", "The provider did not finish the answer."))
        self.assertEqual(len(events), 2)

    def test_stream_reports_stream_ended_when_it_closes_early(self):
        Stub.routes[INVOKE_PATH] = sse_route('event: delta\ndata: {"text":"Hi"}\n\n')
        events = list(self.client().stream({"input": "x"}))
        self.assertEqual(events[1], ErrorEvent("stream_ended", "The stream ended before its final event."))

    def test_a_refused_stream_raises_before_any_event(self):
        Stub.routes[INVOKE_PATH] = json_route(
            422, {"error": "invalid_request", "message": "Streaming needs an API version of 2024-10-21 or later."}
        )
        with self.assertRaises(CogniCloudError) as caught:
            self.client().stream({"input": "x"})
        self.assertEqual((caught.exception.status, caught.exception.code), (422, "invalid_request"))

    def test_a_stream_is_never_retried(self):
        Stub.routes[INVOKE_PATH] = json_route(503, {"error": "gateway_unavailable", "message": "Try again."})
        with self.assertRaises(CogniCloudError):
            self.client(max_retries=3).stream({"input": "x"})
        self.assertEqual(len(Stub.seen), 1)

    def test_an_endpoint_needs_exactly_one_address(self):
        with self.assertRaises(ValueError):
            EndpointClient("k")
        with self.assertRaises(ValueError):
            EndpointClient("k", endpoint_id="e1", url=self.base + INVOKE_PATH)


if __name__ == "__main__":
    unittest.main()
