from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import quote

from ._http import HttpConfig, request


def _screen(data: Optional[dict[str, Any]]) -> Optional[BrowserScreen]:
    if data is None:
        return None
    return BrowserScreen(width=data["width"], height=data["height"])


@dataclass(frozen=True)
class BrowserSession:
    """A session is `active` until it stops; then `cdp_url` and `live_url` are None."""

    id: str
    status: str
    cdp_url: Optional[str]
    live_url: Optional[str]
    profile_id: Optional[str]
    proxy_country_code: Optional[str]
    solve_captchas: bool
    recording: bool
    screen: Optional[BrowserScreen]
    timeout_at: str
    started_at: str
    finished_at: Optional[str]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "BrowserSession":
        return cls(
            id=data["id"],
            status=data["status"],
            cdp_url=data.get("cdpUrl"),
            live_url=data.get("liveUrl"),
            profile_id=data.get("profileId"),
            proxy_country_code=data.get("proxyCountryCode"),
            solve_captchas=bool(data.get("solveCaptchas")),
            recording=bool(data.get("recording")),
            screen=_screen(data.get("screen")),
            timeout_at=data["timeoutAt"],
            started_at=data["startedAt"],
            finished_at=data.get("finishedAt"),
        )


@dataclass(frozen=True)
class BrowserScreen:
    width: int
    height: int


@dataclass(frozen=True)
class BrowserConcurrency:
    active: int
    limit: int


@dataclass(frozen=True)
class BrowserSessionList:
    items: list[BrowserSession]
    concurrency: BrowserConcurrency

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "BrowserSessionList":
        concurrency = data["concurrency"]
        return cls(
            items=[BrowserSession.from_json(item) for item in data["items"]],
            concurrency=BrowserConcurrency(active=concurrency["active"], limit=concurrency["limit"]),
        )


@dataclass(frozen=True)
class ProxyCountry:
    code: str
    name: str


@dataclass(frozen=True)
class BrowserProfile:
    id: str
    name: str
    size_bytes: int
    created_at: str
    last_used_at: Optional[str]
    expires_at: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "BrowserProfile":
        return cls(
            id=data["id"],
            name=data["name"],
            size_bytes=data["sizeBytes"],
            created_at=data["createdAt"],
            last_used_at=data.get("lastUsedAt"),
            expires_at=data["expiresAt"],
        )


class BrowserSessionsApi:
    """Starts, lists, reads and stops browser sessions."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers

    def create(
        self,
        timeout_minutes: Optional[int] = None,
        profile_id: Optional[str] = None,
        screen: Optional[BrowserScreen] = None,
    ) -> BrowserSession:
        """Starts a session. Its `cdp_url` and `live_url` carry the session token; treat them as secrets.

        `timeout_minutes` is 1 to 240 and defaults to 15. `profile_id` starts from a saved profile. `screen` is the
        window size, 320 to 6144 wide and 320 to 3456 high; Chrome starts with it. A start beyond the workspace's limit
        raises CogniCloudError with status 429 and code `concurrency_limit`.
        """
        body: dict[str, Any] = {}
        if timeout_minutes is not None:
            body["timeoutMinutes"] = timeout_minutes
        if profile_id is not None:
            body["profileId"] = profile_id
        if screen is not None:
            body["screen"] = {"width": screen.width, "height": screen.height}
        data = request(self._config, "POST", "/sessions", self._headers, body, retry=False)
        return BrowserSession.from_json(data)

    def list(self) -> BrowserSessionList:
        """The workspace's sessions, newest first, with concurrency."""
        return BrowserSessionList.from_json(request(self._config, "GET", "/sessions", self._headers))

    def get(self, session_id: str) -> BrowserSession:
        return BrowserSession.from_json(
            request(self._config, "GET", f"/sessions/{quote(session_id, safe='')}", self._headers)
        )

    def save_profile(self, session_id: str, name: str) -> BrowserProfile:
        """Closes the session's browser cleanly, keeps its profile under `name` and ends the session.

        Start a session with the returned `id` as `profile_id` to continue from those logins. A profile holds cookies
        and logins, so keep it private. Names are 1 to 80 characters and unique per person.
        """
        data = request(
            self._config,
            "POST",
            f"/sessions/{quote(session_id, safe='')}/profile",
            self._headers,
            {"name": name},
            retry=False,
        )
        return BrowserProfile.from_json(data)

    def stop(self, session_id: str) -> BrowserSession:
        """Closing the CDP connection does not stop a session; this does."""
        data = request(
            self._config, "POST", f"/sessions/{quote(session_id, safe='')}/stop", self._headers, retry=False
        )
        return BrowserSession.from_json(data)


class BrowserApi:
    """Manages the browser product with the signed-in person's session."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers
        self.sessions = BrowserSessionsApi(config, headers)

    def countries(self) -> list[ProxyCountry]:
        """Proxy countries a session can route through. Empty until proxies are available."""
        data = request(self._config, "GET", "/countries", self._headers)
        return [ProxyCountry(code=item["code"], name=item["name"]) for item in data]

    def profiles(self) -> list[BrowserProfile]:
        """Saved profiles, newest first. Save one with `browser.sessions.save_profile`."""
        data = request(self._config, "GET", "/profiles", self._headers)
        return [BrowserProfile.from_json(item) for item in data]
