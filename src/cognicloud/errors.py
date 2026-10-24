from __future__ import annotations


class CogniCloudError(Exception):
    """A failed request. `status` is the HTTP status (0 when no answer came back); `code` is CogniCloud's error code."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
