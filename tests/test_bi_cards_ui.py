"""The 「BI 卡片」 area of the Knowledge tab in a real browser (v1.3 Case A).

The real Agent Web page and server, behind a small proxy that answers the
`/api/bi/*` contract from a stub (the backend is built separately) and passes
every other request to the real server. Covered: the demo load refreshing the
counts; the Dashboard (gaps first, red flag badges, matrix, funnel, card links,
collapse, the domain switch); the 「在 Atlas 開啟」 button; the card browser
(filter, search, sources, links, following a link);
a correction note and a 409 `stale_edit`; loading and error states; dark mode at
390 px. Screenshots in `.scratch/bi-ui/`.
"""

from __future__ import annotations

import copy
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from host_runtime.web_page import PAGE

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "bi-ui"

SCHEMA = {
    "types": [
        {
            "name": "Application",
            "label": "應用",
            "fields": [
                {
                    "name": "name",
                    "label": "名稱",
                    "type": "str",
                    "class": "sourced",
                    "enum": None,
                    "link_to": None,
                    "list": False,
                },
                {
                    "name": "lifecycle",
                    "label": "生命週期",
                    "type": "enum",
                    "class": "sourced",
                    "enum": ["RD", "Certification", "Production"],
                    "link_to": None,
                    "list": False,
                },
                {
                    "name": "priority",
                    "label": "優先度",
                    "type": "int",
                    "class": "judgement",
                    "enum": None,
                    "link_to": None,
                    "list": False,
                },
                {
                    "name": "trends",
                    "label": "趨勢",
                    "type": "linklist",
                    "class": "sourced",
                    "enum": None,
                    "link_to": "Trend",
                    "list": True,
                },
            ],
        },
        {
            "name": "TestSolution",
            "label": "測試方案",
            "fields": [
                {
                    "name": "name",
                    "label": "名稱",
                    "type": "str",
                    "class": "sourced",
                    "enum": None,
                    "link_to": None,
                    "list": False,
                },
                {
                    "name": "applications",
                    "label": "應用",
                    "type": "linklist",
                    "class": "sourced",
                    "enum": None,
                    "link_to": "Application",
                    "list": True,
                },
            ],
        },
    ]
}

APP = "app-wifi7"
SOL = "ts-mlo"
NOW = "2026-10-21T05:00:00+00:00"


def _demo_cards() -> dict[str, dict[str, Any]]:
    return {
        APP: {
            "card": {
                "id": APP,
                "entity_type": "Application",
                "canonical_key": "WiFi7-MLO互通與吞吐量驗證",
                "name": "WiFi7-MLO互通與吞吐量驗證",
                "review_status": "assumed",
                "updated": NOW,
                "fields": 3,
                "version": 3,
                "domain": ["robotics", "wireless"],
            },
            "fields": [
                {
                    "field": "lifecycle",
                    "label": "生命週期",
                    "value": "Certification",
                    "class": "sourced",
                    "source": {
                        "kind": "import",
                        "ref": "application_sample.csv:3",
                        "at": NOW,
                        "by": "leo",
                    },
                    "history": 1,
                },
                {
                    "field": "priority",
                    "label": "優先度",
                    "value": 4,
                    "class": "judgement",
                    "source": {"kind": "human", "ref": "", "at": NOW, "by": "王經理"},
                    "history": 2,
                },
                {
                    "field": "domain",
                    "label": "領域",
                    "value": ["robotics", "wireless"],
                    "class": "sourced",
                    "source": {"kind": "demo", "ref": "", "at": NOW, "by": ""},
                    "history": 0,
                },
            ],
            "links": [
                {"field": "trends", "target_id": None, "target_key": "WiFi7普及", "missing": True},
            ],
            "proposals": [
                {
                    "field": "priority",
                    "value": 5,
                    "source": {
                        "kind": "import",
                        "ref": "application_sample.csv:3",
                        "at": NOW,
                        "by": "leo",
                    },
                },
            ],
            "history": [
                {
                    "field": "priority",
                    "old": 3,
                    "new": 4,
                    "source": {"kind": "human", "ref": "", "at": NOW, "by": "王經理"},
                    "at": NOW,
                    "by": "王經理",
                },
            ],
        },
        SOL: {
            "card": {
                "id": SOL,
                "entity_type": "TestSolution",
                "canonical_key": "MLO吞吐量方案",
                "name": "MLO 吞吐量方案",
                "review_status": "synthetic",
                "updated": NOW,
                "fields": 1,
                "version": 1,
                "domain": "robotics",
            },
            "fields": [
                {
                    "field": "applications",
                    "label": "應用",
                    "value": ["WiFi7-MLO互通與吞吐量驗證"],
                    "class": "sourced",
                    "source": {"kind": "demo", "ref": "", "at": NOW, "by": ""},
                    "history": 0,
                },
            ],
            "links": [
                {
                    "field": "applications",
                    "target_id": APP,
                    "target_key": "WiFi7-MLO互通與吞吐量驗證",
                    "missing": False,
                },
            ],
            "proposals": [],
            "history": [],
        },
    }


DASHBOARD = {
    "domain": "robotics",
    "sections": [
        {
            "id": "4",
            "title": "4. 節點 × 技術 矩陣",
            "kind": "matrix",
            "columns": ["節點", "WiFi-7", "5G"],
            "rows": [["L2", 2, 0], ["L3", 0, 1]],
            "flags": [],
            "note": "每格 = 客戶產品數",
        },
        {
            "id": "6",
            "title": "6. 缺口：Application × 我方方案 / 對手方案",
            "kind": "table",
            "columns": ["應用", "我方方案", "對手方案"],
            "rows": [
                [f"[[card:{APP}|WiFi7-MLO互通與吞吐量驗證]]", "", "Keysight"],
                [{"card_id": SOL, "label": "MLO 吞吐量方案"}, "有", "—"],
            ],
            "flags": [{"row": 0, "level": "red", "text": "對手有、我方無"}],
            "note": "紅色 = 對手有方案而我方沒有",
        },
        {
            "id": "17",
            "title": "17. 商機漏斗",
            "kind": "funnel",
            "columns": ["階段", "筆數", "商機"],
            "rows": [
                ["探索", 5, [{"card_id": SOL, "label": "MLO 吞吐量方案"}]],
                ["評估", 3, []],
                ["提案", 1, []],
            ],
            "flags": [],
            "note": "",
        },
        {
            "id": "8",
            "title": "8. 資料過期提醒",
            "kind": "table",
            "columns": ["卡片", "更新"],
            "rows": [["Trend A", "2026-06-01"]],
            "flags": [{"row": 0, "level": "warn", "text": "超過 90 天未更新"}],
            "note": "",
        },
    ],
}


class Stub:
    """The `/api/bi/*` contract, recording every call."""

    def __init__(self) -> None:
        self.cards: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple[str, str, Any]] = []
        self.fail: set[str] = set()
        self.hold: dict[str, threading.Event] = {}
        self.imported: str | None = None

    def handle(self, method: str, path: str, body: Any) -> tuple[int, dict[str, Any]]:
        url = urllib.parse.urlsplit(path)
        route, query = url.path, dict(urllib.parse.parse_qsl(url.query))
        self.calls.append((method, route, body if body is not None else query))
        gate = self.hold.get(route)
        if gate is not None:
            gate.wait(30)
        if route in self.fail:
            return 500, {"ok": False, "code": "test_failure", "message": "測試用的失敗"}
        if route == "/api/bi/schema":
            return 200, SCHEMA
        if route == "/api/bi/datasets":
            count = len(self.cards)
            return 200, {
                "datasets": [{"name": "demo", "cards": count, "updated": NOW if count else None}]
            }
        if route == "/api/bi/demo/load":
            created = 0 if self.cards else 2
            self.cards.update(_demo_cards())
            return 200, {
                "ok": True,
                "imported": {"created": created, "updated": 0, "unchanged": 2 - created},
            }
        if route == "/api/bi/dashboard":
            answer: dict[str, Any] = copy.deepcopy(DASHBOARD)
            answer["domain"] = query.get("domain")
            if query.get("domain") == "aidc":
                answer["sections"] = []
            return 200, answer
        if route == "/api/bi/import/preview":
            return 200, self.preview()
        if route == "/api/bi/import/apply":
            self.imported = "imp-1"
            new = copy.deepcopy(_demo_cards()[SOL])
            new["card"].update(id="ts-new", name="衛星直連通道模擬方案", canonical_key="NTN方案")
            self.cards["ts-new"] = new
            return 200, {
                "ok": True,
                "import_id": "imp-1",
                "applied": {"created": 1, "updated": 1, "unchanged": 0, "proposals": 1},
            }
        if route == "/api/bi/import/undo":
            self.cards.pop("ts-new", None)
            return 200, {"ok": True}
        if route == "/api/bi/cards":
            found = [item["card"] for item in self.cards.values()]
            if query.get("type"):
                found = [card for card in found if card["entity_type"] == query["type"]]
            if query.get("q"):
                found = [card for card in found if query["q"] in card["name"]]
            return 200, {
                "cards": [{k: v for k, v in card.items() if k != "version"} for card in found]
            }
        parts = route.split("/")
        if len(parts) >= 5 and parts[3] == "cards":
            item = self.cards.get(urllib.parse.unquote(parts[4]))
            if item is None:
                return 404, {"ok": False, "code": "not_found", "message": "沒有這張卡片"}
            if len(parts) == 6 and parts[5] == "history":
                return 200, {"history": item["history"]}
            return 200, {k: item[k] for k in ("card", "fields", "links", "proposals")}
        if route in ("/api/bi/corrections/preview", "/api/bi/corrections/apply"):
            preview = route.endswith("preview")
            given = body if preview else json.loads(body["text"])
            item = self.cards[given["card"]]
            card = item["card"]
            if body["base_version"] != card["version"]:
                return 409, {
                    "ok": False,
                    "code": "stale_edit",
                    "current": 5,
                    "by": "陳主任",
                    "at": NOW,
                }
            entry = next(e for e in item["fields"] if e["field"] == given["field"])
            same = entry["value"] == given["value"]
            if preview:
                return 200, {
                    "ok": True,
                    "field": given["field"],
                    "label": entry.get("label"),
                    "current": entry["value"],
                    "value": given["value"],
                    "unchanged": same,
                    "base_version": body["base_version"],
                    "folder": "library/corrections/sources",
                    "text": json.dumps(given),
                }
            if same:
                # The value it already has: no change (owner 2026-10-24).
                return 200, {"ok": True, "version": card["version"], "unchanged": True}
            card["version"] += 1
            entry["value"] = given["value"]
            entry["source"] = {"kind": "human", "ref": "", "at": NOW, "by": "你"}
            return 200, {"ok": True, "version": card["version"]}
        return 404, {"ok": False, "code": "not_found", "message": route}

    def preview(self) -> dict[str, Any]:
        return {
            "preview_id": "pv-1",
            "entity_type": "Application",
            "columns": [
                {"source": "應用名稱", "field": "name", "status": "mapped", "note": ""},
                {
                    "source": "生命週期",
                    "field": "lifecycle",
                    "status": "alias",
                    "note": "「研發」→ RD",
                },
                {
                    "source": "優先度",
                    "field": None,
                    "status": "ignored",
                    "note": "判斷欄位，分 market、分期間設定，不從 CSV 匯入",
                },
                {
                    "source": "備註2",
                    "field": None,
                    "status": "unknown",
                    "note": "schema 沒有這個欄位",
                },
            ],
            "rows": [
                {
                    "row": 2,
                    "canonical_key": "衛星直連-通道模擬驗證",
                    "action": "create",
                    "fields": [
                        {
                            "field": "lifecycle",
                            "raw": "研發",
                            "normalized": "RD",
                            "current": None,
                            "change": "add",
                        }
                    ],
                    "warnings": [],
                },
                {
                    "row": 3,
                    "canonical_key": "WiFi7-MLO互通與吞吐量驗證",
                    "action": "update",
                    "fields": [
                        {
                            "field": "lifecycle",
                            "raw": "認證",
                            "normalized": "Certification",
                            "current": "RD",
                            "change": "change",
                        },
                        {
                            "field": "priority",
                            "raw": "5",
                            "normalized": 5,
                            "current": 4,
                            "change": "human_kept",
                        },
                    ],
                    "warnings": [{"code": "missing_target", "message": "找不到趨勢「WiFi7普及」"}],
                },
                {
                    "row": 4,
                    "canonical_key": "5G-FR2-AiP-OTA驗證",
                    "action": "unchanged",
                    "fields": [],
                    "warnings": [],
                },
                {
                    "row": 5,
                    "canonical_key": "",
                    "action": "skip",
                    "fields": [],
                    "warnings": [{"code": "missing_name", "message": "缺少應用名稱"}],
                },
            ],
            "summary": {"create": 1, "update": 1, "unchanged": 1, "skip": 1, "warnings": 2},
        }


def _proxy(stub: Stub, upstream: str) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            pass

        def _answer(self, status: int, body: bytes, kind: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve(self, method: str) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            if self.path.startswith("/api/bi/"):
                status, answer = stub.handle(method, self.path, json.loads(raw) if raw else None)
                self._answer(status, json.dumps(answer).encode(), "application/json")
                return
            headers = {
                k: v
                for k, v in self.headers.items()
                if k.lower() in ("authorization", "content-type", "accept")
            }
            request = urllib.request.Request(
                upstream + self.path, data=raw or None, headers=headers, method=method
            )
            try:
                with urllib.request.urlopen(request, timeout=60) as reply:
                    self._answer(
                        reply.status, reply.read(), reply.headers.get("Content-Type", "text/plain")
                    )
            except urllib.error.HTTPError as failure:
                self._answer(
                    failure.code, failure.read(), failure.headers.get("Content-Type", "text/plain")
                )

        def do_GET(self) -> None:  # noqa: N802 - the http.server interface
            self._serve("GET")

        def do_POST(self) -> None:  # noqa: N802 - the http.server interface
            self._serve("POST")

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


def test_the_bi_area_is_a_knowledge_sub_tab_with_every_pane_status() -> None:
    knowledge = PAGE.split('<section id="panel-knowledge"', 1)[1].split(
        "</section>\n  <section", 1
    )[0]
    assert 'id="kn-tabs"' in knowledge and 'data-kn="bi"' in knowledge
    for status in ("bar", "dash", "cards", "detail", "build"):
        assert f'id="bi-status-{status}"' in knowledge, status
    # The 2026-10-21 CSV import tab is gone: 「建立與匯入」 covers CSV (BI_VAULT.md §7.1).
    assert 'data-bi-view="import"' not in knowledge and "匯入 CSV" not in knowledge
    assert 'id="bi-atlas-open"' in knowledge
    assert "載入示範資料" in knowledge and "確認寫入" in knowledge
    assert "哪些測試方案對應 WiFi 7？" in knowledge and "[卡片 …]" in knowledge
    assert "人工值保留，改成提議" in PAGE and "stale_edit" in PAGE


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_bi_cards_end_to_end_in_a_browser(served: Any, tmp_path: Path) -> None:  # noqa: F811
    from integrations.browser import Browser, BrowserError

    _web, server, _recorder, _ = served
    real = urllib.parse.urlsplit(server.address)
    stub = Stub()
    proxy = _proxy(stub, f"{real.scheme}://{real.netloc}")
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    address = f"http://127.0.0.1:{proxy.server_address[1]}/?{real.query}"
    shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
    shots.mkdir(parents=True, exist_ok=True)
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()

    def run(expression: str) -> Any:
        return browser._evaluate(expression)

    # 60 s, the same as the Browser's own timeout: under full-suite CPU load
    # 20 s was too short for a render that is correct, just late (issue 248).
    def wait(expression: str, seconds: float = 60) -> Any:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                value = run(expression)
            except BrowserError:  # an element not rendered yet
                value = None
            if value:
                return value
            time.sleep(0.1)
        raise AssertionError(expression)

    def shown(element_id: str) -> str:
        return str(
            run(
                f"(() => {{ const n = document.getElementById('{element_id}');"
                " return n && !n.hidden ? n.textContent : ''; })()"
            )
        )

    def click_text(scope: str, label: str) -> None:
        assert run(
            f"(() => {{ const b = [...document.querySelectorAll({json.dumps(scope)})]"
            f".find(n => n.textContent.trim() === {json.dumps(label)});"
            " if (!b) return false; b.click(); return true; })()"
        ), label

    def open_priority_editor() -> None:
        # Saving a field re-renders the card: the detail body is emptied and
        # refilled after the notice has already appeared, so a click made as
        # soon as the notice shows can land on an empty body. Wait for the
        # editor button to be back (issue 248).
        wait("!!document.querySelector('[data-field=priority] .bi-field-foot button')")
        run("document.querySelector('[data-field=priority] .bi-field-foot button').click()")

    def click_section(section: str) -> None:
        # The Dashboard is emptied and refilled by any reload that overlaps
        # this one. Find the summary and click it in the same step, retried
        # until it is there, so no reload can come between the two (issue 248).
        selector = json.dumps(f"#bi-dash-sections details[data-section='{section}'] summary")
        wait(
            f"(() => {{ const s = document.querySelector({selector}); if (!s) return false;"
            " s.click(); return true; })()"
        )

    def routes() -> list[str]:
        return [route for _method, route, _body in stub.calls]

    def metrics(width: int, height: int) -> None:
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=width,
            height=height,
            deviceScaleFactor=1,
            mobile=width < 600,
        )

    def scheme(value: str) -> None:
        browser.page().call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": value}],
        )

    def shoot(name: str) -> None:
        time.sleep(0.25)
        browser.screenshot(shots / f"{name}.png")

    def no_side_scroll() -> None:
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )

    try:
        metrics(1366, 1000)
        browser.navigate(address)
        wait('!document.getElementById("send").disabled')
        run("window.confirm = () => true;")
        run("document.getElementById('nav-knowledge').click()")
        # -- loading, then an error with 重試 ----------------------------------------------
        stub.hold["/api/bi/datasets"] = threading.Event()
        run("document.querySelector('#kn-tabs [data-kn=bi]').click()")
        wait("document.getElementById('bi-status-bar').textContent.includes('載入中…')")
        assert run("document.getElementById('kn-pane-bi').getAttribute('aria-busy')") == "true"
        assert run("document.getElementById('kn-pane-pipeline').hidden")
        shoot("loading")
        stub.fail.add("/api/bi/datasets")
        stub.hold.pop("/api/bi/datasets").set()
        wait("document.getElementById('bi-status-bar').textContent.includes('測試用的失敗')")
        assert run("document.getElementById('boot-error').hidden")
        shoot("load-error")
        stub.fail.clear()
        click_text("#bi-status-bar button", "重試")
        wait("document.getElementById('bi-status-bar').hidden")
        # The page opens on 「建立與匯入」; this test starts on the Dashboard.
        run("document.querySelector('#bi-views [data-bi-view=dashboard]').click()")
        assert "0張卡片" in shown("bi-counts").replace(" ", "")
        wait("document.getElementById('bi-dash-sections').textContent.includes('6. 缺口')")
        # -- demo load refreshes the counts ----------------------------------------------
        run("document.getElementById('bi-demo').click()")
        wait("document.getElementById('bi-counts').textContent.startsWith('2')")
        assert "示範資料已載入" in shown("bi-notice")
        assert ("POST", "/api/bi/demo/load", {"dataset": "demo"}) in stub.calls
        # -- Dashboard: gaps first, flags, matrix, funnel, collapse --------------------------
        # Wait for the whole state, not only the count: a reload that overlaps
        # this one empties the sections for a moment (issue 248).
        order_js = (
            "JSON.stringify([...document.querySelectorAll('#bi-dash-sections details')]"
            ".map(d => [d.dataset.section, d.open]))"
        )
        expected_order = [["6", True], ["4", False], ["17", False], ["8", False]]
        wait(f"{order_js} === JSON.stringify({json.dumps(expected_order)})")
        order = run(order_js)
        assert json.loads(order) == expected_order
        stats_js = (
            "[...document.querySelectorAll('#bi-dash-summary .bi-stat b')]"
            ".map(b => b.textContent).join(',')"
        )
        wait(f"({stats_js}) === '1,1,1'")
        stats = run(stats_js)
        assert stats == "1,1,1", stats
        flagged = "#bi-dash-sections details[data-section='6'] tr.bi-flag-red"
        # Each check below is a condition the Dashboard must reach, waited for
        # in one step so a reload in progress cannot empty it between the read
        # and the assertion (issue 248).
        wait(
            f"document.querySelector({json.dumps(flagged)})?.textContent.includes('對手有、我方無')"
        )
        wait(f"!!document.querySelector({json.dumps(flagged + ' .bi-badge.bad')})")
        click_section("4")
        wait("document.querySelectorAll('.bi-matrix td.bi-zero').length === 2")
        click_section("17")
        wait("document.querySelectorAll('.bi-funnel-row').length === 3")
        wait(
            "document.querySelector('.bi-funnel-items .bi-link')?.textContent === 'MLO 吞吐量方案'"
        )
        shoot("dashboard-light")
        click_section("6")
        wait(
            "document.querySelector(\"#bi-dash-sections details[data-section='6']\")"
            "?.open === false"
        )
        click_section("6")
        # the domain switch queries again
        before = len(stub.calls)
        run(
            "{ const d = document.getElementById('bi-domain'); d.value = 'aidc';"
            " d.dispatchEvent(new Event('change')); }"
        )
        wait("document.getElementById('bi-dash-sections').textContent.includes('還沒有卡片')")
        asked = [body for _m, route, body in stub.calls[before:] if route == "/api/bi/dashboard"]
        assert asked and asked[-1]["domain"] == "aidc"
        run(
            "{ const d = document.getElementById('bi-domain'); d.value = 'robotics';"
            " d.dispatchEvent(new Event('change')); }"
        )
        wait("document.querySelectorAll('#bi-dash-sections details').length === 4")
        # a card link opens the card detail
        click_text("#bi-dash-sections .bi-link", "WiFi7-MLO互通與吞吐量驗證")
        wait("!document.getElementById('bi-view-cards').hidden")
        wait(
            "document.getElementById('bi-detail-title')"
            " && (document.getElementById('bi-detail-title')?.textContent || '').includes('WiFi7')"
        )
        cards_query = [body for _m, route, body in stub.calls if route == "/api/bi/cards"][-1]
        assert cards_query["domain"] == "robotics"
        # -- card detail: classes, sources, links, proposals, history ------------------------
        detail = "document.getElementById('bi-detail-body').textContent"
        wait(f"{detail}.includes('王經理')")
        text = str(run(detail))
        for expected in (
            "範例資料／待驗證",
            "事實",
            "判斷",
            "人工",
            "匯入 application_sample.csv:3",
            "示範資料",
            "找不到目標卡片",
            "待審提議（1）",
            "領域：robotics、wireless",
        ):
            assert expected in text, expected
        wait("document.getElementById('bi-history').textContent.includes('3→4')")
        shoot("card-detail")
        # filter and search
        run(
            "{ const t = document.getElementById('bi-type'); t.value = 'TestSolution';"
            " t.dispatchEvent(new Event('change')); }"
        )
        wait("document.querySelectorAll('#bi-cards [data-card]').length === 1")
        assert "草稿／虛構" in str(run("document.getElementById('bi-cards').textContent"))
        run(
            "{ const t = document.getElementById('bi-type'); t.value = '';"
            " t.dispatchEvent(new Event('change')); }"
        )
        wait("document.querySelectorAll('#bi-cards [data-card]').length === 2")
        run(
            "{ const q = document.getElementById('bi-q'); q.value = 'MLO 吞吐';"
            " q.dispatchEvent(new Event('input')); }"
        )
        wait("document.querySelectorAll('#bi-cards [data-card]').length === 1")
        run(f"document.querySelector('#bi-cards [data-card={SOL}]').click()")
        wait(
            "(document.getElementById('bi-detail-title')?.textContent || '')"
            ".includes('MLO 吞吐量方案')"
        )
        # following a link opens the target card
        click_text("#bi-detail-body .bi-link", "WiFi7-MLO互通與吞吐量驗證")
        wait("(document.getElementById('bi-detail-title')?.textContent || '').includes('WiFi7')")
        wait(f"{detail}.includes('王經理')")
        # -- correction note: success, then a stale one ------------------------------------
        open_priority_editor()
        run(
            "document.getElementById('bi-edit-priority').value = '3';"
            "document.getElementById('bi-reason-priority').value = '依 Q4 訊號調整';"
        )
        run("document.querySelector('[data-field=priority] form button[type=submit]').click()")
        # Nothing is written until the person has seen the difference and confirmed.
        confirm = "[data-field=priority] [data-note-confirm=true]"
        wait(f"!!document.querySelector('{confirm}')")
        review = str(
            run("document.querySelector('[data-field=priority] .bi-note-review').textContent")
        )
        assert "→「3」" in review
        assert not [route for _m, route, _b in stub.calls if route.endswith("/apply")]
        run(f"document.querySelector('{confirm}').click()")
        wait("document.getElementById('bi-notice').textContent.includes('版本 4')")
        note = [body for _m, route, body in stub.calls if route.endswith("corrections/preview")][-1]
        assert note == {
            "dataset": "demo",
            "card": APP,
            "field": "priority",
            "value": 3,
            "base_version": 3,
            "reason": "依 Q4 訊號調整",
            "author": "",
        }
        wait("document.querySelector('[data-field=priority] .bi-field-value').textContent === '3'")
        # the same value again is no change: no new version (owner 2026-10-24)
        open_priority_editor()
        run(
            "document.getElementById('bi-edit-priority').value = '3';"
            "document.getElementById('bi-reason-priority').value = '再存一次';"
        )
        run("document.querySelector('[data-field=priority] form button[type=submit]').click()")
        wait(f"!!document.querySelector('{confirm}')")
        run(f"document.querySelector('{confirm}').click()")
        wait("document.getElementById('bi-notice').textContent.includes('沒有變更')")
        notice = str(run("document.getElementById('bi-notice').textContent"))
        assert "版本 4" in notice and "已儲存" not in notice
        assert stub.cards[APP]["card"]["version"] == 4
        # The card reloads after a no-change save; wait for that reload to
        # show version 4, or it could read the version changed below (issue 248).
        wait(f"{detail}.includes('版本 4')")
        stub.cards[APP]["card"]["version"] = 9  # someone else saved meanwhile
        open_priority_editor()
        run(
            "document.getElementById('bi-edit-priority').value = '2';"
            "document.getElementById('bi-reason-priority').value = '測試';"
        )
        run("document.querySelector('[data-field=priority] form button[type=submit]').click()")
        wait("!!document.querySelector('[data-stale=true]')")
        stale = str(run("document.querySelector('[data-stale=true]').textContent"))
        assert "陳主任" in stale and "「5」" in stale and "重新載入卡片" in stale
        run("document.querySelector('[data-field=priority]').scrollIntoView({block: 'start'})")
        shoot("stale-edit")
        click_text("[data-stale=true] button", "重新載入卡片")
        wait(
            "!document.querySelector('[data-stale=true]')"
            " && document.getElementById('bi-detail-title') !== null"
        )
        # -- 在 Atlas 開啟: a stopped Atlas is named, no dead tab ------------------------------
        run("document.querySelector('#bi-views [data-bi-view=dashboard]').click()")
        run("document.getElementById('bi-atlas-set').open = true")
        run(
            "{ const u = document.getElementById('bi-atlas-url'); u.value = 'http://127.0.0.1:9';"
            " document.getElementById('bi-atlas-save').click(); }"
        )
        assert "http://127.0.0.1:9" in shown("bi-atlas-state")
        run("document.getElementById('bi-atlas-open').click()")
        wait("document.getElementById('bi-atlas-state').textContent.includes('Atlas 沒有回應')")
        run(
            "localStorage.removeItem('bi-atlas-url');"
            " document.getElementById('bi-atlas-set').open = false"
        )
        # -- a failing card list shows inline with 重試 ----------------------------------------
        run("document.querySelector('#bi-views [data-bi-view=cards]').click()")
        stub.fail.add("/api/bi/cards")
        run("document.getElementById('bi-refresh').click()")  # 更新 reloads the list
        wait("document.getElementById('bi-status-cards').textContent.includes('測試用的失敗')")
        stub.fail.clear()
        click_text("#bi-status-cards button", "重試")
        wait("document.getElementById('bi-status-cards').hidden")
        # -- dark mode at 390 px ----------------------------------------------------------
        scheme("dark")
        metrics(390, 844)
        run("document.querySelector('#bi-views [data-bi-view=dashboard]').click()")
        run("window.scrollTo(0, 0)")
        no_side_scroll()
        run("document.getElementById('bi-dash-summary').scrollIntoView({block: 'start'})")
        shoot("dashboard-dark-390")
        run(
            "document.querySelector(\"#bi-dash-sections details[data-section='4']\")"
            ".scrollIntoView({block: 'start'})"
        )
        no_side_scroll()
        shoot("matrix-dark-390")
        run(
            "{ const q = document.getElementById('bi-q'); q.value = '';"
            " q.dispatchEvent(new Event('input')); }"
        )
        run("document.querySelector('#bi-views [data-bi-view=cards]').click()")
        wait(f"!!document.querySelector('#bi-cards [data-card={APP}]')")
        run(f"document.querySelector('#bi-cards [data-card={APP}]').click()")
        wait(f"{detail}.includes('王經理')")
        no_side_scroll()
        shoot("card-dark-390")
        small = run(
            "[...document.querySelectorAll('#kn-pane-bi button')].filter(b => b.offsetParent"
            " && !b.classList.contains('bi-link') && b.getBoundingClientRect().height < 44)"
            ".map(b => b.textContent.trim()).join('|')"
        )
        assert small == "", small
        scheme("light")
    finally:
        browser.close()
        browser.discard_profile()
        proxy.shutdown()
        proxy.server_close()
        thread.join(timeout=5)
