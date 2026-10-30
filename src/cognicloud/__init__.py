"""CogniCloud SDK for Python. Standard library only; needs Python 3.10 or newer."""

from .browser import (
    BrowserApi,
    BrowserConcurrency,
    BrowserProfile,
    BrowserScreen,
    BrowserSession,
    BrowserSessionList,
    BrowserSessionsApi,
    ProxyCountry,
)
from .client import CogniCloud, CogniCloudBrowser
from .endpoint import (
    DeltaEvent,
    DoneEvent,
    Embedding,
    EmbeddingsRequest,
    EmbeddingsResult,
    EndpointClient,
    ErrorEvent,
    McpTool,
    ResponseResult,
    ResponsesRequest,
    StreamEvent,
    Usage,
)
from .errors import CogniCloudError
from .mail import Mailbox, MailboxList, CreatedMailbox, MailApi, MailConnectionSettings, MailServerEndpoint

__all__ = [
    "BrowserApi",
    "BrowserConcurrency",
    "BrowserProfile",
    "BrowserScreen",
    "BrowserSession",
    "BrowserSessionList",
    "BrowserSessionsApi",
    "CogniCloud",
    "CogniCloudBrowser",
    "CogniCloudError",
    "CreatedMailbox",
    "MailApi",
    "MailConnectionSettings",
    "MailServerEndpoint",
    "Mailbox",
    "MailboxList",
    "DeltaEvent",
    "DoneEvent",
    "Embedding",
    "EmbeddingsRequest",
    "EmbeddingsResult",
    "EndpointClient",
    "ErrorEvent",
    "McpTool",
    "ProxyCountry",
    "ResponseResult",
    "ResponsesRequest",
    "StreamEvent",
    "Usage",
]
__version__ = "0.15.0"
