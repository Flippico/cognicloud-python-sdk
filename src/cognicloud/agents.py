from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import quote, urlencode

from ._http import HttpConfig, request
from .errors import CogniCloudError

_KEEP: Any = object()


def _query(pairs: tuple[tuple[str, Any], ...]) -> str:
    query = {key: value for key, value in pairs if value is not None}
    return f"?{urlencode(query)}" if query else ""


@dataclass(frozen=True)
class Agent:
    """`status` is `active` or `paused`. `visibility` is `private` or `public`."""

    id: str
    name: str
    description: str
    endpoint_id: str
    instructions: str
    tools: list[str]
    database_id: Optional[str]
    max_steps: int
    timeout_seconds: int
    status: str
    invoke_url: str
    credential_prefix: str
    template_slug: Optional[str]
    skill_ids: list[str]
    visibility: str
    listing_slug: Optional[str]
    published_version: Optional[int]
    has_unpublished_changes: bool
    created_at: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Agent":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            endpoint_id=data["endpointId"],
            instructions=data["instructions"],
            tools=data["tools"],
            database_id=data.get("databaseId"),
            max_steps=data["maxSteps"],
            timeout_seconds=data["timeoutSeconds"],
            status=data["status"],
            invoke_url=data["invokeUrl"],
            credential_prefix=data["credentialPrefix"],
            template_slug=data.get("templateSlug"),
            skill_ids=data["skillIds"],
            visibility=data["visibility"],
            listing_slug=data.get("listingSlug"),
            published_version=data.get("publishedVersion"),
            has_unpublished_changes=bool(data.get("hasUnpublishedChanges")),
            created_at=data["createdAt"],
        )


@dataclass(frozen=True)
class CreatedAgent:
    """`credential` is the agent's `ccag_` secret. It is returned only here and on rotation; store it."""

    agent: Agent
    credential: str = field(repr=False)


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    description: str
    body: str
    version: int
    created_at: str
    updated_at: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Skill":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            body=data["body"],
            version=data["version"],
            created_at=data["createdAt"],
            updated_at=data["updatedAt"],
        )


@dataclass(frozen=True)
class SkillVersion:
    version: int
    name: str
    description: str
    body: str
    created_at: str


@dataclass(frozen=True)
class AgentKey:
    """`prefix` tells keys apart. The full key is shown once, in the dashboard."""

    id: str
    name: str
    prefix: str
    created_at: str
    last_used_at: Optional[str]


@dataclass(frozen=True)
class AgentAction:
    """`outcome` is `started`, `succeeded` or `failed`."""

    id: str
    action: str
    subject_id: Optional[str]
    started_at: str
    finished_at: Optional[str]
    duration_ms: Optional[int]
    outcome: str
    error_code: Optional[str]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "AgentAction":
        return cls(
            id=data["id"],
            action=data["action"],
            subject_id=data.get("subjectId"),
            started_at=data["startedAt"],
            finished_at=data.get("finishedAt"),
            duration_ms=data.get("durationMs"),
            outcome=data["outcome"],
            error_code=data.get("errorCode"),
        )


@dataclass(frozen=True)
class AgentActionList:
    """Pass `next_cursor` as `cursor` for the next page. It is None on the last page."""

    items: list[AgentAction]
    next_cursor: Optional[str]


@dataclass(frozen=True)
class RunStep:
    """`tool` is the tool the step asked for, or None. `error` says why the step failed, such as a refused tool."""

    number: int
    thought: str
    tool: Optional[str]
    summary: str
    error: Optional[str]


@dataclass(frozen=True)
class Run:
    """`status` is `running`, `completed`, `failed` or `stopped`. `error_code` is `max_steps`, `timeout`,
    `model_error`, `invalid_answer`, `interrupted` or `stopped`."""

    id: str
    agent_id: str
    status: str
    input: str
    output: Optional[str]
    steps: list[RunStep]
    error_code: Optional[str]
    error_message: Optional[str]
    max_steps: int
    timeout_seconds: int
    created_at: str
    finished_at: Optional[str]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Run":
        return cls(
            id=data["id"],
            agent_id=data["agentId"],
            status=data["status"],
            input=data["input"],
            output=data.get("output"),
            steps=[
                RunStep(
                    number=step["number"],
                    thought=step["thought"],
                    tool=step.get("tool"),
                    summary=step["summary"],
                    error=step.get("error"),
                )
                for step in data["steps"]
            ],
            error_code=data.get("errorCode"),
            error_message=data.get("errorMessage"),
            max_steps=data["maxSteps"],
            timeout_seconds=data["timeoutSeconds"],
            created_at=data["createdAt"],
            finished_at=data.get("finishedAt"),
        )


@dataclass(frozen=True)
class RunList:
    """Newest first. Pass `next_cursor` as `cursor` for the next page. It is None on the last page."""

    items: list[Run]
    next_cursor: Optional[str]


class AgentKeysApi:
    """Agents keys (`cga_`) are created in the dashboard."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers

    def list(self) -> list[AgentKey]:
        data = request(self._config, "GET", "/keys", self._headers)
        return [
            AgentKey(
                id=item["id"],
                name=item["name"],
                prefix=item["prefix"],
                created_at=item["createdAt"],
                last_used_at=item.get("lastUsedAt"),
            )
            for item in data
        ]

    def revoke(self, key_id: str) -> None:
        request(self._config, "DELETE", f"/keys/{quote(key_id, safe='')}", self._headers, retry=False)


class AgentsApi:
    """Creates and manages agents. Runs are on `runs`, skills on `skills`."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers
        self.keys = AgentKeysApi(config, headers)

    def _path(self, agent_id: str) -> str:
        return f"/agents/{quote(agent_id, safe='')}"

    def list(self) -> list[Agent]:
        """Newest first."""
        return [Agent.from_json(item) for item in request(self._config, "GET", "/agents", self._headers)]

    def get(self, agent_id: str) -> Agent:
        return Agent.from_json(request(self._config, "GET", self._path(agent_id), self._headers))

    def create(
        self,
        name: str,
        endpoint_id: str,
        instructions: str,
        *,
        tools: list[str],
        max_steps: int,
        timeout_seconds: int,
        description: Optional[str] = None,
        database_id: Optional[str] = None,
        skill_ids: Optional[list[str]] = None,
        template_slug: Optional[str] = None,
    ) -> CreatedAgent:
        """`endpoint_id` is the AI Gateway endpoint the agent thinks with. The returned credential is shown once."""
        body: dict[str, Any] = {
            "name": name,
            "endpointId": endpoint_id,
            "instructions": instructions,
            "tools": tools,
            "maxSteps": max_steps,
            "timeoutSeconds": timeout_seconds,
        }
        optional = {
            "description": description,
            "databaseId": database_id,
            "skillIds": skill_ids,
            "templateSlug": template_slug,
        }
        body.update({key: value for key, value in optional.items() if value is not None})
        data = request(self._config, "POST", "/agents", self._headers, body, retry=False)
        return CreatedAgent(agent=Agent.from_json(data["agent"]), credential=data["credential"]["secret"])

    def update(
        self,
        agent_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        endpoint_id: Optional[str] = None,
        instructions: Optional[str] = None,
        tools: Optional[list[str]] = None,
        database_id: Any = _KEEP,
        max_steps: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        skill_ids: Optional[list[str]] = None,
        status: Optional[str] = None,
    ) -> Agent:
        """A field left out stays as it is. `database_id=None` clears the database. `status` is `paused` or `active`."""
        optional = {
            "name": name,
            "description": description,
            "endpointId": endpoint_id,
            "instructions": instructions,
            "tools": tools,
            "maxSteps": max_steps,
            "timeoutSeconds": timeout_seconds,
            "skillIds": skill_ids,
            "status": status,
        }
        body: dict[str, Any] = {key: value for key, value in optional.items() if value is not None}
        if database_id is not _KEEP:
            body["databaseId"] = database_id
        return Agent.from_json(request(self._config, "PATCH", self._path(agent_id), self._headers, body, retry=False))

    def delete(self, agent_id: str) -> None:
        """Deletes the agent and its runs."""
        request(self._config, "DELETE", self._path(agent_id), self._headers, retry=False)

    def rotate_credential(self, agent_id: str) -> str:
        """Returns the new `ccag_` secret, shown once. The earlier one stops working at once."""
        path = f"{self._path(agent_id)}/credential/rotate"
        return request(self._config, "POST", path, self._headers, retry=False)["secret"]

    def publish(self, agent_id: str, *, category: str, publisher_name: str, language: str) -> Agent:
        """Planned: lists the agent in the marketplace. Not available yet; the service answers 503."""
        body = {"category": category, "publisherName": publisher_name, "language": language}
        path = f"{self._path(agent_id)}/publish"
        return Agent.from_json(request(self._config, "POST", path, self._headers, body, retry=False))

    def unpublish(self, agent_id: str) -> Agent:
        """Planned: removes the agent from the marketplace. Not available yet; the service answers 503."""
        path = f"{self._path(agent_id)}/unpublish"
        return Agent.from_json(request(self._config, "POST", path, self._headers, retry=False))

    def actions(self, limit: Optional[int] = None, cursor: Optional[str] = None) -> AgentActionList:
        """Newest first."""
        suffix = _query((("limit", limit), ("cursor", cursor)))
        data = request(self._config, "GET", f"/actions{suffix}", self._headers)
        return AgentActionList(
            items=[AgentAction.from_json(item) for item in data["items"]],
            next_cursor=data.get("nextCursor"),
        )


class SkillsApi:
    """Instructions agents share. Each change makes a new version."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers

    def _path(self, skill_id: str) -> str:
        return f"/skills/{quote(skill_id, safe='')}"

    def list(self) -> list[Skill]:
        return [Skill.from_json(item) for item in request(self._config, "GET", "/skills", self._headers)]

    def get(self, skill_id: str) -> Skill:
        return Skill.from_json(request(self._config, "GET", self._path(skill_id), self._headers))

    def create(self, name: str, description: str, body: str) -> Skill:
        payload = {"name": name, "description": description, "body": body}
        return Skill.from_json(request(self._config, "POST", "/skills", self._headers, payload, retry=False))

    def update(
        self,
        skill_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        body: Optional[str] = None,
    ) -> Skill:
        """A field left out stays as it is."""
        optional = {"name": name, "description": description, "body": body}
        payload = {key: value for key, value in optional.items() if value is not None}
        return Skill.from_json(request(self._config, "PATCH", self._path(skill_id), self._headers, payload, retry=False))

    def delete(self, skill_id: str) -> None:
        request(self._config, "DELETE", self._path(skill_id), self._headers, retry=False)

    def versions(self, skill_id: str) -> list[SkillVersion]:
        data = request(self._config, "GET", f"{self._path(skill_id)}/versions", self._headers)
        return [
            SkillVersion(
                version=item["version"],
                name=item["name"],
                description=item["description"],
                body=item["body"],
                created_at=item["createdAt"],
            )
            for item in data
        ]


class RunsApi:
    """Starts, watches and stops runs of an agent. Works with the agent's `ccag_` credential too."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers

    def _runs_path(self, agent_id: str) -> str:
        return f"/agents/{quote(agent_id, safe='')}/runs"

    def _run_path(self, run_id: str) -> str:
        return f"/runs/{quote(run_id, safe='')}"

    def start(self, agent_id: str, input: str) -> Run:
        """Starts a run and returns at once with `status` `running`. Never retried.

        Raises CogniCloudError with 409 `agent_paused`, 422 `endpoint_missing`, 429 `limit_reached`, or 503.
        """
        path = self._runs_path(agent_id)
        return Run.from_json(request(self._config, "POST", path, self._headers, {"input": input}, retry=False))

    def get(self, run_id: str) -> Run:
        return Run.from_json(request(self._config, "GET", self._run_path(run_id), self._headers))

    def list(self, agent_id: str, *, limit: Optional[int] = None, cursor: Optional[str] = None) -> RunList:
        suffix = _query((("limit", limit), ("cursor", cursor)))
        data = request(self._config, "GET", f"{self._runs_path(agent_id)}{suffix}", self._headers)
        return RunList(items=[Run.from_json(item) for item in data["items"]], next_cursor=data.get("nextCursor"))

    def stop(self, run_id: str) -> Run:
        return Run.from_json(request(self._config, "POST", f"{self._run_path(run_id)}/stop", self._headers, retry=False))

    def run_and_wait(self, agent_id: str, input: str, poll_interval: float = 2.0, timeout: float = 900.0) -> Run:
        """Starts a run and polls every `poll_interval` seconds until it is no longer `running`.

        Raises CogniCloudError with code `timeout` after `timeout` seconds; the run keeps going until it ends or is
        stopped. Raises ValueError for a negative `poll_interval` or `timeout`.
        """
        if poll_interval < 0 or timeout < 0:
            raise ValueError("poll_interval and timeout must not be negative")
        deadline = time.monotonic() + timeout
        run = self.start(agent_id, input)
        while run.status == "running":
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CogniCloudError(0, "timeout", "The run did not finish in time.")
            time.sleep(min(poll_interval, remaining))
            run = self.get(run.id)
        return run
