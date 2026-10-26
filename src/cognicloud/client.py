from __future__ import annotations

from dataclasses import dataclass

from ._http import HttpConfig
from .errors import CogniCloudError
from .browser import BrowserApi

DEFAULT_TENANT = "cognicloud"
DEFAULT_BROWSER_BASE_URL = "https://cognicloud.flippi.co/api/v1/browser"


class CogniCloud:
    """Manage CogniCloud resources with the signed-in person's session.

    `token` is the Amadeus session token, sent as `Authorization: Bearer`. `tenant` is the workspace, sent as the
    `tenant_id` header; it defaults to the platform workspace, which every signed-in user may use.
    """

    def __init__(
        self,
        token: str,
        *,
        tenant: str = DEFAULT_TENANT,
        locale: str = "en",
        timeout: float = 30.0,
        max_retries: int = 2,
        browser_base_url: str = DEFAULT_BROWSER_BASE_URL,
    ) -> None:
        if not isinstance(token, str) or token.strip() == "":
            raise CogniCloudError(
                0,
                "missing_token",
                "A token is required: pass the signed-in person's token, or a browser key for browser calls.",
            )
        config = HttpConfig(base_url=browser_base_url, locale=locale, timeout=timeout, max_retries=max_retries)
        headers = {"authorization": f"Bearer {token}", "tenant_id": tenant}
        self.browser = BrowserApi(config, headers)


class CogniCloudBrowser:
    """The browser product alone. `key` is a browser key from the dashboard (Browser → API keys); it names its
    workspace, so no tenant is sent and no Amadeus token is needed.
    """

    def __init__(
        self,
        key: str,
        *,
        locale: str = "en",
        timeout: float = 30.0,
        max_retries: int = 2,
        browser_base_url: str = DEFAULT_BROWSER_BASE_URL,
    ) -> None:
        if not isinstance(key, str) or key.strip() == "":
            raise CogniCloudError(
                0,
                "missing_key",
                "A browser key is required. Create one in the dashboard under Browser → API keys.",
            )
        config = HttpConfig(base_url=browser_base_url, locale=locale, timeout=timeout, max_retries=max_retries)
        self.browser = BrowserApi(config, {"authorization": f"Bearer {key}"})
