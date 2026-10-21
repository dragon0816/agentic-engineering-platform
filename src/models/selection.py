"""A conversation's own model at the same approved Gateway (owner 2026-10-21).

A Gateway such as LiteLLM serves several models behind one URL. The host's
data approval names that URL, not a model id (`ModelBinding`), and Settings
already treats a model change at the same approved Gateway as needing no new
approval. So a person may pick, per conversation, another model the Gateway
lists, and it applies from the next message without restarting the Agent.

The choice travels as a context variable set around one turn, never as a
field of `ModelRequest`: callers keep naming the stable alias, and a request
made outside a turn (a schedule, a Workflow draft) uses the configured model.

`SelectableModelClient` sits *inside* `ApprovedModelClient`, so the data
policy decides every request first. It sends the chosen model id to the same
endpoint (same URL, credential and capabilities); a model id that is not
approved -- not the configured one and not in the Gateway's current list --
is refused with a typed failure, never sent.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Collection, Iterator
from contextvars import ContextVar

from common.execution import Failure
from models import wire
from models.catalog import ModelEndpoint
from models.contracts import ModelClient, ModelRequest, ModelResponse, ModelStreamEvent

#: The model id the running conversation turn chose; None: the configured one.
TURN_MODEL: ContextVar[str | None] = ContextVar("aep_turn_model", default=None)

NOT_APPROVED = "model_not_approved"


def _only_configured() -> Collection[str]:
    return ()


class SelectableModelClient:
    """`ModelClient` for one endpoint that honours `TURN_MODEL`.

    `build` turns an endpoint into a client (the host's provider registry);
    `approved` returns the model ids the Gateway currently serves. The host
    replaces `approved` once it can read the Gateway's list; until then only
    the configured model is used.
    """

    def __init__(
        self,
        endpoint: ModelEndpoint,
        base: ModelClient,
        build: Callable[[ModelEndpoint], ModelClient | Failure],
        approved: Callable[[], Collection[str]] = _only_configured,
    ) -> None:
        self.endpoint = endpoint
        self.base = base
        self.build = build
        self.approved = approved
        self._lock = threading.Lock()
        self._built: dict[str, ModelClient] = {}

    @property
    def configured_model(self) -> str:
        return self.endpoint.model

    def _client(self, chosen: str | None) -> ModelClient | Failure:
        if chosen is None or chosen == self.endpoint.model:
            return self.base
        try:
            allowed = chosen in set(self.approved())
        except Exception:  # noqa: BLE001 - an unreadable list approves nothing extra
            allowed = False
        if not allowed:
            return Failure(
                code=NOT_APPROVED,
                message="the chosen model is not one this Gateway currently serves",
            )
        with self._lock:
            known = self._built.get(chosen)
            if known is not None:
                return known
            # Same alias, URL, credential and capabilities: only the id differs.
            built = self.build(self.endpoint.model_copy(update={"model": chosen}))
            if isinstance(built, Failure):
                return built
            self._built[chosen] = built
            return built

    def generate(self, request: ModelRequest) -> ModelResponse:
        client = self._client(TURN_MODEL.get())
        if isinstance(client, Failure):
            return wire.failed_response(request, client)
        return client.generate(request)

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        client = self._client(TURN_MODEL.get())
        if isinstance(client, Failure):
            yield wire.failed_event(request, client)
            return
        yield from client.stream(request)
