from __future__ import annotations

import json
import socket
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Union
from urllib.parse import quote

from ._http import HttpConfig, open_stream, request
from ._sse import Record, records
from .errors import CogniCloudError

DEFAULT_TENANT = "cognicloud"
DEFAULT_GATEWAY_BASE_URL = "https://cognicloud.flippi.co/api/v1/ai-gateway"


@dataclass(frozen=True)
class McpTool:
    """An MCP server a Responses call may use.

    Name the server with `server_url` and its bearer token with `bearer_token`. The gateway checks the address (https,
    no credentials or fragment), sets approval to `never`, and passes both to the provider. A tool with only
    `server_label` names a server the gateway is configured with.
    """

    server_label: str
    allowed_tools: Optional[list[str]] = None
    server_url: Optional[str] = None
    bearer_token: Optional[str] = field(default=None, repr=False)

    def to_json(self) -> dict[str, Any]:
        body: dict[str, Any] = {"type": "mcp", "server_label": self.server_label}
        if self.server_url is not None:
            body["server_url"] = self.server_url
        if self.bearer_token is not None:
            body["headers"] = {"Authorization": f"Bearer {self.bearer_token}"}
        if self.allowed_tools is not None:
            body["allowed_tools"] = self.allowed_tools
        return body


@dataclass(frozen=True)
class ResponsesRequest:
    """A Responses call with optional MCP tools, instructions and chaining. `input` is text or role/content messages."""

    input: Union[str, list[dict[str, Any]]]
    instructions: Optional[str] = None
    previous_response_id: Optional[str] = None
    tools: list[McpTool] = field(default_factory=list)
    tool_choice: Optional[Literal["auto", "required", "none"]] = None
    max_output_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    # Any other field, sent to the provider unchanged. The gateway refuses the fields it sets itself, such as `n`.
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        body: dict[str, Any] = {**self.extra, "input": self.input}
        optional = {
            "instructions": self.instructions,
            "previous_response_id": self.previous_response_id,
            "tool_choice": self.tool_choice,
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        body.update({key: value for key, value in optional.items() if value is not None})
        if self.tools:
            body["tools"] = [tool.to_json() for tool in self.tools]
        return body


@dataclass(frozen=True)
class EmbeddingsRequest:
    """Text to embed: one string or up to 256. The endpoint's embedding deployment is the model."""

    input: Union[str, list[str]]
    dimensions: Optional[int] = None

    def to_json(self) -> dict[str, Any]:
        body: dict[str, Any] = {"input": self.input}
        if self.dimensions is not None:
            body["dimensions"] = self.dimensions
        return body


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    total_tokens: int

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Usage":
        return cls(data["inputTokens"], data["outputTokens"], data["totalTokens"])


@dataclass(frozen=True)
class ResponseResult:
    """An answer. `response_id` and `output_items` are set only for Responses calls."""

    id: str
    model: str
    output: str
    finish_reason: Optional[str]
    usage: Usage
    response_id: Optional[str] = None
    output_items: Optional[list[Any]] = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ResponseResult":
        return cls(
            id=data["id"],
            model=data["model"],
            output=data["output"],
            finish_reason=data.get("finishReason"),
            usage=Usage.from_json(data["usage"]),
            response_id=data.get("responseId"),
            output_items=data.get("outputItems"),
        )


@dataclass(frozen=True)
class Embedding:
    index: int
    embedding: list[float]


@dataclass(frozen=True)
class EmbeddingsResult:
    """One item per input, in input order."""

    id: str
    model: str
    data: list[Embedding]
    usage: Usage

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "EmbeddingsResult":
        return cls(
            id=data["id"],
            model=data["model"],
            data=[Embedding(item["index"], item["embedding"]) for item in data["data"]],
            usage=Usage.from_json(data["usage"]),
        )


@dataclass(frozen=True)
class DeltaEvent:
    """Text as it is generated."""

    text: str


@dataclass(frozen=True)
class DoneEvent:
    """The complete answer. It is always the last event of a successful stream."""

    answer: ResponseResult


@dataclass(frozen=True)
class ErrorEvent:
    """A failure, instead of `DoneEvent`. The stream ends after it."""

    code: str
    message: str


StreamEvent = Union[DeltaEvent, DoneEvent, ErrorEvent]


def encode_tenant(tenant: str) -> str:
    """How an invoke URL names its tenant: the tenant's name as UTF-8, in lowercase hex."""
    return tenant.encode("utf-8").hex()


class EndpointClient:
    """Calls one AI Gateway endpoint with its own credential.

    Pass the endpoint's invoke URL as `url` (as CogniCloud issued it), or the `endpoint_id` and `tenant`. Invoke calls
    are never retried, because a retried call can be billed twice.
    """

    def __init__(
        self,
        credential: str,
        *,
        endpoint_id: Optional[str] = None,
        url: Optional[str] = None,
        tenant: str = DEFAULT_TENANT,
        base_url: str = DEFAULT_GATEWAY_BASE_URL,
        locale: str = "en",
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        if (endpoint_id is None) == (url is None):
            raise ValueError("Pass exactly one of endpoint_id or url.")
        if url is None:
            url = f"{base_url.rstrip('/')}/invoke/{encode_tenant(tenant)}/{quote(endpoint_id or '', safe='')}"
        self.url = url
        self._config = HttpConfig(base_url=url, locale=locale, timeout=timeout, max_retries=max_retries)
        self._headers = {"authorization": f"Bearer {credential}"}

    def invoke(self, body: Mapping[str, Any]) -> ResponseResult:
        """Sends the body through the endpoint's request mapping and returns the answer in one shape. Without a mapping
        the body goes to the provider as it is, with no streaming. Use `stream` to stream."""
        data = request(self._config, "POST", "", self._headers, dict(body), retry=False)
        return ResponseResult.from_json(data)

    def responses(self, request_body: ResponsesRequest) -> ResponseResult:
        """A Responses call with optional MCP tools, instructions and chaining. Never retried."""
        data = request(self._config, "POST", "", self._headers, request_body.to_json(), retry=False)
        return ResponseResult.from_json(data)

    def embeddings(self, request_body: EmbeddingsRequest) -> EmbeddingsResult:
        """Embeds text through the endpoint's embedding deployment. Billed as prompt tokens. Never retried."""
        data = request(self._config, "POST", "/embeddings", self._headers, request_body.to_json(), retry=False)
        return EmbeddingsResult.from_json(data)

    def stream(self, body: Union[Mapping[str, Any], ResponsesRequest]) -> Iterator[StreamEvent]:
        """Streams a chat or Responses call: sets `stream: true` and yields events as they arrive.

        The call is opened before this returns, so a refusal raises here, before any event. Stop early by closing the
        iterator; the gateway still settles the call.
        """
        payload = dict(body.to_json() if isinstance(body, ResponsesRequest) else body)
        payload["stream"] = True
        response = open_stream(self._config, "POST", "", self._headers, payload)
        return _events(response)

    def stream_responses(self, request_body: ResponsesRequest) -> Iterator[StreamEvent]:
        """Streams a Responses call, for tools or chaining. See `stream`."""
        return self.stream(request_body)


def _events(response: Any) -> Iterator[StreamEvent]:
    try:
        for record in records(response):
            event = _decode(record)
            if event is None:
                continue
            yield event
            if not isinstance(event, DeltaEvent):
                return
        yield ErrorEvent("stream_ended", "The stream ended before its final event.")
    except (TimeoutError, socket.timeout):
        raise CogniCloudError(0, "timeout", "The stream timed out.") from None
    except OSError:
        raise CogniCloudError(0, "network_error", "The stream was interrupted.") from None
    finally:
        response.close()


def _decode(record: Record) -> Optional[StreamEvent]:
    """Events the gateway does not send are ignored, so a newer gateway can add events without breaking this client."""
    if record.event == "delta":
        return DeltaEvent(json.loads(record.data)["text"])
    if record.event == "done":
        return DoneEvent(ResponseResult.from_json(json.loads(record.data)))
    if record.event == "error":
        error = json.loads(record.data)
        return ErrorEvent(error["code"], error["message"])
    return None
