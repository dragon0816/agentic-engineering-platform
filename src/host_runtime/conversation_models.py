"""The chat composer's model choice (owner 2026-10-21).

A person picks, per conversation, one of the models the configured Gateway
serves; the pick is also remembered as that person's default for
conversations that have not chosen one. It applies from the next message
without restarting the Agent: the turn sets `models.selection.TURN_MODEL`,
and the router's `SelectableModelClient` sends that model id to the same
approved Gateway, after the data approval has decided the request.

Which models may be chosen is the Gateway's own list (`/v1/models`, read by
`AgentWeb.available_models` with the Host's credential mapping) plus the
model Settings configured. When the list cannot be read, only the configured
model is offered. Nothing here holds or returns a secret.

One small JSON file in the workspace, `conversation-models.json`:
`{"defaults": {actor: model}, "sessions": {session_id: model}}`.
Gateway keys stay unchanged; native keys are prefixed with `backend::`.
An empty native choice explicitly uses the provider default and sends no flag.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from host_runtime.workspace import write_atomically

CHOICES_FILE = "conversation-models.json"
#: How long a read Gateway list is trusted before it is read again.
LIST_TTL_SECONDS = 300.0
MAX_MODEL_ID = 200
# None means no active Web-turn snapshot. A tuple containing None explicitly
# freezes the provider default, even if another session changes the actor default.
BACKEND_TURN_MODEL: ContextVar[tuple[str, str | None] | None] = ContextVar(
    "aep_backend_turn_model", default=None
)


class ConversationModels:
    """Lists, remembers and resolves the composer's model choice."""

    def __init__(
        self,
        workspace_root: Path,
        *,
        listing: Callable[[], Mapping[str, Any]],
        configured: Callable[[], str | None],
        native_listing: Callable[[str], Mapping[str, Any]] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.path = workspace_root / CHOICES_FILE
        self.listing = listing
        self.configured = configured
        self.native_listing = native_listing
        self._native: dict[str, tuple[float, Mapping[str, Any]]] = {}
        self.clock = clock
        self._lock = threading.Lock()
        self._listed: tuple[str, ...] = ()
        self._listed_at: float | None = None
        self._list_code: str | None = None

    # -- the Gateway's list ------------------------------------------------

    def _read_list(self, *, refresh: bool = False) -> tuple[tuple[str, ...], str | None]:
        """The Gateway's model ids (cached) and why they could not be read."""
        now = self.clock()
        stale = self._listed_at is None or now - self._listed_at >= LIST_TTL_SECONDS
        if refresh or stale:
            try:
                answer = self.listing()
            except Exception:  # noqa: BLE001 - an unreadable list is a code, not a crash
                answer = {"ok": False, "code": "gateway_unreachable"}
            if answer.get("ok"):
                names = answer.get("models") or ()
                self._listed = tuple(
                    str(name)
                    for name in names
                    if isinstance(name, str) and 0 < len(name) <= MAX_MODEL_ID
                )
                self._listed_at = now
                self._list_code = None
            else:
                # The last list the Gateway gave stays usable; it is retried
                # at the next read rather than trusted for another period.
                self._list_code = str(answer.get("code") or "gateway_unreachable")
                if not self._listed:
                    self._listed_at = None
        return self._listed, self._list_code

    def approved(self) -> frozenset[str]:
        """Every model id a turn may use: the configured one and the list."""
        with self._lock:
            listed, _ = self._read_list()
        configured = self.configured()
        return frozenset((*listed, *((configured,) if configured else ())))

    # -- the stored choices --------------------------------------------------

    def _load(self) -> dict[str, dict[str, str]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return {"defaults": {}, "sessions": {}}
        stored: dict[str, dict[str, str]] = {"defaults": {}, "sessions": {}}
        if isinstance(raw, dict):
            for key in stored:
                values = raw.get(key)
                if isinstance(values, dict):
                    stored[key] = {
                        str(name): value
                        for name, value in values.items()
                        if isinstance(value, str) and (value or "::" in str(name))
                    }
        return stored

    def _save(self, stored: dict[str, dict[str, str]]) -> None:
        write_atomically(
            self.path,
            (json.dumps(stored, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode(
                "utf-8"
            ),
        )

    def chosen(
        self, actor: str, session_id: str | None, *, backend: str = "gateway"
    ) -> tuple[str | None, str]:
        """The stored choice for this conversation and where it came from:
        the conversation itself, the person's default, or nothing."""
        with self._lock:
            stored = self._load()
        actor = self._key(actor, backend)
        session_id = self._key(session_id, backend) if session_id else None
        if session_id and session_id in stored["sessions"]:
            return stored["sessions"][session_id], "conversation"
        if actor in stored["defaults"]:
            return stored["defaults"][actor], "default"
        return None, "settings"

    def for_turn(self, actor: str, session_id: str, *, backend: str = "gateway") -> str | None:
        """The model id a Gateway turn in this conversation asks for; None
        keeps the configured one. A stored id the Gateway no longer serves is
        still returned, so the turn says so instead of silently using another
        model."""
        snapshot = BACKEND_TURN_MODEL.get()
        if backend != "gateway" and snapshot is not None and snapshot[0] == backend:
            return snapshot[1]
        model, _ = self.chosen(actor, session_id, backend=backend)
        if backend != "gateway":
            return model or None
        configured = self.configured()
        return None if model is None or model == configured else model

    def forget(self, session_id: str) -> None:
        with self._lock:
            stored = self._load()
            stored["sessions"].pop(session_id, None)
            for key in list(stored["sessions"]):
                if key.endswith("::" + session_id):
                    del stored["sessions"][key]
            self._save(stored)

    # -- what the page asks for ------------------------------------------------

    def listed(
        self, actor: str, session_id: str | None, *, backend: str = "gateway", refresh: bool = False
    ) -> dict[str, Any]:
        if backend != "gateway":
            answer = self._native_list(backend, refresh=refresh)
            names = answer.get("models", []) if answer.get("ok") else []
            model, source = self.chosen(actor, session_id, backend=backend)
            native_unavailable = model if model and model not in names else None
            return {
                "ok": True,
                "backend": backend,
                "source": "native",
                "code": answer.get("code"),
                "configured": "",
                "selected": model if model and not native_unavailable else "",
                "selected_from": source
                if model is not None and not native_unavailable
                else "provider",
                "unavailable": native_unavailable,
                "models": [
                    {"id": "", "label": "Provider default", "status": "CLI default"},
                    *[{"id": name, "label": name, "status": "CLI catalog"} for name in names],
                ],
            }
        configured = self.configured()
        if not configured:
            return {"ok": False, "code": "model_not_configured", "models": []}
        with self._lock:
            names, code = self._read_list(refresh=self._listed_at is None)
        ids = list(dict.fromkeys((configured, *sorted(names))))
        model, source = self.chosen(actor, session_id)
        unavailable = model is not None and model not in ids
        return {
            "ok": True,
            "source": "gateway" if names else "configured",
            "code": code,
            "configured": configured,
            "selected": model if model is not None and not unavailable else configured,
            "selected_from": "settings" if model is None or unavailable else source,
            "unavailable": model if unavailable else None,
            "models": [
                {
                    "id": name,
                    "label": name,
                    "status": "Settings default" if name == configured else "Gateway",
                }
                for name in ids
            ],
        }

    def choose(
        self, actor: str, session_id: str, model: str, *, backend: str = "gateway"
    ) -> dict[str, Any]:
        """Remember `model` for this conversation and as the person's default."""
        if backend != "gateway":
            answer = self._native_list(backend)
            if model and (not answer.get("ok") or model not in answer.get("models", [])):
                return {"ok": False, "code": "model_not_approved"}
            with self._lock:
                stored = self._load()
                stored["sessions"][self._key(session_id, backend)] = model
                stored["defaults"][self._key(actor, backend)] = model
                self._save(stored)
            return {"ok": True, "selected": model, "configured": "", "backend": backend}
        configured = self.configured()
        if not configured:
            return {"ok": False, "code": "model_not_configured"}
        with self._lock:
            names, _ = self._read_list(refresh=model not in self._listed)
        if model != configured and model not in names:
            return {"ok": False, "code": "model_not_approved"}
        with self._lock:
            stored = self._load()
            stored["sessions"][session_id] = model
            stored["defaults"][actor] = model
            self._save(stored)
        return {"ok": True, "selected": model, "configured": configured}

    @staticmethod
    def _key(value: str, backend: str) -> str:
        return value if backend == "gateway" else backend + "::" + value

    def _native_list(self, backend: str, *, refresh: bool = False) -> Mapping[str, Any]:
        with self._lock:
            cached = self._native.get(backend)
            if not refresh and cached and self.clock() - cached[0] < LIST_TTL_SECONDS:
                return cached[1]
            try:
                answer = self.native_listing(backend) if self.native_listing else {"ok": False}
            except Exception:  # noqa: BLE001 - metadata failure is an explicit fallback
                answer = {"ok": False, "code": "model_catalog_unavailable", "models": []}
            self._native[backend] = (self.clock(), answer)
            return answer
