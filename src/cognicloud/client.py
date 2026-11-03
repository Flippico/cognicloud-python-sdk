from __future__ import annotations

from typing import Optional

from ._http import HttpConfig
from .errors import CogniCloudError
from .agents import AgentsApi, RunsApi, SkillsApi
from .browser import BrowserApi
from .database import DatabaseApi, DatabaseDataApi
from .mail import MailApi
from .marketplace import MarketplaceApi
from .web_builder import WebBuilderApi

DEFAULT_TENANT = "cognicloud"
DEFAULT_BROWSER_BASE_URL = "https://cognicloud.dev/api/v1/browser"
DEFAULT_MAIL_BASE_URL = "https://cognicloud.dev/api/v1/mail"
DEFAULT_DATABASE_BASE_URL = "https://cognicloud.dev/api/v1/database"
DEFAULT_WEB_BUILDER_BASE_URL = "https://cognicloud.dev/api/v1/web-builder"
DEFAULT_AGENTS_BASE_URL = "https://cognicloud.dev/api/v1/agents"
DEFAULT_MARKETPLACE_BASE_URL = "https://cognicloud.dev/api/v1/marketplace"
WORKSPACE_KEY_PREFIXES = ("ccag_", "cga_")


class CogniCloud:
    """Manage CogniCloud resources with the signed-in person's session.

    `token` is the Amadeus session token, sent as `Authorization: Bearer`. `tenant` is the workspace, sent as the
    `tenant_id` header; it defaults to the platform workspace, which every signed-in user may use. An agent credential
    (`ccag_`) or agents key (`cga_`) names its workspace, so with no `tenant` given, agents and marketplace calls send
    no `tenant_id`.
    """

    def __init__(
        self,
        token: str,
        *,
        tenant: Optional[str] = None,
        locale: str = "en",
        timeout: float = 30.0,
        max_retries: int = 2,
        browser_base_url: str = DEFAULT_BROWSER_BASE_URL,
        mail_base_url: str = DEFAULT_MAIL_BASE_URL,
        database_base_url: str = DEFAULT_DATABASE_BASE_URL,
        web_builder_base_url: str = DEFAULT_WEB_BUILDER_BASE_URL,
        agents_base_url: str = DEFAULT_AGENTS_BASE_URL,
        marketplace_base_url: str = DEFAULT_MARKETPLACE_BASE_URL,
    ) -> None:
        if not isinstance(token, str) or token.strip() == "":
            raise CogniCloudError(
                0,
                "missing_token",
                "A token is required: pass the signed-in person's token, or a browser key for browser calls.",
            )
        config = HttpConfig(base_url=browser_base_url, locale=locale, timeout=timeout, max_retries=max_retries)
        headers = {"authorization": f"Bearer {token}", "tenant_id": DEFAULT_TENANT if tenant is None else tenant}
        names_workspace = tenant is None and token.startswith(WORKSPACE_KEY_PREFIXES)
        agents_headers = {"authorization": f"Bearer {token}"} if names_workspace else headers
        self.browser = BrowserApi(config, headers)
        self.mail = MailApi(HttpConfig(base_url=mail_base_url, locale=locale, timeout=timeout, max_retries=max_retries), headers)
        self.database = DatabaseApi(
            HttpConfig(base_url=database_base_url, locale=locale, timeout=timeout, max_retries=max_retries), headers
        )
        self.web_builder = WebBuilderApi(
            HttpConfig(base_url=web_builder_base_url, locale=locale, timeout=timeout, max_retries=max_retries), headers
        )
        agents_config = HttpConfig(base_url=agents_base_url, locale=locale, timeout=timeout, max_retries=max_retries)
        self.agents = AgentsApi(agents_config, agents_headers)
        self.skills = SkillsApi(agents_config, agents_headers)
        self.runs = RunsApi(agents_config, agents_headers)
        self.marketplace = MarketplaceApi(
            HttpConfig(base_url=marketplace_base_url, locale=locale, timeout=timeout, max_retries=max_retries),
            agents_headers,
        )


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


class CogniCloudDatabase(DatabaseDataApi):
    """Queries one database. `key` is a database key from the dashboard (Database → API keys); it names its database
    and workspace, so no tenant is sent and no Amadeus token is needed.
    """

    def __init__(
        self,
        key: str,
        *,
        locale: str = "en",
        timeout: float = 30.0,
        max_retries: int = 2,
        database_base_url: str = DEFAULT_DATABASE_BASE_URL,
    ) -> None:
        if not isinstance(key, str) or key.strip() == "":
            raise CogniCloudError(
                0,
                "missing_key",
                "A database key is required. Create one in the dashboard under Database → API keys.",
            )
        super().__init__(
            HttpConfig(base_url=database_base_url, locale=locale, timeout=timeout, max_retries=max_retries), key
        )
