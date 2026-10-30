# cognicloud

Use CogniCloud from Python. Version 0.4.0 covers browser sessions for agents; the other products come later. Same behaviour as [`@cognicloud/sdk`](https://github.com/Flippico/cognicloud-js-sdk) and [`cognicloud-sdk`](https://github.com/Flippico/cognicloud-rust-sdk).

## Install

Python 3.10 or newer. No dependencies.

```bash
pip install "git+https://github.com/Flippico/cognicloud-python-sdk.git"
```

## Browser sessions

Browser calls accept the signed-in person's token, or a browser key. Create a key in the dashboard under **Browser → API keys** and pass it as the token. A key keeps working after its owner signs out. Keys cannot be created through the SDK or the API.

Use the browser product with a browser key alone. The key names its workspace, so no Amadeus token or tenant is needed:

```python
import os

from cognicloud import CogniCloudBrowser

browser = CogniCloudBrowser(os.environ["COGNICLOUD_BROWSER_KEY"])
session = browser.browser.sessions.create(timeout_minutes=15)
```

Upload a profile folder packed as a `.tar.gz` (see the app docs for how to pack it), then start a session from it:

```python
profile = browser.browser.import_profile("Shop account", "shop-profile.tar.gz")
session = browser.browser.sessions.create(profile_id=profile.id)
```


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

## Mail

Mailboxes on the Flippico mail server. The token is a signed-in person's token or a mail key (`cgm_...`). The password is returned once; store it.

```python
created = cc.mail.create("support")
settings = cc.mail.connection_settings()  # IMAP and SMTP hosts, and default_domain

# Your own domain: add it, publish domain.records at your DNS provider, then verify.
domain = cc.mail.domains.add("yourcompany.com")
cc.mail.domains.verify(domain.id)
cc.mail.create("ceo", domain="yourcompany.com")
```

`mail.list`, `get`, `rotate_password` and `delete` manage mailboxes; `mail.domains.list`, `get` and `delete` manage domains. Adding, verifying and deleting domains need a signed-in person's token.

## Database

Hosted Postgres. A signed-in person creates databases; a database key (`cgd_...`) from the dashboard queries one of them and needs nothing else. A `read` key can only read. A `write` key runs as the database owner.

```python
import os

from cognicloud import CogniCloud, CogniCloudDatabase, Statement

cc = CogniCloud(session_token)
database = cc.database.create("Orders")

db = CogniCloudDatabase(os.environ["COGNICLOUD_DATABASE_KEY"])

db.query("CREATE TABLE orders (id serial PRIMARY KEY, email text, total numeric)")
rows = db.query("SELECT * FROM orders WHERE total > $1", [100]).rows

db.table("orders").insert({"email": "a@example.com", "total": "19.90"})
paid = db.table("orders").select("id", "email").gt("total", 10).order("id", desc=True).limit(20).execute()
db.table("orders").update({"total": "0"}).eq("id", 1).execute()
db.table("orders").delete().eq("id", 1).execute()

db.transaction([
    Statement("UPDATE accounts SET balance = balance - $1 WHERE id = $2", [10, 1]),
    Statement("UPDATE accounts SET balance = balance + $1 WHERE id = $2", [10, 2]),
])
tables = db.tables()
```

- Filters are `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `is_` and `in_`. `update` and `delete` need at least one; to change every row, use `query`.
- `select`, `update` and `delete` run on `execute()`. `insert` runs at once.
- A result has `rows`, `columns`, `row_count` and `truncated`. One request stops after 15 seconds and returns at most 1,000 rows and 5 MB.
- `numeric` values, and `bigint` values beyond 2^53, come back as strings, so nothing is rounded. `bytea` comes back as base64.
- A failed statement raises `CogniCloudError` with `code` `query_failed` and `query_code`: a Postgres SQLSTATE such as `23505`, or `query_timeout`.
- `query` and `transaction`, inserts, updates and deletes are never retried, because they may change data.

`cc.database.list`, `get` and `delete` manage databases, `cc.database.keys.list` and `revoke` manage keys, and `cc.database.actions` lists what was done. Keys are created in the dashboard.

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

`ResponsesRequest(extra={...})` sends any other field to the provider unchanged, such as `seed` or `reasoning`. The gateway refuses the fields it sets itself, such as `n` or `store`.

`stream` opens the call before it returns, so a refusal raises immediately, before any event. Each event is a `DeltaEvent` (`text`), then one `DoneEvent` (`answer`), or one `ErrorEvent` (`code`, `message`). Streams are not retried and have no total timeout; the gateway ends them at five minutes. Stop early by closing the iterator; the gateway still settles the call.

## Errors

Every failed request raises `CogniCloudError` with `status` (the HTTP status, `0` when no answer came back), `code` (CogniCloud's stable error code, or a local one such as `timeout` or `network_error`) and `message`.

## Configuration

| Option | Default | |
| --- | --- | --- |
| `token` | required | The account the calls act as: the signed-in person's Amadeus session token, or a browser key for browser calls. A missing or blank token raises `CogniCloudError` with code `missing_token` when the client is created. |
| `tenant` | `"cognicloud"` | The workspace, sent as `tenant_id`. The platform workspace is open to every signed-in user. |
| `locale` | `"en"` | `Accept-Language` for localised responses. |
| `timeout` | `30.0` | Seconds per request. |
| `max_retries` | `2` | For `429` and `5xx`, on reads only. Starts and stops are never retried. |
| `browser_base_url` | `https://cognicloud.dev/api/v1/browser` | Point at another environment. |
| `mail_base_url` | `https://cognicloud.dev/api/v1/mail` | Point at another environment. |
| `database_base_url` | `https://cognicloud.dev/api/v1/database` | Point at another environment. |

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

The tests run against a local HTTP stub and need no network access.

See [CHANGELOG.md](./CHANGELOG.md).
