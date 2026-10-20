"""The managed-Edge lifecycle the consumer job calls (AEP port of the source's
`jobs.edge_session`, reduced to what `loan_process` uses).

The source started Edge through a PowerShell script on a fixed debugging port
per profile and shared it with workflow 03 through leases. In AEP each profile
is a persistent browser profile under the host workspace, opened and closed by
`LoanBridge`; nothing else drives these profiles, so a lease is the profile's
name and releasing it keeps the browser for the next run. The names, ports and
ready titles are the source's, so the oracle tests read the same.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from capabilities.loan_reply.bridge_api import Bridge

LogFn = Callable[[str], None]

#: The source's ports, kept for the oracle tests and for the person reading
#: the source; AEP's browser lets Edge choose its own debugging port.
PROFILE_PORTS: dict[str, int] = {
    "c4c": 9222,
    "loan": 9223,
}
DEFAULT_PORT = 9222

#: The title an application shows once it is usable (source: C4C only).
PROFILE_READY_TITLES: dict[str, str] = {
    "c4c": "SAP Cloud for Customer",
}

#: How long to wait for the application after the browser is up (source value).
APP_READY_TIMEOUT_SEC = 120.0


def resolve_port(profile: str, port: Any | None) -> int:
    """Explicit port wins; otherwise the profile's own port."""
    if port:
        return int(port)
    return PROFILE_PORTS.get(profile, DEFAULT_PORT)


def open_session(
    bridge: Bridge,
    profile: str,
    port: int,
    url: str | None,
    log: LogFn,
    *,
    ready_title: str | None = None,
    ready_timeout: float = APP_READY_TIMEOUT_SEC,
    owner: str | None = None,
) -> dict[str, Any]:
    """Start (or reuse) the profile's browser, optionally on `url`, and wait
    for `ready_title` when one is given."""
    opener = getattr(bridge, "open_profile", None)
    if opener is None:
        raise RuntimeError("this host cannot open a browser profile")
    opener(profile, url, ready_title=ready_title, ready_timeout=ready_timeout, log=log)
    return {"leaseId": profile, "holders": 1}


def close_session(
    bridge: Bridge,
    profile: str,
    port: int,
    *,
    force: bool,
    grace_sec: int,
    log: LogFn,
    lease_id: str | None = None,
    force_close: bool = False,
) -> dict[str, Any]:
    """Close the profile's browser."""
    closer = getattr(bridge, "close_profile", None)
    if closer is not None:
        closer(profile)
    return {"closed": True}


def release_lease(profile: str, lease_id: str) -> tuple[bool, int]:
    """Nothing else shares these profiles, so there is no other holder; the
    browser stays open for the next run (`closeBrowsersAfter: false`)."""
    return True, 0
