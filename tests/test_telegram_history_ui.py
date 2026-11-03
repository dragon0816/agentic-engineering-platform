"""A stored Telegram conversation on the page, in a real browser when one is
installed (docs/phases/TELEGRAM_HISTORY.md): the mark in the list, the opening
selection, the read-only view, search and delete. No Telegram and no model."""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from test_agent_web_followups_ui import _browser_missing, _Page
from test_host_wiring import ready

from host_runtime.host import HostRuntime, build_runtime
from host_runtime.telegram_history import StoredTurn, TelegramHistory
from host_runtime.web import AgentWeb, AgentWebServer
from host_runtime.web_page import PAGE

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "telegram-history"
CHAT = 7654321987654


def test_the_page_has_the_read_only_note_and_the_search_call() -> None:
    assert PAGE.index('id="read-only-note"') < PAGE.index('<form class="ask" id="ask">')
    for hook in (
        "這是 Telegram 對話，只能閱讀；要繼續請回到 Telegram。",
        '"/api/conversations/search?q="',
        'el("ask").hidden = readOnly;',
    ):
        assert hook in PAGE, hook


@pytest.fixture
def page(tmp_path: Path) -> Iterator[tuple[HostRuntime, AgentWebServer, _Page]]:
    from integrations.browser import Browser

    config, layout = ready(tmp_path)
    shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
    shots.mkdir(parents=True, exist_ok=True)
    with build_runtime(config, layout=layout) as runtime:
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()
        shown = _Page(browser, shots)
        try:
            shown.size(1280, 900)
            yield runtime, server, shown
        finally:
            browser.close()
            browser.discard_profile()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def store(runtime: HostRuntime, said: str) -> str:
    history = runtime.telegram_history
    assert isinstance(history, TelegramHistory)
    history.start_new(CHAT, CHAT)
    history.add_turn(CHAT, CHAT, StoredTurn(said, "the stored answer"))
    return runtime.state.conversations(runtime.actor, source="telegram")[0].session_id


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_a_telegram_conversation_is_marked_read_only_found_and_deleted(page: tuple) -> None:  # type: ignore[type-arg]
    runtime, server, ui = page
    session = store(runtime, "a title from telegram")
    ui.browser.navigate(server.address)
    ui.wait('!document.getElementById("send").disabled')

    # The newest record is Telegram's, yet the page opens on a conversation
    # it can write to, made for the purpose when there is none.
    assert str(ui.run("activeConversation")).startswith("conversation-")
    assert not ui.run("document.getElementById('ask').hidden")
    assert ui.run("document.getElementById('read-only-note').hidden")
    listed = str(ui.run("document.getElementById('session-list').textContent"))
    assert "a title from telegram" in listed and "Telegram" in listed
    assert str(CHAT) not in str(ui.run("document.body.textContent"))
    ui.shoot("list-light-1280")

    # Opening it: read, no composer, no controls on the turn.
    ui.run(
        "[...document.querySelectorAll('.session-item')]"
        ".find(b => b.textContent.includes('a title from telegram')).click()"
    )
    ui.wait("document.getElementById('log').textContent.includes('the stored answer')")
    ui.wait("document.getElementById('ask').hidden")
    assert not ui.run("document.getElementById('read-only-note').hidden")
    assert ui.run("document.getElementById('conversation-backend').disabled")
    assert ui.run("document.querySelector('#log .turn-tools') === null")
    assert str(ui.run("activeConversation")) == session
    ui.shoot("read-only-light-1280")
    ui.size(390, 800, mobile=True)
    ui.no_side_scroll()
    ui.shoot("read-only-light-390")
    ui.size(1280, 900)

    # Search: words only in a message's text, shown with a snippet.
    ui.run(
        "const box = document.getElementById('session-search'); box.value = 'stored answer';"
        "box.dispatchEvent(new Event('input'));"
    )
    ui.wait("document.querySelector('.session-snippet') !== null")
    assert "stored answer" in str(ui.run("document.querySelector('.session-snippet').textContent"))
    ui.shoot("search-light-1280")
    ui.run(
        "const box2 = document.getElementById('session-search'); box2.value = '';"
        "box2.dispatchEvent(new Event('input'));"
    )
    ui.wait("document.querySelector('.session-snippet') === null")

    # A new session gets the composer back.
    ui.run("document.getElementById('new-conversation').click()")
    ui.wait("!document.getElementById('ask').hidden")
    assert ui.run("document.getElementById('read-only-note').hidden")
    assert not ui.run("document.getElementById('conversation-backend').disabled")

    # Delete works from the same button as any session.
    ui.run("window.confirm = () => true")
    ui.run(
        "[...document.querySelectorAll('.session-row')]"
        ".find(r => r.textContent.includes('a title from telegram'))"
        ".querySelector('.session-delete-button').click()"
    )
    ui.wait("!document.getElementById('session-list').textContent.includes('from telegram')")
    assert runtime.state.conversation(session, runtime.actor) is None
