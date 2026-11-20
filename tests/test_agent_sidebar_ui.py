"""The Agent Web sidebar's three collapsible sections (owner 2026-11-20,
docs/DECISIONS.md "Sidebar sections and agents bound to Telegram bots"): 主功能,
Sessions with 「New session」 above the search box, and Agents. Each remembers
being open or closed in the browser. In a real browser when one is installed."""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from test_agent_web_followups_ui import _browser_missing, _Page
from test_host_wiring import ready

from host_runtime.host import HostRuntime, build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from host_runtime.web_page import PAGE

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "agent-sidebar"


def test_the_sidebar_has_three_sections_in_order() -> None:
    sidebar = PAGE.split('<aside class="sidebar"', 1)[1].split("</aside>", 1)[0]
    order = [
        'id="side-main"',
        'id="nav-capabilities"',
        'id="nav-settings"',
        'id="nav-schedules"',
        'id="nav-knowledge"',
        'id="nav-tasks"',
        'id="nav-reviews"',
        'id="nav-memory"',
        'id="side-sessions"',
        'id="new-conversation"',
        'id="session-search"',
        'id="session-list"',
        'id="side-agents"',
        'id="agent-list"',
    ]
    places = [sidebar.index(item) for item in order]
    assert places == sorted(places)
    assert "主功能" in sidebar
    # The state is kept per browser.
    assert 'const key = "aep.side." + section.dataset.side;' in PAGE


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


def _visible(ui: _Page, element: str) -> bool:
    return bool(ui.run(f"!!document.getElementById('{element}').offsetParent"))


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_sections_fold_and_are_remembered_after_a_reload(page: tuple) -> None:  # type: ignore[type-arg]
    runtime, server, ui = page
    ui.browser.navigate(server.address)
    ui.wait('!document.getElementById("send").disabled')
    # All open at first; New session sits above the search box.
    for element in ("nav-settings", "new-conversation", "session-search", "agent-list"):
        assert _visible(ui, element), element
    above = ui.run(
        "document.getElementById('new-conversation').getBoundingClientRect().bottom"
        " <= document.getElementById('session-search').getBoundingClientRect().top"
    )
    assert above is True
    ui.shoot("open")

    ui.run("document.getElementById('side-main-toggle').click()")
    ui.run("document.getElementById('side-agents-toggle').click()")
    assert not _visible(ui, "nav-settings")
    assert not _visible(ui, "agent-list")
    assert _visible(ui, "session-list")
    assert ui.run("document.getElementById('side-main-toggle').getAttribute('aria-expanded')") == (
        "false"
    )
    ui.shoot("folded")

    ui.browser.navigate(server.address)
    ui.wait('!document.getElementById("send").disabled')
    assert not _visible(ui, "nav-settings")
    assert not _visible(ui, "agent-list")
    assert _visible(ui, "new-conversation")

    # Opened again, the nav still works and the choice is kept.
    ui.run("document.getElementById('side-main-toggle').click()")
    ui.run("document.getElementById('nav-settings').click()")
    ui.wait("document.getElementById('panel-settings').hasAttribute('data-open')")
    ui.browser.navigate(server.address)
    ui.wait('!document.getElementById("send").disabled')
    assert _visible(ui, "nav-settings")

    # New session still makes and opens a session.
    before = str(ui.run("activeConversation"))
    ui.run("document.getElementById('new-conversation').click()")
    ui.wait(f"activeConversation && activeConversation !== {before!r}")
    assert str(ui.run("activeConversation")).startswith("conversation-")
