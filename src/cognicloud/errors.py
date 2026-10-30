from __future__ import annotations

from typing import Optional


class CogniCloudError(Exception):
    """A failed request. `status` is the HTTP status (0 when no answer came back); `code` is CogniCloud's error code.
    For `query_failed`, `query_code` is a Postgres SQLSTATE such as `23505`, or `query_timeout` or `unsupported_type`."""

    def __init__(self, status: int, code: str, message: str, query_code: Optional[str] = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.query_code = query_code
