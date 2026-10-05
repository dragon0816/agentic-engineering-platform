"""Telegram bot settings on the Agent Web settings page.

The token is the one secret the page accepts. It goes to the user's
environment (a fake writer here, never the real registry) and the running
process, never to a file and never back to the page.
"""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any

import pytest
from test_host_wiring import host_json, ready

from host_runtime.host import build_runtime
from host_runtime.telegram_loop import ResidentTelegram
from host_runtime.telegram_settings import (
    TOKEN_VARIABLE,
    TelegramSettingsError,
    TelegramSettingsUpdate,
    apply_telegram_settings,
)
from host_runtime.web import AgentWeb
from host_runtime.web_page import PAGE

TOKEN = "123456789:AAH" + "x" * 32


class Store:
    def __init__(self) -> None:
        self.saved: dict[str, str] = {}

    def __call__(self, name: str, value: str) -> None:
        self.saved[name] = value


def _update(**changes: Any) -> TelegramSettingsUpdate:
    values: dict[str, Any] = {
        "enabled": True, "token": TOKEN, "senders": [{"sender_id": 42, "actor": "engineer"}],
    }
    values.update(changes)
    return TelegramSettingsUpdate.model_validate(values)


def test_the_token_goes_to_the_environment_and_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(TOKEN_VARIABLE, raising=False)
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    store = Store()
    updated = apply_telegram_settings(path, layout, _update(), store=store)
    assert store.saved == {TOKEN_VARIABLE: TOKEN}
    assert updated.credential_environment()["telegram_bot"] == TOKEN_VARIABLE
    for written in (path, layout.telegram):
        assert TOKEN not in written.read_text(encoding="utf-8")
    ingress = json.loads(layout.telegram.read_text(encoding="utf-8"))
    assert ingress["credential"] == {"name": "telegram_bot"}
    assert ingress["senders"] == [{"sender_id": 42, "actor": "engineer"}]
    assert "123456789" not in repr(_update())               # SecretStr hides it

    # Saving again without a token keeps the stored one.
    monkeypatch.setenv(TOKEN_VARIABLE, TOKEN)
    again = Store()
    apply_telegram_settings(path, layout, _update(token=None), store=again)
    assert again.saved == {}

    apply_telegram_settings(path, layout, _update(enabled=False), store=again)
    assert not layout.telegram.exists()
    assert (layout.workspace_root / "telegram.disabled.json").is_file()


@pytest.mark.parametrize(("changes", "code"), [
    ({"token": "not-a-token"}, "telegram_token_invalid"),
    ({"senders": []}, "telegram_senders_missing"),
    ({"token": None}, "telegram_token_missing"),
])
def test_incomplete_settings_are_refused_before_anything_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changes: dict[str, Any], code: str
) -> None:
    monkeypatch.delenv(TOKEN_VARIABLE, raising=False)
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    before = path.read_text(encoding="utf-8")
    store = Store()
    with pytest.raises(TelegramSettingsError, match=code):
        apply_telegram_settings(path, layout, _update(**changes), store=store)
    assert store.saved == {} and path.read_text(encoding="utf-8") == before
    assert not layout.telegram.exists()


def test_agent_web_saves_and_starts_the_bot_without_echoing_the_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(TOKEN_VARIABLE, raising=False)
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    with build_runtime(config, layout=layout) as runtime:
        web = AgentWeb(runtime, config_path=path)
        store = Store()
        web.user_environment = store
        started = threading.Event()
        monkeypatch.setattr(web, "start_telegram", started.set)   # no network in tests
        assert web.settings()["telegram"]["configured"] is False
        result = web.update_telegram_settings(_update())
        assert result["ok"] is True and result["restart_required"] is False
        assert TOKEN not in json.dumps(result)
        assert runtime.telegram is not None
        assert started.wait(timeout=5)
        status = web.settings()["telegram"]
        assert status["enabled"] and status["token_present"]
        assert TOKEN not in json.dumps(web.settings())
        refused = web.update_telegram_settings(_update(senders=[]))
        assert refused == {"ok": False, "code": "telegram_senders_missing"}


def test_the_resident_loop_starts_and_stops_on_request() -> None:
    class Ingress:
        def __init__(self) -> None:
            self.polling = threading.Event()

        async def run(self, stop: asyncio.Event) -> None:
            self.polling.set()
            await stop.wait()

    ingress = Ingress()
    loop = ResidentTelegram(ingress)  # type: ignore[arg-type]
    loop.start()
    assert ingress.polling.wait(timeout=5) and loop.running
    loop.stop(timeout=5)
    assert not loop.running and loop.failure is None


def test_the_page_offers_a_write_only_token_field_and_tucks_recent_runs_away() -> None:
    assert 'id="telegram-token" type="password"' in PAGE
    installed = PAGE.split('<section id="panel-installed">', 1)[1].split("</section>", 1)[0]
    tail = installed.rstrip().rsplit("<details", 1)[1]
    assert tail.startswith(' id="recent-runs"') and " open" not in tail.split(">", 1)[0]
    assert 'id="runs"' in tail
    script = PAGE.split("<script>", 1)[1].split("</script>", 1)[0]
    section = script.split("function showTelegram", 1)[1]
    section = section.split("async function loadModelChoices", 1)[0]
    for unsafe in ("innerHTML", "insertAdjacentHTML", "outerHTML"):
        assert unsafe not in section
