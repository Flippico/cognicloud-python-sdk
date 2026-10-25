# cognicloud

Use CogniCloud from Python. Version 0.4.0 covers browser sessions for agents; the other products come later. Same behaviour as [`@cognicloud/sdk`](https://github.com/Flippico/cognicloud-js-sdk) and [`cognicloud-sdk`](https://github.com/Flippico/cognicloud-rust-sdk).

## Install

Python 3.10 or newer. No dependencies.

```bash
pip install "git+https://github.com/Flippico/cognicloud-python-sdk.git"
```

## Browser sessions

```python
from cognicloud import CogniCloud

cc = CogniCloud(amadeus_token)
session = cc.browser.sessions.create(timeout_minutes=15)
print(session.cdp_url)   # connect Playwright, Puppeteer or any CDP client here
cc.browser.sessions.stop(session.id)
```

- `timeout_minutes` is 1 to 240 and defaults to 15.
- Closing the CDP connection does not stop a session; call `sessions.stop`.
- `status` is `active` or `stopped`; `cdp_url` and `live_url` are `None` once stopped. `live_url` is a page where a person can watch and take over the browser.
- `sessions.list()` returns `items` and `concurrency` (`active`, `limit`). A start beyond the limit raises `CogniCloudError` with `status == 429` and `code == "concurrency_limit"`.
- Proxy countries, profiles, screen sizes, captcha solving and recording are not available yet. `browser.countries()` and `browser.profiles()` return empty lists.

## Call an endpoint

```python
import os
from cognicloud import EndpointClient, ResponsesRequest, McpTool, EmbeddingsRequest, DeltaEvent, DoneEvent, ErrorEvent

endpoint = EndpointClient(os.environ["COGNICLOUD_KEY"], endpoint_id=os.environ["COGNICLOUD_ENDPOINT_ID"])

answer = endpoint.responses(
    ResponsesRequest(
        input="Is this invoice valid?",
        instructions="Check invoices.",
        tools=[McpTool("ksef", allowed_tools=["validate_invoice_xml"])],
        tool_choice="required",
    )
)
next_answer = endpoint.responses(ResponsesRequest("And this one?", previous_response_id=answer.response_id))

vectors = endpoint.embeddings(EmbeddingsRequest(["first text", "second text"], dimensions=256))
```

`McpTool` names an MCP server with `server_url` and `bearer_token`. The gateway checks the address (https, with no credentials or fragment) and passes both to the provider. A tool with only `server_label` names a server the gateway is configured with. The answer's `response_id` continues the conversation on the same endpoint, and `output_items` holds the tool calls. `embeddings` needs an endpoint whose deployment is an embedding model, and returns one vector per input.

## Streaming

```python
for event in endpoint.stream({"messages": [{"role": "user", "content": "Write a haiku."}]}):
    if isinstance(event, DeltaEvent):
        print(event.text, end="")
    elif isinstance(event, DoneEvent):
        print(f"\n{event.answer.usage.total_tokens} tokens")
    elif isinstance(event, ErrorEvent):
        print(f"{event.code}: {event.message}")
```

`stream` opens the call before it returns, so a refusal raises immediately, before any event. Each event is a `DeltaEvent` (`text`), then one `DoneEvent` (`answer`), or one `ErrorEvent` (`code`, `message`). Streams are not retried and have no total timeout; the gateway ends them at five minutes. Stop early by closing the iterator; the gateway still settles the call.

## Errors

Every failed request raises `CogniCloudError` with `status` (the HTTP status, `0` when no answer came back), `code` (CogniCloud's stable error code, or a local one such as `timeout` or `network_error`) and `message`.

## Configuration

| Option | Default | |
| --- | --- | --- |
| `token` | required | The signed-in person's Amadeus session token. |
| `tenant` | `"cognicloud"` | The workspace, sent as `tenant_id`. The platform workspace is open to every signed-in user. |
| `locale` | `"en"` | `Accept-Language` for localised responses. |
| `timeout` | `30.0` | Seconds per request. |
| `max_retries` | `2` | For `429` and `5xx`, on reads only. Starts and stops are never retried. |
| `browser_base_url` | `https://cognicloud.flippi.co/api/v1/browser` | Point at another environment. |

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

The tests run against a local HTTP stub and need no network access.

See [CHANGELOG.md](./CHANGELOG.md).
