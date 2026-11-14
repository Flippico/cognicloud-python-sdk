from __future__ import annotations

from ._http import HttpConfig
from .agents import AgentsApi, RunsApi, SkillsApi
from .browser import BrowserApi
from .database import DatabaseApi
from .endpoint import DEFAULT_GATEWAY_BASE_URL, EndpointClient
from .keys import parse_key
from .mail import MailApi
from .marketplace import MarketplaceApi
from .web_builder import WebBuilderApi

DEFAULT_BROWSER_BASE_URL = "https://cognicloud.dev/api/v1/browser"
DEFAULT_MAIL_BASE_URL = "https://cognicloud.dev/api/v1/mail"
DEFAULT_DATABASE_BASE_URL = "https://cognicloud.dev/api/v1/database"
DEFAULT_WEB_BUILDER_BASE_URL = "https://cognicloud.dev/api/v1/web-builder"
DEFAULT_AGENTS_BASE_URL = "https://cognicloud.dev/api/v1/agents"
DEFAULT_MARKETPLACE_BASE_URL = "https://cognicloud.dev/api/v1/marketplace"


class CogniCloud:
    """Every CogniCloud product with one API key.

    `api_key` is an account key (`cc_acc_`) for every product, or a product key (`cc_gw_`, `cc_db_`, `cc_br_`,
    `cc_ml_`, `cc_ag_`) for one, created in the dashboard under Settings → API keys. It names its workspace, so no
    tenant is sent.
    """

    def __init__(
        self,
        api_key: str,
        *,
        locale: str = "en",
        timeout: float = 30.0,
        max_retries: int = 2,
        gateway_base_url: str = DEFAULT_GATEWAY_BASE_URL,
        browser_base_url: str = DEFAULT_BROWSER_BASE_URL,
        mail_base_url: str = DEFAULT_MAIL_BASE_URL,
        database_base_url: str = DEFAULT_DATABASE_BASE_URL,
        web_builder_base_url: str = DEFAULT_WEB_BUILDER_BASE_URL,
        agents_base_url: str = DEFAULT_AGENTS_BASE_URL,
        marketplace_base_url: str = DEFAULT_MARKETPLACE_BASE_URL,
    ) -> None:
        parse_key(api_key)
        self._api_key = api_key
        self._gateway = dict(base_url=gateway_base_url, locale=locale, timeout=timeout, max_retries=max_retries)

        def config(base_url: str) -> HttpConfig:
            return HttpConfig(base_url=base_url, locale=locale, timeout=timeout, max_retries=max_retries)

        headers = {"authorization": f"Bearer {api_key}"}
        self.browser = BrowserApi(config(browser_base_url), headers)
        self.mail = MailApi(config(mail_base_url), headers)
        self.database = DatabaseApi(config(database_base_url), headers)
        self.web_builder = WebBuilderApi(config(web_builder_base_url), headers)
        agents = config(agents_base_url)
        self.agents = AgentsApi(agents, headers)
        self.skills = SkillsApi(agents, headers)
        self.runs = RunsApi(agents, headers)
        self.marketplace = MarketplaceApi(config(marketplace_base_url), headers)

    def endpoint(self, endpoint_id: str) -> EndpointClient:
        """Calls one AI Gateway endpoint with this key, as its owner."""
        return EndpointClient(self._api_key, endpoint_id=endpoint_id, **self._gateway)
