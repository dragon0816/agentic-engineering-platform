"""Agent Web's microphone in a headless browser with a fake audio device
(docs/phases/VOICE_INPUT.md §4.4; slice V7). No real microphone and no
visible window: Chromium plays a committed synthetic WAV as the microphone.
The recording reaches the route, the transcript lands in the message box and
nothing is sent until the person presses Send; a denied microphone and voice
off leave the box alone."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from test_host_wiring import ready

from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from voice.contracts import VoiceConfig
from voice.service import VoiceService
from voice.stt import FakeSttProvider, Pcm16k, Segment, SttResult
from voice.transcript import TranscriptStore

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "voice" / "zh_ask.wav"
HEARD = "幫我查 CMX500 的 Wi-Fi 8 選項"
FAKE_MIC = (
    "--use-fake-device-for-media-stream",
    f"--use-file-for-fake-audio-capture={FIXTURE}",
)


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


pytestmark = pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")


@contextmanager
def page(
    tmp_path: Path, *, voice_on: bool = True, arguments: tuple[str, ...] = ()
) -> Iterator[tuple[Any, Any, Any, list[tuple[str | None, int]]]]:
    from integrations.browser import Browser

    config, layout = ready(tmp_path)
    received: list[tuple[str | None, int]] = []

    def decoder(data: bytes, mime_type: str | None, _config: VoiceConfig) -> Pcm16k:
        # The browser's WebM/Opus needs PyAV, which CI does not install; the
        # recording's arrival is what this test checks.
        received.append((mime_type, len(data)))
        return Pcm16k(bytes(2 * Pcm16k.RATE))

    with build_runtime(config) as runtime:
        voice = (
            VoiceService(
                VoiceConfig(),
                FakeSttProvider(
                    default=SttResult(
                        segments=(Segment(0.0, 1.0, HEARD),),
                        language="zh",
                        duration_seconds=1.0,
                        elapsed_seconds=0.01,
                        engine="fake",
                        model="fake",
                        model_revision="1",
                    )
                ),
                TranscriptStore(layout.workspace_root),
                decoder=decoder,
            )
            if voice_on
            else None
        )
        server = AgentWebServer(AgentWeb(runtime), voice=voice)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        browser = Browser(tmp_path / "browser", timeout_s=60, extra_arguments=arguments)
        try:
            browser.start()
            browser.navigate(server.address)
            yield runtime, server, browser, received
        finally:
            browser.close()
            server.shutdown()
            server.server_close()
            thread.join(5)


def wait(browser: Any, expression: str, seconds: float = 60) -> Any:
    from integrations.browser import BrowserError

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            value = browser._evaluate(expression)
        except BrowserError:
            value = None
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(expression)


def open_conversation(server: Any, browser: Any) -> str:
    session = str(server.web.create_conversation()["conversation"]["session_id"])
    wait(browser, "typeof loadChat === 'function' && voiceSettings !== null")
    browser._evaluate(f"loadChat({session!r})")
    wait(browser, f"activeConversation === {session!r}")
    return session


def test_a_recording_fills_the_box_and_sends_only_on_send(tmp_path: Path) -> None:
    arguments = ("--use-fake-ui-for-media-stream", *FAKE_MIC)
    with page(tmp_path, arguments=arguments) as (runtime, server, browser, received):
        session = open_conversation(server, browser)
        wait(browser, "!document.getElementById('mic').hidden")
        browser._evaluate("document.getElementById('mic').click()")
        wait(browser, "document.getElementById('mic-status').textContent.includes('錄音中')")
        time.sleep(1.5)
        browser._evaluate("document.getElementById('mic').click()")
        wait(browser, f"document.getElementById('message').value === {HEARD!r}")
        status = browser._evaluate("document.getElementById('mic-status').textContent")
        assert status == "語音轉文字，請確認內容後送出。"
        assert received and received[0][0] == "audio/webm" and received[0][1] > 0
        history = runtime.state.conversation(session, runtime.actor)
        assert history is not None and history.messages == ()  # nothing sent yet

        edited = HEARD + "，只看摘要"
        browser._evaluate(
            "(() => { const f = document.getElementById('message');"
            f" f.value = {edited!r}; f.dispatchEvent(new Event('input'));"
            " document.getElementById('ask').requestSubmit(); })()"
        )
        store = TranscriptStore(runtime.layout.workspace_root)
        [record] = store.list(runtime.actor, session)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            record = store.get(runtime.actor, session, record.id) or record
            if record.used_as is not None:
                break
            time.sleep(0.2)
        assert record.used_as is not None and record.used_as.edited is True
        history = runtime.state.conversation(session, runtime.actor)
        assert history is not None
        assert [m.text for m in history.messages if m.role == "user"] == [edited]


def test_a_denied_microphone_leaves_the_box_alone(tmp_path: Path) -> None:
    arguments = ("--deny-permission-prompts", *FAKE_MIC)
    with page(tmp_path, arguments=arguments) as (_, server, browser, received):
        open_conversation(server, browser)
        browser._evaluate(
            "document.getElementById('message').value = '原本的文字';"
            " document.getElementById('mic').click()"
        )
        wait(browser, "document.getElementById('mic-status').textContent.includes('麥克風')")
        assert browser._evaluate("document.getElementById('message').value") == "原本的文字"
        assert received == []


def test_voice_off_hides_the_microphone(tmp_path: Path) -> None:
    with page(tmp_path, voice_on=False) as (_, server, browser, _received):
        open_conversation(server, browser)
        assert browser._evaluate("voiceSettings.enabled") is False
        assert browser._evaluate("document.getElementById('mic').hidden") is True
