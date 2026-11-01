"""Agent Web's voice route and the turn's `voice_transcript` (docs/phases/
VOICE_INPUT.md §3.1, §3.2, §2.4; slice V6): transcription only fills the
message box; the turn is the typed turn; a spoken yes never confirms an
open form; voice off answers `voice_disabled`."""

from __future__ import annotations

import base64
import hashlib
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import base, fetch
from test_host_wiring import ready

from host_runtime.conversations import ConversationTurnRequest
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from voice.contracts import REPLIES, VoiceConfig
from voice.service import VoiceService
from voice.stt import FakeSttProvider, Segment, SttResult
from voice.transcript import TranscriptStore

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "voice"
SPEECH = (FIXTURES / "zh_ask.wav").read_bytes()


def heard(text: str) -> SttResult:
    return SttResult(
        segments=(Segment(0.0, 1.0, text),),
        language="zh",
        duration_seconds=1.0,
        elapsed_seconds=0.01,
        engine="fake",
        model="fake",
        model_revision="1",
    )


@contextmanager
def served(tmp_path: Path, text: str | None = "幫我查 CMX500") -> Iterator[tuple[Any, Any, Any]]:
    config, layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        voice = (
            VoiceService(
                VoiceConfig(),
                FakeSttProvider(default=heard(text)),
                TranscriptStore(layout.workspace_root),
            )
            if text is not None
            else None
        )
        server = AgentWebServer(AgentWeb(runtime), voice=voice)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield runtime, server, layout
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)


def post(server: AgentWebServer, path: str, body: Any) -> Any:
    return fetch(base(server) + path, token=server.token, body=body)


def new_session(server: AgentWebServer) -> str:
    return str(post(server, "/api/conversations", {}).json()["conversation"]["session_id"])


def transcribe(server: AgentWebServer, session: str, data: bytes = SPEECH, **changes: Any) -> Any:
    body = {
        "session_id": session,
        "mime_type": "audio/webm;codecs=opus",
        "duration_ms": 3000,
        "data": base64.b64encode(data).decode("ascii"),
        **changes,
    }
    return post(server, "/api/voice/transcribe", body)


def test_voice_off_answers_voice_disabled(tmp_path: Path) -> None:
    with served(tmp_path, None) as (_, server, _):
        session = new_session(server)
        response = transcribe(server, session)
        assert response.status == 200
        assert response.json() == {
            "ok": False,
            "code": "voice_disabled",
            "message": REPLIES["voice_disabled"],
        }


def test_a_transcript_fills_the_box_and_sends_nothing(tmp_path: Path) -> None:
    with served(tmp_path) as (runtime, server, layout):
        session = new_session(server)
        response = transcribe(server, session)
        assert response.status == 200
        body = response.json()
        assert body["ok"] is True and body["transcript"]["text"] == "幫我查 CMX500"
        history = runtime.state.conversation(session, runtime.actor)
        assert history is not None and history.messages == ()
        record = TranscriptStore(layout.workspace_root).get(
            runtime.actor, session, body["transcript"]["id"]
        )
        assert record is not None and record.channel == "web" and record.used_as is None


def test_requests_that_are_not_valid(tmp_path: Path) -> None:
    with served(tmp_path) as (_, server, _):
        session = new_session(server)
        assert transcribe(server, "c-unknown").status == 404
        assert transcribe(server, session, data=b"").status == 400
        broken = post(
            server,
            "/api/voice/transcribe",
            {"session_id": session, "mime_type": "audio/webm", "data": "***"},
        )
        assert broken.status == 400
        assert post(server, "/api/voice/transcribe", {"session_id": session}).status == 400


def test_a_body_over_fourteen_mib_is_refused(tmp_path: Path) -> None:
    with served(tmp_path) as (_, server, _):
        big = post(server, "/api/voice/transcribe", {"pad": "x" * (14 * 1024 * 1024 + 1)})
        assert big.status == 413


def test_a_spoken_credential_is_refused_and_not_shown(tmp_path: Path) -> None:
    secret = "123456789:" + "A" * 35
    with served(tmp_path, f"token {secret}") as (_, server, layout):
        response = transcribe(server, new_session(server))
        assert response.json() == {
            "ok": False,
            "code": "transcript_credential",
            "message": REPLIES["transcript_credential"],
        }
        stored = "".join(path.read_text("utf-8") for path in layout.workspace_root.rglob("*.json"))
        assert secret not in stored


@pytest.mark.parametrize("sent", ["幫我查 CMX500", "/help"])
def test_the_turn_records_how_the_transcript_was_used(tmp_path: Path, sent: str) -> None:
    with served(tmp_path) as (runtime, server, layout):
        session = new_session(server)
        view = transcribe(server, session).json()["transcript"]
        turn = post(
            server,
            "/api/conversations/turn",
            {"session_id": session, "message": sent, "voice_transcript": view["id"]},
        )
        assert turn.status == 200
        record = TranscriptStore(layout.workspace_root).get(runtime.actor, session, view["id"])
        assert record is not None and record.used_as is not None
        assert record.used_as.edited is (sent != view["text"])
        assert record.used_as.sent_text_sha256 == hashlib.sha256(sent.encode()).hexdigest()


def test_an_unknown_transcript_id_never_blocks_a_turn(tmp_path: Path) -> None:
    with served(tmp_path) as (_, server, _):
        session = new_session(server)
        turn = post(
            server,
            "/api/conversations/turn",
            {"session_id": session, "message": "/help", "voice_transcript": "vt-nothing"},
        )
        assert turn.status == 200 and turn.json()["ok"] is True


def test_a_typed_turn_is_unchanged_by_the_new_field() -> None:
    typed = ConversationTurnRequest.model_validate({"session_id": "c-1", "message": "hi"})
    assert typed.voice_transcript is None
    assert typed == ConversationTurnRequest(session_id="c-1", message="hi")


@pytest.mark.parametrize("spoken", ["好", "好。", "確認執行"])
def test_a_spoken_yes_never_confirms_an_open_form(tmp_path: Path, spoken: str) -> None:
    with served(tmp_path, spoken) as (runtime, server, _):
        session = new_session(server)
        web = server.web
        web._form_is_open = lambda record: True
        view = transcribe(server, session).json()["transcript"]
        spoken_turn = post(
            server,
            "/api/conversations/turn",
            {"session_id": session, "message": view["text"], "voice_transcript": view["id"]},
        ).json()
        assert REPLIES["voice_not_confirmation"] in spoken_turn["answer"]["answer"]
        assert runtime.state.runs() == ()
        typed = post(
            server, "/api/conversations/turn", {"session_id": session, "message": spoken}
        ).json()
        assert REPLIES["voice_not_confirmation"] not in typed["answer"]["answer"]
