from __future__ import annotations

from collections.abc import Mapping
from typing import Optional

from ._http import HttpConfig
from .agents import AgentsApi, RunsApi, SkillsApi
from .browser import BrowserApi
from .database import DatabaseApi
from .endpoint import DEFAULT_GATEWAY_BASE_URL, EndpointClient
from .keys import check_keys, pair_headers
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
    """Every CogniCloud product: your account key together with one product key per product.

    `account_key` (`cc_acc_`) is required and sent with every call. `product_keys` maps a product to its key:
    `gateway` (`cc_gw_`), `database` (`cc_db_`), `browser` (`cc_br_`), `mail` (`cc_ml_`), `agents` (`cc_ag_`). Each
    call sends its product key as the Bearer token and the account key in `X-CogniCloud-Account-Key`. Create both in
    the dashboard under Settings → API keys. Web Builder and the marketplace take the account key alone for now.
    """

    def __init__(
        self,
        account_key: str,
        product_keys: Optional[Mapping[str, Optional[str]]] = None,
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
        self._keys = dict(product_keys or {})
        check_keys(account_key, self._keys)
        self._account_key = account_key
        self._gateway = dict(base_url=gateway_base_url, locale=locale, timeout=timeout, max_retries=max_retries)

        def config(base_url: str) -> HttpConfig:
            return HttpConfig(base_url=base_url, locale=locale, timeout=timeout, max_retries=max_retries)

        self._configs = {
            "browser": config(browser_base_url),
            "mail": config(mail_base_url),
            "database": config(database_base_url),
            "agents": config(agents_base_url),
        }
        account_only = {"authorization": f"Bearer {account_key}"}
        self.web_builder = WebBuilderApi(config(web_builder_base_url), account_only)
        self.marketplace = MarketplaceApi(config(marketplace_base_url), account_only)

    def _headers(self, product: str) -> dict[str, str]:
        return pair_headers(self._account_key, self._keys, product)

    @property
    def browser(self) -> BrowserApi:
        """Needs `product_keys["browser"]`."""
        return BrowserApi(self._configs["browser"], self._headers("browser"))

    @property
    def mail(self) -> MailApi:
        """Needs `product_keys["mail"]`."""
        return MailApi(self._configs["mail"], self._headers("mail"))

    @property
    def database(self) -> DatabaseApi:
        """Needs `product_keys["database"]`."""
        return DatabaseApi(self._configs["database"], self._headers("database"))

    @property
    def agents(self) -> AgentsApi:
        """Needs `product_keys["agents"]`."""
        return AgentsApi(self._configs["agents"], self._headers("agents"))

    @property
    def skills(self) -> SkillsApi:
        """Needs `product_keys["agents"]`."""
        return SkillsApi(self._configs["agents"], self._headers("agents"))

    @property
    def runs(self) -> RunsApi:
        """Needs `product_keys["agents"]`."""
        return RunsApi(self._configs["agents"], self._headers("agents"))

    def endpoint(self, endpoint_id: str) -> EndpointClient:
        """Calls one AI Gateway endpoint as its owner. Needs `product_keys["gateway"]`."""
        self._headers("gateway")
        return EndpointClient(self._account_key, self._keys["gateway"], endpoint_id=endpoint_id, **self._gateway)
