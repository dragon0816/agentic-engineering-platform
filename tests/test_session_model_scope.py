"""Whichever session a request belongs to uses that session's model (owner
2026-10-22).

The Agent Web turn and the Telegram turn enter `session_model` once; every
model call of the turn -- the conversation, the Knowledge Harness answer, a
Workflow draft -- goes through the host's one `SelectableModelClient`, after
the data approval. Work with no session (schedules, the nightly job, the
experience review) uses the Settings model. Fakes only: a fake Gateway that
records the model it was asked for, a fake Bot API.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import threading
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import test_agent_web
from test_conversation_models import CONFIGURED, _choose, _session, _turn, chat
from test_host_models import GatewayReply, endpoint
from test_product_e2e_05 import V1
from test_settings_model_choices import _Lister
from test_telegram_ingress import OWNER, FakeTransport, ingress, poll, update

from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from capabilities.workflow_author.contracts import DraftWorkflowRequest
from capabilities.workflow_author.handlers import DRAFT_SPEC
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.conversation_models import CHOICES_FILE, ConversationModels
from host_runtime.conversations import ConversationTurnRequest
from host_runtime.schedule_control import ScheduleControl
from host_runtime.web import AgentWeb
from models.catalog import ModelEndpoint
from models.contracts import ModelMessage, ModelRequest, ModelResponse, ModelStreamEvent
from models.selection import (
    NOT_APPROVED,
    TURN_MODEL,
    SelectableModelClient,
    answered_by,
    session_model,
    settings_model,
)

__all__ = ["chat"]  # the shared fixture, re-exported for pytest

QUESTION = "According to widget-guide, what firmware does Safe mode require?"
SERVED = {"data": [{"id": "fixture-model"}, {"id": "claude-opus"}]}


class _RecordingKnowledgeGateway(test_agent_web.KnowledgeGateway):
    """The Knowledge fixture's Gateway, recording every model asked for."""

    models: list[str] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> GatewayReply:
        type(self).models.append(json.loads(body)["model"])
        return super().send(url, body, headers, timeout_s)


@pytest.fixture
def knowledge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[AgentWeb]:
    _RecordingKnowledgeGateway.models = []
    monkeypatch.setattr(test_agent_web, "KnowledgeGateway", _RecordingKnowledgeGateway)
    with test_agent_web.knowledge_runtime(tmp_path) as runtime:
        web = AgentWeb(runtime)
        web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        web.model_listing_transport = _Lister(200, SERVED)
        yield web


# -- one switch for every client ------------------------------------------------


def test_the_router_and_every_drafting_client_share_one_switch(knowledge: AgentWeb) -> None:
    gateway = knowledge.runtime.agent.gateway
    switch = gateway.router.model.client  # type: ignore[union-attr]
    assert isinstance(switch, SelectableModelClient)
    for identity in (KNOWLEDGE_QUERY_SPEC.identity, DRAFT_SPEC.identity):
        installed = gateway.bridge.installed.get(identity)
        assert installed is not None
        model = installed.handler.model  # type: ignore[attr-defined]
        # Each is still wrapped by the data approval, around the same switch.
        assert type(model).__name__ == "ApprovedModelClient"
        assert model.client is switch
    # Agent Web gave the shared switch the Gateway's list once.
    assert switch.approved == knowledge.conversation_models.approved


# -- the Knowledge answer ---------------------------------------------------------


def test_a_knowledge_answer_in_a_session_uses_the_session_model(knowledge: AgentWeb) -> None:
    web = knowledge
    session = _session(web)
    assert _choose(web, session, "claude-opus")["ok"]
    answered = _turn(web, session, QUESTION)
    assert answered["answer"]["status"] == "answered"
    assert "Safe mode requires firmware 2.0 [1]." in answered["answer"]["answer"]
    assert _RecordingKnowledgeGateway.models
    assert set(_RecordingKnowledgeGateway.models) == {"claude-opus"}
    # The answer records which model answered.
    assert answered["conversation"]["messages"][-1]["model"] == "claude-opus"
    assert answered["conversation"]["messages"][-2].get("model") is None
    # The Knowledge page's own ask belongs to no session: the Settings model.
    _RecordingKnowledgeGateway.models.clear()
    from host_runtime.contracts import KnowledgeAskRequest

    asked = web.ask_knowledge(
        KnowledgeAskRequest(asset=V1, question="What does Safe mode require?")
    )
    assert asked["ok"]
    assert set(_RecordingKnowledgeGateway.models) == {"fixture-model"}


def test_a_session_without_a_choice_uses_the_settings_model(knowledge: AgentWeb) -> None:
    web = knowledge
    answered = _turn(web, _session(web), QUESTION)
    assert answered["answer"]["status"] == "answered"
    assert set(_RecordingKnowledgeGateway.models) == {"fixture-model"}
    assert answered["conversation"]["messages"][-1]["model"] == "fixture-model"


def test_a_knowledge_answer_with_a_dropped_model_is_refused_and_not_sent(
    knowledge: AgentWeb,
) -> None:
    web = knowledge
    session = _session(web)
    (web.runtime.layout.workspace_root / CHOICES_FILE).write_text(
        json.dumps({"defaults": {}, "sessions": {session: "dropped-model"}}), encoding="utf-8"
    )
    refused = _turn(web, session, QUESTION)
    assert refused["answer"]["status"] != "answered"
    assert _RecordingKnowledgeGateway.models == []
    assert refused["conversation"]["messages"][-1].get("model") is None


# -- Workflow drafting -------------------------------------------------------------


def _draft(web: AgentWeb) -> None:
    installed = web.runtime.agent.gateway.bridge.installed.get(DRAFT_SPEC.identity)
    assert installed is not None
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor=web.runtime.actor,
        namespace="engineering",
        message="draft it",
        channel="local",
        session_id="session-x",
    )
    # The handler runs its model call in a worker thread (`asyncio.to_thread`).
    asyncio.run(
        installed.handler(
            context,
            DraftWorkflowRequest(
                sop="Copy the file, then tell the owner.", namespace="engineering"
            ),
        )
    )


def test_drafting_in_a_session_uses_its_model_and_outside_the_settings_model(
    chat: Any,
) -> None:
    web, gateway = chat
    web.conversation_models.approved()  # read the Gateway's list once
    with session_model("claude-opus") as used:
        _draft(web)
    assert gateway.models and set(gateway.models) == {"claude-opus"}
    assert used and set(used) == {"claude-opus"}
    gateway.models.clear()
    _draft(web)
    assert set(gateway.models) == {CONFIGURED}
    gateway.models.clear()
    with session_model("not-served"):
        _draft(web)
    assert gateway.models == []


# -- the answer message ----------------------------------------------------------


def test_each_answer_records_the_model_that_answered(chat: Any) -> None:
    web, _ = chat
    session = _session(web)
    first = _turn(web, session)
    assert first["conversation"]["messages"][-1]["model"] == CONFIGURED
    assert _choose(web, session, "claude-opus")["ok"]
    second = _turn(web, session)
    assert second["conversation"]["messages"][-1]["model"] == "claude-opus"
    # A turn no model answered (a command) records none.
    helped = web.conversation_turn(ConversationTurnRequest(session_id=session, message="/help"))
    assert helped["conversation"]["messages"][-1].get("model") is None
    # Stored, and read back after a restart of the record.
    record = web.runtime.state.conversation(session, web.runtime.actor)
    assert record is not None
    assert [m.model for m in record.messages if m.role == "assistant"] == [
        CONFIGURED,
        "claude-opus",
        None,
    ]


def test_a_question_cannot_claim_a_model() -> None:
    from datetime import UTC, datetime

    from host_runtime.conversations import ConversationMessage

    with pytest.raises(ValueError):
        ConversationMessage(
            message_id="m",
            role="user",
            text="hi",
            created_at=datetime.now(UTC),
            status="submitted",
            model="claude-opus",
        )


# -- Telegram ----------------------------------------------------------------------


class _Recorded:
    """A model client recording the model id it stands for."""

    def __init__(self, model: str, sent: list[str]) -> None:
        self.model = model
        self.sent = sent

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.sent.append(self.model)
        return ModelResponse(
            trace=request.trace, model_alias=request.model_alias, text=f"by {self.model}"
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def _telegram(tmp_path: Path, transport: FakeTransport) -> tuple[Any, list[str], Any]:
    item, agent, _ = ingress(tmp_path, transport)
    sent: list[str] = []
    the_endpoint = ModelEndpoint.model_validate(endpoint(credential=None, model=CONFIGURED))
    choices = ConversationModels(
        tmp_path,
        listing=lambda: {"ok": True, "models": [CONFIGURED, "claude-opus", "gpt-5.5"]},
        configured=lambda: CONFIGURED,
    )
    agent.gateway.router.model = SelectableModelClient(
        the_endpoint,
        _Recorded(CONFIGURED, sent),
        lambda chosen: _Recorded(chosen.model, sent),
        approved=choices.approved,
    )
    item.cards = SimpleNamespace(conversation_models=choices)
    return item, sent, choices


def test_a_telegram_turn_uses_its_chats_model(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            [update(1, OWNER, "hello")],
            [update(2, OWNER, "/model")],
            [update(3, OWNER, "/model 2")],
            [update(4, OWNER, "hello again")],
            [update(5, OWNER, "/model gpt-5.5")],
            [update(6, OWNER, "/model not-served")],
            [update(7, OWNER, "and now?")],
        ]
    )
    item, sent, choices = _telegram(tmp_path, transport)
    for _ in range(7):
        poll(item)
    replies = transport.sent()
    assert replies[0] == f"by {CONFIGURED}"
    listing = replies[1]
    assert f"Model for this chat: {CONFIGURED} (Settings default)." in listing
    assert "1. fixture-model · Settings default ✓" in listing and "2. claude-opus" in listing
    assert replies[2].startswith("This chat now uses claude-opus")
    assert replies[3] == "by claude-opus"
    assert replies[4].startswith("This chat now uses gpt-5.5")
    assert replies[5].startswith(f"Not changed ({NOT_APPROVED})")
    assert replies[6] == "by gpt-5.5"
    assert sent == [CONFIGURED, "claude-opus", "gpt-5.5"]
    # The chat's choice is its own session, and the person's default.
    assert choices.chosen("engineer", f"telegram-chat-{OWNER}") == ("gpt-5.5", "conversation")
    assert choices.chosen("engineer", "another-session") == ("gpt-5.5", "default")


def test_a_telegram_chat_follows_the_persons_default_and_refuses_a_dropped_model(
    tmp_path: Path,
) -> None:
    transport = FakeTransport([[update(1, OWNER, "hello")], [update(2, OWNER, "hi")]])
    item, sent, choices = _telegram(tmp_path, transport)
    path = tmp_path / CHOICES_FILE
    path.write_text(json.dumps({"defaults": {"engineer": "claude-opus"}, "sessions": {}}))
    poll(item)
    assert sent == ["claude-opus"]
    path.write_text(json.dumps({"defaults": {"engineer": "dropped-model"}, "sessions": {}}))
    poll(item)
    assert sent == ["claude-opus"]  # nothing sent for the dropped model
    assert transport.sent()[0] == "by claude-opus"
    assert len(transport.sent()) == 2 and "by" not in transport.sent()[1]


def test_telegram_without_agent_web_uses_the_settings_model(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "hello")], [update(2, OWNER, "/model")]])
    item, sent, _ = _telegram(tmp_path, transport)
    item.cards = None
    poll(item)
    poll(item)
    assert sent == [CONFIGURED]
    assert transport.sent()[1] == "Choosing a model needs Agent Web on this Bridge."


# -- no session: the Settings model --------------------------------------------------


def test_a_schedule_tick_uses_the_settings_model_whatever_called_it(
    chat: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    web, _ = chat
    seen: list[str | None] = []

    class _Worker:
        async def poll_once(self, *, now: Any) -> tuple[()]:
            seen.append(TURN_MODEL.get())
            return ()

        async def run_approved(self, key: str, **kwargs: Any) -> None:
            seen.append(TURN_MODEL.get())

    monkeypatch.setattr(ScheduleControl, "worker", lambda self, store: _Worker())
    control = ScheduleControl(web.runtime, lock=None)
    with session_model("claude-opus"):
        control.tick()
        control.approve("some-key")
        assert TURN_MODEL.get() == "claude-opus"
    assert seen == [None, None]


def test_the_nightly_job_and_experience_review_use_the_settings_model(chat: Any) -> None:
    web, _ = chat
    seen: list[str | None] = []

    def nightly(now: Any = None) -> None:
        seen.append(TURN_MODEL.get())

    def review() -> dict[str, Any]:
        seen.append(TURN_MODEL.get())
        return {}

    web._nightly_tick = nightly
    web._experience_review = review
    with session_model("claude-opus"):
        web.nightly_tick()
        web.experience_review()
    assert seen == [None, None]


# -- context across threads --------------------------------------------------------------


def test_the_session_model_crosses_to_thread_and_asyncio_run_but_not_a_plain_thread() -> None:
    seen: dict[str, str | None] = {}

    async def turn() -> None:
        seen["task"] = TURN_MODEL.get()
        seen["to_thread"] = await asyncio.to_thread(TURN_MODEL.get)

    def plain() -> None:
        seen["thread"] = TURN_MODEL.get()

    with session_model("claude-opus") as used:
        asyncio.run(turn())
        with ThreadPoolExecutor(max_workers=1) as pool:
            seen["executor_copied"] = pool.submit(
                contextvars.copy_context().run, TURN_MODEL.get
            ).result()
        worker = threading.Thread(target=plain)
        worker.start()
        worker.join()
        # A model call made in a worker thread is recorded on the turn's list.
        sent: list[str] = []
        switch = SelectableModelClient(
            ModelEndpoint.model_validate(endpoint(credential=None, model=CONFIGURED)),
            _Recorded(CONFIGURED, sent),
            lambda chosen: _Recorded(chosen.model, sent),
            approved=lambda: {"claude-opus"},
        )
        request = ModelRequest(
            trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
            model_alias="company",
            messages=(ModelMessage(role="user", text="hi"),),
        )
        asyncio.run(asyncio.to_thread(switch.generate, request))
        assert sent == ["claude-opus"] and used == ["claude-opus"]
        assert answered_by() == "claude-opus"
        with settings_model():
            assert TURN_MODEL.get() is None and answered_by() is None
        assert TURN_MODEL.get() == "claude-opus"
    assert seen == {
        "task": "claude-opus",
        "to_thread": "claude-opus",
        "executor_copied": "claude-opus",
        "thread": None,
    }
    assert TURN_MODEL.get() is None and answered_by() is None
