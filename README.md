# cognicloud

Use CogniCloud from Python: browser sessions, mail, databases, the web builder, agents and AI Gateway endpoints. Same behaviour as [`@cognicloud/sdk`](https://github.com/Flippico/cognicloud-js-sdk) and [`cognicloud-sdk`](https://github.com/Flippico/cognicloud-rust-sdk).

## Install

Python 3.10 or newer. No dependencies.

```bash
pip install "git+https://github.com/Flippico/cognicloud-python-sdk.git"
```

1.0 changes how you sign in: one API key replaces the session token, the `tenant` option and the per-product keys. See [Migrating from 0.x](#migrating-from-0x).

## API keys

Create a key in the dashboard under **Settings → API keys**. It is shown once.

- An **account key** (`cc_acc_...`) reaches every product of the workspace and acts as the person who created it.
- A **product key** reaches one product: `cc_gw_` AI Gateway, `cc_db_` Database, `cc_br_` Browser, `cc_ml_` Mail, `cc_ag_` Agents. It can be narrowed to one resource, such as one endpoint, database or agent.

The key names its workspace, so there is no `tenant` option and no `tenant_id` header. Keys cannot be created through the SDK or the API.

```python
import os

from cognicloud import CogniCloud

cc = CogniCloud(os.environ["COGNICLOUD_API_KEY"])
```

A missing or blank key raises `CogniCloudError` with code `missing_key` when the client is created. A key in a retired format (`cgb_`, `cgd_`, `cga_`, `ccag_`, `cgm_`, `cgv_`, `cc_live_`) raises `retired_key`, and anything else, such as a session token, raises `invalid_key`. `parse_key(key)` reads a key's kind and workspace without a request.

## Browser sessions

Browser calls take an account key or a browser key (`cc_br_`):

```python
browser = CogniCloud(os.environ["COGNICLOUD_BROWSER_KEY"]).browser
session = browser.sessions.create(timeout_minutes=15)
```

Upload a profile folder packed as a `.tar.gz` (see the app docs for how to pack it), then start a session from it:

```python
profile = browser.import_profile("Shop account", "shop-profile.tar.gz")
session = browser.sessions.create(profile_id=profile.id)
```

```python
session = cc.browser.sessions.create(timeout_minutes=15)
print(session.cdp_url)   # connect Playwright, Puppeteer or any CDP client here

page = cc.browser.sessions.read_page(session.id)
cc.browser.sessions.act(session.id, {"type": "navigate", "url": "https://example.com"})
cc.browser.sessions.act(session.id, {"type": "click", "index": 3})

run = cc.browser.sessions.start_agent_run(session.id, "Find the price of the Pro plan", endpoint_id, credential)
print(cc.browser.sessions.get_agent_run(session.id, run.id).result)

# For serverless callers: a stored run that does one step per request.
stored = cc.browser.sessions.create_step_run(session.id, "Find the price", endpoint_id)
after = cc.browser.sessions.run_step(session.id, stored.id, credential, timeout_seconds=120)

cc.browser.sessions.stop(session.id)
```

- `act` takes `navigate`, `click`, `type`, `key`, `scroll`, `back` and `wait`, and returns the page afterwards. Each step of an agent run is a call billed to the endpoint.
- `timeout_minutes` is 1 to 240 and defaults to 15.
- `create(headful=True)` starts a visible Chrome window instead of a headless one, for sites that turn headless Chrome away. Needs browser service 0.10.0.
- Closing the CDP connection does not stop a session; call `sessions.stop`.
- `status` is `active` or `stopped`; `cdp_url` and `live_url` are `None` once stopped. `live_url` is a page where a person can watch and take over the browser.
- `sessions.list()` returns `items` and `concurrency` (`active`, `limit`). A start beyond the limit raises `CogniCloudError` with `status == 429` and `code == "concurrency_limit"`.
- Proxy countries, profiles, screen sizes, captcha solving and recording are not available yet. `browser.countries()` and `browser.profiles()` return empty lists.

## Mail

Mailboxes on the Flippico mail server, with an account key or a mail key (`cc_ml_`). The password is returned once; store it.

```python
created = cc.mail.create("support")
settings = cc.mail.connection_settings()  # IMAP and SMTP hosts, and default_domain

# Your own domain: add it, publish domain.records at your DNS provider, then verify.
domain = cc.mail.domains.add("yourcompany.com")
cc.mail.domains.verify(domain.id)
cc.mail.create("ceo", domain="yourcompany.com")
```

`mail.list`, `get`, `rotate_password` and `delete` manage mailboxes; `mail.domains.list`, `get` and `delete` manage domains.

## Database

Hosted Postgres. An account key or a database key (`cc_db_`) for every database creates and lists databases. `cc.database.data()` queries one: with a database key narrowed to one database it needs nothing else; with an account key, name the database, `cc.database.data(database.id)` (sent as `x-database-id`).

```python
from cognicloud import Statement

database = cc.database.create("Orders")
db = cc.database.data(database.id)

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

Pass values as `params`, never inside the SQL. They need no quotes and cannot break the statement:

```python
db.query("INSERT INTO members (id, user_id) VALUES ($1, $2)", [member_id, user_id])
```

`cc.database.query(database.id, sql, params)` and `cc.database.tables(database.id)` also work without `data`. `cc.database.list`, `get` and `delete` manage databases, and `cc.database.actions` lists what was done.

## Web builder

Build a React application and host it at `https://<subdomain>.cognicloud.dev`. Leave out `repo_url` to start from a Vite + React starter. Each person can have 3 applications.

```python
app = cc.web_builder.create("shop", repo_url="https://github.com/acme/shop")

status = cc.web_builder.get(app.id).status
logs = cc.web_builder.logs(app.id)
```

`create` starts the build and returns at once, with `status` set to `building`. It then becomes `running` or `failed`. `branch`, `build_command` and `output_dir` default to `main`, `npm run build` and `dist`. `cc.web_builder.list`, `redeploy` and `delete` do the rest.

```python
cc.web_builder.update(app.id, branch="next")
cc.web_builder.pause(app.id)
cc.web_builder.resume(app.id)
requests = cc.web_builder.runtime_logs(app.id)
history = cc.web_builder.actions(application_id=app.id)

cc.web_builder.create_repository(app.id, "shop")
cc.web_builder.enable_auto_deploy(app.id)
cc.web_builder.disable_auto_deploy(app.id)
```

`update` starts a build, and a paused site has `status` set to `paused`. `create_repository` and the auto-deploy methods need a connected GitHub account: `authorize_github`, `connect_github`, `github_repositories` and `disconnect_github`.

## Agents

An agent thinks with one of your AI Gateway endpoints, follows its instructions and skills, and answers a task. Creating it returns its `ccag_` credential once; store it.

```python
created = cc.agents.create(
    "Researcher",
    endpoint_id,
    "Answer briefly and cite sources.",
    tools=[],
    max_steps=20,
    timeout_seconds=300,
)
agent = created.agent
credential = created.credential

run = cc.runs.run_and_wait(agent.id, "What is CogniCloud?")
print(run.status, run.output)
```

`run_and_wait(agent_id, input, poll_interval=2.0, timeout=900.0)` starts a run and polls until it is no longer `running`. It returns the finished run, also when it `failed` or was `stopped`; read `error_code` and `error_message`. After `timeout` seconds it raises `CogniCloudError` with code `timeout`, and the run keeps going.

```python
started = cc.runs.start(agent.id, "Summarise today's news")
run = cc.runs.get(started.id)
page = cc.runs.list(agent.id, limit=20)        # page.items, page.next_cursor
cc.runs.stop(started.id)
```

- A run's `status` is `running`, `completed`, `failed` or `stopped`. `error_code` is `max_steps`, `timeout`, `model_error`, `invalid_answer`, `interrupted` or `stopped`. Each step has `number`, `thought`, `tool`, `summary` and `error`. Tools are refused in this release.
- `start` raises `CogniCloudError` with 409 `agent_paused`, 422 `endpoint_missing`, 429 `limit_reached`, or 503. Starts and stops are never retried.
- An Agents key (`cc_ag_`) narrowed to one agent replaces the old agent credential: it runs that agent and nothing else; other calls raise 403.

```python
agent_client = CogniCloud(os.environ["COGNICLOUD_AGENT_KEY"])
run = agent_client.runs.run_and_wait(agent_id, "Check the status page")
```

Manage agents and skills:

```python
cc.agents.list()
cc.agents.update(agent.id, status="paused")    # "active" resumes; database_id=None clears the database
new_credential = cc.agents.rotate_credential(agent.id)
cc.agents.delete(agent.id)

skill = cc.skills.create("Cite sources", "Always cite", "Cite every fact with its link.")
cc.skills.update(skill.id, body="Cite every fact.")
history = cc.skills.versions(skill.id)
cc.agents.update(agent.id, skill_ids=[skill.id])

log = cc.agents.actions(limit=50)              # log.items, log.next_cursor
```

`cc.agents.publish(agent_id, category=..., publisher_name=..., language=...)` and `unpublish` are planned: the service answers 503 until marketplace publishing ships.

## Marketplace

Agent templates to start from.

```python
templates = cc.marketplace.list_templates(category="research")
template = cc.marketplace.get_template("web-researcher")
cc.agents.create(
    template.name,
    endpoint_id,
    template.instructions,
    tools=template.tools,
    max_steps=template.max_steps,
    timeout_seconds=template.timeout_seconds,
    template_slug=template.slug,
)
log = cc.marketplace.actions()
```

## Call an endpoint

```python
from cognicloud import ResponsesRequest, McpTool, EmbeddingsRequest, DeltaEvent, DoneEvent, ErrorEvent

endpoint = cc.endpoint(os.environ["COGNICLOUD_ENDPOINT_ID"])

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

The call acts as the endpoint's owner, with an account key or an AI Gateway key; a key narrowed to one endpoint reaches only that one. The workspace in the invoke address comes from the key. `EndpointClient(api_key, endpoint_id=...)` or `EndpointClient(api_key, url=endpoint_url)` makes the same client without a `CogniCloud`.

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
| `api_key` | required | An account key or a product key from Settings → API keys. It names its workspace. |
| `locale` | `"en"` | `Accept-Language` for localised responses. |
| `timeout` | `30.0` | Seconds per request. |
| `max_retries` | `2` | For `429` and `5xx`, on reads only. Starts and stops are never retried. |
| `gateway_base_url` | `https://cognicloud.dev/api/v1/ai-gateway` | Point at another environment. |
| `browser_base_url` | `https://cognicloud.dev/api/v1/browser` | Point at another environment. |
| `mail_base_url` | `https://cognicloud.dev/api/v1/mail` | Point at another environment. |
| `database_base_url` | `https://cognicloud.dev/api/v1/database` | Point at another environment. |
| `web_builder_base_url` | `https://cognicloud.dev/api/v1/web-builder` | Point at another environment. |
| `agents_base_url` | `https://cognicloud.dev/api/v1/agents` | Point at another environment. |
| `marketplace_base_url` | `https://cognicloud.dev/api/v1/marketplace` | Point at another environment. |

## Migrating from 0.x

| 0.x | 1.0 |
| --- | --- |
| `CogniCloud(session_token, tenant=...)` | `CogniCloud(api_key)` with an account key |
| `EndpointClient("cc_live_...", endpoint_id=..., tenant=...)` | `cc.endpoint(endpoint_id)`, or `EndpointClient(api_key, endpoint_id=...)` |
| `CogniCloudBrowser("cgb_...")` | `CogniCloud("cc_br_...").browser` |
| `CogniCloudDatabase("cgd_...")` | `CogniCloud("cc_db_...").database.data()` |
| `CogniCloud("ccag_...")` | `CogniCloud("cc_ag_...")` narrowed to the agent |
| `cc.database.keys`, `cc.agents.keys` | Settings → API keys in the dashboard |

The old keys keep working on the services for two weeks after the new keys launch, then stop. SDK 1.0 refuses them at once with `retired_key`, so create the new keys before you upgrade.

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

The tests run against a local HTTP stub and need no network access.

See [CHANGELOG.md](./CHANGELOG.md).
