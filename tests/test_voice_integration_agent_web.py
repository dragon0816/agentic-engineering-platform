"""Agent Web voice contracts exercised through the authenticated HTTP routes."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import base, fetch, knowledge_runtime
from test_chat_workflow_forms import _plain
from test_host_wiring import ready
from voice_integration_helpers import (
    FIXTURES,
    MAX_BYTES,
    TextModel,
    assert_no_audio,
    conversation,
    fixture,
    payload,
    post,
    provider,
    serve,
    service,
    user_messages,
    wav,
)

from capabilities.coding_change.manifest import CHANGE_SPEC, coding_workflow
from host_runtime.host import build_runtime
from host_runtime.workflow_form_tool import workflow_form_tools
from voice.contracts import REPLIES, ErrorCode, VoiceConfig
from voice.stt import SttError
from voice.transcript import TranscriptStore


def test_disabled_host_keeps_text_working_and_refuses_voice(tmp_path: Path) -> None:
    """VOICE_INPUT §1.1 F8, §3.1, §4.3: default off does not affect text."""
    config, _ = ready(tmp_path)
    assert VoiceConfig().enabled is False
    with build_runtime(config) as runtime, serve(runtime) as server:
        session = conversation(server)
        typed = post(server, "/api/conversations/turn", {"session_id": session, "message": "/help"})
        assert typed.status == 200 and typed.json()["ok"] is True
        denied = post(server, "/api/voice/transcribe", payload(session, fixture("zh_ask")[0]))
        assert denied.status == 200
        assert denied.json()["ok"] is False and denied.json()["code"] == "voice_disabled"
        assert runtime.state.runs() == ()


@pytest.mark.parametrize("guard,status", [("missing-token", 401), ("foreign-host", 403)])
def test_voice_route_keeps_existing_http_guards(tmp_path: Path, guard: str, status: int) -> None:
    """VOICE_INPUT §3.1: voice keeps bearer and loopback Host guards."""
    config, _ = ready(tmp_path)
    with build_runtime(config) as runtime, serve(runtime) as server:
        response = fetch(
            base(server) + "/api/voice/transcribe",
            token=None if guard == "missing-token" else server.token,
            host="attacker.example" if guard == "foreign-host" else None,
            body=payload("guard-session", fixture("zh_ask")[0]),
        )
        assert response.status == status
        assert runtime.state.runs() == ()


def test_success_records_metadata_without_sending_a_turn_or_persisting_audio(
    tmp_path: Path,
) -> None:
    """VOICE_INPUT §3.1, §3.4, §4.2: transcription is visible, scoped, and audio-free."""
    config, layout = ready(tmp_path)
    data, pcm, expected = fixture("zh_ask")
    fake = provider("zh_ask")
    store = TranscriptStore(layout.workspace_root)
    with (
        build_runtime(config) as runtime,
        serve(runtime, service(layout.workspace_root, fake)) as server,
    ):
        session = conversation(server)
        response = post(server, "/api/voice/transcribe", payload(session, data))
        assert response.status == 200
        body = response.json()
        assert body["ok"] is True
        view = body["transcript"]
        assert view["text"] == expected and view["engine"] == "fake"
        assert view["duration_seconds"] == pytest.approx(pcm.duration_seconds, abs=0.01)
        assert [call.sha256 for call in fake.calls] == [pcm.sha256]
        record = store.get(runtime.actor, session, view["id"])
        assert record is not None and record.status == "ok" and record.channel == "web"
        assert record.text == expected and record.used_as is None
        assert record.audio.sha256 == hashlib.sha256(data).hexdigest()
        assert record.audio.bytes == len(data)
        assert record.stt is not None and record.stt.model_revision == "a" * 64
        assert store.get("another-person", session, record.id) is None
        assert store.get(runtime.actor, "another-session", record.id) is None
        assert store.list("another-person", session) == []
        assert store.list(runtime.actor, "another-session") == []
        folder = hashlib.sha256(session.encode()).hexdigest()[:24]
        assert (
            layout.workspace_root / "voice" / "transcripts" / folder / f"{record.id}.json"
        ).is_file()
        assert runtime.state.runs() == ()
        history = runtime.state.conversation(session, runtime.actor)
        assert history is not None and history.messages == ()
    assert_no_audio(layout.workspace_root, data, pcm.samples)


@pytest.mark.parametrize("code", ["stt_unavailable", "stt_busy", "stt_timeout", "stt_failed"])
def test_provider_errors_are_safe_user_errors_and_never_call_agent(
    tmp_path: Path, code: ErrorCode
) -> None:
    """VOICE_INPUT §3.6, §4.2: each STT error is surfaced with no Agent side effect."""
    config, layout = ready(tmp_path)
    data, pcm, _ = fixture("zh_ask")
    fake = provider("zh_ask", SttError(code))
    with (
        build_runtime(config) as runtime,
        serve(runtime, service(layout.workspace_root, fake)) as server,
    ):
        model = TextModel()
        runtime.agent.gateway.router.model = model
        session = conversation(server)
        response = post(server, "/api/voice/transcribe", payload(session, data))
        assert response.status == (503 if code == "stt_busy" else 200)
        assert response.json() == {"ok": False, "code": code, "message": REPLIES[code]}
        assert model.requests == [] and runtime.state.runs() == ()
        records = TranscriptStore(layout.workspace_root).list(runtime.actor, session)
        assert len(records) == 1 and records[0].error_code == code
        assert records[0].status == "failed" and records[0].text is None
    assert_no_audio(layout.workspace_root, data, pcm.samples)


@pytest.mark.parametrize(
    "case,code",
    [
        ("declared-duration", "audio_too_long"),
        ("measured-duration", "audio_too_long"),
        ("audio-bytes", "audio_too_large"),
        ("mime", "audio_unsupported_format"),
        ("corrupt", "audio_decode_failed"),
        ("truncated", "audio_decode_failed"),
        ("silence", "transcript_empty"),
    ],
)
def test_limits_decode_and_empty_errors(tmp_path: Path, case: str, code: ErrorCode) -> None:
    """VOICE_INPUT §3.1, §3.3, §3.6: measured limits win and failed audio never acts."""
    config, layout = ready(tmp_path)
    data = fixture("zh_ask")[0]
    fake = provider("silence_2s", "") if case == "silence" else provider("zh_ask")
    changes: dict[str, Any] = {}
    if case == "declared-duration":
        changes["duration_ms"] = 180001
    elif case == "measured-duration":
        data = wav(180.001)
        changes["duration_ms"] = 1
    elif case == "audio-bytes":
        data = data + b"\0" * (MAX_BYTES + 1 - len(data))
    elif case == "mime":
        changes["mime_type"] = "video/mp4"
    elif case in {"corrupt", "truncated"}:
        data = (FIXTURES / ("not_audio.ogg" if case == "corrupt" else "truncated.wav")).read_bytes()
    elif case == "silence":
        data = fixture("silence_2s")[0]
    with (
        build_runtime(config) as runtime,
        serve(runtime, service(layout.workspace_root, fake)) as server,
    ):
        session = conversation(server)
        response = post(server, "/api/voice/transcribe", payload(session, data, **changes))
        assert response.status == 200
        assert response.json() == {"ok": False, "code": code, "message": REPLIES[code]}
        assert runtime.state.runs() == ()
        records = TranscriptStore(layout.workspace_root).list(runtime.actor, session)
        assert len(records) == 1 and records[0].error_code == code
        assert records[0].status == ("empty" if code == "transcript_empty" else "failed")
        assert records[0].text is None
        if case != "silence":
            assert fake.calls == []
    assert_no_audio(layout.workspace_root, data)


def test_request_body_over_fourteen_mib_is_413(tmp_path: Path) -> None:
    """VOICE_INPUT §3.1: the independent 14 MiB JSON body cap returns HTTP 413."""
    config, layout = ready(tmp_path)
    fake = provider("zh_ask")
    with (
        build_runtime(config) as runtime,
        serve(runtime, service(layout.workspace_root, fake)) as server,
    ):
        response = post(server, "/api/voice/transcribe", {"padding": "x" * (14 * 1024 * 1024 + 1)})
        assert response.status == 413
        assert fake.calls == [] and runtime.state.runs() == ()


@pytest.mark.parametrize("name", ["zh_ask", "zh_workflow", "zh_coding"])
def test_fixture_transcript_uses_the_same_text_model_and_form_path(
    tmp_path: Path, name: str
) -> None:
    """VOICE_INPUT §2.3, §3.2, §4.3: all three uses enter the ordinary turn and retain forms."""
    data, _, expected = fixture(name)
    with knowledge_runtime(tmp_path) as runtime:
        root = runtime.layout.workspace_root
        model = TextModel(
            None
            if name == "zh_ask"
            else ("coding-change" if name == "zh_coding" else "weekly-report")
        )
        runtime.agent.gateway.router.model = model
        engine = runtime.agent.gateway.engine
        engine.workflows.register(
            coding_workflow() if name == "zh_coding" else _plain("weekly-report")
        )
        runtime.agent.gateway.host_tools = lambda: workflow_form_tools(engine)
        with serve(runtime, service(root, provider(name))) as server:
            session = conversation(server)
            voice = post(server, "/api/voice/transcribe", payload(session, data)).json()
            assert voice["ok"] is True and voice["transcript"]["text"] == expected
            assert model.requests == [] and runtime.state.runs() == ()
            spoken = post(
                server,
                "/api/conversations/turn",
                {
                    "session_id": session,
                    "message": expected,
                    "voice_transcript": voice["transcript"]["id"],
                },
            ).json()
            assert spoken["ok"] is True
            typed_session = conversation(server)
            typed = post(
                server,
                "/api/conversations/turn",
                {"session_id": typed_session, "message": expected},
            ).json()
            assert typed["ok"] is True
            assert spoken["answer"]["status"] == typed["answer"]["status"]
            assert spoken["answer"]["answer"] == typed["answer"]["answer"]
            assert user_messages(model).count(expected) == 2
            if name != "zh_ask":
                spoken_offer = spoken["answer"]["workflow_form"]
                typed_offer = typed["answer"]["workflow_form"]
                assert spoken_offer is not None and spoken_offer == typed_offer
                assert spoken_offer["workflow"]["name"] == model.workflow
                assert runtime.state.runs() == ()
            if name == "zh_coding":
                assert (
                    CHANGE_SPEC.policy.approval_required is True
                    and CHANGE_SPEC.side_effect == "write"
                )
            record = TranscriptStore(root).get(runtime.actor, session, voice["transcript"]["id"])
            assert record is not None and record.used_as is not None
            assert record.used_as.edited is False
            assert record.used_as.sent_text_sha256 == hashlib.sha256(expected.encode()).hexdigest()
        assert_no_audio(root, data)


@pytest.mark.parametrize("foreign", [False, True])
def test_sent_message_wins_and_foreign_transcript_never_blocks_a_turn(
    tmp_path: Path, foreign: bool
) -> None:
    """VOICE_INPUT §3.2: edits win; unknown/foreign transcript ids are ignored."""
    config, layout = ready(tmp_path)
    with (
        build_runtime(config) as runtime,
        serve(runtime, service(layout.workspace_root, provider("zh_ask"))) as server,
    ):
        owner = conversation(server)
        view = post(server, "/api/voice/transcribe", payload(owner, fixture("zh_ask")[0])).json()[
            "transcript"
        ]
        target = conversation(server) if foreign else owner
        result = post(
            server,
            "/api/conversations/turn",
            {"session_id": target, "message": "/help", "voice_transcript": view["id"]},
        )
        assert result.status == 200 and result.json()["ok"] is True
        assert "help" in result.json()["answer"]["answer"].lower()
        record = TranscriptStore(layout.workspace_root).get(runtime.actor, owner, view["id"])
        assert record is not None
        if foreign:
            assert record.used_as is None
        else:
            assert record.used_as is not None and record.used_as.edited is True
            assert record.used_as.sent_text_sha256 == hashlib.sha256(b"/help").hexdigest()


@pytest.mark.parametrize("name", ["zh_confirm", "zh_cancel"])
def test_spoken_card_reply_never_executes_and_cancel_matches_typed_text(
    tmp_path: Path, name: str
) -> None:
    """VOICE_INPUT §2.4, §4.3: spoken 好 cannot confirm; 取消 retains text semantics."""
    with knowledge_runtime(tmp_path) as runtime:
        engine = runtime.agent.gateway.engine
        engine.workflows.register(_plain("weekly-report"))
        model = TextModel("weekly-report")
        runtime.agent.gateway.router.model = model
        runtime.agent.gateway.host_tools = lambda: workflow_form_tools(engine)
        root = runtime.layout.workspace_root
        with serve(runtime, service(root, provider(name))) as server:
            sessions = [conversation(server), conversation(server)]
            for session in sessions:
                offered = post(
                    server,
                    "/api/conversations/turn",
                    {"session_id": session, "message": "run weekly-report"},
                ).json()
                assert offered["answer"]["workflow_form"]["workflow"]["name"] == "weekly-report"
            runtime.agent.gateway.router.model = TextModel()
            view = post(
                server, "/api/voice/transcribe", payload(sessions[0], fixture(name)[0])
            ).json()["transcript"]
            spoken = post(
                server,
                "/api/conversations/turn",
                {
                    "session_id": sessions[0],
                    "message": view["text"],
                    "voice_transcript": view["id"],
                },
            ).json()
            assert runtime.state.runs() == ()
            if name == "zh_confirm":
                assert REPLIES["voice_not_confirmation"] in spoken["answer"]["answer"]
            else:
                typed = post(
                    server,
                    "/api/conversations/turn",
                    {"session_id": sessions[1], "message": "取消"},
                ).json()
                assert spoken["answer"]["status"] == typed["answer"]["status"]
                assert spoken["answer"]["answer"] == typed["answer"]["answer"]
                assert spoken["answer"].get("workflow_form") == typed["answer"].get("workflow_form")
                assert runtime.state.runs() == ()


def test_coding_audio_creates_the_same_real_pending_approval_as_text(tmp_path: Path) -> None:
    """VOICE_INPUT §2.3, §4.3: coding.change requires the same ApprovalRequest before any write."""
    from voice_integration_helpers import CODING_ARGUMENTS, CodingModel, coding_approvals

    with knowledge_runtime(tmp_path) as runtime:
        root = runtime.layout.workspace_root
        chat, writes = coding_approvals(runtime.agent, root)
        runtime.chat_authoring = chat
        runtime.agent.gateway.router.model = CodingModel()
        with serve(runtime, service(root, provider("zh_coding"))) as server:
            spoken_session, typed_session = conversation(server), conversation(server)
            view = post(
                server, "/api/voice/transcribe", payload(spoken_session, fixture("zh_coding")[0])
            ).json()["transcript"]
            for session, extra in [
                (spoken_session, {"voice_transcript": view["id"]}),
                (typed_session, {}),
            ]:
                reply = post(
                    server,
                    "/api/conversations/turn",
                    {"session_id": session, "message": view["text"], **extra},
                ).json()
                assert reply["ok"] is True
            approvals = chat.approvals("engineer")
            assert len(approvals) == 2
            assert {item.session_id for item in approvals} == {spoken_session, typed_session}
            assert all(item.status == "pending" and item.kind == "capability" for item in approvals)
            assert all(
                item.workflow == "coding/change@1.0.0" and item.arguments == CODING_ARGUMENTS
                for item in approvals
            )
            assert writes == []


def test_edited_knowledge_transcript_keeps_real_raw_citations_and_route(tmp_path: Path) -> None:
    """VOICE_INPUT §3.2, §4.3: an edited recording uses the real Knowledge route and citations."""
    with knowledge_runtime(tmp_path) as runtime:
        root = runtime.layout.workspace_root
        with serve(runtime, service(root, provider("zh_ask"))) as server:
            spoken_session, typed_session = conversation(server), conversation(server)
            view = post(
                server, "/api/voice/transcribe", payload(spoken_session, fixture("zh_ask")[0])
            ).json()["transcript"]
            message = "According to widget_guide, what firmware does Safe mode require?"
            spoken = post(
                server,
                "/api/conversations/turn",
                {"session_id": spoken_session, "message": message, "voice_transcript": view["id"]},
            ).json()
            typed = post(
                server, "/api/conversations/turn", {"session_id": typed_session, "message": message}
            ).json()
            assert spoken["answer"]["status"] == typed["answer"]["status"] == "answered"
            assert spoken["answer"]["answer"] == typed["answer"]["answer"]
            assert "Safe mode requires firmware 2.0 [1]." in spoken["answer"]["answer"]
            assert "Sources (Raw):" in spoken["answer"]["answer"]
            assert spoken["answer"]["outcome"]["decision"] == typed["answer"]["outcome"]["decision"]
