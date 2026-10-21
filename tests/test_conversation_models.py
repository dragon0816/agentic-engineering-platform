"""The chat composer's model choice (owner 2026-10-21).

The composer lists what the configured Gateway serves (`/v1/models`, read by
the Host with its own credential mapping), remembers a choice per
conversation and as the person's default, and the next Gateway turn sends
that model id to the same approved endpoint, after the data approval. A
model the Gateway does not serve is refused, never sent.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from test_host_models import GATEWAY, GatewayReply, binding, endpoint
from test_host_wiring import host_json, ready
from test_settings_model_choices import _Lister
from test_settings_model_choices import _web as _web_with_credential

from common.execution import TraceIdentifiers
from host_runtime.conversation_models import CHOICES_FILE, ConversationModels
from host_runtime.conversations import ConversationModelSelectRequest, ConversationTurnRequest
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from models.approved import ApprovedModelClient
from models.catalog import ModelEndpoint
from models.contracts import ModelMessage, ModelRequest, ModelResponse, ModelStreamEvent
from models.selection import NOT_APPROVED, TURN_MODEL, SelectableModelClient

CONFIGURED = "fixture-model"
LISTED = {"data": [{"id": CONFIGURED}, {"id": "claude-opus"}, {"id": "gpt-5.5"}]}


class _Gateway:
    """An OpenAI-compatible Gateway that answers with the model it was asked for."""

    def __init__(self) -> None:
        self.models: list[str] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> GatewayReply:
        payload = json.loads(body)
        self.models.append(payload["model"])
        message = {"role": "assistant", "content": f"answered by {payload['model']}"}
        return GatewayReply(
            200,
            {
                "choices": [{"index": 0, "message": message}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )


class _Unreachable:
    def request(self, *args: Any, **kwargs: Any) -> Any:
        raise OSError("connection refused")


@pytest.fixture
def chat(tmp_path: Path) -> Iterator[tuple[AgentWeb, _Gateway]]:
    config, layout = ready(
        tmp_path,
        config_changes={
            "models": binding(
                catalog={
                    "endpoints": [endpoint(credential=None, model=CONFIGURED)],
                    "routes": [{"name": "default", "alias": "company"}],
                }
            ),
        },
    )
    gateway = _Gateway()
    with build_runtime(config, layout=layout, model_transport=gateway) as runtime:
        web = AgentWeb(runtime, config_path=host_json(tmp_path, config))
        web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        web.model_listing_transport = _Lister(200, LISTED)
        yield web, gateway


def _session(web: AgentWeb) -> str:
    return str(web.create_conversation()["conversation"]["session_id"])


def _turn(web: AgentWeb, session: str, message: str = "hello there") -> dict[str, Any]:
    reply: dict[str, Any] = web.conversation_turn(
        ConversationTurnRequest(session_id=session, message=message)
    )
    return reply


def _choose(web: AgentWeb, session: str, model: str) -> dict[str, Any]:
    return web.select_conversation_model(
        ConversationModelSelectRequest(session_id=session, model=model)
    )


# -- the list ---------------------------------------------------------------


def test_the_list_is_what_the_gateway_serves_and_holds_no_secret(
    tmp_path: Path, monkeypatch: Any
) -> None:
    with _web_with_credential(tmp_path) as runtime:
        web = AgentWeb(runtime)
        variable = runtime.config.credential_environment()["llm_gateway_token"]
        monkeypatch.setenv(variable, "sk-composer-secret")
        lister = _Lister(200, {"data": [{"id": "gpt-5.5"}, {"id": "claude-opus"}, {"x": 1}]})
        web.model_listing_transport = lister
        session = _session(web)
        listed = web.conversation_model_choices(session)
        assert listed["ok"] and listed["source"] == "gateway" and listed["code"] is None
        assert listed["configured"] == "gpt-5.5" and listed["selected"] == "gpt-5.5"
        assert [item["id"] for item in listed["models"]] == ["gpt-5.5", "claude-opus"]
        assert listed["models"][0]["status"] == "Settings default"
        # The Host's credential mapping, at the saved Gateway only.
        method, url, headers = lister.calls[0]
        assert (method, url) == ("GET", GATEWAY.rstrip("/") + "/models")
        assert headers["Authorization"] == "Bearer sk-composer-secret"
        text = json.dumps(listed)
        assert "sk-composer-secret" not in text and "Bearer" not in text
        assert "AEP_LLM_TOKEN" not in text and GATEWAY not in text


def test_an_unreachable_gateway_offers_the_configured_model_alone(chat: Any) -> None:
    web, _ = chat
    web.model_listing_transport = _Unreachable()
    listed = web.conversation_model_choices(_session(web))
    assert listed["ok"] and listed["source"] == "configured"
    assert listed["code"] == "gateway_unreachable"
    assert [item["id"] for item in listed["models"]] == [CONFIGURED]
    assert listed["selected"] == CONFIGURED


def test_no_configured_model_is_a_code(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    with build_runtime(config, layout=layout) as runtime:
        web = AgentWeb(runtime)
        assert web.conversation_model_choices(None) == {
            "ok": False,
            "code": "model_not_configured",
            "models": [],
        }


def test_the_routes_answer_over_http(chat: Any) -> None:
    import urllib.request

    web, _ = chat
    session = _session(web)
    server = AgentWebServer(web)
    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        root = server.address.split("?", 1)[0].rstrip("/")
        auth = {"Authorization": f"Bearer {server.token}"}
        listed = json.loads(
            urllib.request.urlopen(
                urllib.request.Request(
                    f"{root}/api/conversations/models?session_id={session}", headers=auth
                )
            ).read()
        )
        assert [item["id"] for item in listed["models"]] == [CONFIGURED, "claude-opus", "gpt-5.5"]
        body = json.dumps({"session_id": session, "model": "claude-opus"}).encode()
        chosen = json.loads(
            urllib.request.urlopen(
                urllib.request.Request(
                    f"{root}/api/conversations/model",
                    data=body,
                    headers={**auth, "Content-Type": "application/json"},
                )
            ).read()
        )
        assert chosen == {"ok": True, "selected": "claude-opus", "configured": CONFIGURED}
        refused = urllib.request.Request(
            f"{root}/api/conversations/model",
            data=json.dumps({"session_id": session, "model": "not-served"}).encode(),
            headers={**auth, "Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(refused)
        assert caught.value.code == 409
        assert json.loads(caught.value.read())["code"] == NOT_APPROVED
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# -- the turn ----------------------------------------------------------------


def test_the_chosen_model_answers_the_next_turn_without_a_restart(chat: Any) -> None:
    web, gateway = chat
    session = _session(web)
    first = _turn(web, session)
    assert first["answer"]["answer"] == f"answered by {CONFIGURED}"
    assert _choose(web, session, "claude-opus")["ok"]
    second = _turn(web, session)
    assert second["answer"]["answer"] == "answered by claude-opus"
    assert gateway.models == [CONFIGURED, "claude-opus"]
    # Outside a turn, the configured model is used again.
    assert TURN_MODEL.get() is None


def test_a_model_the_gateway_does_not_serve_is_refused_and_never_sent(chat: Any) -> None:
    web, gateway = chat
    session = _session(web)
    assert _choose(web, session, "not-served") == {"ok": False, "code": NOT_APPROVED}
    # A stored choice the Gateway dropped since: the turn refuses, not sent.
    path = web.runtime.layout.workspace_root / CHOICES_FILE
    path.write_text(
        json.dumps({"defaults": {}, "sessions": {session: "dropped-model"}}), encoding="utf-8"
    )
    refused = _turn(web, session)
    assert refused["answer"]["status"] == "failed"
    assert NOT_APPROVED in refused["answer"]["answer"]
    assert gateway.models == []
    listed = web.conversation_model_choices(session)
    assert listed["unavailable"] == "dropped-model" and listed["selected"] == CONFIGURED


def test_the_data_approval_still_decides_before_the_chosen_model() -> None:
    endpoint_value = ModelEndpoint.model_validate(endpoint(credential=None, model=CONFIGURED))
    sent: list[str] = []

    class _Client:
        def __init__(self, model: str) -> None:
            self.model = model

        def generate(self, request: ModelRequest) -> ModelResponse:
            sent.append(self.model)
            return ModelResponse(trace=request.trace, model_alias=request.model_alias, text="ok")

        def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
            raise NotImplementedError

    switch = SelectableModelClient(
        endpoint_value,
        _Client(CONFIGURED),
        lambda item: _Client(item.model),
        approved=lambda: {"claude-opus"},
    )
    request = ModelRequest(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        model_alias="company",
        messages=(ModelMessage(role="user", text="hi"),),
    )
    unapproved_host = ApprovedModelClient(switch, None)
    token = TURN_MODEL.set("claude-opus")
    try:
        refused = unapproved_host.generate(request)
        assert refused.failure is not None and refused.failure.code != NOT_APPROVED
        assert sent == []
        assert switch.generate(request).text == "ok"
        assert sent == ["claude-opus"]
    finally:
        TURN_MODEL.reset(token)
    token = TURN_MODEL.set("other")
    try:
        answer = switch.generate(request)
        assert answer.failure is not None and answer.failure.code == NOT_APPROVED
        assert sent == ["claude-opus"]
    finally:
        TURN_MODEL.reset(token)


def test_a_cli_backend_turn_does_not_carry_the_gateway_choice(chat: Any) -> None:
    web, _ = chat
    session = _session(web)
    _choose(web, session, "claude-opus")
    seen: list[str | None] = []

    def recorded(item: ConversationTurnRequest) -> dict[str, Any]:
        seen.append(TURN_MODEL.get())
        return {}

    web._conversation_turn = recorded
    record = web.runtime.state.conversation(session, web.runtime.actor)
    assert record is not None
    web.runtime.state.save_conversation(record.model_copy(update={"backend": "codex"}))
    _turn(web, session)
    web.runtime.state.save_conversation(record)
    _turn(web, session)
    assert seen == [None, "claude-opus"]


# -- persistence ---------------------------------------------------------------


def test_the_choice_is_remembered_and_becomes_the_default_for_new_conversations(
    chat: Any,
) -> None:
    web, gateway = chat
    first = _session(web)
    assert _choose(web, first, "gpt-5.5")["ok"]
    # A fresh service over the same file: as after an Agent restart.
    again = ConversationModels(
        web.runtime.layout.workspace_root,
        listing=web.available_models,
        configured=lambda: CONFIGURED,
    )
    assert again.chosen(web.runtime.actor, first) == ("gpt-5.5", "conversation")
    second = _session(web)
    listed = web.conversation_model_choices(second)
    assert listed["selected"] == "gpt-5.5" and listed["selected_from"] == "default"
    _turn(web, second)
    assert gateway.models == ["gpt-5.5"]
    # A conversation's own pick outlives a later default from elsewhere.
    assert _choose(web, second, "claude-opus")["ok"]
    assert web.conversation_model_choices(first)["selected"] == "gpt-5.5"
    # Deleting a conversation forgets its pick, not the person's default.
    from host_runtime.conversations import ConversationDeleteRequest

    web.delete_conversation(ConversationDeleteRequest(session_id=second))
    stored = json.loads(
        (web.runtime.layout.workspace_root / CHOICES_FILE).read_text(encoding="utf-8")
    )
    assert second not in stored["sessions"] and first in stored["sessions"]
    assert stored["defaults"][web.runtime.actor] == "claude-opus"


def test_an_unknown_conversation_cannot_be_given_a_model(chat: Any) -> None:
    web, _ = chat
    assert _choose(web, "conversation-unknown", "claude-opus") == {
        "ok": False,
        "code": "conversation_unknown",
    }
