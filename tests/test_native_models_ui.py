"""Real composer JavaScript ignores late catalogs and locks native choices."""

import json
import time
from pathlib import Path
from typing import Any

import pytest

from host_runtime.web_page import PAGE
from integrations.browser import Browser, browser_path


@pytest.mark.skipif(browser_path() is None, reason="Chromium is not installed")
def test_native_picker_catalog_races_fallback_and_turn_lock(tmp_path: Path) -> None:
    browser = Browser(tmp_path / "browser", timeout_s=30)
    browser.start()
    try:
        browser.navigate("about:blank")
        script = (
            "// "
            + PAGE.split("// The composer's model (owner 2026-10-21):", 1)[1].split(
                "async function loadBackends()", 1
            )[0]
        )
        script += (
            "async function changeConversationBackend("
            + PAGE.split("async function changeConversationBackend(", 1)[1].split(
                "async function loadChat(selectId)", 1
            )[0]
        )
        script += (
            'el("backend-public-start").addEventListener'
            + PAGE.split('el("backend-public-start").addEventListener', 1)[1].split(
                'el("backend-auth-cancel")', 1
            )[0]
        )
        script += (
            'el("backend-auth-check").addEventListener'
            + PAGE.split('el("backend-auth-check").addEventListener', 1)[1].split(
                "// New session:", 1
            )[0]
        )
        setup = """
          document.body.innerHTML = '<select id="conversation-model"></select>'
            + '<span id="model-readonly"></span><span id="model-state"></span>'
            + '<form id="ask"></form>';
          document.body.innerHTML += '<select id="conversation-backend"></select>'
            + '<span id="backend-state"></span><button id="backend-public-start"></button>'
            + '<span id="backend-public-result"></span><button id="backend-auth-check"></button>'
            + '<span id="backend-auth-result"></span>';
          window.el = id => document.getElementById(id);
          window.activeConversation = 'one'; window.activeBackend = 'gateway';
          window.backendStatuses = new Map(); window.__busy = false;
          window.sessionBusy = () => window.__busy;
          window.renderBackendState = () => {};
          window.renderAgentModeLine = () => {};
          window.loadBackends = async () => {};
          window.__requests = [];
          window.call = (path, body) => new Promise(resolve =>
            __requests.push({path, body, resolve}));
        """
        browser._evaluate(setup)
        browser._evaluate(
            "const s = document.createElement('script'); s.textContent = "
            + json.dumps(script)
            + "; document.body.append(s); true"
        )
        browser._evaluate("loadConversationModels(); true")
        browser._evaluate("activeBackend = 'codex'; loadConversationModels(); true")
        native: dict[str, Any] = {
            "ok": True,
            "backend": "codex",
            "source": "native",
            "configured": "",
            "selected": "actual-native",
            "selected_from": "conversation",
            "models": [
                {"id": "", "label": "Provider default", "status": "CLI default"},
                {"id": "actual-native", "label": "actual-native", "status": "CLI catalog"},
            ],
        }
        browser._evaluate("__requests[1].resolve(" + json.dumps(native) + "); true")

        def wait(expression: str) -> None:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if browser._evaluate(expression):
                    return
                time.sleep(0.05)
            raise AssertionError(expression)

        wait("el('conversation-model').value === 'actual-native'")
        browser._evaluate(
            "__requests[0].resolve({ok:true, "
            "models:[{id:'stale-gateway',label:'stale-gateway'}],"
            "selected:'stale-gateway'}); true"
        )
        assert browser._evaluate("el('conversation-model').value") == "actual-native"
        assert browser._evaluate("el('model-state').textContent.includes('account')")
        browser._evaluate("__busy=true; renderModelControl(); true")
        assert browser._evaluate("el('conversation-model').disabled")
        browser._evaluate("__busy=false; activeConversation='two'; loadConversationModels(); true")
        assert browser._evaluate("el('model-readonly').textContent") == "Reading models…"
        fallback = {
            **native,
            "code": "model_catalog_timeout",
            "selected": "",
            "models": native["models"][:1],
        }
        browser._evaluate("__requests[2].resolve(" + json.dumps(fallback) + "); true")
        wait("el('model-state').textContent.includes('model_catalog_timeout')")
        assert browser._evaluate("el('conversation-model').value") == ""
        browser._evaluate("el('conversation-model').dispatchEvent(new Event('change')); true")
        assert browser._evaluate("__requests[3].body.backend") == "codex"
        assert browser._evaluate("__requests[3].body.model") == ""
        browser._evaluate(
            "activeBackend='gateway'; activeConversation='one'; activeConversationPublic=true;"
            "backendStatuses.set('claude_code',{selectable:true,authentication:'ready'});"
            "chooseBackend('claude_code').then(() => window.__switchDone=true);"
            "activeConversation='two'; true"
        )
        browser._evaluate(
            "__requests[4].resolve({ok:true,conversation:{data_classification:'PUBLIC'}}); true"
        )
        wait("window.__switchDone")
        assert browser._evaluate("activeBackend") == "gateway"
        browser._evaluate(
            "window.__writes=[]; window.__server={};"
            "window.call=(path,body) => path === '/api/conversations/backend'"
            "? new Promise((resolve,reject) => __writes.push({body,reject,finish:() => {"
            "__server[body.session_id]=body.backend;"
            "resolve({ok:true,conversation:{data_classification:'PUBLIC'}});}}))"
            ": Promise.resolve(" + json.dumps(fallback) + ");"
            "backendStatuses.set('codex',{selectable:true,authentication:'ready'});"
            "window.__firstDone=false; chooseBackend('claude_code').then(() => __firstDone=true);"
            "chooseBackend('codex'); true"
        )
        assert browser._evaluate("__writes.length") == 1
        assert browser._evaluate("el('conversation-backend').disabled")
        browser._evaluate("__writes[0].finish(); true")
        wait("__firstDone")
        assert browser._evaluate("activeBackend === __server[activeConversation]")
        assert not browser._evaluate("el('conversation-backend').disabled")
        browser._evaluate(
            "window.__oldDone=false; window.__newDone=false;"
            "activeConversation='old'; chooseBackend('codex').then(() => __oldDone=true);"
            "activeConversation='new'; el('conversation-backend').disabled=false;"
            "chooseBackend('claude_code').then(() => __newDone=true); true"
        )
        assert browser._evaluate("el('conversation-backend').disabled")
        browser._evaluate("__writes[1].finish(); true")
        wait("__oldDone")
        assert browser._evaluate("el('conversation-backend').disabled")
        browser._evaluate("__writes[2].finish(); true")
        wait("__newDone")
        assert not browser._evaluate("el('conversation-backend').disabled")
        assert browser._evaluate("activeBackend === __server[activeConversation]")
        browser._evaluate(
            "window.pendingPublicBackend='codex'; window.pendingPublicSession='stale';"
            "window.pendingBackend='codex'; window.pendingBackendSession='stale';"
            "window.activeConversationMessages=0; window.__beforeWrites=__writes.length;"
            "el('backend-public-start').click(); el('backend-auth-check').click(); true"
        )
        wait("el('backend-public-result').textContent.includes('Conversation changed')")
        wait("el('backend-auth-result').textContent.includes('Conversation changed')")
        assert browser._evaluate("__writes.length === __beforeWrites")
        browser._evaluate(
            "chooseBackend('codex').catch(() => window.__rejected=true);"
            "__writes[3].reject(new Error('fixture')); true"
        )
        wait("window.__rejected")
        assert browser._evaluate("activeBackend === __server[activeConversation]")
        assert not browser._evaluate("el('conversation-backend').disabled")
    finally:
        browser.close()
        browser.discard_profile()
