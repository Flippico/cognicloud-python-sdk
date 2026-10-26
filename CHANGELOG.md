# Changelog

## [0.10.1] - 2026-10-26

- A missing or blank `token` raises `CogniCloudError` with code `missing_token` when the client is created, before any request is made.
- Docs: a browser key can be used as the token; the token and workspace are described in each README.

## [0.10.0] - 2026-10-26

- `browser.sessions.save_profile(session_id, name)` saves a running session as a profile and ends the session. `create(profile_id=...)` starts a session from a saved profile.
- Breaking: `BrowserProfile` has `size_bytes` and `expires_at` in place of `cookie_domains`.

## [0.9.0] - 2026-10-25

- `ResponsesRequest(extra={...})` sends any other field to the provider unchanged. The gateway refuses the fields it sets itself (`n`, `best_of`, `background`, `store`, `stream_options`, `prompt`, `conversation`).

## [0.8.0] - 2026-10-25

- `McpTool(label, server_url=..., bearer_token=...)` names an MCP server's address and bearer token. The gateway checks them and passes them to the provider. The token is hidden in `repr`. A tool with only a label still names a server the gateway is configured with.

## [0.7.0] - 2026-10-25

- `stream(body)` and `stream_responses(request)` yield `DeltaEvent`, then one `DoneEvent` or `ErrorEvent`. The call is opened before `stream` returns, so refusals raise first. Streams are never retried. A stream that closes early yields `ErrorEvent` with the code `stream_ended`.

## [0.6.0] - 2026-10-24

- `embeddings(EmbeddingsRequest(input, dimensions=...))` returns one vector per input, in input order, and bills the prompt tokens. `EmbeddingsResult` and `Embedding` are exported.

## [0.5.0] - 2026-10-24

- `EndpointClient(credential, endpoint_id=..., tenant=..., base_url=...)` or `EndpointClient(credential, url=...)` with the URL CogniCloud issued.
- `invoke(body)` and `responses(ResponsesRequest)`, with MCP tools by label, `instructions`, `tool_choice` and `previous_response_id`. `ResponseResult` carries `response_id` and `output_items`.

## [0.4.0] - 2026-10-24

First release. Browser sessions:

- `CogniCloud(token, tenant=..., locale=..., timeout=..., max_retries=..., browser_base_url=...)`.
- `browser.sessions.create(timeout_minutes=None)`, `list()`, `get(id)`, `stop(id)`.
- `browser.countries()` and `browser.profiles()` return empty lists until those features exist.
- `CogniCloudError` with `status`, `code` and `message`.
- Standard library only; Python 3.10 or newer.
