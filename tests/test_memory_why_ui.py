"""「為什麼」 and the health cards in a real browser (accumulated memory M5).

The real Agent Web server and page and a headless browser when one is
installed: an answer that used memory shows a small 「為什麼？」; it lists the
preference, contact, note and sync state the answer used, each linking to the
memory page where it can be edited or deleted. The health check's findings
are cards of their own type in 待確認, and its settings are in 紀錄.
Screenshots in `.scratch/memory-why/`.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from capabilities.business_cards.manifest import business_cards_skill
from capabilities.business_cards.space import CONTACTS_ORG
from host_runtime.conversations import ConversationMessage, ConversationRecord
from host_runtime.web import AgentWeb

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "memory-why"
SCOPE = "skill:engineering/business-cards"
COMPANY = "範例科技股份有限公司"


def _seed(web: AgentWeb) -> dict[str, Any]:
    layout = web.runtime.layout
    layout.skills.mkdir(parents=True, exist_ok=True)
    (layout.skills / "engineering__business-cards__1.0.0.json").write_text(
        business_cards_skill().model_dump_json(), encoding="utf-8"
    )
    actor = web.runtime.actor
    store = web.memory_page.cards()

    def add(name: str, when: date, **values: str) -> str:
        fields = {"name": name, "company": COMPANY, "title": "經理", **values}
        return store.add(
            fields, source="card", source_date=when, source_ref="", uncertain=(), actor="seed"
        ).person_id

    person = add("王小明", date(2026, 9, 1), email="hm@a.example", department="射頻部")
    add("王小明", date(2026, 9, 2), email="hm@b.example", department="業務部")
    rule, _ = web.personal_memory.preferences(actor).save(
        SCOPE, "組織圖不用問是否含離職", actor=f"{actor} via web", scope_label="名片／組織圖"
    )
    note, _ = web.personal_memory.notes(actor).save(
        "WNC 的 RF 主管是王小明", actor=f"{actor} via web", source_kind="answer"
    )
    web.memory_page.service().owned(CONTACTS_ORG).advance_sync(
        "mail:Inbox",
        "wnc.com.tw",
        last_message_date="2026-10-19T08:00:00+00:00",
        message_ids=["m-1"],
        extractor_version="sig-3",
        actor=f"{actor} via web",
    )
    now = datetime.now(UTC)
    web.runtime.state.create_conversation(
        ConversationRecord(
            session_id="why-1",
            actor=actor,
            title="WNC 組織圖",
            created_at=now,
            updated_at=now + timedelta(seconds=2),
            messages=(
                ConversationMessage(
                    message_id="why-q",
                    role="user",
                    text="WNC 組織圖",
                    created_at=now,
                    status="submitted",
                ),
                ConversationMessage(
                    message_id="why-a",
                    role="assistant",
                    text="## WNC\n\nRF 主管是王小明。",
                    created_at=now + timedelta(seconds=1),
                    status="answered",
                    preferences_used=(rule.preference_id,),
                    memory_used=(
                        f"contacts/org:person:{person}",
                        f"personal/notes:note:{note.note_id}",
                        "contacts/org:sync:wnc.com.tw",
                    ),
                ),
                ConversationMessage(
                    message_id="why-q2",
                    role="user",
                    text="謝謝",
                    created_at=now + timedelta(seconds=2),
                    status="submitted",
                ),
                ConversationMessage(
                    message_id="why-a2",
                    role="assistant",
                    text="不客氣。",
                    created_at=now + timedelta(seconds=2),
                    status="answered",
                ),
            ),
        )
    )
    web.memory_health.model_source = lambda: None
    web.memory_health.run(actor)
    return {"person": person, "preference": rule.preference_id, "note": note.note_id}


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_why_lists_what_an_answer_used_with_links_in_a_real_browser(
    served: Any,  # noqa: F811
    tmp_path: Path,
) -> None:
    from integrations.browser import Browser

    web, server, _recorder, _ = served
    seeded = _seed(web)
    shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
    shots.mkdir(parents=True, exist_ok=True)
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()

    def run(expression: str) -> Any:
        return browser._evaluate(expression)

    def wait(expression: str, seconds: float = 30) -> Any:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = run(expression)
            if value:
                return value
            time.sleep(0.2)
        raise AssertionError(
            expression + " | " + str(run("document.getElementById('mem-notice').textContent"))
        )

    def click(scope: str, label: str) -> None:
        found = run(
            "(() => { const b = [...document.querySelectorAll("
            + json.dumps(scope + " button")
            + ")].find(item => item.textContent.trim() === "
            + json.dumps(label)
            + " && item.offsetParent !== null); if (!b) return false; b.click(); return true; })()"
        )
        assert found, (scope, label)

    def no_side_scroll() -> None:
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )

    def open_answer() -> None:
        run("selectPrimaryTab('ask').then(() => memOpenConversation('why-1', 'why-a'))")
        wait("!!document.querySelector('.turn.sg-target[data-message-id=\"why-a\"] .why-btn')")
        time.sleep(0.3)

    try:
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=1280,
            height=900,
            deviceScaleFactor=1,
            mobile=False,
        )
        browser.navigate(server.address)
        wait('!document.getElementById("send").disabled')
        run("window.confirm = () => true;")
        open_answer()
        # Only the answer that used memory has the affordance.
        assert run("document.querySelectorAll('.why-btn').length") == 1
        assert not run("!!document.querySelector('.turn[data-message-id=\"why-a2\"] .why-btn')")
        turn = '.turn[data-message-id="why-a"]'
        assert run(f"document.querySelector({json.dumps(turn + ' .why-btn')}).textContent") == (
            "為什麼？"
        )
        run(f"document.querySelector({json.dumps(turn + ' .why-btn')}).click()")
        wait(f"document.querySelectorAll({json.dumps(turn + ' .why-box li')}).length === 4")
        shown = str(run(f"document.querySelector({json.dumps(turn + ' .why-box')}).innerText"))
        for words in (
            "這則回答用到",
            "偏好：組織圖不用問是否含離職（名片／組織圖）",
            "聯絡人：王小明",
            "筆記：WNC 的 RF 主管是王小明",
            "整理進度：wnc.com.tw",
            "到記憶頁修改或刪除",
            "到同步進度",
        ):
            assert words in shown, (words, shown)
        browser.screenshot(shots / "why-list.png")

        # The preference's link opens it on the memory page, highlighted.
        click(f"{turn} .why-box li:nth-child(1)", "到記憶頁修改或刪除")
        target = f"#mem-pane-preferences .mem-target[data-preference='{seeded['preference']}']"
        wait(f"!!document.querySelector({json.dumps(target)})")
        assert run("!document.getElementById('mem-pane-preferences').hidden")
        assert run("document.getElementById('nav-memory').hasAttribute('aria-current')")
        browser.screenshot(shots / "why-goto-preference.png")
        # The contact's link opens their history.
        open_answer()
        run(f"document.querySelector({json.dumps(turn + ' .why-btn')}).click()")
        wait(f"document.querySelectorAll({json.dumps(turn + ' .why-box li')}).length === 4")
        click(f"{turn} .why-box li:nth-child(2)", "到記憶頁修改或刪除")
        wait("!!document.getElementById('mem-person-panel')")
        assert "王小明 的歷史" in str(run("document.getElementById('mem-person').innerText"))
        # The note's link.
        open_answer()
        run(f"document.querySelector({json.dumps(turn + ' .why-btn')}).click()")
        wait(f"document.querySelectorAll({json.dumps(turn + ' .why-box li')}).length === 4")
        click(f"{turn} .why-box li:nth-child(3)", "到記憶頁修改或刪除")
        note = f"#mem-pane-notes .mem-target[data-note='{seeded['note']}']"
        wait(f"!!document.querySelector({json.dumps(note)})")

        # -- 待確認: the health check's cards, a distinct type ------------------
        run("document.querySelector('#mem-tabs [data-mem=confirm]').click()")
        wait("!!document.querySelector('#mem-health-list .mem-health')")
        cards = str(run("document.getElementById('mem-health-list').innerText"))
        assert "健康檢查：可能重複" in cards and "可能是同一個人：王小明、王小明" in cards
        assert "上次檢查" in str(run("document.getElementById('mem-health-last').textContent"))
        small = run(
            "JSON.stringify([...document.querySelectorAll('#panel-memory button')]"
            ".filter(b => b.offsetParent !== null).map(b => { const r = "
            "b.getBoundingClientRect(); return [b.textContent.trim(), Math.round(r.width),"
            " Math.round(r.height)]; }).filter(([, w, h]) => w < 44 || h < 44))"
        )
        assert json.loads(str(small)) == []
        browser.screenshot(shots / "health-cards.png")
        click("#mem-health-list", "不是同一人")
        wait("document.getElementById('mem-notice').textContent.includes('好，保留不動')")
        wait("!document.querySelector('#mem-health-list .mem-health')")
        click("#mem-health-bar", "立即檢查")
        wait("document.getElementById('mem-notice').textContent.includes('檢查完成')")
        # A dismissed duplicate is not offered again.
        assert not run("!!document.querySelector('#mem-health-list .mem-health')")

        # -- 紀錄: the settings --------------------------------------------------
        run("document.querySelector('#mem-tabs [data-mem=records]').click()")
        wait("!!document.getElementById('mem-health-settings')")
        run(
            "document.getElementById('mem-health-days').value = '30';"
            "document.getElementById('mem-health-months').value = '18';"
        )
        click("#mem-health-settings", "儲存")
        wait("document.getElementById('mem-notice').textContent.includes('已儲存健康檢查設定')")
        settings = web.memory_health.overview(web.runtime.actor)["settings"]
        assert settings == {"enabled": True, "freshness_months": 18, "unused_days": 30}
        browser.screenshot(shots / "health-settings.png")

        # -- dark and 390 px -------------------------------------------------------
        browser.page().call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": "dark"}],
        )
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=390,
            height=844,
            deviceScaleFactor=1,
            mobile=True,
        )
        open_answer()
        run(f"document.querySelector({json.dumps(turn + ' .why-btn')}).click()")
        wait(f"document.querySelectorAll({json.dumps(turn + ' .why-box li')}).length === 4")
        time.sleep(0.2)
        no_side_scroll()
        run(f"document.querySelector({json.dumps(turn)}).scrollIntoView({{block: 'start'}})")
        browser.screenshot(shots / "why-list-dark-390.png")
    finally:
        browser.close()
        browser.discard_profile()
