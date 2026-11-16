"""Feature mount points: core without BI, and BI through them unchanged.

Proposal r3 stage A (docs/phases/FEATURE_PLUGIN_BI_STAGE2_PROPOSAL_DRAFT_20261115.md):
the Host reaches BI only through `host_runtime.features`, so an empty feature set
is a working AEP with no BI, and the built-in set is the AEP that was.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import _WATCH, browser_missing
from test_host_wiring import host_json, ready

from host_runtime import features, features_bi, web_page
from host_runtime.assets import shipped
from host_runtime.assistant_tools import AssistantTools
from host_runtime.change_proposals import ProposalRefused
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from integrations.browser import Browser

ROOT = Path(__file__).resolve().parents[1]
NONE = features.FeatureSet(())


def test_the_built_in_features_are_bi_and_its_page_is_the_default_page() -> None:
    assert [feature.name for feature in features.active()] == ["bi-knowledge"]
    assert web_page.page(features.FeatureSet((features_bi.FEATURE,))) == web_page.page()
    assert web_page.PAGE == web_page.page()
    page = web_page.page()
    assert page.count('id="kn-pane-bi"') == 1 and "BI Knowledge is not installed" not in page


def test_without_bi_the_page_keeps_the_shell_and_offers_no_bi_tab() -> None:
    page = web_page.page(NONE)
    assert "BI Knowledge is not installed" in page
    assert page.count('id="kn-pane-bi"') == 1 and page.count('id="bi-b-askable"') == 1
    assert 'id="bi-dataset"' not in page and "function biBuildMarkdown" not in page
    for slot in ("/* FEATURE_CSS */", "<!-- KNOWLEDGE_PANE -->", "/* FEATURE_JS */"):
        assert slot not in page
    # Every BI name the shell itself calls has a stand-in.
    for name in ("biLoad", "biDataset", "biVaultOf", "biBadge", "biTime", "biAtlasUrl"):
        assert f"function {name}(" in page, name
    assert "const bh = " in page


def test_core_modules_import_no_bi_code_when_no_feature_is_built_in() -> None:
    script = (
        "import sys\n"
        "from host_runtime import features\n"
        "features.BUILTIN = ()\n"
        "import host_runtime.host, host_runtime.web, host_runtime.sync, channels.telegram\n"
        "import host_runtime.change_proposals, host_runtime.assistant_tools\n"
        "import host_runtime.knowledge_binding, host_runtime.assets, host_runtime.web_page\n"
        "host_runtime.web_page.page()\n"
        "assert not host_runtime.assets.shipped() is None\n"
        "print('\\n'.join(sorted(n for n in sys.modules if n.startswith(("
        "'capabilities.bi_cards', 'host_runtime.bi_', 'host_runtime.features_bi')))))\n"
    )
    found = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env={**_environment(), "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert found.returncode == 0, found.stderr
    assert found.stdout.split() == []


def test_without_bi_the_host_offers_no_bi_tool_skill_capability_or_route(tmp_path: Path) -> None:
    with features.use(NONE):
        assert "bi-knowledge" not in {skill.metadata.identity.name for skill in shipped()}
        with _served(tmp_path) as (web, server):
            gateway = web.runtime.agent.gateway
            assert gateway.host_tools is not None
            names = {tool.tool.name for tool in gateway.host_tools()}
            assert not any(name.startswith("bi__") for name in names)
            assert "bi-cards.query" not in gateway.bridge.installed.names
            status, _ = _request(server, "GET", "/api/bi/datasets")
            assert status == 404
            # The Atlas feed is not answered without its token, nor refused as GET-only.
            status, _ = _request(server, "GET", "/api/v1/bi/analyses", token=False)
            assert status == 401
            status, _ = _request(server, "POST", "/api/v1/bi/analyses", token=False)
            assert status == 401
            assert features.active().finish_answer("plain", None) == "plain"
            assert not features.active().bypasses_knowledge("客戶有哪些機會？", gateway)
            with pytest.raises(ProposalRefused, match="not installed"):
                web.proposals._bi_chat_save()

            class On(AssistantTools):
                def bi_query_on(self) -> bool:
                    return True

            tools = On(web)
            assert "aep_bi_query" not in tools.listed()
            assert tools.bi_query({})["code"] == "bi_not_installed"


def test_with_bi_the_same_host_serves_bi(tmp_path: Path) -> None:
    with _served(tmp_path) as (web, server):
        gateway = web.runtime.agent.gateway
        assert "bi-knowledge" in {skill.metadata.identity.name for skill in shipped()}
        assert "bi-cards.query" in gateway.bridge.installed.names
        status, body = _request(server, "GET", "/api/bi/datasets")
        assert status == 200 and "datasets" in body
        status, body = _request(server, "POST", "/api/v1/bi/analyses", token=False)
        assert status == 405 and body["message"] == features_bi.FEED_POST_REFUSAL


def test_a_feature_answer_text_goes_through_finish_answer_in_order() -> None:
    class Mark(features.Feature):
        def __init__(self, mark: str) -> None:
            self.mark = mark

        def finish_answer(self, text: str, result: Any) -> str:
            return text + self.mark

    assert features.FeatureSet((Mark("a"), Mark("b"))).finish_answer("x", None) == "xab"


def test_telegram_answers_go_through_the_features_finish_answer() -> None:
    # Telegram had no test of its BI source line (proposal r3 §7): it now asks the
    # same mount point as the Web answer.
    import inspect

    from channels import telegram

    source = inspect.getsource(telegram)
    assert "features.active().finish_answer(conversation.text, conversation)" in source
    assert "with_bi_sources" not in source


def test_an_unknown_page_slot_is_refused() -> None:
    class Bad(features.Feature):
        name = "bad"

        def page_fragments(self) -> dict[str, str]:
            return {"sidebar": "<p>x</p>"}

    with pytest.raises(ValueError, match="unknown page slot sidebar"):
        features.FeatureSet((Bad(),)).page_fragments()


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_without_bi_the_page_loads_and_knowledge_opens_with_no_script_error(
    tmp_path: Path,
) -> None:
    with features.use(NONE), _served(tmp_path) as (_web, server):
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()
        try:
            browser.page().call("Page.enable")
            browser.page().call("Page.addScriptToEvaluateOnNewDocument", source=_WATCH)
            browser.navigate(server.address)
            _wait(browser, '!document.getElementById("send").disabled')
            browser.evaluate("document.getElementById('nav-knowledge').click()")
            _wait(browser, "!document.getElementById('panel-knowledge').hidden")
            hidden = browser.evaluate(
                "getComputedStyle(document.querySelector('#kn-tabs [data-kn=\"bi\"]')).display"
            )
            assert hidden == "none"
            assert browser.evaluate("window.__aepWatch.errors") == []
        finally:
            browser.close()


def _wait(browser: Browser, expression: str, seconds: float = 60) -> None:
    import time

    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if browser.evaluate(expression):
            return
        time.sleep(0.2)
    raise AssertionError(expression)


@contextmanager
def _served(tmp_path: Path) -> Iterator[tuple[AgentWeb, AgentWebServer]]:
    config, layout = ready(tmp_path / "pc")
    path = host_json(tmp_path, config)
    with build_runtime(config, layout=layout) as runtime:
        web = AgentWeb(runtime, config_path=path)
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield web, server
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def _request(
    server: AgentWebServer, method: str, path: str, *, token: bool = True
) -> tuple[int, Any]:
    host, port = server.server_address[0], server.server_address[1]
    name = host.decode() if isinstance(host, bytes) else host
    request = urllib.request.Request(
        f"http://{name}:{port}{path}",
        method=method,
        data=b"{}" if method == "POST" else None,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {server.token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as reply:
            return reply.status, json.loads(reply.read() or b"null")
    except urllib.error.HTTPError as failure:
        text = failure.read()
        try:
            return failure.code, json.loads(text or b"null")
        except ValueError:
            return failure.code, text.decode("utf-8", "replace")


def _environment() -> dict[str, str]:
    import os

    return dict(os.environ)


def test_only_the_bi_feature_installs_subscribed_bi_dataset_packages() -> None:
    assert NONE.package_installer("bi_dataset") is None
    assert features.active().package_installer("bi_dataset") is not None
    assert features.active().package_installer("knowledge") is None
