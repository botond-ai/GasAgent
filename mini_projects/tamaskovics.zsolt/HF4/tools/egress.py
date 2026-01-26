from __future__ import annotations

from urllib.parse import urlparse

def enforce_host_allowlist(url: str, allowed_hosts: set[str]) -> None:
    host = urlparse(url).hostname or ""
    if host not in allowed_hosts:
        raise RuntimeError(f"host_not_allowed:{host}")
