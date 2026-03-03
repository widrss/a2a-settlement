"""Shim configuration -- loaded from environment variables."""

from __future__ import annotations

import os
from typing import Optional


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    return int(val)


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    return float(val)


class ShimSettings:
    port: int = _get_int("A2A_SHIM_PORT", 3300)
    host: str = os.getenv("A2A_SHIM_HOST", "127.0.0.1")

    exchange_url: str = os.getenv("A2A_EXCHANGE_URL", "http://localhost:3000")
    exchange_api_key: str = os.getenv("A2A_EXCHANGE_API_KEY", "")

    vault_url: str = os.getenv("A2A_SHIM_VAULT_URL", "")
    vault_api_key: str = os.getenv("A2A_SHIM_VAULT_API_KEY", "")

    # Destination policy: "allow" = sandbox (default-allow, blocklist),
    # "deny" = production (default-deny, allowlist)
    destination_mode: str = os.getenv("A2A_SHIM_DESTINATION_MODE", "allow")
    destination_list: list[str] = [
        d.strip()
        for d in os.getenv("A2A_SHIM_DESTINATION_LIST", "").split(",")
        if d.strip()
    ]

    default_cost: float = _get_float("A2A_SHIM_DEFAULT_COST", 1.0)
    max_request_size: int = _get_int("A2A_SHIM_MAX_REQUEST_SIZE", 1_048_576)  # 1 MB

    request_timeout: float = _get_float("A2A_SHIM_REQUEST_TIMEOUT", 30.0)

    def is_destination_allowed(self, url: str) -> bool:
        """Check whether a destination URL is permitted by the current policy."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or ""

        if self.destination_mode == "deny":
            # Production: default-deny, allowlist only
            return any(
                host == d or host.endswith(f".{d}")
                for d in self.destination_list
            )
        else:
            # Sandbox: default-allow, blocklist
            if not self.destination_list:
                return True
            return not any(
                host == d or host.endswith(f".{d}")
                for d in self.destination_list
            )


shim_settings = ShimSettings()
