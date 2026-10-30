from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Union
from urllib.parse import quote, urlencode

from ._http import HttpConfig, request


@dataclass(frozen=True)
class HostedDatabase:
    id: str
    name: str
    created_at: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "HostedDatabase":
        return cls(id=data["id"], name=data["name"], created_at=data["createdAt"])


@dataclass(frozen=True)
class DatabaseKey:
    """`access` is `read` or `write`. `prefix` tells keys apart; the secret is shown only when a key is created."""

    id: str
    database_id: str
    name: str
    access: str
    prefix: str
    created_at: str
    last_used_at: Optional[str]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "DatabaseKey":
        return cls(
            id=data["id"],
            database_id=data["databaseId"],
            name=data["name"],
            access=data["access"],
            prefix=data["prefix"],
            created_at=data["createdAt"],
            last_used_at=data.get("lastUsedAt"),
        )


@dataclass(frozen=True)
class DatabaseAction:
    """`action` is `create_database`, `delete_database`, `create_key` or `revoke_key`."""

    id: str
    action: str
    database_id: Optional[str]
    name: Optional[str]
    started_at: str
    finished_at: Optional[str]
    duration_ms: Optional[int]
    outcome: str
    error_code: Optional[str]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "DatabaseAction":
        return cls(
            id=data["id"],
            action=data["action"],
            database_id=data.get("databaseId"),
            name=data.get("name"),
            started_at=data["startedAt"],
            finished_at=data.get("finishedAt"),
            duration_ms=data.get("durationMs"),
            outcome=data["outcome"],
            error_code=data.get("errorCode"),
        )


@dataclass(frozen=True)
class DatabaseActionList:
    """Pass `next_cursor` as `cursor` for the next page. It is None on the last page."""

    items: list[DatabaseAction]
    next_cursor: Optional[str]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "DatabaseActionList":
        return cls(items=[DatabaseAction.from_json(item) for item in data["items"]], next_cursor=data.get("nextCursor"))


@dataclass(frozen=True)
class ResultColumn:
    name: str
    type: str


@dataclass(frozen=True)
class QueryResult:
    """`row_count` is the rows returned or changed, including any not sent back. `truncated` says more matched than
    came back: at most 1,000 rows and 5 MB do."""

    columns: list[ResultColumn]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "QueryResult":
        return cls(
            columns=[ResultColumn(name=column["name"], type=column["type"]) for column in data["columns"]],
            rows=data["rows"],
            row_count=data["rowCount"],
            truncated=data["truncated"],
        )


@dataclass(frozen=True)
class TableColumn:
    name: str
    type: str
    nullable: bool


@dataclass(frozen=True)
class DatabaseTable:
    name: str
    columns: list[TableColumn]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "DatabaseTable":
        return cls(name=data["name"], columns=[TableColumn(**column) for column in data["columns"]])


@dataclass(frozen=True)
class Statement:
    """One SQL statement, with `$1`, `$2` for `params`."""

    sql: str
    params: Sequence[Any] = ()


class _Filtered:
    def __init__(self) -> None:
        self._filters: list[dict[str, Any]] = []

    def _add(self, column: str, op: str, value: Any) -> Any:
        self._filters.append({"column": column, "op": op, "value": value})
        return self

    def eq(self, column: str, value: Any) -> Any:
        return self._add(column, "eq", value)

    def neq(self, column: str, value: Any) -> Any:
        return self._add(column, "neq", value)

    def gt(self, column: str, value: Any) -> Any:
        return self._add(column, "gt", value)

    def gte(self, column: str, value: Any) -> Any:
        return self._add(column, "gte", value)

    def lt(self, column: str, value: Any) -> Any:
        return self._add(column, "lt", value)

    def lte(self, column: str, value: Any) -> Any:
        return self._add(column, "lte", value)

    def like(self, column: str, pattern: str) -> Any:
        return self._add(column, "like", pattern)

    def ilike(self, column: str, pattern: str) -> Any:
        return self._add(column, "ilike", pattern)

    def is_(self, column: str, value: Optional[bool]) -> Any:
        """Compares with None, True or False."""
        return self._add(column, "is", value)

    def in_(self, column: str, values: Sequence[Any]) -> Any:
        return self._add(column, "in", list(values))


class SelectQuery(_Filtered):
    """A select, sent by `execute`. Without `limit` it returns up to 1,000 rows, the most one response can hold."""

    def __init__(self, table: "TableApi", columns: Sequence[str]) -> None:
        super().__init__()
        self._table = table
        self._columns = list(columns)
        self._order: list[dict[str, Any]] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None

    def order(self, column: str, desc: bool = False) -> "SelectQuery":
        self._order.append({"column": column, "desc": desc})
        return self

    def limit(self, limit: int) -> "SelectQuery":
        self._limit = limit
        return self

    def offset(self, offset: int) -> "SelectQuery":
        self._offset = offset
        return self

    def execute(self) -> QueryResult:
        body: dict[str, Any] = {"columns": self._columns, "filters": self._filters, "order": self._order}
        if self._limit is not None:
            body["limit"] = self._limit
        if self._offset is not None:
            body["offset"] = self._offset
        return self._table._post("select", body, retry=True)


class WriteQuery(_Filtered):
    """An update or delete, sent by `execute`. At least one filter is required."""

    def __init__(self, table: "TableApi", verb: str, body: dict[str, Any]) -> None:
        super().__init__()
        self._table = table
        self._verb = verb
        self._body = body

    def execute(self) -> QueryResult:
        return self._table._post(self._verb, {**self._body, "filters": self._filters}, retry=False)


class TableApi:
    """One table in the `public` schema. Table and column names are checked against the database."""

    def __init__(self, config: HttpConfig, headers: dict[str, str], name: str) -> None:
        self._config = config
        self._headers = headers
        self._path = f"/tables/{quote(name, safe='')}"

    def _post(self, verb: str, body: dict[str, Any], retry: bool) -> QueryResult:
        path = f"{self._path}/{verb}"
        return QueryResult.from_json(request(self._config, "POST", path, self._headers, body, retry=retry))

    def select(self, *columns: str) -> SelectQuery:
        """The named columns, or every column with none."""
        return SelectQuery(self, columns)

    def insert(self, rows: Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]) -> QueryResult:
        """Inserts now and returns the new rows. A column a row leaves out takes its default. Needs a write key."""
        rows = [rows] if isinstance(rows, Mapping) else rows
        return self._post("insert", {"rows": [dict(row) for row in rows]}, retry=False)

    def update(self, values: Mapping[str, Any]) -> WriteQuery:
        """Changes the rows the filters match and returns them. Needs a write key."""
        return WriteQuery(self, "update", {"values": dict(values)})

    def delete(self) -> WriteQuery:
        """Deletes the rows the filters match and returns them. Needs a write key."""
        return WriteQuery(self, "delete", {})


class DatabaseDataApi:
    """Queries one database with its key."""

    def __init__(self, config: HttpConfig, key: str) -> None:
        self._config = config
        self._headers = {"authorization": f"Bearer {key}"}

    def query(self, sql: str, params: Sequence[Any] = ()) -> QueryResult:
        """Runs one SQL statement, with `$1`, `$2` for `params`. It stops after 15 seconds. Never retried, because it
        may change data."""
        body = {"sql": sql, "params": list(params)}
        return QueryResult.from_json(request(self._config, "POST", "/query", self._headers, body, retry=False))

    def transaction(self, statements: Sequence[Statement]) -> list[QueryResult]:
        """Runs 1 to 20 statements that commit together, or none do. Needs a write key. Never retried."""
        body = {"statements": [{"sql": item.sql, "params": list(item.params)} for item in statements]}
        data = request(self._config, "POST", "/transaction", self._headers, body, retry=False)
        return [QueryResult.from_json(item) for item in data["results"]]

    def tables(self) -> list[DatabaseTable]:
        """Tables and views in the `public` schema that this key can read."""
        data = request(self._config, "GET", "/tables", self._headers)
        return [DatabaseTable.from_json(item) for item in data["tables"]]

    def table(self, name: str) -> TableApi:
        return TableApi(self._config, self._headers, name)


class DatabaseKeysApi:
    """A database's keys. Keys are created in the dashboard and shown there once."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers

    def list(self, database_id: str) -> list[DatabaseKey]:
        """Active keys, newest first."""
        path = f"/databases/{quote(database_id, safe='')}/keys"
        return [DatabaseKey.from_json(item) for item in request(self._config, "GET", path, self._headers)]

    def revoke(self, database_id: str, key_id: str) -> None:
        """The key stops working on its next request."""
        path = f"/databases/{quote(database_id, safe='')}/keys/{quote(key_id, safe='')}"
        request(self._config, "DELETE", path, self._headers, retry=False)


class DatabaseApi:
    """Creates and removes hosted Postgres databases. Needs a signed-in person's token; a key is refused."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers
        self.keys = DatabaseKeysApi(config, headers)

    def list(self) -> list[HostedDatabase]:
        """Newest first."""
        data = request(self._config, "GET", "/databases", self._headers)
        return [HostedDatabase.from_json(item) for item in data["items"]]

    def get(self, database_id: str) -> HostedDatabase:
        path = f"/databases/{quote(database_id, safe='')}"
        return HostedDatabase.from_json(request(self._config, "GET", path, self._headers))

    def create(self, name: str) -> HostedDatabase:
        """Creates an empty database. You can have up to 3."""
        data = request(self._config, "POST", "/databases", self._headers, {"name": name}, retry=False)
        return HostedDatabase.from_json(data)

    def delete(self, database_id: str) -> None:
        """Deletes the database, all its data and its keys. This cannot be undone."""
        request(self._config, "DELETE", f"/databases/{quote(database_id, safe='')}", self._headers, retry=False)

    def actions(self, limit: Optional[int] = None, cursor: Optional[str] = None) -> DatabaseActionList:
        """Creating and deleting databases and keys, newest first. Queries are not listed."""
        query = {key: value for key, value in (("limit", limit), ("cursor", cursor)) if value is not None}
        suffix = f"?{urlencode(query)}" if query else ""
        return DatabaseActionList.from_json(request(self._config, "GET", f"/actions{suffix}", self._headers))
