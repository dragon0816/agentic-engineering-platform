"""Agent Web's 附加資料顯示區 (owner 2026-11-20, docs/DECISIONS.md "Agent Web three-area
layout with a tabbed side area"): any page opens items as browser-like tabs on the right with
`sideOpen`, switches and closes them, and the area folds away with no tab open. A page's own
element moved into a tab goes back where it was when the tab closes. In a real browser when
one is installed."""

from __future__ import annotations

import pytest
from test_agent_sidebar_ui import page  # noqa: F401 - the browser fixture
from test_agent_web_followups_ui import _browser_missing

from host_runtime.web_page import PAGE


def test_the_side_area_is_a_generic_shell_part() -> None:
    area = PAGE.split('<aside class="extra-area"', 1)[1].split("</aside>", 1)[0]
    assert 'id="extra-tabs"' in area and 'role="tablist"' in area
    for name in ("function sideOpen(", "function sideClose(", "function sideFocus("):
        assert name in PAGE
    shell = PAGE.split("/* FEATURE_CSS */", 1)[0]
    assert "bi-" not in shell.split(".extra-area {", 1)[1].split("@media", 1)[0]


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_two_items_are_two_tabs_that_switch_and_close(page: tuple) -> None:  # type: ignore[type-arg]  # noqa: F811
    _runtime, server, ui = page
    ui.browser.navigate(server.address)
    ui.wait('!document.getElementById("send").disabled')
    assert ui.run("document.getElementById('extra-area').hidden") is True
    width = ui.run("document.querySelector('main').getBoundingClientRect().width")

    ui.run(
        "sideOpen({id: 'one', title: '第一個', render: (p) => { p.textContent = 'ONE'; }});"
        "const mine = document.createElement('p'); mine.id = 'own-node'; mine.textContent = 'MINE';"
        "document.getElementById('log').append(mine);"
        "sideOpen({id: 'two', title: '第二個', element: mine});"
    )
    tabs = ui.run(
        "[...document.querySelectorAll('#extra-tabs [role=tab]')].map(t => t.textContent)"
    )
    assert tabs == ["第一個", "第二個"]
    assert ui.run("document.getElementById('extra-area').hidden") is False
    assert ui.run("document.querySelector('main').getBoundingClientRect().width") < width
    # The newest is in front; the page's own node now lives in its tab.
    assert ui.run("document.getElementById('own-node').closest('.extra-panel') !== null") is True
    assert ui.run("document.querySelector('#extra-tabs [aria-selected=true]').textContent") == (
        "第二個"
    )
    ui.shoot("side-two-tabs")

    # Switching shows the other panel; opening the same id again only focuses it.
    ui.run("document.querySelector('#extra-tabs [role=tab]').click()")
    assert ui.run("document.querySelector('#extra-tabs [aria-selected=true]').textContent") == (
        "第一個"
    )
    assert ui.run("document.getElementById('extra-panel-one').hidden") is False
    assert ui.run("document.getElementById('extra-panel-two').hidden") is True
    ui.run("sideOpen({id: 'two'})")
    assert ui.run("document.querySelectorAll('#extra-tabs [role=tab]').length") == 2
    assert ui.run("document.querySelector('#extra-tabs [aria-selected=true]').textContent") == (
        "第二個"
    )

    # Closing a tab puts the page's node back; closing the last folds the area away.
    ui.run("document.querySelector('#extra-tabs .extra-tab.on .extra-tab-close').click()")
    assert ui.run("document.getElementById('own-node').parentElement.id") == "log"
    assert ui.run("document.querySelector('#extra-tabs [aria-selected=true]').textContent") == (
        "第一個"
    )
    ui.run("sideClose('one')")
    assert ui.run("document.getElementById('extra-area').hidden") is True
    assert ui.run("document.querySelector('.app-shell').classList.contains('extra-open')") is False
