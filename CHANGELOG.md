# Changelog

## [2.1.0] - 2026-11-20

### Added
- `client.storage` manages buckets and objects, with a storage key (`cc_st_`, `product_keys["storage"]`): `buckets` (`list`, `get`, `create`, `update`, `delete`, with `force=True` to delete a non-empty bucket), `objects` (`list` with `prefix`, `delimiter`, `cursor` and `limit`, `pages` over every page, `upload` from bytes, a bytearray, a memoryview, a `pathlib.Path` or an open binary file (a `str` raises `TypeError`, so text is never read as a path), `download` with `range_`, `metadata`, `delete`) and `folders.create`. `Bucket`, `ObjectList`, `StorageObject`, `ObjectMetadata` and `Visibility` are exported. The `storage_base_url` option points it at another environment.
- Object keys and prefixes are checked before any request: an empty, `.` or `..` part, a leading `/`, a control character or an empty key raises `CogniCloudError` with code `invalid_key`. One trailing `/` is allowed. Each key part is URL-encoded on its own.
- `CogniCloudError` with status `409` and code `conflict` when a bucket with objects is deleted without `force`.

### Documentation
- README: Storage section, the `cc_st_` key and the `storage_base_url` option.

### Notes
- Needs storage service 0.2.0 and Core with `cc_st_` keys.

## [2.0.0] - 2026-11-14

### Breaking
- An account key is required and works in a pair with a product key. `CogniCloud(account_key, product_keys)` replaces `CogniCloud(api_key)`; `product_keys` maps `gateway`, `database`, `browser`, `mail` and `agents` to their keys. Each call sends its product key as the Bearer token and the account key in `X-CogniCloud-Account-Key`; the services refuse a product key alone (`401`) and an account key alone (`403`).
- `EndpointClient(account_key, gateway_key, ...)` instead of `EndpointClient(api_key, ...)`.
- `browser`, `mail`, `database`, `agents`, `skills` and `runs` are properties that raise `missing_product_key` when their key is missing. Web Builder and the marketplace send the account key alone.
- New error codes when the client is created: `missing_account_key`, `key_mismatch`, `invalid_key` for a key of the wrong kind.

### Added
- `check_keys`, `ACCOUNT_KEY_HEADER`. README: API keys rewritten, "Migrating from 1.x".
- Needs the services on common-lib 0.10.0.

## [1.0.0] - Unreleased

### Breaking
- One API key signs every call. `CogniCloud(api_key)` takes an account key (`cc_acc_`) for every product or a product key (`cc_gw_`, `cc_db_`, `cc_br_`, `cc_ml_`, `cc_ag_`) for one, created in the dashboard under Settings → API keys. The key names its workspace: the `token` and `tenant` arguments and the `tenant_id` header are gone.
- `EndpointClient` takes `api_key` instead of the endpoint credential and `tenant`, and calls the endpoint as its owner; `client.endpoint(id)` makes one from a client (`gateway_base_url` option).
- Removed: `CogniCloudBrowser` and `CogniCloudDatabase` (use `CogniCloud(api_key)` with a browser or database key), `database.keys`, `agents.keys`, `DatabaseKey`, `DatabaseKeysApi`, `AgentKey` and `AgentKeysApi`. Keys are managed in the dashboard.
- A key in a retired format (`cgb_`, `cgd_`, `cga_`, `ccag_`, `cgm_`, `cgv_`, `cc_live_`) raises `retired_key` when the client is created, and anything that is not a key raises `invalid_key`; a missing one raises `missing_key`.

### Added
- `client.database.data(database_id=None)` queries a database: a database key narrowed to one database needs no id; an account key sends it as `x-database-id`.
- `parse_key(key)` and `ParsedKey` read a key's kind and workspace without a request.
- README: API keys and a "Migrating from 0.x" table.
- Needs core 0.14.0, ai-gateway 0.10.0, agents 0.18.0, browser 0.13.0, database 0.5.0 and mail 0.11.0.

## [0.24.0] - Unreleased

### Added
- `client.agents` manages agents: `list`, `get`, `create` (returns the `ccag_` credential once), `update`, `delete`, `rotate_credential` and `actions`; `agents.keys.list` and `revoke`. `publish` and `unpublish` are planned and answer 503 for now.
- `client.skills`: `list`, `get`, `create`, `update`, `delete` and `versions`.
- `client.runs` runs agents: `start`, `get`, `list`, `stop`, and `run_and_wait(agent_id, input, poll_interval=2.0, timeout=900.0)`, which returns the finished run and raises `CogniCloudError` with code `timeout` when time runs out; a negative `poll_interval` or `timeout` raises `ValueError`. `Run`, `RunStep` and `RunList` are exported. Needs agents service 0.2.0.
- `client.marketplace`: `list_templates`, `get_template` and `actions`.
- The `agents_base_url` and `marketplace_base_url` options point them at another environment.
- A client made with an agent credential (`ccag_`) or agents key (`cga_`) and no `tenant` sends no `tenant_id` to agents and marketplace, because the credential names its workspace.
- `browser.sessions.create(headful=True)` starts a visible Chrome window. Needs browser service 0.10.0.

## [0.23.0] - 2026-11-02

### Added
- `browser.sessions.set_step_run_file` gives a stored run the file its agent uploads, and `StepRun.file_name` names it. `browser.delete_profile` deletes a saved profile. Needs browser service 0.8.0.
- Session lists give `concurrency.available`, the slots free on the service. `concurrency.active` now counts only your own sessions.

## [0.22.0] - 2026-11-02

### Added
- Browser sessions: stored runs that do one step per request. `create_step_run`, `get_step_run`, `run_step`, `step_run_human_done`, `report_step_run_upload`, `send_step_run_message`, `continue_step_run` and `stop_step_run`. Needs browser service 0.7.0.

## [0.21.0] - 2026-11-02

### Added
- Browser sessions: `read_page` and `act` control a page without a CDP client. `start_agent_run`, `get_agent_run` and `stop_agent_run` run an agent in the service. Needs browser service 0.6.0.

## [0.20.0] - 2026-11-02

### Added
- Web Builder: `update`, `pause`, `resume`, `runtime_logs`, `create_repository`, `enable_auto_deploy`, `disable_auto_deploy`, `actions`, `authorize_github`, `connect_github`, `github_repositories` and `disconnect_github`.
- `Application.auto_deploy` and the `paused` status.

## [0.19.0] - 2026-11-01

### Added
- `client.web_builder` builds and hosts React applications on `<subdomain>.cognicloud.dev`: `create`, `list`, `get`, `redeploy`, `logs` and `delete`. The `web_builder_base_url` option points it at another environment.

## [0.18.0] - 2026-10-30

### Added
- `client.database.query(id, sql, params)` and `client.database.tables(id)` let a signed-in person run SQL and list tables in their own database, as its owner, without a key.

### Documentation
- The README explains passing values as parameters.

## [0.17.0] - 2026-10-30

### Added
- `CogniCloudDatabase` queries a hosted database with a database key: `query`, `transaction`, `tables`, and `table(name)` with `select`, `insert`, `update` and `delete`.
- `client.database` manages databases, their keys (`keys.list`, `keys.revoke`) and the action log (`actions`). The `database_base_url` option points it at another environment.
- `CogniCloudError.query_code` carries the Postgres code of a failed statement.

## [0.16.0] - 2026-10-30

### Added
- Custom mail domains: `mail.domains` lists, reads, adds, verifies and deletes your own domains, each with the DNS records to publish and their last check. `mail.create(local_part, domain=...)` creates a mailbox on one of your verified domains.
- Mail connection settings include `default_domain`, the shared domain.

### Documentation
- The README has a Mail section, and documents the mail base URL option and its default, `https://cognicloud.dev/api/v1/mail`.

## [0.15.0] - 2026-10-30

### Changed
- The default service URLs are on `https://cognicloud.dev`: `https://cognicloud.dev/api/v1/ai-gateway`, `https://cognicloud.dev/api/v1/browser` and `https://cognicloud.dev/api/v1/mail`, instead of `cognicloud.flippi.co`. Set the base URL options to keep using the old host.

## [0.14.0] - 2026-10-29

- `client.mail` manages mailboxes on the Flippico mail server: `create(local_part)` returns the generated password once, `list`, `get`, `delete`, `rotate_password`, and `connection_settings`. The `mail_base_url` option points it at another environment.

## [0.13.0] - 2026-10-26

- `browser.import_profile(name, archive)` uploads a Chrome profile folder packed as a `.tar.gz` (bytes or a file path), so sessions can start from it (`profile_id`).

## [0.12.0] - 2026-10-26

- `create(screen=BrowserScreen(width, height))` sets the window size: 320 to 6144 wide, 320 to 3456 high. Chrome starts with it, and the session returns it.

## [0.11.0] - 2026-10-26

- `CogniCloudBrowser(key)` uses the browser product with a browser key alone: no Amadeus token and no tenant. A browser key names its workspace.

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
