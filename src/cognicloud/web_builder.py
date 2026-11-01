from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import quote

from ._http import HttpConfig, request


@dataclass(frozen=True)
class Application:
    """`status` is `building`, `running`, `failed` or `unknown`."""

    id: str
    subdomain: str
    url: str
    status: str
    repo_url: Optional[str]
    branch: Optional[str]
    build_command: str
    output_dir: str
    created_at: str

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
        )


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

    def delete(self, application_id: str) -> None:
        """Takes the site offline and frees its subdomain. This cannot be undone."""
        request(self._config, "DELETE", self._path(application_id), self._headers, retry=False)
