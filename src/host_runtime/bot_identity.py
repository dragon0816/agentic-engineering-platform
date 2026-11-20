"""Which Telegram bot a token belongs to, for Settings → Agents (owner 2026-11-20).

`getMe` with the bot's token gives its `@username` and display name, so the page can
show which agent is bound to which bot instead of only an environment variable name.
Results are cached per token *fingerprint* (a SHA-256 prefix of origin and token;
the token itself is never kept), refreshed when settings are saved (`clear`), and
each lookup has a short timeout; several bots are looked up at once, so the
settings page never waits longer than one timeout. A failure is a short code:
`token_missing`, `token_invalid`, `network_unreachable` or `telegram_error`.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from models.wire import Transport, UrllibTransport, close_quietly

DEFAULT_API_BASE = "https://api.telegram.org"
LOOKUP_TIMEOUT_S = 3.0
#: A bot's identity rarely changes; a failure is retried soon.
KNOWN_TTL_S = 3600.0
FAILED_TTL_S = 60.0
#: After a save, how long a failed lookup is not cached: the bots are being
#: rebuilt and a first connection may be slow, so each page refresh asks again
#: instead of showing a stale 「連不上 Telegram」 for a minute (owner 2026-11-21).
SETTLING_S = 60.0


def _default_transport() -> Transport:
    return UrllibTransport()


#: Replaced in tests so no lookup reaches the network.
TRANSPORT_FACTORY: Callable[[], Transport] = _default_transport


def fingerprint(api_base: str, token: str) -> str:
    return hashlib.sha256(f"{api_base}\n{token}".encode()).hexdigest()[:24]


class BotIdentities:
    """`identities(tokens)` → one `{username, title, problem}` per token."""

    def __init__(
        self,
        transport: Transport | None = None,
        *,
        timeout_s: float = LOOKUP_TIMEOUT_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport
        self.timeout_s = timeout_s
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._settling_until = 0.0

    def clear(self) -> None:
        """Forget every identity (settings were saved; tokens may have changed).
        For `SETTLING_S` afterwards a failed lookup is not cached."""
        with self._lock:
            self._cache.clear()
            self._settling_until = self._clock() + SETTLING_S

    def identities(
        self, tokens: Sequence[str], *, api_base: str = DEFAULT_API_BASE
    ) -> list[dict[str, Any]]:
        unique = sorted({token for token in tokens if token})
        missing = [token for token in unique if self._cached(api_base, token) is None]
        if missing:
            with ThreadPoolExecutor(max_workers=min(8, len(missing))) as pool:
                found = list(pool.map(lambda token: self._lookup(api_base, token), missing))
            fresh = dict(zip(missing, found, strict=True))
            with self._lock:
                settling = self._clock() < self._settling_until
                for token, identity in fresh.items():
                    if identity["problem"] and settling:
                        continue  # served this once, asked again next time
                    ttl = FAILED_TTL_S if identity["problem"] else KNOWN_TTL_S
                    self._cache[fingerprint(api_base, token)] = (self._clock() + ttl, identity)
        else:
            fresh = {}
        out = []
        for token in tokens:
            known = fresh.get(token) or (self._cached(api_base, token) if token else None)
            out.append(
                dict(known)
                if known is not None
                else {"username": None, "title": None, "problem": "token_missing"}
            )
        return out

    def _cached(self, api_base: str, token: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._cache.get(fingerprint(api_base, token))
        if entry is None or entry[0] < self._clock():
            return None
        return entry[1]

    def _lookup(self, api_base: str, token: str) -> dict[str, Any]:
        def failed(code: str) -> dict[str, Any]:
            return {"username": None, "title": None, "problem": code}

        transport = self._transport or TRANSPORT_FACTORY()
        try:
            reply = transport.send(
                f"{api_base}/bot{token}/getMe",
                b"{}",
                {"Content-Type": "application/json"},
                self.timeout_s,
            )
            try:
                body = b"".join(reply.chunks())
            finally:
                close_quietly(reply)
        except (OSError, ValueError):
            # Timeouts and refused connections; never the URL (it holds the token).
            return failed("network_unreachable")
        if reply.status in (401, 404):
            return failed("token_invalid")
        try:
            data = json.loads(body)
            result = data["result"] if data.get("ok") is True else None
        except (ValueError, KeyError, TypeError, AttributeError):
            result = None
        if reply.status != 200 or not isinstance(result, dict):
            return failed("telegram_error")
        username = result.get("username")
        title = " ".join(
            str(result[key]) for key in ("first_name", "last_name") if result.get(key)
        ).strip()
        return {
            "username": str(username) if username else None,
            "title": title or None,
            "problem": None,
        }
