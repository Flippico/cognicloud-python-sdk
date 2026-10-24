# Changelog

## [0.4.0] - 2026-10-24

First release. Browser sessions:

- `CogniCloud(token, tenant=..., locale=..., timeout=..., max_retries=..., browser_base_url=...)`.
- `browser.sessions.create(timeout_minutes=None)`, `list()`, `get(id)`, `stop(id)`.
- `browser.countries()` and `browser.profiles()` return empty lists until those features exist.
- `CogniCloudError` with `status`, `code` and `message`.
- Standard library only; Python 3.10 or newer.
