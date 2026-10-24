from __future__ import annotations

from dataclasses import dataclass

from ._http import HttpConfig
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
        config = HttpConfig(base_url=browser_base_url, locale=locale, timeout=timeout, max_retries=max_retries)
        headers = {"authorization": f"Bearer {token}", "tenant_id": tenant}
        self.browser = BrowserApi(config, headers)
