from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional

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
SETTINGS = "Create your account key and a product key for each product in the dashboard under Settings → API keys."
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


ACCOUNT_KEY_HEADER = "x-cognicloud-account-key"
PRODUCT_LABELS = {
    "gateway": "AI Gateway",
    "database": "Database",
    "browser": "Browser",
    "mail": "Mail",
    "agents": "Agents",
    "vault": "Vault",
}


def check_keys(account_key: object, product_keys: Optional[Mapping[str, Optional[str]]] = None) -> ParsedKey:
    """Checks the account key and every product key: right kinds, one workspace."""
    if not isinstance(account_key, str) or account_key.strip() == "":
        raise CogniCloudError(0, "missing_account_key", f"An account key is required. {SETTINGS}")
    account = parse_key(account_key)
    if account.kind != "account":
        raise CogniCloudError(0, "invalid_key", f"account_key must be an account key (cc_acc_...). {SETTINGS}")
    for product, key in (product_keys or {}).items():
        if key is None:
            continue
        if product not in PRODUCT_LABELS:
            raise CogniCloudError(0, "invalid_key", f"Unknown product {product!r} in product_keys.")
        parsed = parse_key(key)
        if parsed.kind != product:
            raise CogniCloudError(0, "invalid_key", f"product_keys[{product!r}] must be a {PRODUCT_LABELS[product]} key.")
        if parsed.tenant_hex != account.tenant_hex:
            raise CogniCloudError(0, "key_mismatch", "The account key and the product keys must be from one workspace.")
    return account


def pair_headers(account_key: str, product_keys: Mapping[str, Optional[str]], product: str) -> dict[str, str]:
    """The headers of a call to one product: its product key as the Bearer token, plus the account key."""
    key = product_keys.get(product)
    if not key:
        raise CogniCloudError(
            0, "missing_product_key", f"Add {'an' if product == 'gateway' else 'a'} {PRODUCT_LABELS[product]} product key to product_keys[{product!r}]. {SETTINGS}"
        )
    return {"authorization": f"Bearer {key}", ACCOUNT_KEY_HEADER: account_key}
