"""Charts in the general AI chat (BI C1, C2).

`docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md`: a `bi__query` answer
carries a chart spec (the saved one, or a bar for one label and one number
column, else a table), and the Host writes one self-contained HTML page per
call, drawn by the Dashboard tab's own renderer, which Agent Web shows in the
conversation's sandboxed file viewer. All data is fictional.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

import pytest
from test_chat_workflow_forms_telegram import _Scripted
from test_host_models import binding, endpoint
from test_host_wiring import grant_record, host_json, membership_record, workspace

from agent.gateway import ConversationToolExecution, GatewayConversationResult, HostToolOutcome
from capabilities.bi_cards import analyses, vault
from capabilities.bi_cards.capability import QUERY_SPEC
from common.execution import RequestContext, TraceIdentifiers
from host_runtime import bi_chart_html, skill_packs
from host_runtime.assets import shipped
from host_runtime.bi_cards_tools import TOOL_NAME, bi_cards_tools, bi_chart_files, chart_page
from host_runtime.conversations import ConversationTurnRequest
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from host_runtime.web_page import PAGE
from scripts import bi_feed_fixtures as fixtures

DATASET = vault.dataset_name(fixtures.VAULT_ID)
SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "bi-chat-charts"
TRACE = TraceIdentifiers(trace_id="t1", request_id="r1", span_id="s1")


# -- the chart spec (C1) -------------------------------------------------------------------


def test_one_label_and_one_number_column_is_a_bar_anything_else_a_table() -> None:
    assert analyses.default_chart(["region", "n"], [["TW", 3], ["JP", None]]) == {
        "type": "bar",
        "x": "region",
        "y": "n",
    }
    assert analyses.default_chart(["n", "region"], [[3, "TW"]]) == {
        "type": "bar",
        "x": "region",
        "y": "n",
    }
    table = {"type": "table"}
    assert analyses.default_chart(["a", "b", "c"], [["x", 1, 2]]) == table
    assert analyses.default_chart(["a", "b"], [[1, 2]]) == table  # two numbers
    assert analyses.default_chart(["a", "b"], [["x", "y"]]) == table  # two labels
    assert analyses.default_chart(["a", "b"], [["x", True]]) == table  # a bool is no number
    assert analyses.default_chart(["a", "b"], []) == table


def test_a_spec_naming_the_columns_is_kept_otherwise_the_default() -> None:
    rows = [["TW", 3]]
    line = {"type": "line", "x": "region", "y": "n"}
    assert analyses.chart_for(line, ["region", "n"], rows) == line
    assert analyses.chart_for({"type": "table"}, ["region", "n"], rows) == {"type": "table"}
    wrong = {"type": "line", "x": "level", "y": "n"}  # a column the section dropped
    assert analyses.chart_for(wrong, ["region", "n"], rows)["type"] == "bar"
    assert analyses.chart_for(None, ["region", "n"], rows)["type"] == "bar"


# -- the page (C2) -------------------------------------------------------------------------


def test_the_page_is_self_contained_and_uses_the_dashboards_renderer() -> None:
    # One renderer: the Agent Web page embeds the same source.
    assert bi_chart_html.BI_CHART_JS.strip() in PAGE
    assert bi_chart_html.BI_CHART_CSS.strip() in PAGE
    assert "/* BI_CHART" not in PAGE
    hostile = "</script><script>alert(1)</script>"
    page = bi_chart_html.page(
        "各地區 <b>",
        [{"title": hostile, "chart": {"type": "bar", "x": "r", "y": "n"},
          "columns": ["r", "n"], "rows": [[hostile, 1], [" ", 2]], "truncated": True}],
        about="vault-x · 發佈版本 v1",
    )  # fmt: skip
    assert page.count("</script>") == 2  # the data block and the drawing script only
    assert "<script src" not in page and "http://" not in page and "https://" not in page
    assert "fetch(" not in page and "XMLHttpRequest" not in page and "localStorage" not in page
    assert "innerHTML" not in page.replace('holder.innerHTML = "<svg></svg>"', "")
    assert "<title>各地區 &lt;b&gt;</title>" in page
    assert "default-src 'none'" in page
    block = page.split('id="bi-chart-data">', 1)[1].split("</script>", 1)[0]
    data = json.loads(block)
    assert data["sections"][0]["table"]["rows"][0][0] == hostile
    assert data["sections"][0]["table"]["truncated"] is True


def test_cards_become_a_table_of_their_fields() -> None:
    cards = [
        {"name": "Alder", "entity_type": "Account",
         "fields": {"region": {"value": "TW"}, "domain": {"value": ["robotics", "AIDC"]}}},
        {"name": "Fir", "entity_type": "Account", "fields": {"region": {"value": "US"}}},
    ]  # fmt: skip
    table = bi_chart_html.cards_table(cards)
    assert table["columns"] == ["name", "type", "region", "domain"]
    assert table["rows"] == [
        ["Alder", "Account", "TW", "robotics、AIDC"],
        ["Fir", "Account", "US", None],
    ]


def test_a_chart_page_is_written_per_call_and_nothing_for_an_empty_answer(
    tmp_path: Path,
) -> None:
    section = {"id": "accounts-by-region", "title": "各地區的客戶數", "chart": {"type": "bar",
               "x": "region", "y": "accounts"}, "columns": ["region", "accounts"],
               "rows": [["TW", 3]], "params": {"domain": "robotics"}}  # fmt: skip
    written = chart_page(tmp_path, {"dataset": DATASET, "analysis": [section]}, {})
    assert written is not None and written["media_type"] == "text/html"
    path = Path(written["path"])
    assert path.parent == tmp_path / "bi-chat-charts"
    assert path.name.startswith("bi-accounts-by-region-") and path.suffix == ".html"
    assert "domain=robotics" in path.read_text("utf-8")
    two = chart_page(tmp_path, {"dataset": DATASET, "analysis": [section, section]}, {})
    assert two is not None and Path(two["path"]).name.startswith("bi-all-")
    cards = chart_page(tmp_path, {"dataset": "demo", "cards": [{"name": "A"}]}, {})
    assert cards is not None and Path(cards["path"]).name.startswith("bi-cards-")
    assert chart_page(tmp_path, {"dataset": "demo", "cards": [], "analysis": []}, {}) is None


def test_agent_web_shows_only_the_answered_queries_pages(tmp_path: Path) -> None:
    page = tmp_path / "bi-chat-charts" / "bi-x.html"
    page.parent.mkdir()
    page.write_text("<p>x</p>", encoding="utf-8")
    attach = [{"path": str(page), "filename": page.name, "media_type": "text/html"}]

    def call(name: str, status: str, data: Any) -> ConversationToolExecution:
        return ConversationToolExecution(
            call_id=f"c-{name}-{status}", name=name, host=HostToolOutcome(status=status, data=data)
        )

    result = GatewayConversationResult(
        trace=TRACE,
        status="answered",
        text="ok",
        model_turns=2,
        tools=(
            call(TOOL_NAME, "succeeded", {"attach": attach}),
            call(TOOL_NAME, "failed", {"attach": attach}),
            call("other__tool", "succeeded", {"attach": attach}),
            call(TOOL_NAME, "succeeded", {"attach": [{"path": str(tmp_path / "gone.html")}]}),
        ),
    )
    assert bi_chart_files(result) == [{"filename": "bi-x.html", "kind": "html", "path": str(page)}]


# -- through the Bridge, then in Agent Web -------------------------------------------------


def _host(tmp_path: Path) -> tuple[Any, Any]:
    grants = [
        *grant_record(),
        {
            "actor": "engineer",
            "asset": QUERY_SPEC.identity.model_dump(mode="json"),
            "permissions": list(QUERY_SPEC.policy.required_permissions),
            "policy_refs": list(QUERY_SPEC.policy.policy_refs),
        },
    ]
    config, layout = workspace(
        tmp_path,
        membership=membership_record(),
        grants=grants,
        config_changes={
            "models": binding(
                catalog={
                    "endpoints": [endpoint(credential=None, model="fixture-model")],
                    "routes": [{"name": "default", "alias": "company"}],
                }
            )
        },
    )
    skill_packs.install_bundle(layout, None, shipped=shipped())
    copy = tmp_path / "shared" / "vault"
    shutil.copytree(fixtures.VAULT_DIR, copy)
    fixtures.join(layout.workspace_root, copy)
    return config, layout


def _call(tool: Any, arguments: dict[str, Any]) -> HostToolOutcome:
    """One call of a Host tool's handler, as the Gateway makes it."""

    async def once() -> HostToolOutcome:
        outcome: HostToolOutcome = await tool.handler(_context(), arguments)
        return outcome

    return asyncio.run(once())


def _data(outcome: HostToolOutcome) -> dict[str, Any]:
    assert outcome.status == "succeeded" and isinstance(outcome.data, dict)
    return dict(outcome.data)


def _context(session: str = "s-1") -> RequestContext:
    return RequestContext(
        trace=TRACE, actor="engineer", namespace="engineering", message="bi", channel="local",
        session_id=session,
    )  # fmt: skip


def test_the_query_tool_attaches_the_chart_page_of_a_published_analysis(tmp_path: Path) -> None:
    config, layout = _host(tmp_path)
    with build_runtime(config, layout=layout) as runtime:
        (tool, _atlas) = bi_cards_tools(runtime.agent.gateway)
        answer = _call(tool, {"dataset": DATASET, "analysis": "accounts-by-region"})
    data = _data(answer)
    (section,) = data["analysis"]
    assert section["chart"] == {"type": "bar", "x": "region", "y": "accounts"}
    (attached,) = data["attach"]
    assert data["chart_file"] == attached["filename"]
    page = Path(attached["path"]).read_text("utf-8")
    assert Path(attached["path"]).parent == layout.workspace_root / "bi-chat-charts"
    assert "各地區的客戶數" in page and "發佈版本 v1" in page
    # A search of cards is a table of the cards.
    with build_runtime(config, layout=layout) as runtime:
        (tool, _atlas) = bi_cards_tools(runtime.agent.gateway)
        cards = _call(tool, {"dataset": DATASET, "text": "Robotics"})
    found = _data(cards)
    assert found["cards"]
    assert Path(found["attach"][0]["path"]).name.startswith("bi-cards-")


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_a_bi_answer_shows_its_chart_inline_in_the_file_viewer(tmp_path: Path) -> None:
    """A real turn: the scripted model asks `bi__query`; the answer shows the
    chart page in the conversation's sandboxed frame, drawn with one bar per row."""
    import threading

    from integrations.browser import Browser
    from integrations.websocket import Devtools

    config, layout = _host(tmp_path)
    path = host_json(tmp_path, config)
    shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
    shots.mkdir(parents=True, exist_ok=True)
    with build_runtime(config, layout=layout) as runtime:
        web = AgentWeb(runtime, config_path=path)
        web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        browser = Browser(tmp_path / "browser", timeout_s=60)
        try:
            session = web.create_conversation()["conversation"]["session_id"]
            runtime.agent.gateway.router.model = _Scripted(
                {"tools": [(TOOL_NAME, {"dataset": DATASET, "analysis": "accounts-by-region"})]},
                {"text": "robotics 的客戶以 TW 最多（3 家）。"},
            )
            replied = web.conversation_turn(
                ConversationTurnRequest(session_id=session, message="robotics 客戶在哪些地區？")
            )
            (shown,) = [f for f in replied["answer"]["files"] if f["kind"] == "html"]
            assert shown["filename"].startswith("bi-accounts-by-region-")

            browser.start()
            browser.navigate(server.address)

            def wait(expression: str, seconds: float = 30) -> Any:
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    value = browser._evaluate(expression)
                    if value:
                        return value
                    time.sleep(0.2)
                raise AssertionError(expression)

            wait('!document.getElementById("send").disabled')
            browser._evaluate(f"loadConversations({json.dumps(session)})")
            wait("!!document.querySelector('.answer-html iframe')")
            frame = browser._evaluate(
                "(() => { const f = document.querySelector('.answer-html iframe');"
                " return {sandbox: f.getAttribute('sandbox'), src: f.getAttribute('src'),"
                " same: f.contentDocument !== null}; })()"
            )
            assert frame["sandbox"] == "allow-scripts" and frame["same"] is False
            assert frame["src"].startswith("/view/file?nonce=") and "token" not in frame["src"]

            def in_frame(expression: str) -> Any:
                for target in browser._targets():
                    if target.get("type") == "iframe" and "/view/file" in str(target.get("url")):
                        with Devtools(str(target["webSocketDebuggerUrl"]), timeout_s=30) as dev:
                            got = dev.call(
                                "Runtime.evaluate", expression=expression, returnByValue=True
                            )
                        return got.get("result", {}).get("value")
                tree = browser.page().call("Page.getFrameTree")
                children = tree["frameTree"].get("childFrames", [])
                if not children:
                    return None
                world = browser.page().call(
                    "Page.createIsolatedWorld", frameId=children[0]["frame"]["id"]
                )
                got = browser.page().call(
                    "Runtime.evaluate",
                    expression=expression,
                    contextId=world["executionContextId"],
                    returnByValue=True,
                )
                return got.get("result", {}).get("value")

            deadline = time.monotonic() + 30
            drawn = None
            while time.monotonic() < deadline and not drawn:
                drawn = in_frame(
                    "(() => { const s = document.querySelector('svg.bi-chart');"
                    " return s ? {bars: s.querySelectorAll('rect.bar').length,"
                    " title: document.querySelector('h1').textContent,"
                    " label: s.getAttribute('aria-label')} : null; })()"
                )
                time.sleep(0.2)
            # robotics in v1: TW 3, DE 1, JP 1, US 1 (fixture vault).
            assert drawn == {
                "bars": 4,
                "title": "各地區的客戶數",
                "label": "accounts（依 region）",
            }
            time.sleep(0.3)
            browser.screenshot(shots / "answer-chart.png")
        finally:
            browser.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
