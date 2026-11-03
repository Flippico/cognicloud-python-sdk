from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import quote, urlencode

from ._http import HttpConfig, request


@dataclass(frozen=True)
class TemplatePublisher:
    """`workspace` is set for CogniCloud's own templates."""

    name: str
    workspace: Optional[str]


@dataclass(frozen=True)
class TemplateSkill:
    name: str
    description: str
    body: str


@dataclass(frozen=True)
class Template:
    """An agent to start from. Pass `slug` as `template_slug` when creating an agent."""

    slug: str
    kind: str
    version: int
    language: Optional[str]
    name: str
    summary: str
    description: str
    category: str
    publisher: TemplatePublisher
    tools: list[str]
    instructions: str
    max_steps: int
    timeout_seconds: int
    skills: list[TemplateSkill]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Template":
        publisher = data["publisher"]
        return cls(
            slug=data["slug"],
            kind=data["kind"],
            version=data["version"],
            language=data.get("language"),
            name=data["name"],
            summary=data["summary"],
            description=data["description"],
            category=data["category"],
            publisher=TemplatePublisher(name=publisher["name"], workspace=publisher.get("workspace")),
            tools=data["tools"],
            instructions=data["instructions"],
            max_steps=data["maxSteps"],
            timeout_seconds=data["timeoutSeconds"],
            skills=[
                TemplateSkill(name=skill["name"], description=skill["description"], body=skill["body"])
                for skill in data["skills"]
            ],
        )


@dataclass(frozen=True)
class MarketplaceAction:
    """`outcome` is `started`, `succeeded` or `failed`."""

    id: str
    action: str
    subject_id: Optional[str]
    started_at: str
    finished_at: Optional[str]
    duration_ms: Optional[int]
    outcome: str
    error_code: Optional[str]


@dataclass(frozen=True)
class MarketplaceActionList:
    """Pass `next_cursor` as `cursor` for the next page. It is None on the last page."""

    items: list[MarketplaceAction]
    next_cursor: Optional[str]


class MarketplaceApi:
    """Agent templates to start from."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers

    def list_templates(self, category: Optional[str] = None) -> list[Template]:
        """`category` is `research`, `monitoring`, `operations` or `data`."""
        suffix = f"?{urlencode({'category': category})}" if category is not None else ""
        data = request(self._config, "GET", f"/templates{suffix}", self._headers)
        return [Template.from_json(item) for item in data]

    def get_template(self, slug: str) -> Template:
        return Template.from_json(request(self._config, "GET", f"/templates/{quote(slug, safe='')}", self._headers))

    def actions(self, limit: Optional[int] = None, cursor: Optional[str] = None) -> MarketplaceActionList:
        """Newest first."""
        pairs = (("limit", limit), ("cursor", cursor))
        query = {key: value for key, value in pairs if value is not None}
        suffix = f"?{urlencode(query)}" if query else ""
        data = request(self._config, "GET", f"/actions{suffix}", self._headers)
        return MarketplaceActionList(
            items=[
                MarketplaceAction(
                    id=item["id"],
                    action=item["action"],
                    subject_id=item.get("subjectId"),
                    started_at=item["startedAt"],
                    finished_at=item.get("finishedAt"),
                    duration_ms=item.get("durationMs"),
                    outcome=item["outcome"],
                    error_code=item.get("errorCode"),
                )
                for item in data["items"]
            ],
            next_cursor=data.get("nextCursor"),
        )
