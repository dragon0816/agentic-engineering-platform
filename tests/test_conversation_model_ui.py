"""The chat composer's model menu and the backend selector at the top (owner
2026-10-21), in a real browser when one is installed.

The real Agent Web server and page, with a stub Gateway behind the real
model chain: the backend selector sits in the top bar above the messages,
the model menu under the message box; choosing a model changes the model the
next request sends, the menu is locked while the answer runs, a Gateway that
serves one model shows it as a label. Light, dark and 390 px; screenshots in
`.scratch/model-select/`.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from test_agent_web_followups_ui import _browser_missing, _Page
from test_conversation_models import CONFIGURED, LISTED
from test_host_models import GatewayReply, binding, endpoint
from test_host_wiring import host_json, ready
from test_settings_model_choices import _Lister

from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from host_runtime.web_page import PAGE

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "model-select"


def test_the_page_has_the_backend_on_top_and_the_model_in_the_composer() -> None:
    top = PAGE.index('<header class="topbar">')
    log = PAGE.index('<div id="log">')
    assert top < PAGE.index('id="conversation-backend"') < log
    footer = PAGE.index('<div class="composer-footer">')
    assert PAGE.index('id="message"') < footer < PAGE.index('id="conversation-model"')
    for hook in (
        '<label class="visually-hidden" for="conversation-model">LLM model</label>',
        'call("/api/conversations/models?session_id="',
        'call("/api/conversations/model", {session_id: session, model: chosen})',
        'el("chat-backend-bar").hidden = name !== "ask";',
        "select.disabled = busy;",
        'id="model-default-note"',
    ):
        assert hook in PAGE, hook


class _HeldGateway:
    """An OpenAI-compatible Gateway that waits for the test, then answers
    with the model it was asked for."""

    def __init__(self) -> None:
        self.models: list[str] = []
        self.release = threading.Event()
        self.release.set()

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> GatewayReply:
        payload = json.loads(body)
        self.models.append(payload["model"])
        self.release.wait(30)
        message = {"role": "assistant", "content": f"answered by {payload['model']}"}
        return GatewayReply(
            200,
            {
                "choices": [{"index": 0, "message": message}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )


@pytest.fixture
def page(tmp_path: Path) -> Iterator[tuple[AgentWeb, AgentWebServer, _HeldGateway, _Page]]:
    from integrations.browser import Browser

    config, layout = ready(
        tmp_path,
        config_changes={
            "models": binding(
                catalog={
                    "endpoints": [endpoint(credential=None, model=CONFIGURED)],
                    "routes": [{"name": "default", "alias": "company"}],
                }
            ),
        },
    )
    gateway = _HeldGateway()
    shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
    shots.mkdir(parents=True, exist_ok=True)
    with build_runtime(config, layout=layout, model_transport=gateway) as runtime:
        web = AgentWeb(runtime, config_path=host_json(tmp_path, config))
        web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        web.model_listing_transport = _Lister(200, LISTED)
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()
        shown = _Page(browser, shots)
        try:
            shown.size(1280, 900)
            yield web, server, gateway, shown
        finally:
            gateway.release.set()
            browser.close()
            browser.discard_profile()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def _rect(ui: _Page, selector: str) -> dict[str, float]:
    return dict(
        json.loads(
            str(
                ui.run(
                    f"JSON.stringify(document.querySelector({json.dumps(selector)})"
                    ".getBoundingClientRect())"
                )
            )
        )
    )


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_choosing_a_model_changes_the_next_request(page: Any) -> None:
    web, server, gateway, ui = page
    ui.browser.navigate(server.address)
    ui.wait('!document.getElementById("send").disabled')
    ui.wait('!document.getElementById("conversation-model").hidden')
    # The backend selector is at the top left of the chat, above the messages
    # and left of the "as … on …" line; the model menu is in the composer.
    assert ui.run("!!document.querySelector('.topbar #conversation-backend')")
    assert ui.run("!!document.querySelector('#ask .composer-footer #conversation-model')")
    backend, who, log = (
        _rect(ui, "#conversation-backend"),
        _rect(ui, "#who"),
        _rect(ui, "#log"),
    )
    assert backend["bottom"] <= log["top"] and backend["right"] <= who["left"]
    assert "Configured" in str(ui.run("document.getElementById('backend-state').textContent"))
    assert _rect(ui, "#conversation-model")["height"] >= 44
    assert _rect(ui, "#conversation-backend")["height"] >= 44
    options = json.loads(
        str(
            ui.run(
                "JSON.stringify([...document.getElementById('conversation-model').options]"
                ".map(o => o.value))"
            )
        )
    )
    assert options == [CONFIGURED, "claude-opus", "gpt-5.5"]
    ui.shoot("model-menu-light-1280")
    # Choose with the keyboard's result: a change event on the select.
    ui.run(
        "const s = document.getElementById('conversation-model'); s.focus();"
        "s.value = 'claude-opus'; s.dispatchEvent(new Event('change'));"
    )
    ui.wait("document.getElementById('model-state').textContent.startsWith('This conversation')")
    session = str(ui.run("activeConversation"))
    assert web.conversation_models.for_turn(web.runtime.actor, session) == "claude-opus"
    # Send; the menu is locked while the answer runs.
    gateway.release.clear()
    ui.run(
        "document.getElementById('message').value = 'which model are you?';"
        "document.getElementById('ask').requestSubmit();"
    )
    ui.wait("document.getElementById('conversation-model').disabled")
    assert "Locked" in str(ui.run("document.getElementById('model-state').textContent"))
    ui.shoot("model-menu-locked-light-1280")
    gateway.release.set()
    ui.wait("document.getElementById('log').textContent.includes('answered by claude-opus')")
    ui.wait("!document.getElementById('conversation-model').disabled")
    assert gateway.models[-1] == "claude-opus"
    # Dark mode at 390 px: the top bar wraps, nothing scrolls sideways.
    ui.dark(True)
    ui.size(390, 844, mobile=True)
    ui.no_side_scroll()
    assert _rect(ui, "#conversation-backend")["right"] <= 390
    assert _rect(ui, "#conversation-model")["right"] <= 390
    ui.shoot("model-menu-dark-390")
    ui.run("window.scrollTo(0, document.body.scrollHeight)")
    ui.shoot("model-menu-dark-390-composer")
    # Other tabs do not show the chat's backend selector.
    ui.run("document.getElementById('nav-settings').click()")
    ui.wait("document.getElementById('chat-backend-bar').hidden")
    ui.dark(False)
    ui.size(1280, 900)


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_one_served_model_is_a_label_not_a_menu(page: Any) -> None:
    web, server, _gateway, ui = page
    web.model_listing_transport = _Lister(200, {"data": [{"id": CONFIGURED}]})
    ui.browser.navigate(server.address)
    ui.wait('!document.getElementById("send").disabled')
    ui.wait("document.getElementById('model-readonly').textContent === " + json.dumps(CONFIGURED))
    assert ui.run("document.getElementById('conversation-model').hidden")
    assert "only model" in str(ui.run("document.getElementById('model-state').textContent"))
    ui.dark(True)
    ui.size(390, 844, mobile=True)
    ui.no_side_scroll()
    ui.shoot("model-label-dark-390")
