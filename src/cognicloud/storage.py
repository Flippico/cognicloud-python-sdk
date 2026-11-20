from __future__ import annotations

import mimetypes
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, BinaryIO, Literal, Optional, Union
from urllib.parse import quote, urlencode

from ._http import HttpConfig, request
from .errors import CogniCloudError

Visibility = Literal["private", "public_read"]
DEFAULT_CONTENT_TYPE = "application/octet-stream"
_KEEP: Any = object()
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _suffix(pairs: tuple[tuple[str, Any], ...]) -> str:
    query = {key: value for key, value in pairs if value is not None}
    return f"?{urlencode(query)}" if query else ""


def _check_path(value: str, field: str) -> None:
    """Refuses, before any request, a key or prefix that URL handling would collapse or that is not a path at all. The
    rule mirrors the service: one trailing `/` is allowed (folder keys and prefixes such as `reports/`)."""
    problem = None
    if value == "":
        problem = "no name"
    elif _CONTROL.search(value):
        problem = "control characters"
    elif value.startswith("/"):
        problem = "a leading '/'"
    else:
        segments = value.split("/")
        if len(segments) > 1 and segments[-1] == "":
            segments = segments[:-1]
        if any(segment in ("", ".", "..") for segment in segments):
            problem = "an empty, '.' or '..' segment"
    if problem is not None:
        raise CogniCloudError(0, "invalid_key", f"The {field} {value!r} has {problem}.")


def _bucket_path(name: str) -> str:
    return f"/buckets/{quote(name, safe='')}"


def _object_path(bucket: str, key: str) -> str:
    """Each segment of the key is encoded on its own, so the slashes that make folders stay."""
    _check_path(key, "key")
    segments = "/".join(quote(segment, safe="") for segment in key.split("/"))
    return f"{_bucket_path(bucket)}/objects/{segments}"


@dataclass(frozen=True)
class Bucket:
    """`visibility` is `private` or `public_read`. The counts are approximate."""

    id: str
    name: str
    visibility: str
    description: Optional[str]
    object_count: int
    total_size: int
    created_at: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Bucket":
        return cls(
            id=data["id"],
            name=data["name"],
            visibility=data["visibility"],
            description=data.get("description"),
            object_count=data["objectCount"],
            total_size=data["totalSize"],
            created_at=data["createdAt"],
        )


@dataclass(frozen=True)
class StorageObject:
    """An object in a listing. Listings carry no content type; `metadata` does."""

    key: str
    size: int
    etag: Optional[str]
    last_modified: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "StorageObject":
        return cls(
            key=data["key"],
            size=data["size"],
            etag=data.get("etag"),
            last_modified=data["lastModified"],
        )


@dataclass(frozen=True)
class ObjectMetadata:
    key: str
    size: int
    content_type: str
    etag: Optional[str]
    last_modified: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ObjectMetadata":
        return cls(
            key=data["key"],
            size=data["size"],
            content_type=data["contentType"],
            etag=data.get("etag"),
            last_modified=data["lastModified"],
        )


@dataclass(frozen=True)
class ObjectList:
    """One page. `folders` are prefixes ending in `/`. Pass `next_cursor` as `cursor` for the next page; it is None on
    the last page."""

    folders: list[str]
    objects: list[StorageObject]
    next_cursor: Optional[str]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ObjectList":
        return cls(
            folders=list(data["folders"]),
            objects=[StorageObject.from_json(item) for item in data["objects"]],
            next_cursor=data.get("nextCursor"),
        )


class StorageBucketsApi:
    """Buckets hold objects. A name is unique within your workspace."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers

    def list(self) -> list[Bucket]:
        data = request(self._config, "GET", "/buckets", self._headers)
        return [Bucket.from_json(item) for item in data["buckets"]]

    def get(self, name: str) -> Bucket:
        return Bucket.from_json(request(self._config, "GET", _bucket_path(name), self._headers))

    def create(self, name: str, *, description: Optional[str] = None) -> Bucket:
        """Creates a private bucket. The service answers 429 when you are at the bucket limit."""
        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        return Bucket.from_json(request(self._config, "POST", "/buckets", self._headers, body, retry=False))

    def update(self, name: str, *, description: Any = _KEEP, visibility: Optional[Visibility] = None) -> Bucket:
        """A field left out stays as it is. `description=None` clears it."""
        body: dict[str, Any] = {}
        if description is not _KEEP:
            body["description"] = description
        if visibility is not None:
            body["visibility"] = visibility
        return Bucket.from_json(request(self._config, "PATCH", _bucket_path(name), self._headers, body, retry=False))

    def delete(self, name: str, *, force: bool = False) -> None:
        """Deletes an empty bucket. A bucket that still holds objects raises `CogniCloudError` with status 409; pass
        `force=True` to delete its objects too. This cannot be undone."""
        path = _bucket_path(name) + ("?force=true" if force else "")
        request(self._config, "DELETE", path, self._headers, retry=False)


class StorageObjectsApi:
    """Objects are bytes under a key. Keys may contain `/`, which makes folders in listings."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers

    def list(
        self,
        bucket: str,
        *,
        prefix: Optional[str] = None,
        delimiter: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> ObjectList:
        """One page, up to `limit` (1 to 1000, 100 by default). The `delimiter` defaults to `/` on the service; pass
        `""` to list every key flat. A `prefix` that is not a path raises `CogniCloudError` with code `invalid_key`."""
        if prefix:
            _check_path(prefix, "prefix")
        path = f"{_bucket_path(bucket)}/objects" + _suffix(
            (("prefix", prefix), ("delimiter", delimiter), ("cursor", cursor), ("limit", limit))
        )
        return ObjectList.from_json(request(self._config, "GET", path, self._headers))

    def pages(
        self,
        bucket: str,
        *,
        prefix: Optional[str] = None,
        delimiter: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Iterator[ObjectList]:
        """Yields every page in order, requesting the next one only when it is reached."""
        cursor: Optional[str] = None
        while True:
            page = self.list(bucket, prefix=prefix, delimiter=delimiter, cursor=cursor, limit=limit)
            yield page
            if page.next_cursor is None:
                return
            cursor = page.next_cursor

    def upload(
        self,
        bucket: str,
        key: str,
        body: Union[bytes, bytearray, memoryview, os.PathLike[str], BinaryIO],
        *,
        content_type: Optional[str] = None,
    ) -> ObjectMetadata:
        """Stores `body` under `key`, replacing an object with the same key. Up to 100 MB.

        `body` is bytes, a bytearray or a memoryview; or a `pathlib.Path` (or other path), read in full; or an open
        binary file, read from its current position. A `str` raises `TypeError`: pass `Path(...)` for a file or
        `text.encode()` for text. The content type is `content_type` if given, else guessed from a file's name, else
        `application/octet-stream`."""
        target = _object_path(bucket, key)
        guessed: Optional[str] = None
        if isinstance(body, str):
            raise TypeError("A str is not a file path or content. Pass Path(...) for a file, or text.encode() for text.")
        if isinstance(body, (bytes, bytearray, memoryview)):
            data = bytes(body)
        elif isinstance(body, os.PathLike):
            file_path = os.fspath(body)
            with open(file_path, "rb") as file:
                data = file.read()
            guessed = mimetypes.guess_type(file_path)[0] if isinstance(file_path, str) else None
        elif hasattr(body, "read"):
            data = body.read()
            if not isinstance(data, bytes):
                raise TypeError("The file must be opened in binary mode, for example open(path, 'rb').")
            name = getattr(body, "name", None)
            guessed = mimetypes.guess_type(name)[0] if isinstance(name, str) else None
        else:
            raise TypeError("The body must be bytes, bytearray, memoryview, a path or a binary file.")
        raw = (data, content_type or guessed or DEFAULT_CONTENT_TYPE)
        return ObjectMetadata.from_json(request(self._config, "PUT", target, self._headers, retry=False, raw=raw))

    def download(self, bucket: str, key: str, *, range_: Optional[str] = None) -> bytes:
        """The object's bytes. `range_` is a `Range` header value such as `bytes=0-1023`, which returns just that part.
        An invalid key or range raises `CogniCloudError` with status 422."""
        headers = {**self._headers, "accept": "*/*"}
        if range_ is not None:
            headers["range"] = range_
        content: bytes = request(self._config, "GET", _object_path(bucket, key), headers, binary=True)
        return content

    def metadata(self, bucket: str, key: str) -> ObjectMetadata:
        return ObjectMetadata.from_json(
            request(self._config, "GET", f"{_object_path(bucket, key)}?metadata=true", self._headers)
        )

    def delete(self, bucket: str, key: str) -> None:
        """Deletes the object. An object that is already gone counts as deleted."""
        request(self._config, "DELETE", _object_path(bucket, key), self._headers, retry=False)


class StorageFoldersApi:
    """Folders are marker objects, so an empty folder stays listed."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self._config = config
        self._headers = headers

    def create(self, bucket: str, prefix: str) -> None:
        """Creates the folder `prefix`, such as `photos/2026/`. A prefix that is not a path raises `CogniCloudError` with
        code `invalid_key`, before any request."""
        _check_path(prefix, "prefix")
        request(self._config, "POST", f"{_bucket_path(bucket)}/folders", self._headers, {"prefix": prefix}, retry=False)


class StorageApi:
    """Buckets, objects and folders in CogniCloud Storage."""

    def __init__(self, config: HttpConfig, headers: dict[str, str]) -> None:
        self.buckets = StorageBucketsApi(config, headers)
        self.objects = StorageObjectsApi(config, headers)
        self.folders = StorageFoldersApi(config, headers)
