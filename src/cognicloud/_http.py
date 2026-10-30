from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from .errors import CogniCloudError

RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class HttpConfig:
    base_url: str
    locale: str
    timeout: float
    max_retries: int


def request(
    config: HttpConfig,
    method: str,
    path: str,
    headers: dict[str, str],
    body: Optional[Any] = None,
    retry: bool = True,
    raw: Optional[tuple[bytes, str]] = None,
) -> Any:
    """Sends one request and returns the decoded JSON body (None for 204). Retries 429 and 5xx only when `retry` is set.
    `raw` is a body sent as it is, with its content type, instead of JSON."""
    url = config.base_url.rstrip("/") + path
    retries = config.max_retries if retry else 0
    payload = None if body is None else json.dumps(body).encode("utf-8")
    all_headers = {"accept": "application/json", "accept-language": config.locale, **headers}
    if raw is not None:
        payload, all_headers["content-type"] = raw
    elif payload is not None:
        all_headers["content-type"] = "application/json"

    attempt = 0
    while True:
        http_request = urllib.request.Request(url, data=payload, method=method, headers=all_headers)
        try:
            with urllib.request.urlopen(http_request, timeout=config.timeout) as response:
                raw = response.read()
                return None if response.status == 204 or not raw else json.loads(raw)
        except urllib.error.HTTPError as error:
            if error.code in RETRYABLE_STATUSES and attempt < retries:
                time.sleep(0.25 * 2**attempt)
                attempt += 1
                continue
            raise _api_error(error.code, error.read()) from None
        except (TimeoutError, socket.timeout):
            if attempt < retries:
                time.sleep(0.25 * 2**attempt)
                attempt += 1
                continue
            raise CogniCloudError(0, "timeout", "The request timed out.") from None
        except urllib.error.URLError as error:
            timed_out = isinstance(error.reason, (TimeoutError, socket.timeout))
            if attempt < retries:
                time.sleep(0.25 * 2**attempt)
                attempt += 1
                continue
            if timed_out:
                raise CogniCloudError(0, "timeout", "The request timed out.") from None
            raise CogniCloudError(0, "network_error", "The request could not reach CogniCloud.") from None


def _api_error(status: int, raw: bytes) -> CogniCloudError:
    try:
        body = json.loads(raw) if raw else {}
    except ValueError:
        body = {}
    code = body.get("error") if isinstance(body.get("error"), str) else "http_error"
    message = body.get("message") if isinstance(body.get("message"), str) else "The request failed."
    query_code = body.get("code") if isinstance(body.get("code"), str) else None
    return CogniCloudError(status, code, message, query_code)


def open_stream(
    config: HttpConfig,
    method: str,
    path: str,
    headers: dict[str, str],
    body: Optional[Any] = None,
) -> Any:
    """Opens a streamed call and returns the response to read as it arrives. Never retried, and the timeout bounds each
    read rather than the whole stream, because a stream may run for minutes."""
    url = config.base_url.rstrip("/") + path
    payload = None if body is None else json.dumps(body).encode("utf-8")
    all_headers = {"accept": "text/event-stream", "accept-language": config.locale, **headers}
    if payload is not None:
        all_headers["content-type"] = "application/json"
    http_request = urllib.request.Request(url, data=payload, method=method, headers=all_headers)
    try:
        return urllib.request.urlopen(http_request, timeout=config.timeout)
    except urllib.error.HTTPError as error:
        raise _api_error(error.code, error.read()) from None
    except (TimeoutError, socket.timeout):
        raise CogniCloudError(0, "timeout", "The request timed out.") from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise CogniCloudError(0, "timeout", "The request timed out.") from None
        raise CogniCloudError(0, "network_error", "The request could not reach CogniCloud.") from None
