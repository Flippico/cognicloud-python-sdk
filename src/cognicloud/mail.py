from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import quote, urlencode

from ._http import HttpConfig, request


@dataclass(frozen=True)
class Mailbox:
    id: str
    address: str
    local_part: str
    domain: str
    created_at: str
    updated_at: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Mailbox":
        return cls(
            id=data["id"],
            address=data["address"],
            local_part=data["localPart"],
            domain=data["domain"],
            created_at=data["createdAt"],
            updated_at=data["updatedAt"],
        )


@dataclass(frozen=True)
class MailboxList:
    items: list[Mailbox]
    total: int
    limit: int
    offset: int

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "MailboxList":
        return cls(
            items=[Mailbox.from_json(item) for item in data["items"]],
            total=data["total"],
            limit=data["limit"],
            offset=data["offset"],
        )


@dataclass(frozen=True)
class CreatedMailbox:
    """`password` is returned once; the server keeps no copy."""

    mailbox: Mailbox
    password: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "CreatedMailbox":
        return cls(mailbox=Mailbox.from_json(data["mailbox"]), password=data["password"])


@dataclass(frozen=True)
class MailServerEndpoint:
    host: str
    port: int
    security: str


@dataclass(frozen=True)
class MailConnectionSettings:
    username_format: str
    imap: MailServerEndpoint
    smtp: MailServerEndpoint

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "MailConnectionSettings":
        return cls(
            username_format=data["usernameFormat"],
            imap=MailServerEndpoint(**_endpoint(data["imap"])),
            smtp=MailServerEndpoint(**_endpoint(data["smtp"])),
        )


def _endpoint(data: dict[str, Any]) -> dict[str, Any]:
    return {"host": data["host"], "port": data["port"], "security": data["security"]}


class MailApi:
    """Creates, lists and removes mailboxes on the Flippico mail server."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers

    def list(self, *, limit: Optional[int] = None, offset: Optional[int] = None) -> MailboxList:
        """Newest first."""
        query = {key: value for key, value in (("limit", limit), ("offset", offset)) if value is not None}
        suffix = f"?{urlencode(query)}" if query else ""
        return MailboxList.from_json(request(self._config, "GET", f"/mailboxes{suffix}", self._headers))

    def create(self, local_part: str) -> CreatedMailbox:
        """Creates `<local_part>@<domain>`. Save the returned password now; it is not stored."""
        data = request(self._config, "POST", "/mailboxes", self._headers, {"localPart": local_part}, retry=False)
        return CreatedMailbox.from_json(data)

    def get(self, mailbox_id: str) -> Mailbox:
        return Mailbox.from_json(
            request(self._config, "GET", f"/mailboxes/{quote(mailbox_id, safe='')}", self._headers)
        )

    def delete(self, mailbox_id: str) -> None:
        """Deletes the mailbox and its mail on the server."""
        request(self._config, "DELETE", f"/mailboxes/{quote(mailbox_id, safe='')}", self._headers, retry=False)

    def rotate_password(self, mailbox_id: str) -> str:
        """Replaces the password on the server and returns the new one once."""
        data = request(
            self._config,
            "POST",
            f"/mailboxes/{quote(mailbox_id, safe='')}/password/rotate",
            self._headers,
            retry=False,
        )
        return data["password"]

    def connection_settings(self) -> MailConnectionSettings:
        return MailConnectionSettings.from_json(request(self._config, "GET", "/mailboxes/settings", self._headers))
