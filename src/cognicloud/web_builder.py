from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import quote, urlencode

from ._http import HttpConfig, request


@dataclass(frozen=True)
class Application:
    """`status` is `building`, `running`, `failed`, `paused` or `unknown`."""

    id: str
    subdomain: str
    url: str
    status: str
    repo_url: Optional[str]
    branch: Optional[str]
    build_command: str
    output_dir: str
    created_at: str
    auto_deploy: bool = False

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Application":
        return cls(
            id=data["id"],
            subdomain=data["subdomain"],
            url=data["url"],
            status=data["status"],
            repo_url=data.get("repoUrl"),
            branch=data.get("branch"),
            build_command=data["buildCommand"],
            output_dir=data["outputDir"],
            created_at=data["createdAt"],
            auto_deploy=data.get("autoDeploy", False),
        )


@dataclass(frozen=True)
class WebBuilderAction:
    """`outcome` is `started`, `succeeded` or `failed`."""

    id: str
    action: str
    application_id: Optional[str]
    name: Optional[str]
    started_at: str
    finished_at: Optional[str]
    duration_ms: Optional[int]
    outcome: str
    error_code: Optional[str]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "WebBuilderAction":
        return cls(
            id=data["id"],
            action=data["action"],
            application_id=data.get("applicationId"),
            name=data.get("name"),
            started_at=data["startedAt"],
            finished_at=data.get("finishedAt"),
            duration_ms=data.get("durationMs"),
            outcome=data["outcome"],
            error_code=data.get("errorCode"),
        )


@dataclass(frozen=True)
class WebBuilderActionList:
    """Pass `next_cursor` as `cursor` for the next page. It is None on the last page."""

    items: list[WebBuilderAction]
    next_cursor: Optional[str]


@dataclass(frozen=True)
class GithubRepository:
    full_name: str
    url: str
    default_branch: str
    private: bool


@dataclass(frozen=True)
class GithubRepositories:
    login: str
    items: list[GithubRepository]


class WebBuilderApi:
    """Builds React applications and hosts them on their own subdomain."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers

    def _path(self, application_id: str) -> str:
        return f"/applications/{quote(application_id, safe='')}"

    def list(self) -> list[Application]:
        """Newest first."""
        data = request(self._config, "GET", "/applications", self._headers)
        return [Application.from_json(item) for item in data["items"]]

    def create(
        self,
        subdomain: str,
        *,
        repo_url: Optional[str] = None,
        branch: Optional[str] = None,
        build_command: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> Application:
        """Starts the build and returns at once. Leave out `repo_url` to build the React starter."""
        optional = {"repoUrl": repo_url, "branch": branch, "buildCommand": build_command, "outputDir": output_dir}
        body = {"subdomain": subdomain, **{key: value for key, value in optional.items() if value is not None}}
        return Application.from_json(request(self._config, "POST", "/applications", self._headers, body, retry=False))

    def get(self, application_id: str) -> Application:
        return Application.from_json(request(self._config, "GET", self._path(application_id), self._headers))

    def redeploy(self, application_id: str) -> Application:
        """Builds the latest code. The running version keeps serving until the new one is ready."""
        path = f"{self._path(application_id)}/redeploy"
        return Application.from_json(request(self._config, "POST", path, self._headers, retry=False))

    def logs(self, application_id: str) -> str:
        """The last 500 lines of the latest build."""
        return request(self._config, "GET", f"{self._path(application_id)}/logs", self._headers)["logs"]

    def update(
        self,
        application_id: str,
        *,
        repo_url: Optional[str] = None,
        branch: Optional[str] = None,
        build_command: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> Application:
        """Changes build settings and starts a build. A field left out stays as it is."""
        optional = {"repoUrl": repo_url, "branch": branch, "buildCommand": build_command, "outputDir": output_dir}
        body = {key: value for key, value in optional.items() if value is not None}
        path = self._path(application_id)
        return Application.from_json(request(self._config, "PATCH", path, self._headers, body, retry=False))

    def pause(self, application_id: str) -> Application:
        """Takes the site offline and keeps its settings and subdomain."""
        path = f"{self._path(application_id)}/pause"
        return Application.from_json(request(self._config, "POST", path, self._headers, retry=False))

    def resume(self, application_id: str) -> Application:
        """Builds the site again after `pause`."""
        path = f"{self._path(application_id)}/resume"
        return Application.from_json(request(self._config, "POST", path, self._headers, retry=False))

    def runtime_logs(self, application_id: str) -> str:
        """The web server's latest request logs."""
        return request(self._config, "GET", f"{self._path(application_id)}/runtime-logs", self._headers)["logs"]

    def create_repository(self, application_id: str, name: str) -> Application:
        """Creates a public GitHub repository from the starter and builds from it."""
        path = f"{self._path(application_id)}/repository"
        return Application.from_json(request(self._config, "POST", path, self._headers, {"name": name}, retry=False))

    def enable_auto_deploy(self, application_id: str) -> Application:
        """Turns on building and deploying on every push to the branch."""
        path = f"{self._path(application_id)}/auto-deploy"
        return Application.from_json(request(self._config, "PUT", path, self._headers, retry=False))

    def disable_auto_deploy(self, application_id: str) -> Application:
        path = f"{self._path(application_id)}/auto-deploy"
        return Application.from_json(request(self._config, "DELETE", path, self._headers, retry=False))

    def actions(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        application_id: Optional[str] = None,
    ) -> WebBuilderActionList:
        """Newest first. Pass `application_id` for one application's history."""
        pairs = (("limit", limit), ("cursor", cursor), ("applicationId", application_id))
        query = {key: value for key, value in pairs if value is not None}
        suffix = f"?{urlencode(query)}" if query else ""
        data = request(self._config, "GET", f"/actions{suffix}", self._headers)
        return WebBuilderActionList(
            items=[WebBuilderAction.from_json(item) for item in data["items"]],
            next_cursor=data.get("nextCursor"),
        )

    def authorize_github(self, redirect_uri: str) -> str:
        """The address to send the person to. GitHub returns to `redirect_uri` with `code` and `state`."""
        body = {"redirectUri": redirect_uri}
        return request(self._config, "POST", "/github/authorize", self._headers, body, retry=False)["authorizeUrl"]

    def connect_github(self, code: str, state: str) -> str:
        """Returns the GitHub login."""
        body = {"code": code, "state": state}
        return request(self._config, "POST", "/github/connect", self._headers, body, retry=False)["login"]

    def github_repositories(self) -> GithubRepositories:
        """The 100 most recently pushed repositories."""
        data = request(self._config, "GET", "/github/repositories", self._headers)
        return GithubRepositories(
            login=data["login"],
            items=[
                GithubRepository(
                    full_name=item["fullName"],
                    url=item["url"],
                    default_branch=item["defaultBranch"],
                    private=item["private"],
                )
                for item in data["items"]
            ],
        )

    def disconnect_github(self) -> None:
        """Removes this service's access. Deployed applications keep running."""
        request(self._config, "DELETE", "/github", self._headers, retry=False)

    def delete(self, application_id: str) -> None:
        """Takes the site offline and frees its subdomain. This cannot be undone."""
        request(self._config, "DELETE", self._path(application_id), self._headers, retry=False)
