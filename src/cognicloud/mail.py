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
    default_domain: str = ""

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "MailConnectionSettings":
        return cls(
            default_domain=data.get("defaultDomain", ""),
            username_format=data["usernameFormat"],
            imap=MailServerEndpoint(**_endpoint(data["imap"])),
            smtp=MailServerEndpoint(**_endpoint(data["smtp"])),
        )


def _endpoint(data: dict[str, Any]) -> dict[str, Any]:
    return {"host": data["host"], "port": data["port"], "security": data["security"]}


@dataclass(frozen=True)
class MailDnsRecord:
    """One DNS record to publish for a domain; `ok` is the last check's result, None when not checked."""

    type: str
    host: str
    value: str
    purpose: str
    ok: Optional[bool]


@dataclass(frozen=True)
class MailDomain:
    id: str
    name: str
    status: str
    records: list[MailDnsRecord]
    other_mx: list[str]
    created_at: str
    verified_at: Optional[str]
    last_checked_at: Optional[str]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "MailDomain":
        return cls(
            id=data["id"],
            name=data["name"],
            status=data["status"],
            records=[
                MailDnsRecord(
                    type=record["type"],
                    host=record["host"],
                    value=record["value"],
                    purpose=record["purpose"],
                    ok=record.get("ok"),
                )
                for record in data.get("records", [])
            ],
            other_mx=list(data.get("otherMx", [])),
            created_at=data["createdAt"],
            verified_at=data.get("verifiedAt"),
            last_checked_at=data.get("lastCheckedAt"),
        )


class MailDomainsApi:
    """Your own domains for mailboxes. Adding, verifying and deleting need a signed-in person's token."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers

    def list(self) -> list[MailDomain]:
        """Newest first, each with the DNS records to publish."""
        data = request(self._config, "GET", "/domains", self._headers)
        return [MailDomain.from_json(item) for item in data["items"]]

    def get(self, domain_id: str) -> MailDomain:
        return MailDomain.from_json(request(self._config, "GET", f"/domains/{quote(domain_id, safe='')}", self._headers))

    def add(self, name: str) -> MailDomain:
        """Adds the domain as pending. Publish its records, then call `verify`."""
        return MailDomain.from_json(request(self._config, "POST", "/domains", self._headers, {"name": name}, retry=False))

    def verify(self, domain_id: str) -> MailDomain:
        """Checks the domain's DNS now; the first time the ownership record is found, it becomes verified."""
        data = request(self._config, "POST", f"/domains/{quote(domain_id, safe='')}/verify", self._headers, retry=False)
        return MailDomain.from_json(data)

    def delete(self, domain_id: str) -> None:
        """Refused while the domain has mailboxes."""
        request(self._config, "DELETE", f"/domains/{quote(domain_id, safe='')}", self._headers, retry=False)


class MailApi:
    """Creates, lists and removes mailboxes on the Flippico mail server."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers
        self.domains = MailDomainsApi(config, headers)

    def list(self, *, limit: Optional[int] = None, offset: Optional[int] = None) -> MailboxList:
        """Newest first."""
        query = {key: value for key, value in (("limit", limit), ("offset", offset)) if value is not None}
        suffix = f"?{urlencode(query)}" if query else ""
        return MailboxList.from_json(request(self._config, "GET", f"/mailboxes{suffix}", self._headers))

    def create(self, local_part: str, *, domain: Optional[str] = None) -> CreatedMailbox:
        """Creates `<local_part>@<domain>` on the shared domain, or on one of your verified domains with `domain`.

        Save the returned password now; it is not stored.
        """
        body = {"localPart": local_part} if domain is None else {"localPart": local_part, "domain": domain}
        data = request(self._config, "POST", "/mailboxes", self._headers, body, retry=False)
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
