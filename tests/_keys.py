TENANT = "636f676e69636c6f7564"


def _key(prefix: str, fill: str) -> str:
    return f"{prefix}{TENANT}_{fill * 64}"


KEY = _key("cc_acc_", "a")
PRODUCT_KEYS = {
    "gateway": _key("cc_gw_", "1"),
    "database": _key("cc_db_", "2"),
    "browser": _key("cc_br_", "3"),
    "mail": _key("cc_ml_", "4"),
    "agents": _key("cc_ag_", "5"),
}
