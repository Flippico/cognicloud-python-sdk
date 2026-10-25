# Changelog

## [0.8.0] - 2026-10-25

- `McpTool(label, server_url=..., bearer_token=...)` names an MCP server's address and bearer token. The gateway checks them and passes them to the provider. The token is hidden in `repr`. A tool with only a label still names a server the gateway is configured with.

## [0.7.0] - 2026-10-25

Endpoint calls, matching the Rust and JavaScript SDKs:

- `EndpointClient(credential, endpoint_id=..., tenant=..., base_url=...)` or `EndpointClient(credential, url=...)` with the URL CogniCloud issued.
- `invoke(body)`, `responses(ResponsesRequest)` with MCP tools by label, `instructions`, `tool_choice` and `previous_response_id`, and `embeddings(EmbeddingsRequest)`.
- `stream(body)` and `stream_responses(request)` yield `DeltaEvent`, then one `DoneEvent` or `ErrorEvent`. The call is opened before `stream` returns, so refusals raise first. Streams are never retried.
- The `ResponseResult` and `EmbeddingsResult` types, and `McpTool`.

## [0.4.0] - 2026-10-24

First release. Browser sessions:

- `CogniCloud(token, tenant=..., locale=..., timeout=..., max_retries=..., browser_base_url=...)`.
- `browser.sessions.create(timeout_minutes=None)`, `list()`, `get(id)`, `stop(id)`.
- `browser.countries()` and `browser.profiles()` return empty lists until those features exist.
- `CogniCloudError` with `status`, `code` and `message`.
- Standard library only; Python 3.10 or newer.
