"""Bounded transport evidence for a fresh, scoped XHR/Fetch completion.

CDP timestamps establish freshness; injected local monotonic time establishes
quiet. This neither proves business data correctness nor grants permission.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

_START = "Network.requestWillBeSent"
_RESPONSE = "Network.responseReceived"
_FINISH = "Network.loadingFinished"
_FAIL = "Network.loadingFailed"
_METHODS = frozenset({_START, _RESPONSE, _FINISH, _FAIL})
_TYPES = frozenset({"XHR", "Fetch"})


def _text(value: object, limit: int = 128) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > limit
        or any(ord(char) < 32 for char in value)
    ):
        raise ValueError("metadata")
    return value


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("metadata")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("metadata")
    return number


def _timestamp(value: object) -> float:
    number = _number(value)
    if number < 0:
        raise ValueError("metadata")
    return number


def _status(value: object) -> int:
    number = _number(value)
    if not number.is_integer() or not 100 <= number <= 599:
        raise ValueError("metadata")
    return int(number)


def _origin(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("metadata")
    # Only the authority is examined/retained, even when URL query/headers are huge.
    match = re.match(r"^(https?)://([^/?#]+)", value, re.IGNORECASE)
    if match is None:
        raise ValueError("metadata")
    origin = _text(match.group(0), 512).lower()
    parts = urlsplit(origin)
    if not parts.hostname or parts.username is not None or parts.password is not None:
        raise ValueError("metadata")
    _ = parts.port  # validate malformed ports without retaining a raw URL
    return origin


def sanitize_network_event(method: str, params: Mapping[str, object]) -> dict[str, object] | None:
    """Extract needed metadata before transport pruning; never retain raw params."""
    if method not in _METHODS:
        return None
    if not isinstance(params, Mapping):
        return {"malformed": True}
    try:
        if method in {_START, _RESPONSE}:
            kind = params.get("type")
            if (kind is not None and not isinstance(kind, str)) or (
                method == _START and kind is None
            ):
                raise ValueError("metadata")
            if kind is not None and kind not in _TYPES:
                return None
        if method == _START and params.get("frameId") is None:
            if params.get("redirectResponse") is not None:
                raise ValueError("metadata")
            return None  # worker requests have no main-frame identity
        result: dict[str, object] = {
            "requestId": _text(params.get("requestId")),
            "timestamp": _timestamp(params.get("timestamp")),
        }
        if method == _START:
            kind = _text(params.get("type"))
            if kind not in _TYPES:
                return None
            request = params.get("request")
            if not isinstance(request, Mapping):
                raise ValueError("metadata")
            result.update(
                frameId=_text(params.get("frameId")), type=kind, origin=_origin(request.get("url"))
            )
            redirect = params.get("redirectResponse")
            if redirect is not None:
                if not isinstance(redirect, Mapping):
                    raise ValueError("metadata")
                status = _status(redirect.get("status"))
                if not 300 <= status < 400:
                    raise ValueError("metadata")
                result.update(redirectOrigin=_origin(redirect.get("url")), redirectStatus=status)
        elif method == _RESPONSE:
            response = params.get("response")
            if not isinstance(response, Mapping):
                raise ValueError("metadata")
            result["status"] = _status(response.get("status"))
        return result
    except (ValueError, TypeError, OverflowError, UnicodeError):
        return {"malformed": True}


@dataclass
class _Request:
    frame: str
    origin: str
    timestamp: float
    pre_arm: bool
    current_origin: str
    current_frame: str
    redirect: bool = False
    redirect_invalid: bool = False
    scoped: bool = False
    fresh: bool = False
    done: bool = False
    status: int | None = None
    failure: str = ""


class NetworkBarrier:
    """One observation window. Loss/errors are latched; arm never clears records."""

    def __init__(self, allowed_origins: tuple[str, ...], max_pending: int = 256) -> None:
        if type(max_pending) is not int or not 1 <= max_pending <= 256:
            raise ValueError("max_pending")
        if len(allowed_origins) > 256:
            raise ValueError("allowed_origins")
        self._allowed = frozenset(
            "*" if value == "*" else _origin(value) for value in allowed_origins
        )
        self._limit = max_pending
        self._requests: dict[str, _Request] = {}
        self._frame = ""
        self._origin = ""
        self._epoch = 0.0
        self._armed = False
        self._armed_at = 0.0
        self._activity = 0.0
        self._failure = ""
        self._lost = False
        self._fresh_started = 0
        self._fresh_finished = 0

    def _refuse(self, reason: str) -> None:
        if not self._failure:
            self._failure = reason

    def mark_lost(self) -> None:
        self._lost = True
        self._refuse("events_lost")

    def arm(self, frame_id: str, origin: str, epoch_cdp_timestamp: float, now: float) -> None:
        if self._armed:
            self._refuse("arm_repeated")
            return
        try:
            self._frame = _text(frame_id)
            self._origin = _origin(origin)
            self._epoch = _timestamp(epoch_cdp_timestamp)
            self._activity = _number(now)
            self._armed_at = self._activity
            if "*" not in self._allowed and self._origin not in self._allowed:
                self._refuse("origin_not_allowed")
            self._armed = True
            for request in self._requests.values():
                self._scope(request)
        except (ValueError, TypeError, OverflowError, UnicodeError):
            self._refuse("metadata_invalid")

    def _scope(self, request: _Request) -> None:
        initial = request.frame == self._frame and request.origin == self._origin
        current = request.current_frame == self._frame and request.current_origin == self._origin
        request.scoped = initial or current
        if request.scoped:
            if request.redirect and (not initial or not current or request.redirect_invalid):
                self._refuse("redirect_out_of_scope")
            if request.fresh and request.failure:
                self._refuse(request.failure)

    def event(self, method: str, params: Mapping[str, object], now: float) -> None:
        if method not in _METHODS or self._failure:
            return
        if not isinstance(params, Mapping):
            self._refuse("metadata_invalid")
            return
        try:
            moment = _number(now)
            if params.get("malformed"):
                raise ValueError("metadata")
            ident = _text(params.get("requestId"))
            stamp = _timestamp(params.get("timestamp"))
            request = self._requests.get(ident)
            if method == _START:
                kind = _text(params.get("type"))
                if kind not in _TYPES:
                    return
                frame = _text(params.get("frameId"))
                origin = _origin(params.get("origin"))
                if request is not None:
                    if request.done or "redirectOrigin" not in params or stamp < request.timestamp:
                        raise ValueError("metadata")
                    previous_origin = _origin(params.get("redirectOrigin"))
                    if not 300 <= _status(params.get("redirectStatus")) < 400:
                        raise ValueError("metadata")
                    request.redirect = True
                    request.redirect_invalid |= (
                        previous_origin != request.current_origin
                        or origin != request.origin
                        or frame != request.frame
                    )
                    request.current_origin, request.current_frame = origin, frame
                else:
                    if "*" not in self._allowed and origin not in self._allowed:
                        return
                    if len(self._requests) >= self._limit:
                        self._refuse("overflow")
                        return
                    request = _Request(
                        frame,
                        origin,
                        stamp,
                        not self._armed or moment < self._armed_at,
                        origin,
                        frame,
                    )
                    self._requests[ident] = request
                    if "redirectOrigin" in params:
                        request.redirect = True
                        request.redirect_invalid = True  # an unobserved initial hop
                if self._armed:
                    self._scope(request)
                    if request.scoped:
                        self._activity = max(self._activity, moment)
                        if (
                            not request.pre_arm
                            and request.timestamp >= self._epoch
                            and not request.fresh
                        ):
                            request.fresh = True
                            self._fresh_started += 1
                return
            if request is None:
                return  # terminal events also arrive for untracked images/scripts
            if request.done or stamp < request.timestamp:
                raise ValueError("metadata")
            if method == _RESPONSE:
                request.status = _status(params.get("status"))
                if request.status >= 400 or request.status < 200:
                    request.failure = "http_error"
            elif method == _FAIL:
                request.done, request.failure = True, "request_failed"
            else:
                request.done = True
                if request.status is None:
                    request.failure = "response_missing"
                elif request.fresh and not request.failure:
                    self._fresh_finished += 1
            if self._armed and request.scoped:
                self._activity = max(self._activity, moment)
                if request.fresh and request.failure:
                    self._refuse(request.failure)
        except (ValueError, TypeError, OverflowError, UnicodeError):
            self._refuse("metadata_invalid")

    def ready(self, now: float, quiet_s: float) -> bool:
        try:
            moment, quiet = _number(now), _number(quiet_s)
            if quiet < 0:
                raise ValueError("quiet")
        except (ValueError, TypeError, OverflowError):
            self._refuse("metadata_invalid")
            return False
        return (
            self._armed
            and not self._failure
            and self._fresh_finished > 0
            and not any(r.scoped and not r.done for r in self._requests.values())
            and moment - self._activity >= quiet
        )

    def evidence(self) -> dict[str, int | bool | str]:
        return {
            "armed": self._armed,
            "lost": self._lost,
            "overflow": self._failure == "overflow",
            "failed_reason": self._failure,
            "observed": len(self._requests),
            "pending": sum(r.scoped and not r.done for r in self._requests.values()),
            "fresh_started": self._fresh_started,
            "fresh_finished": self._fresh_finished,
        }
