"""The Host owns backend scoping and the running-turn selection lock."""

import threading
from typing import Any

import pytest
from test_conversation_backends import Runner, installed
from test_conversation_models import chat  # noqa: F401 - shared Gateway fixture

from agent.turn_progress import TurnProgress
from host_runtime.conversations import ConversationModelSelectRequest, ConversationTurnRequest


def test_native_selection_stale_backend_busy_and_gateway_compatibility(chat: Any) -> None:  # noqa: F811
    web, _ = chat
    session = web.create_conversation()["conversation"]["session_id"]
    original = web.runtime.state.conversation(session, web.runtime.actor)
    web.conversation_models.native_listing = lambda backend: {
        "ok": True,
        "models": [backend + "-m"],
    }
    web.runtime.state.save_conversation(original.model_copy(update={"backend": "codex"}))
    listed = web.conversation_model_choices(session, "codex")
    assert listed["backend"] == "codex"
    assert [x["id"] for x in listed["models"]] == ["", "codex-m"]
    assert (
        web.conversation_model_choices(session, "gateway")["code"] == "conversation_backend_changed"
    )
    request = ConversationModelSelectRequest(session_id=session, model="codex-m", backend="codex")
    assert web.select_conversation_model(request)["ok"]
    progress = TurnProgress("fixture", session_id=session, owner=web.runtime.actor)
    web.turn_progress.begin(progress)
    try:
        assert web.select_conversation_model(request)["code"] == "conversation_busy"
    finally:
        web.turn_progress.end(progress)
    web.runtime.state.save_conversation(original)
    assert web.select_conversation_model(request)["code"] == "conversation_backend_changed"
    assert web.conversation_model_choices(session)["selected"] == "fixture-model"
    web.runtime.state.save_conversation(original.model_copy(update={"backend": "codex"}))
    assert web.select_conversation_model(
        ConversationModelSelectRequest(session_id=session, model="", backend="codex")
    )["ok"]
    assert web.conversation_models.for_turn(web.runtime.actor, session, backend="codex") is None


@pytest.mark.parametrize("initial", [None, "m1"], ids=["provider-default", "actor-default"])
def test_native_turn_snapshots_default_before_another_session_changes_it(
    chat: Any,  # noqa: F811
    initial: str | None,
) -> None:
    web, _ = chat
    sessions = [web.create_conversation()["conversation"]["session_id"] for _ in range(2)]
    for session in sessions:
        record = web.runtime.state.conversation(session, web.runtime.actor)
        web.runtime.state.save_conversation(
            record.model_copy(
                update={
                    "backend": "codex",
                    "data_classification": "PUBLIC",
                    "classified_by": web.runtime.actor,
                }
            )
        )
    web.conversation_models.native_listing = lambda backend: {"ok": True, "models": ["m1", "m2"]}
    web.backends.available_models = lambda backend: {"ok": True, "models": ["m1", "m2"]}
    runner = Runner('{"result":"native answer"}')
    web.backends._which = installed
    web.backends._runner = runner
    if initial:
        assert web.conversation_models.choose(
            web.runtime.actor, sessions[1], initial, backend="codex"
        )["ok"]
    entered, release = threading.Event(), threading.Event()
    original = web._conversation_turn

    def paused(item: ConversationTurnRequest) -> dict[str, Any]:
        entered.set()
        assert release.wait(10)
        answer: dict[str, Any] = original(item)
        return answer

    web._conversation_turn = paused
    outcomes: list[dict[str, Any]] = []
    worker = threading.Thread(
        target=lambda: outcomes.append(
            web.conversation_turn(ConversationTurnRequest(session_id=sessions[0], message="Hello"))
        )
    )
    worker.start()
    try:
        assert entered.wait(10)
        assert web.select_conversation_model(
            ConversationModelSelectRequest(session_id=sessions[1], backend="codex", model="m2")
        )["ok"]
    finally:
        release.set()
        worker.join(20)
    assert not worker.is_alive()
    assert outcomes
    argv = runner.calls[-1][0]
    if initial is None:
        assert "--model" not in argv
    else:
        assert argv[argv.index("--model") + 1] == initial
