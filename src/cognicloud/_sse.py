from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Record:
    event: str
    data: str


def records(lines: Iterable[bytes]) -> Iterator[Record]:
    """Splits Server-Sent Events into records. Lines may end in LF or CRLF; a record ends at a blank line, and its
    `data:` lines are joined with newlines. A record without an `event:` line is named `message`."""
    event: Optional[str] = None
    data: list[str] = []
    for raw in lines:
        line = raw.decode("utf-8").rstrip("\r\n")
        if line == "":
            if event is not None or data:
                yield Record(event or "message", "\n".join(data))
                event = None
                data = []
        elif line.startswith("event:"):
            event = _value(line[len("event:") :])
        elif line.startswith("data:"):
            data.append(_value(line[len("data:") :]))


def _value(text: str) -> str:
    return text[1:] if text.startswith(" ") else text
