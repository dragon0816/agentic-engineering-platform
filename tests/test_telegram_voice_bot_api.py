"""Telegram voice end to end over real HTTP against a fake Bot API
(docs/phases/VOICE_INPUT.md §4.5; slice V5): a voice note is fetched with
`getFile` and a GET download, shown as heard, opens the Workflow's card,
and runs only after the 「確認執行」 button. The production `api_base` stays
HTTPS; a forwarding transport points it at the local server."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fake_bot_api import FakeBotApi
from test_telegram_ingress import OWNER, TOKEN, CountingCredentials, config, ingress
from test_telegram_workflow_flow import _install

from channels.telegram import TelegramIngress
from voice.contracts import REPLIES, VoiceConfig
from voice.service import VoiceService
from voice.stt import FakeSttProvider, Segment, SttResult
from voice.transcript import TranscriptStore

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "voice"
# WAV content sent as Telegram's OGG voice note: decodes without PyAV (CI).
SPEECH = (FIXTURES / "zh_workflow.wav").read_bytes()
SPOKEN = "run release-validation-form package=quick"


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


def voice_note(number: int) -> dict[str, Any]:
    return {
        "update_id": number,
        "message": {
            "message_id": number,
            "chat": {"id": OWNER, "type": "private"},
            "from": {"id": OWNER, "is_bot": False, "first_name": "someone"},
            "voice": {
                "file_id": "note1",
                "file_unique_id": "u1",
                "duration": 2,
                "mime_type": "audio/ogg",
                "file_size": len(SPEECH),
            },
        },
    }


def tap(number: int, message_id: int, data: str) -> dict[str, Any]:
    return {
        "update_id": number,
        "callback_query": {
            "id": f"cb-{number}",
            "from": {"id": OWNER, "is_bot": False},
            "message": {"message_id": message_id, "chat": {"id": OWNER, "type": "private"}},
            "data": data,
        },
    }


def telegram(
    tmp_path: Path, bot: FakeBotApi, spoken: str | None, *, enabled: bool = True
) -> tuple[TelegramIngress, Any, FakeSttProvider]:
    _, agent, runner = ingress(tmp_path, bot.transport())  # type: ignore[arg-type]
    _install(agent, [{"name": "package", "label": "Mode", "kind": "text", "required": True}])
    fake = FakeSttProvider(default=heard(spoken) if spoken is not None else None)
    voice = VoiceService(VoiceConfig(), fake, TranscriptStore(tmp_path / "workspace"))
    item = TelegramIngress(
        config(),
        agent,
        CountingCredentials({"telegram_bot": TOKEN}),
        transport=bot.transport(),
        voice=voice if enabled else None,
    )
    assert item.config.api_base == "https://api.telegram.org"
    return item, runner, fake


def poll(item: TelegramIngress) -> Any:
    return asyncio.run(item.poll_once())


def test_a_voice_note_runs_a_workflow_only_after_the_button(tmp_path: Path) -> None:
    with FakeBotApi(TOKEN) as bot:
        bot.state.files["note1"] = SPEECH
        item, runner, fake = telegram(tmp_path, bot, SPOKEN)
        bot.push(voice_note(1))
        card = poll(item).deliveries[0]
        assert card.buttons == ((("確認執行", "run:yes"), ("修改", "run:edit")),)
        assert runner.bridge.events == ()
        assert bot.state.downloads == ["voice/note1.oga"]
        assert len(fake.calls) == 1
        said = bot.state.said()
        assert said.index("🎤 轉文字中…") < said.index(f"🎤 你說：「{SPOKEN}」")
        assert any("確認" in text or "Mode" in text for text in said[2:])

        bot.push(tap(2, bot.state.last_keyboard(), "run:yes"))
        ran = poll(item).deliveries[0]
        assert ran.outcome is not None and ran.outcome.workflow is not None
        assert "answerCallbackQuery" in bot.state.methods()
    [record] = TranscriptStore(tmp_path / "workspace").list("engineer", f"telegram-chat-{OWNER}")
    assert record.text == SPOKEN and record.used_as is not None
    assert TOKEN not in record.model_dump_json()
    assert sorted(
        path.suffix for path in (tmp_path / "workspace").rglob("*") if path.is_file()
    ) == [".json"]


def test_spoken_yes_at_the_card_does_not_run_over_http(tmp_path: Path) -> None:
    with FakeBotApi(TOKEN) as bot:
        bot.state.files["note1"] = SPEECH
        item, runner, fake = telegram(tmp_path, bot, SPOKEN)
        bot.push(voice_note(1))
        poll(item)
        fake.default = heard("好")
        bot.push(voice_note(2))
        refused = poll(item).deliveries[0]
        assert refused.reply == REPLIES["voice_not_confirmation"]
        assert runner.bridge.events == () and item._flows


def test_voice_off_over_http_never_calls_get_file(tmp_path: Path) -> None:
    with FakeBotApi(TOKEN) as bot:
        bot.state.files["note1"] = SPEECH
        item, _, fake = telegram(tmp_path, bot, SPOKEN, enabled=False)
        bot.push(voice_note(1))
        delivery = poll(item).deliveries[0]
        assert delivery.reply == "Only text messages are accepted here."
        assert "getFile" not in bot.state.methods() and bot.state.downloads == []
        assert fake.calls == []


def test_a_failed_download_over_http_is_refused(tmp_path: Path) -> None:
    with FakeBotApi(TOKEN) as bot:
        item, runner, fake = telegram(tmp_path, bot, SPOKEN)  # no file served
        bot.push(voice_note(1))
        delivery = poll(item).deliveries[0]
        assert delivery.reply and "🎤 你說" not in " ".join(bot.state.said())
        assert fake.calls == [] and runner.bridge.events == ()
