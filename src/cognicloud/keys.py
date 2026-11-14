from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import CogniCloudError

PREFIXES = {
    "cc_acc_": "account",
    "cc_gw_": "gateway",
    "cc_db_": "database",
    "cc_br_": "browser",
    "cc_ml_": "mail",
    "cc_ag_": "agents",
    "cc_vt_": "vault",
}
RETIRED = ("cc_live_", "ccag_", "cga_", "cgb_", "cgd_", "cgm_", "cgv_")
SETTINGS = "Create an account key or a product key in the dashboard under Settings → API keys."
REST = re.compile(r"^([0-9a-f]+)_[A-Za-z0-9]+$")


@dataclass(frozen=True)
class ParsedKey:
    """A CogniCloud API key read without a request. `tenant_hex` is the workspace as the key and invoke URLs name it."""

    kind: str
    tenant_hex: str


def parse_key(key: object) -> ParsedKey:
    """Reads an account or product key, or raises `missing_key`, `retired_key` or `invalid_key`."""
    if not isinstance(key, str) or key.strip() == "":
        raise CogniCloudError(0, "missing_key", f"An API key is required. {SETTINGS}")
    old = next((prefix for prefix in RETIRED if key.startswith(prefix)), None)
    if old is not None:
        raise CogniCloudError(0, "retired_key", f"Keys starting with {old} were retired in SDK 1.0. {SETTINGS}")
    prefix = next((candidate for candidate in PREFIXES if key.startswith(candidate)), None)
    match = REST.match(key[len(prefix) :]) if prefix else None
    if prefix is None or match is None or len(match.group(1)) % 2 != 0:
        raise CogniCloudError(0, "invalid_key", f"This is not a CogniCloud API key. {SETTINGS}")
    return ParsedKey(kind=PREFIXES[prefix], tenant_hex=match.group(1))
