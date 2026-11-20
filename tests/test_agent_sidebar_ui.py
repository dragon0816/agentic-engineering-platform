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
from test_host_wiring import host_json, ready

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
        # A host.json to write, as the installed launcher has.
        server = AgentWebServer(AgentWeb(runtime, config_path=host_json(tmp_path, config)))
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


def _seed_agent(runtime: HostRuntime) -> str:
    from datetime import UTC, datetime

    from host_runtime.conversations import ConversationMessage, ConversationRecord
    from host_runtime.persistent_agents import AgentStore, PersistentAgent

    AgentStore(runtime.layout.workspace_root).save(
        PersistentAgent(
            id="sales", name="Sales", profile="engineering/sales-profile@1.0.0", skills=()
        )
    )
    now = datetime.now(UTC)
    runtime.state.create_conversation(
        ConversationRecord(
            session_id="conversation-parent",
            actor=runtime.actor,
            title="Parent turn",
            created_at=now,
            updated_at=now,
            messages=(
                ConversationMessage(
                    message_id="m1", role="user", text="ask", created_at=now, status="submitted"
                ),
                ConversationMessage(
                    message_id="m2",
                    role="assistant",
                    text="done",
                    created_at=now,
                    status="answered",
                    delegations=(
                        {
                            "profile": "engineering/sales-profile@1.0.0",
                            "status": "succeeded",
                            "summary": "Three shipments found.",
                        },
                    ),
                ),
            ),
        )
    )
    return "conversation-parent"


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_agents_section_lists_agents_and_opens_their_conversations(page: tuple) -> None:  # type: ignore[type-arg]
    runtime, server, ui = page
    parent = _seed_agent(runtime)
    ui.browser.navigate(server.address)
    ui.wait('!document.getElementById("send").disabled')
    ui.wait("document.querySelectorAll('#agent-list .agent-entry').length === 2")
    names = ui.run(
        "[...document.querySelectorAll('#agent-list .agent-entry > summary')]"
        ".map((s) => s.textContent).join('|')"
    )
    assert "Sales" in str(names)
    ui.run("document.querySelector('.agent-entry[data-agent=sales] > summary').click()")
    delegation = "document.querySelector('.agent-entry[data-agent=sales] [data-kind=delegation]')"
    ui.wait(f"!!{delegation}")
    assert "Three shipments found." in str(ui.run(f"{delegation}.textContent"))
    ui.shoot("agents-section")

    # A new conversation of the agent opens, and stays out of the Sessions list.
    ui.run("document.querySelector('.agent-entry[data-agent=sales] .agent-new').click()")
    ui.wait(
        "document.querySelectorAll('.agent-entry[data-agent=sales] [data-kind=conversation]')"
        ".length === 1"
    )
    owned = ui.wait(
        "(() => { const b = document.querySelector("
        "'.agent-entry[data-agent=sales] [data-kind=conversation]');"
        " return b && activeConversation === b.dataset.session && b.dataset.session; })()"
    )
    listed = str(ui.run("document.getElementById('session-list').innerHTML"))
    assert str(owned) not in listed
    record = runtime.state.conversation(str(owned), runtime.actor)
    assert record is not None and record.agent == "sales"

    # A delegation record opens the conversation it is in.
    ui.run(f"{delegation}.click()")
    ui.wait(f"activeConversation === {parent!r}")


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_settings_agents_adds_an_agent_and_refuses_a_pasted_token(page: tuple) -> None:  # type: ignore[type-arg]
    runtime, server, ui = page
    ui.browser.navigate(server.address)
    ui.wait('!document.getElementById("send").disabled')
    ui.run("document.getElementById('nav-settings').click()")
    ui.wait("!!document.querySelector('#agents-rows table')")
    ui.run("document.getElementById('agent-add').click()")
    ui.run(
        "document.getElementById('agent-form-name').value = 'Sales';"
        "document.getElementById('agent-bot-on').checked = true;"
        "document.getElementById('agent-bot-variable').value = "
        "'1234567890:AAE' + 'x'.repeat(32);"
        "document.getElementById('agent-save').click()"
    )
    # Non-ASCII stays on the Python side of the browser bridge.
    ui.wait("document.getElementById('agents-result').textContent.includes('token')")
    assert "token 本身" in str(ui.run("document.getElementById('agents-result').textContent"))
    assert not (runtime.layout.workspace_root / "agents.json").exists()
    ui.run(
        "document.getElementById('agent-bot-on').checked = false;"
        "document.getElementById('agent-save').click()"
    )
    ui.wait("document.getElementById('agents-rows').textContent.includes('Sales')")
    ui.wait("document.getElementById('agent-form').hidden")
    ui.wait(
        "[...document.querySelectorAll('#agent-list .agent-entry > summary')]"
        ".some((s) => s.textContent.includes('Sales'))"
    )
    ui.run("document.getElementById('agents-heading').scrollIntoView()")
    ui.shoot("settings-agents")
    (agent,) = (
        __import__("host_runtime.persistent_agents", fromlist=["AgentStore"])
        .AgentStore(runtime.layout.workspace_root)
        .agents()
    )
    assert agent.name == "Sales"
