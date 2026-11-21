"""新增 BI 收集 bot sets the bot and its 收集時間 in one save (owner 2026-11-21). The form
starts at 18:00; a target that is not exactly one BI domain is said beside 儲存 and nothing
is written. In a real browser when one is installed (`test_agent_sidebar_ui`'s page)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from test_agent_sidebar_ui import page  # noqa: F401 - the real Agent Web page fixture
from test_agent_web_followups_ui import _browser_missing


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_a_target_that_is_no_domain_is_said_beside_save_and_nothing_is_written(
    page: tuple,  # type: ignore[type-arg]  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from test_bot_identity import FakeTelegram
    from test_telegram_settings import TOKEN, Store, _update

    from host_runtime import bot_identity

    runtime, server, ui = page
    web = server.web
    web.user_environment = Store()  # never the real registry in tests
    monkeypatch.setattr(web, "start_telegram", lambda: None)  # no network
    monkeypatch.setenv("AEP_TELEGRAM_BOT_TOKEN", TOKEN)
    fake: Any = FakeTelegram({TOKEN: ("aep_main_bot", "AEP Main")})
    monkeypatch.setattr(bot_identity, "TRANSPORT_FACTORY", lambda: fake)
    assert web.update_telegram_settings(_update())["ok"] is True

    ui.browser.navigate(server.address)
    ui.wait('!document.getElementById("send").disabled')
    ui.run("document.getElementById('nav-settings').click()")
    ui.wait("!!document.querySelector('#agents-rows table')")
    ui.wait("!document.getElementById('collect-add').disabled", seconds=20)
    ui.run("document.getElementById('collect-add').click()")
    assert ui.run("document.getElementById('collect-time').value") == "18:00"
    ui.run(
        "document.getElementById('collect-name').value = 'bi_robotics';"
        "document.getElementById('collect-target').value = 'robotics';"
        "document.getElementById('collect-save').click()"
    )
    status = "document.getElementById('collect-save-status')"
    ui.wait(f"{status}.textContent.includes('找不到領域「robotics」')", seconds=20)
    assert ui.run(f"{status}.parentElement.contains(document.getElementById('collect-save'))")
    telegram = json.loads(runtime.layout.telegram.read_text(encoding="utf-8"))
    assert telegram.get("collection_bots", []) == []
