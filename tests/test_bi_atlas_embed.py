"""Atlas panels and dashboards framed in the general chat (BI E2-E5).

`docs/phases/BI_CHAT_EMBED_AND_PANEL_EDIT.md` §4, against Atlas's
`docs/AEP_EMBED_CONTRACT.md`: the model asks with a slug or a name, the Host builds
the path, the page asks whether Atlas can be framed and otherwise shows AEP's own
chart with a note. A stand-in Atlas on a loopback port answers like the contract.
All data is fictional.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from test_bi_chat_charts import DATASET, _browser_missing, _host
from test_chat_workflow_forms_telegram import _Scripted
from test_host_wiring import host_json

from capabilities.bi_cards.store import BiStoreError
from common.execution import RequestContext, TraceIdentifiers
from host_runtime import bi_atlas_embed, bi_atlas_import
from host_runtime.bi_cards_api import route
from host_runtime.bi_cards_tools import ATLAS_TOOL, TOOL_NAME
from host_runtime.conversations import ConversationTurnRequest
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from host_runtime.web_page import PAGE
from knowledge.repo import repository
from scripts import bi_feed_fixtures as fixtures
from scripts import check_atlas_dashboard_golden as drift

SLUG = "accounts-by-region"
GOLDEN = Path(__file__).resolve().parent / "fixtures" / "atlas_embed_golden"
EMBED_PAGE = """<!doctype html><title>stand-in</title><div data-embed-state="ready">Atlas</div>
<script>
const parent_ = location.ancestorOrigins[0];
window.parent.postMessage({type: "atlas-embed-size", height: 640}, parent_);
</script>"""
DOCUMENT = {
    "id": "d1",
    "panels": [
        {"id": "b", "layout": {"y": 4, "x": 0}, "datasource": {"id": "aep.bi.result"},
         "query": {"vault": fixtures.VAULT_ID, "slug": "tech-updates"}},
        {"id": "a", "layout": {"y": 0, "x": 0}, "datasource": {"id": "aep.bi.result"},
         "query": {"vault": fixtures.VAULT_ID, "slug": SLUG}},
        {"id": "a2", "layout": {"y": 8, "x": 0}, "datasource": {"id": "aep.bi.result"},
         "query": {"vault": fixtures.VAULT_ID, "slug": SLUG}},
        {"id": "c", "layout": {"y": 1, "x": 0}, "datasource": {"id": "other"}, "query": {}},
    ],
}  # fmt: skip


def _golden(name: str) -> dict[str, Any]:
    found: dict[str, Any] = json.loads((GOLDEN / name).read_text("utf-8"))
    return found


class _Atlas(ThreadingHTTPServer):
    head_status = 200
    seen: list[dict[str, Any]]


class _Handler(BaseHTTPRequestHandler):
    server: _Atlas

    def log_message(self, *_args: Any) -> None:
        pass

    def _answer(self, status: int, body: bytes, kind: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self) -> None:  # noqa: N802
        self.server.seen.append({"method": "HEAD", "path": self.path,
                                 "origin": self.headers.get("Origin")})  # fmt: skip
        self._answer(self.server.head_status, b"")

    def do_GET(self) -> None:  # noqa: N802
        self.server.seen.append({"method": "GET", "path": self.path,
                                 "referer": self.headers.get("Referer")})  # fmt: skip
        if self.path == "/dashboards":
            self._answer(200, json.dumps(["儀表板 one"]).encode("utf-8"))
        elif self.path.startswith("/dashboards/"):
            self._answer(200, json.dumps(DOCUMENT).encode("utf-8"))
        elif self.path.startswith("/embed/"):
            self._answer(200, EMBED_PAGE.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._answer(404, b"{}")


@pytest.fixture
def atlas(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Atlas]:
    server = _Atlas(("127.0.0.1", 0), _Handler)
    server.seen = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(bi_atlas_import, "DEFAULT_PORT", server.server_address[1])
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture
def web(tmp_path: Path) -> Iterator[AgentWeb]:
    config, layout = _host(tmp_path)
    path = host_json(tmp_path, config)
    with build_runtime(config, layout=layout) as runtime:
        agent_web = AgentWeb(runtime, config_path=path)
        agent_web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        yield agent_web


def _show(web: AgentWeb, arguments: dict[str, Any], channel: str = "local") -> Any:
    host_tools = web.runtime.agent.gateway.host_tools
    assert host_tools is not None
    tool = next(item for item in host_tools() if item.tool.name == ATLAS_TOOL)
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t1", request_id="r1", span_id="s1"),
        actor="engineer",
        namespace="engineering",
        channel=channel,
        message="show it",
        session_id="session-1",
    )

    async def run() -> Any:
        return await tool.handler(context, arguments)

    return asyncio.run(run())


def _turn(web: AgentWeb, *replies: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    session = web.create_conversation()["conversation"]["session_id"]
    web.runtime.agent.gateway.router.model = _Scripted(*replies)
    replied = web.conversation_turn(
        ConversationTurnRequest(session_id=session, message="給我看各地區的客戶")
    )
    return session, replied["answer"]


# -- the paths ---------------------------------------------------------------------------


def _route(path: str) -> dict[str, Any]:
    """A path read as the contract's parser reads it (URLSearchParams, one path segment)."""
    from urllib.parse import unquote

    parts = urlsplit(path)
    if parts.path == "/embed/panel":
        query = parse_qs(parts.query, keep_blank_values=True)
        assert all(len(values) == 1 for values in query.values())
        flat = {key: values[0] for key, values in query.items()}
        vault_id, slug = flat.pop("vault"), flat.pop("slug")
        return {"kind": "panel", "vault": vault_id, "slug": slug, "params": flat}
    segment = parts.path.removeprefix("/embed/dashboard/")
    assert "/" not in segment
    return {"kind": "dashboard", "name": unquote(segment)}


def _urls() -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = _golden("example-urls.json")["urls"]
    return examples


@pytest.mark.parametrize("example", _urls(), ids=lambda e: str(e["name"]))
def test_every_path_the_contract_accepts_is_one_we_can_build(example: dict[str, Any]) -> None:
    wanted = example["route"]
    if wanted["kind"] == "invalid":
        return
    assert _route(example["url"]) == wanted  # the test's reader agrees with Atlas's parser
    if wanted["kind"] == "dashboard":
        assert bi_atlas_embed.dashboard_path(wanted["name"]) == example["url"]
    else:
        built = bi_atlas_embed.panel_path(wanted["vault"], wanted["slug"], wanted["params"])
        assert _route(built) == wanted


def test_a_name_with_url_characters_stays_one_segment() -> None:
    path = bi_atlas_embed.dashboard_path("a/b?c#d")
    assert path == "/embed/dashboard/a%2Fb%3Fc%23d"
    assert _route(path) == {"kind": "dashboard", "name": "a/b?c#d"}


def test_the_contracts_decisions_match_how_the_page_asks() -> None:
    cases = {c["name"]: c for c in _golden("access-decisions.json")["cases"]}
    probe = cases["server-side availability probe"]
    assert probe["method"] == "HEAD" and probe["headers"] == {} and probe["status"] == 200
    # No Referer is refused cross-site: why the frame sets referrerpolicy="origin".
    refused = cases[
        "framed cross-site with no Referer (Agent Web's no-referrer, no iframe attribute)"
    ]
    assert refused["status"] == 403
    assert 'frame.setAttribute("referrerpolicy", "origin")' in PAGE
    headers = _golden("response-headers.json")
    assert "X-Frame-Options" not in headers["embed"]["headers"]
    assert headers["other"]["headers"]["X-Frame-Options"] == "DENY"


def test_the_drift_check_covers_the_embed_goldens(tmp_path: Path) -> None:
    atlas = tmp_path / "atlas"
    upstream = atlas / drift.EMBED_UPSTREAM
    upstream.mkdir(parents=True)
    for path in GOLDEN.glob("*.json"):
        shutil.copyfile(path, upstream / path.name)
    assert drift.check_embed(atlas) == 3
    (upstream / "example-urls.json").write_bytes(b"{}")
    with pytest.raises(drift.Drift, match="embed golden differs: example-urls.json"):
        drift.check_embed(atlas)


@pytest.mark.skipif(not os.environ.get("AEP_ATLAS_REPO"), reason="AEP_ATLAS_REPO not set")
def test_the_vendored_embed_goldens_match_the_atlas_checkout() -> None:
    assert drift.check_embed(Path(os.environ["AEP_ATLAS_REPO"])) == 3


@pytest.mark.parametrize("reserved", ["vault", "slug"])
def test_a_reserved_key_is_never_a_parameter(reserved: str) -> None:
    with pytest.raises(BiStoreError):
        bi_atlas_embed.panel_path("v", "s", {reserved: "x"})


def test_a_dashboards_panels_are_read_top_to_bottom_each_once() -> None:
    assert bi_atlas_embed.panels_of(DOCUMENT) == [
        (fixtures.VAULT_ID, SLUG),
        (fixtures.VAULT_ID, "tech-updates"),
    ]
    assert bi_atlas_embed.panels_of({"panels": "nope"}) == []
    mixed = Path(__file__).resolve().parent / "fixtures" / "atlas_dashboard_golden"
    document = json.loads((mixed / "dashboard-mixed.json").read_text("utf-8"))
    assert bi_atlas_embed.panels_of(document)  # the contract's own mixed dashboard
    assert bi_atlas_embed.panels_of(None) == []


# -- the probe ---------------------------------------------------------------------------


def test_the_probe_asks_without_origin_and_only_200_is_framable(
    atlas: _Atlas, tmp_path: Path
) -> None:
    port = atlas.server_address[1]
    assert route(tmp_path, "engineer", "GET", "/api/bi/atlas-embed", {"port": str(port)}, None)[
        1
    ] == {"ok": True, "port": port, "framable": True}
    assert atlas.seen == [{"method": "HEAD", "path": "/embed/panel", "origin": None}]
    atlas.head_status = 503  # the frontend is not built
    assert bi_atlas_embed.framable(port) is False


def test_nothing_listening_is_not_framable(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = server.server_address[1]
    server.server_close()
    assert bi_atlas_embed.framable(port) is False
    status, refused = route(tmp_path, "engineer", "GET", "/api/bi/atlas-embed", {"port": "x"}, None)
    assert status == 400 and refused["code"] == "atlas_port_invalid"


# -- the tool ----------------------------------------------------------------------------


def test_a_panel_is_built_by_the_host_with_its_chart_page(web: AgentWeb) -> None:
    outcome = _show(web, {"dataset": DATASET, "analysis": SLUG, "params": {"domain": "aidc"}})
    assert outcome.status == "succeeded", outcome
    embed = outcome.data["atlas_embed"]
    assert embed["kind"] == "panel" and embed["slug"] == SLUG
    # The enum's own spelling goes in the URL; what was not asked for keeps the feed's default.
    assert _route(embed["path"])["params"] == {"domain": "AIDC"}
    assert Path(embed["fallback"]).is_file()
    assert outcome.data["attach"][0]["path"] == embed["fallback"]
    assert outcome.data["rows"]  # the model states numbers from these


@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        ({"dataset": "demo", "analysis": SLUG}, "embed_not_a_vault"),
        ({"dataset": DATASET, "analysis": "no-such"}, "analysis_unknown"),
        ({"dataset": DATASET, "analysis": SLUG, "params": {"nope": "1"}}, "param_invalid"),
        ({"dataset": DATASET, "analysis": SLUG, "params": {"domain": "nowhere"}}, "param_invalid"),
    ],
)
def test_what_atlas_would_refuse_goes_back_to_the_model(
    web: AgentWeb, arguments: dict[str, Any], code: str
) -> None:
    outcome = _show(web, arguments)
    assert outcome.status == "failed" and outcome.failure.code == code


def test_a_model_given_url_goes_nowhere(web: AgentWeb) -> None:
    outcome = _show(web, {"dataset": DATASET, "analysis": SLUG, "url": "http://evil.example/"})
    assert "evil" not in json.dumps(outcome.data["atlas_embed"], ensure_ascii=False)
    assert outcome.data["atlas_embed"]["path"].startswith("/embed/panel?")


def test_telegram_is_told_to_use_the_query_tool(web: AgentWeb) -> None:
    outcome = _show(web, {"dataset": DATASET, "analysis": SLUG}, channel="telegram")
    assert outcome.status == "failed" and "bi__query" in outcome.failure.message


def test_dashboards_are_listed_and_a_named_one_gets_a_page(web: AgentWeb, atlas: _Atlas) -> None:
    assert _show(web, {}).data == {"dashboards": ["儀表板 one"]}
    unknown = _show(web, {"dashboard": "nope"})
    assert unknown.failure.code == "atlas_not_found" and "儀表板 one" in unknown.failure.message
    shown = _show(web, {"dashboard": "儀表板 one"})
    embed = shown.data["atlas_embed"]
    assert embed["kind"] == "dashboard"
    assert _route(embed["path"]) == {"kind": "dashboard", "name": "儀表板 one"}
    page = Path(embed["fallback"]).read_text("utf-8")
    assert "各地區的客戶數" in page  # the dashboard's own analyses, for when Atlas is down
    assert all(call["method"] == "GET" for call in atlas.seen)  # never written to


def test_atlas_down_tells_the_model_to_use_the_chart(
    web: AgentWeb, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = server.server_address[1]
    server.server_close()
    monkeypatch.setattr(bi_atlas_import, "DEFAULT_PORT", port)
    outcome = _show(web, {"dashboard": "x"})
    assert outcome.failure.code == "atlas_unreachable"
    assert "bi__query" in outcome.failure.message and "opening Atlas" in outcome.failure.message


# -- the answer --------------------------------------------------------------------------


def test_the_answer_stores_the_embed_and_keeps_its_page_once(web: AgentWeb) -> None:
    session, answer = _turn(
        web,
        {"tools": [(TOOL_NAME, {"dataset": DATASET, "analysis": SLUG}),
                   (ATLAS_TOOL, {"dataset": DATASET, "analysis": SLUG})]},
        {"text": "請看圖。"},
    )  # fmt: skip
    (embed,) = answer["atlas_embeds"]
    pages = [f for f in answer["files"] if f["kind"] == "html"]
    # bi__query's own page of the same analysis is left out: one chart, not two.
    assert [p["path"] for p in pages] == [embed["fallback"]]
    stored = web.conversations(session)["selected"]["messages"][-1]
    assert stored["atlas_embeds"][0]["path"] == embed["path"]
    assert embed["fallback"] in {item["path"] for item in stored["attachments"]}


def test_a_framed_panels_answer_cites_the_vault_and_version(web: AgentWeb) -> None:
    # Asking a vault (BI_VAULT_ASKING.md): an answer from a vault says which version it read.
    read = _show(web, {"dataset": DATASET, "analysis": SLUG}).data["vault"]
    line = repository.source_line(DATASET, read)
    _session, answer = _turn(
        web,
        {"tools": [(ATLAS_TOOL, {"dataset": DATASET, "analysis": SLUG})]},
        {"text": "TW 最多，3 家。"},
    )
    assert line in answer["answer"]


def test_an_ad_hoc_query_still_shows_its_chart(web: AgentWeb) -> None:
    _session, answer = _turn(
        web,
        {"tools": [(TOOL_NAME, {"dataset": DATASET, "analysis": SLUG})]},
        {"text": "好了。"},
    )
    assert "atlas_embeds" not in answer
    assert [f for f in answer["files"] if f["kind"] == "html"]


# -- in a real browser -------------------------------------------------------------------


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_frame_shows_atlas_and_falls_back_when_it_cannot(tmp_path: Path, atlas: _Atlas) -> None:
    from integrations.browser import Browser

    config, layout = _host(tmp_path)
    path = host_json(tmp_path, config)
    with build_runtime(config, layout=layout) as runtime:
        web = AgentWeb(runtime, config_path=path)
        web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        browser = Browser(tmp_path / "browser", timeout_s=60)
        try:
            session, _answer = _turn(
                web,
                {"tools": [(ATLAS_TOOL, {"dataset": DATASET, "analysis": SLUG})]},
                {"text": "請看圖。"},
            )
            port = atlas.server_address[1]
            origin = f"http://127.0.0.1:{port}"

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

            def load(preference: str) -> None:
                browser._evaluate(f"localStorage.setItem('bi-atlas-url', {json.dumps(preference)})")
                browser._evaluate(f"loadConversations({json.dumps(session)})")

            wait('!document.getElementById("send").disabled')
            load(origin)
            wait("!!document.querySelector('iframe[data-atlas-origin]')")
            frame = browser._evaluate(
                "(() => { const f = document.querySelector('iframe[data-atlas-origin]');"
                " return {sandbox: f.getAttribute('sandbox'), src: f.getAttribute('src'),"
                " referrer: f.getAttribute('referrerpolicy'), title: f.title}; })()"
            )
            assert frame["sandbox"] == "allow-scripts allow-same-origin"
            assert frame["referrer"] == "origin"
            assert frame["src"].startswith(f"{origin}/embed/panel?")
            assert _route(frame["src"].removeprefix(origin))["slug"] == SLUG
            assert frame["title"] == "各地區的客戶數"
            # The page's own chart stays out while Atlas is framed.
            assert not browser._evaluate("!!document.querySelector('.atlas-embed-note')")

            # Sized from the embed's message; another window's or origin's is ignored.
            wait("document.querySelector('iframe[data-atlas-origin]').parentNode.style.height"
                 " === '640px'")  # fmt: skip
            browser._evaluate("window.postMessage({type: 'atlas-embed-size', height: 900}, '*')")
            time.sleep(0.3)
            assert (
                browser._evaluate(
                    "document.querySelector('iframe[data-atlas-origin]').parentNode.style.height"
                )
                == "640px"
            )
            # The Referer Atlas identifies the parent by, despite the page's no-referrer:
            # only the origin, so Agent Web's token in its address never reaches Atlas.
            framed = [c for c in atlas.seen if c["path"].startswith("/embed/panel?")]
            parts = urlsplit(server.address)
            assert framed and framed[-1]["referer"] == f"{parts.scheme}://{parts.netloc}/"

            # Atlas's frontend is not built: AEP's chart, with the note.
            atlas.head_status = 503
            load(origin)
            wait("!!document.querySelector('.atlas-embed-note')")
            assert "完整版本" in browser._evaluate(
                "document.querySelector('.atlas-embed-note').textContent"
            )
            wait("!!document.querySelector('.answer-atlas .answer-html iframe')")
            assert (
                browser._evaluate(
                    "document.querySelector('.answer-atlas .answer-html iframe')"
                    ".getAttribute('sandbox')"
                )
                == "allow-scripts"
            )
            assert not browser._evaluate("!!document.querySelector('iframe[data-atlas-origin]')")

            # A dashboard none of whose panels this PC can read has no chart to fall back to
            # (an imported file's other vault), and the note does not promise one.
            assert "看到「別處的」" in browser._evaluate(
                "answerAtlasEmbed('s', {kind: 'dashboard', path: 'nope', title: '別處的'}, [])"
                ".textContent"
            )

            # An address that is not this PC is never framed.
            atlas.head_status = 200
            load("http://atlas.example:8127")
            wait("!!document.querySelector('.atlas-embed-note')")
            assert not browser._evaluate("!!document.querySelector('iframe[data-atlas-origin]')")
        finally:
            browser.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
