"""BI dataset sharing (slice 1) in the 「BI 卡片」 area, in a real browser.

The real Agent Web page and server behind the stub proxy of
`test_bi_cards_ui.py`, extended with the sharing routes: 發佈到 Shared Platform
(the team is the default, 全公司 needs a confirmation, the first version of a
name waits for review, a found secret names the card and field without the
value), the publish state in the dataset bar, 已訂閱的資料集 with its status
badges, 更新 and 取消訂閱, the dataset select's two groups, a subscribed
dataset opened read-only (banner; no import, edit, demo load or publish) and
one whose access was taken back (已停止更新（無權限）, still readable); dark
mode at 390 px. Screenshots in `.scratch/bi-share-ui/`.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any

import pytest
from test_bi_cards_ui import NOW, Stub, _demo_cards, _proxy
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from host_runtime.web_page import PAGE

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "bi-share-ui"
ROBOTICS = "engineering/robotics-bi"
OLD = "sales/old-bi"
WIRELESS = "wireless/customers"
SECRET = "hunter2-very-secret"


class ShareStub(Stub):
    """The BI contract plus publishing and subscriptions."""

    def __init__(self) -> None:
        super().__init__()
        self.cards.update(_demo_cards())
        self.last: dict[str, Any] | None = None
        self.next_publish: list[tuple[int, dict[str, Any]]] = []
        self.available = [
            {
                "name": WIRELESS,
                "version": "1.3.0",
                "description": "無線客戶",
                "owner": "team:wireless",
            }
        ]
        self.subs: dict[str, dict[str, Any]] = {
            ROBOTICS: {
                "name": ROBOTICS,
                "subscribed": True,
                "read_only": True,
                "version": "1.1.0",
                "published_by": "leo.chi",
                "published_at": NOW,
                "note": "十月更新",
                "status": "update_available",
                "status_text": "有新版本",
                "latest": "1.2.0",
                "latest_note": "加入 AIDC 客戶",
                "cards": 2,
                "updated": NOW,
            },
            OLD: {
                "name": OLD,
                "subscribed": True,
                "read_only": True,
                "version": "2.0.0",
                "published_by": "amy.lin",
                "published_at": NOW,
                "note": "",
                "status": "stopped_no_access",
                "status_text": "已停止更新（無權限）",
                "latest": None,
                "latest_note": "",
                "cards": 2,
                "updated": NOW,
            },
        }

    def handle(self, method: str, path: str, body: Any) -> tuple[int, dict[str, Any]]:
        url = urllib.parse.urlsplit(path)
        route, query = url.path, dict(urllib.parse.parse_qsl(url.query))
        if route == "/api/bi/datasets":
            self.calls.append((method, route, query))
            own = {"name": "demo", "cards": len(self.cards), "updated": NOW, "read_only": False}
            return 200, {"datasets": [own, *self.subs.values()]}
        if route == "/api/bi/subscriptions":
            self.calls.append((method, route, query))
            reply: dict[str, Any] = {
                "ok": True,
                "configured": True,
                "subscriptions": list(self.subs.values()),
            }
            if query.get("refresh") == "1":
                reply["connection"] = "answered"
                reply["available"] = [
                    item for item in self.available if item["name"] not in self.subs
                ]
            return 200, reply
        if route == "/api/bi/subscriptions/update":
            self.calls.append((method, route, body))
            sub = self.subs[body["dataset"]]
            sub.update(version=sub["latest"], latest=None, status="current", latest_note="")
            return 200, {"ok": True, "subscription": sub}
        if route == "/api/bi/subscriptions/subscribe":
            self.calls.append((method, route, body))
            offer = next(item for item in self.available if item["name"] == body["dataset"])
            sub = {
                **self.subs[ROBOTICS],
                "name": offer["name"],
                "version": offer["version"],
                "published_by": "kevin.wu",
                "status": "current",
                "latest": None,
            }
            self.subs[offer["name"]] = sub
            return 200, {"ok": True, "subscription": sub}
        if route == "/api/bi/subscriptions/unsubscribe":
            self.calls.append((method, route, body))
            self.subs.pop(body["dataset"])
            return 200, {"ok": True, "removed": body["dataset"], "deselected": True}
        if route == "/api/bi/publish/status":
            self.calls.append((method, route, query))
            return 200, {
                "ok": True,
                "dataset": query.get("dataset"),
                "last": self.last,
                "name": self.last["name"] if self.last else "engineering/demo",
                "cards": len(self.cards),
                "proposals": 1,
            }
        if route == "/api/bi/publish":
            self.calls.append((method, route, body))
            status, answer = self.next_publish.pop(0)
            if answer.get("ok"):
                self.last = {
                    "name": answer["name"],
                    "version": answer["version"],
                    "status": answer["status"],
                    "at": NOW,
                    "readers": body["readers"],
                    "note": body["note"],
                }
            return status, answer
        return super().handle(method, path, body)


def test_the_sharing_controls_are_in_the_bi_area() -> None:
    pane = PAGE.split('<div id="kn-pane-bi"', 1)[1].split('<div id="bi-view-dashboard"', 1)[0]
    for needle in (
        "發佈到 Shared Platform",
        'id="bi-publish-panel"',
        "版本說明（必填）",
        "我的團隊（預設）",
        "開放給全公司",
        "第一次發佈需要管理員審核",
        "已訂閱的資料集",
        'id="bi-ro"',
    ):
        assert needle in pane, needle
    # No public option: only the team or, confirmed, the whole platform.
    assert "public" not in pane.lower()
    assert "已停止更新（無權限）" in PAGE and "到 Shared Platform 選取資料集" in PAGE


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_bi_sharing_end_to_end_in_a_browser(served: Any, tmp_path: Path) -> None:  # noqa: F811
    from integrations.browser import Browser, BrowserError

    _web, server, _recorder, _ = served
    real = urllib.parse.urlsplit(server.address)
    stub = ShareStub()
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

    def wait(expression: str, seconds: float = 20) -> Any:
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

    def content(element_id: str) -> str:
        return str(run(f"document.getElementById('{element_id}').textContent"))

    def hidden(element_id: str) -> bool:
        return bool(run(f"document.getElementById('{element_id}').hidden"))

    def click(element_id: str) -> None:
        run(f"document.getElementById('{element_id}').click()")

    def click_in(scope: str, label: str) -> None:
        assert run(
            f"(() => {{ const b = [...document.querySelectorAll({json.dumps(scope)})]"
            f".find(n => n.textContent.trim() === {json.dumps(label)});"
            " if (!b) return false; b.click(); return true; })()"
        ), label

    def posted(route: str) -> list[Any]:
        return [body for method, r, body in stub.calls if method == "POST" and r == route]

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

    def small_buttons() -> str:
        return str(
            run(
                "[...document.querySelectorAll('#kn-pane-bi button, #kn-pane-bi .bi-check')]"
                ".filter(b => b.offsetParent && !b.classList.contains('bi-link')"
                " && b.getBoundingClientRect().height < 44)"
                ".map(b => b.textContent.trim()).join('|')"
            )
        )

    try:
        metrics(1366, 1000)
        browser.navigate(address)
        wait('!document.getElementById("send").disabled')
        run("window.confirm = () => true;")
        click("nav-knowledge")
        run("document.querySelector('#kn-tabs [data-kn=bi]').click()")
        wait("document.getElementById('bi-status-bar').hidden")
        wait("document.getElementById('bi-subs-count').textContent === '2'")

        # -- the dataset select: 我的資料集, then 已訂閱 -----------------------------------
        groups = json.loads(
            run(
                "JSON.stringify([...document.querySelectorAll('#bi-dataset optgroup')]"
                ".map(g => [g.label, [...g.children].map(o => o.value)]))"
            )
        )
        assert groups == [["我的資料集", ["demo"]], ["已訂閱", [ROBOTICS, OLD]]], groups
        assert "唯讀" in str(
            run("document.querySelector('#bi-dataset optgroup + optgroup').textContent")
        )
        assert hidden("bi-ro") and not hidden("bi-publish") and not hidden("bi-demo")
        assert content("bi-pub-state") == ""  # never published

        # -- 發佈: the team by default, the first-time review, what is shared ---------------
        click("bi-publish")
        wait("!document.getElementById('bi-publish-panel').hidden")
        assert run("document.getElementById('bi-publish').getAttribute('aria-expanded')") == (
            "true"
        )
        wait("document.getElementById('bi-pub-what').textContent.includes('1 筆不會分享')")
        assert "我的團隊" in content("bi-pub-team")
        assert not run("document.getElementById('bi-pub-org').checked")
        assert hidden("bi-pub-confirm-box")
        assert not hidden("bi-pub-first")
        assert "第一次發佈需要管理員審核" in content("bi-pub-first")
        what = content("bi-pub-what")
        assert "卡片 2 張" in what and "修改歷史" in what and "不含待審提議" in what
        wait("document.getElementById('bi-pub-name').value === 'engineering/demo'")
        assert not hidden("bi-pub-name-box")
        assert run("document.activeElement.id") == "bi-pub-note"
        shoot("publish-dialog")

        # A note is required; nothing is sent without one.
        click("bi-pub-go")
        wait("document.getElementById('bi-pub-err').textContent.includes('版本說明')")
        assert run("document.getElementById('bi-pub-note').getAttribute('aria-invalid')") == (
            "true"
        )
        # 全公司 needs its own confirmation.
        run("document.getElementById('bi-pub-note').value = '十月更新';")
        click("bi-pub-org")
        assert not hidden("bi-pub-confirm-box")
        assert "全公司" in content("bi-pub-team")
        click("bi-pub-go")
        wait("document.getElementById('bi-pub-err').textContent.includes('勾選確認')")
        assert posted("/api/bi/publish") == []
        shoot("publish-organization-confirm")

        # A secret in a field: named by card and field, the value never shown.
        click("bi-pub-org-confirm")
        stub.next_publish.append(
            (
                400,
                {
                    "ok": False,
                    "code": "secret_found",
                    "card": "WiFi7-MLO互通與吞吐量驗證",
                    "field": "備註",
                    "message": "卡片 WiFi7-MLO互通與吞吐量驗證 的欄位 備註 看起來含有秘密",
                },
            )
        )
        click("bi-pub-go")
        wait("document.getElementById('bi-pub-err').textContent.includes('備註')")
        problem = content("bi-pub-err")
        assert "WiFi7-MLO互通與吞吐量驗證" in problem and "密碼或 token" in problem
        assert SECRET not in str(run("document.body.innerText"))
        assert posted("/api/bi/publish")[-1] == {
            "dataset": "demo",
            "note": "十月更新",
            "readers": "organization",
            "confirm_organization": True,
            "name": "engineering/demo",
        }
        assert not hidden("bi-publish-panel")
        shoot("publish-secret")

        # Back to the team: the first version waits for an administrator.
        click("bi-pub-org")
        assert hidden("bi-pub-confirm-box")
        assert not run("document.getElementById('bi-pub-org-confirm').checked")
        stub.next_publish.append(
            (200, {"ok": True, "name": ROBOTICS, "version": "1.0.0", "status": "pending_review"})
        )
        click("bi-pub-go")
        wait("!document.getElementById('bi-pub-result').hidden")
        assert posted("/api/bi/publish")[-1] == {
            "dataset": "demo",
            "note": "十月更新",
            "readers": "team",
            "confirm_organization": False,
            "name": "engineering/demo",
        }
        assert hidden("bi-publish-panel")
        assert "待審核" in content("bi-pub-result")
        assert f"{ROBOTICS}@1.0.0" in content("bi-pub-result")
        wait("document.getElementById('bi-pub-state').textContent.includes('待審核')")
        shoot("publish-pending")

        # Approved later: the next version is published at once.
        stub.last = {
            "name": ROBOTICS,
            "version": "1.0.0",
            "status": "published",
            "at": NOW,
            "readers": "team",
            "note": "十月更新",
        }
        click("bi-publish")
        wait("document.getElementById('bi-pub-first').hidden")  # the reloaded state
        assert hidden("bi-pub-name-box")  # the name is kept after the first publish
        assert "上次 v1.0.0" in content("bi-pub-dataset")
        run("document.getElementById('bi-pub-note').value = '修正 AIDC 卡片';")
        stub.next_publish.append(
            (200, {"ok": True, "name": ROBOTICS, "version": "1.1.0", "status": "published"})
        )
        click("bi-pub-go")
        wait("document.getElementById('bi-pub-result').textContent.includes('已發佈')")
        assert f"{ROBOTICS}@1.1.0" in content("bi-pub-result")
        wait("document.getElementById('bi-pub-state').textContent.includes('已發佈 v1.1.0')")
        assert "我的團隊" in content("bi-pub-state")
        shoot("publish-published")
        click_in("#bi-pub-result button", "關閉")
        assert hidden("bi-pub-result")

        # A version superseded on the platform is explained.
        click("bi-publish")
        run("document.getElementById('bi-pub-note').value = '舊的那份';")
        stub.next_publish.append(
            (409, {"ok": False, "code": "version_superseded", "message": "version_superseded"})
        )
        click("bi-pub-go")
        wait("document.getElementById('bi-pub-err').textContent.includes('請先更新')")
        click("bi-pub-cancel")
        assert hidden("bi-publish-panel")

        # -- 已訂閱的資料集: badges, 更新 -----------------------------------------------------
        run("document.querySelector('#bi-subs > summary').click()")
        wait("document.getElementById('bi-subs').open")
        rows = json.loads(
            run(
                "JSON.stringify([...document.querySelectorAll('#bi-subs-list li[data-sub]')]"
                ".map(li => [li.dataset.sub, li.querySelector('.bi-badge').textContent,"
                " [...li.querySelectorAll('button')].map(b => b.textContent)]))"
            )
        )
        assert rows == [
            [ROBOTICS, "有新版本", ["開啟", "更新", "取消訂閱"]],
            [OLD, "已停止更新（無權限）", ["開啟", "取消訂閱"]],
        ], rows
        assert "最新 v1.2.0：加入 AIDC 客戶" in content("bi-subs-list")
        assert "leo.chi 發佈 · v1.1.0" in content("bi-subs-list")
        assert "到 Shared Platform 選取資料集" in content("bi-subs-how")
        shoot("subscriptions")
        click_in(f"#bi-subs-list li[data-sub='{ROBOTICS}'] button", "更新")
        wait("document.getElementById('bi-notice').textContent.includes('v1.2.0')")
        assert posted("/api/bi/subscriptions/update") == [{"dataset": ROBOTICS}]
        wait(
            f"document.querySelector(\"#bi-subs-list li[data-sub='{ROBOTICS}'] .bi-badge\")"
            ".textContent === '已是最新'"
        )

        # -- 瀏覽平台上的資料集 → 訂閱 -----------------------------------------------------------
        click("bi-subs-browse")
        wait(f"!!document.querySelector(\"#bi-subs-avail li[data-avail='{WIRELESS}']\")")
        assert "v1.3.0 · 無線客戶 · wireless" in content("bi-subs-avail")
        shoot("subscriptions-browse")
        click_in(f"#bi-subs-avail li[data-avail='{WIRELESS}'] button", "訂閱")
        wait("document.getElementById('bi-subs-count').textContent === '3'")
        assert posted("/api/bi/subscriptions/subscribe") == [{"dataset": WIRELESS}]
        assert "已訂閱「wireless/customers」v1.3.0" in content("bi-notice")

        # -- a subscribed dataset opens read-only ---------------------------------------------
        click_in(f"#bi-subs-list li[data-sub='{ROBOTICS}'] button", "開啟")
        wait(f"document.getElementById('bi-dataset').value === '{ROBOTICS}'")
        wait("!document.getElementById('bi-ro').hidden")
        assert content("bi-ro-title") == "唯讀：leo.chi 發佈的 v1.2.0"
        assert hidden("bi-demo") and hidden("bi-publish")
        assert run("document.querySelector('#bi-views [data-bi-view=import]').hidden")
        assert content("bi-pub-state") == ""
        wait("document.getElementById('bi-dash-sections').textContent.includes('6. 缺口')")
        run("document.querySelector('#bi-views [data-bi-view=cards]').click()")
        wait("document.querySelectorAll('#bi-cards .bi-card-row').length === 2")
        run("document.querySelector('#bi-cards .bi-card-row').click()")
        wait("document.querySelectorAll('#bi-detail-body .bi-field').length > 0")
        assert run(
            "[...document.querySelectorAll('#bi-detail-body button')]"
            ".every(b => b.textContent.trim() !== '編輯')"
        )
        shoot("read-only")

        # -- access taken back: still readable, marked as no longer updated -------------------
        run(
            f"{{ const s = document.getElementById('bi-dataset'); s.value = '{OLD}';"
            " s.dispatchEvent(new Event('change')); }"
        )
        wait("document.getElementById('bi-ro-title').textContent.includes('amy.lin')")
        assert content("bi-ro-title") == "唯讀：amy.lin 發佈的 v2.0.0"
        assert "已停止更新（無權限）" in content("bi-ro-note")
        assert run("document.getElementById('bi-ro').classList.contains('stopped')")
        wait("document.querySelectorAll('#bi-cards .bi-card-row').length === 2")
        shoot("stopped")

        # -- dark mode at 390 px --------------------------------------------------------------
        metrics(390, 844)
        scheme("dark")
        time.sleep(0.3)
        no_side_scroll()
        assert small_buttons() == "", small_buttons()
        run("document.getElementById('bi-ro').scrollIntoView()")
        shoot("stopped-dark-390")
        run(
            "{ const s = document.getElementById('bi-dataset'); s.value = 'demo';"
            " s.dispatchEvent(new Event('change')); }"
        )
        wait("!document.getElementById('bi-publish').hidden")
        assert hidden("bi-ro")
        assert not run("document.querySelector('#bi-views [data-bi-view=import]').hidden")
        click("bi-publish")
        wait("!document.getElementById('bi-publish-panel').hidden")
        click("bi-pub-org")
        no_side_scroll()
        assert small_buttons() == "", small_buttons()
        shoot("publish-dark-390")
        click("bi-pub-cancel")
        run("document.querySelector('#bi-subs').open = true")
        no_side_scroll()
        assert small_buttons() == "", small_buttons()
        shoot("subscriptions-dark-390")

        # -- 取消訂閱 asks first ---------------------------------------------------------------
        run("window.confirm = () => false;")
        click_in(f"#bi-subs-list li[data-sub='{OLD}'] button", "取消訂閱")
        time.sleep(0.3)
        assert posted("/api/bi/subscriptions/unsubscribe") == []
        run("window.confirm = () => true;")
        click_in(f"#bi-subs-list li[data-sub='{OLD}'] button", "取消訂閱")
        wait("document.getElementById('bi-subs-count').textContent === '2'")
        assert posted("/api/bi/subscriptions/unsubscribe") == [{"dataset": OLD}]
        assert "已取消訂閱" in content("bi-notice")
    finally:
        browser.close()
        proxy.shutdown()
        proxy.server_close()
