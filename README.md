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
