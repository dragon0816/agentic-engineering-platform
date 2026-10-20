"""The 記憶 tab of Agent Web in a real browser (accumulated memory M4).

The real Agent Web server and page and a real headless browser when one is
installed, against a fixture workspace: every section renders (待確認, 偏好,
筆記, 資料, 同步進度, 紀錄) and its actions work end to end through the
token-checked routes; light, dark and 390 px wide, with 44 px targets and no
horizontal scroll. Screenshots in `.scratch/memory-page/`.
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

from capabilities.business_cards.contracts import PersonRef
from capabilities.business_cards.manifest import business_cards_skill
from capabilities.business_cards.space import CONTACTS_ORG
from host_runtime.conversations import ConversationMessage, ConversationRecord
from host_runtime.web import AgentWeb
from host_runtime.web_page import PAGE

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "memory-page"
SCOPE = "skill:engineering/business-cards"
CARD = {
    "name": "王小明",
    "romanised_name": "Hsiao-Ming Wang",
    "company": "範例科技股份有限公司",
    "department": "射頻部",
    "title": "經理",
    "email": "hm.wang@example.com",
}


def test_the_page_has_the_memory_tab_and_its_routes() -> None:
    for hook in (
        '<button id="nav-memory" type="button">記憶</button>',
        '<section id="panel-memory"',
        'data-mem="confirm"',
        'data-mem="records"',
        '"/api/memory/overview"',
        '"/api/memory/proposals/decide"',
        '"/api/memory/preferences/edit"',
        '"/api/memory/notes/edit"',
        '"/api/memory/sync/reset"',
        '"/api/memory/sync/restore"',
        '"/api/memory/space/delete"',
        "memory: loadMemory",
    ):
        assert hook in PAGE, hook
    # The panes are divs: a section would stay hidden (`section{display:none}`).
    memory = PAGE.split('<section id="panel-memory"', 1)[1].split("</section>", 1)[0]
    assert "<section" not in memory


def _seed(web: AgentWeb) -> dict[str, Any]:
    """A fixture workspace: one open proposal, a preference used in a turn,
    two notes, a sync state and an orphan space."""
    layout = web.runtime.layout
    layout.skills.mkdir(parents=True, exist_ok=True)
    (layout.skills / "engineering__business-cards__1.0.0.json").write_text(
        business_cards_skill().model_dump_json(), encoding="utf-8"
    )
    store = web.memory_page.cards()
    first = store.add(
        CARD,
        source="card",
        source_date=date(2026, 1, 10),
        source_ref="sha256:" + "ab" * 32,
        uncertain=(),
        actor="seed",
    )
    store.edit(PersonRef(person_id=first.person_id), {}, actor="seed", reason="", confirm=["email"])
    store.add(
        {**CARD, "email": "hm.wamg@example.com"},
        source="card",
        source_date=date(2026, 2, 1),
        source_ref="sha256:" + "cd" * 32,
        uncertain=("email",),
        actor="seed",
    )
    now = datetime.now(UTC)
    prefs = web.personal_memory.preferences(web.runtime.actor)
    saved, _ = prefs.save(
        SCOPE,
        "執行時不需要問是否包含在職人員",
        actor=f"{web.runtime.actor} via web",
        scope_label="名片／組織圖",
        source_session="mem-1",
        source_message="mem-q",
    )
    web.runtime.state.create_conversation(
        ConversationRecord(
            session_id="mem-1",
            actor=web.runtime.actor,
            title="WNC 組織圖",
            created_at=now,
            updated_at=now + timedelta(seconds=1),
            messages=(
                ConversationMessage(
                    message_id="mem-q",
                    role="user",
                    text="WNC 組織圖，執行時不需要問是否包含在職人員",
                    created_at=now,
                    status="submitted",
                ),
                ConversationMessage(
                    message_id="mem-a",
                    role="assistant",
                    text="## WNC\n\nRF 主管是王小明。",
                    created_at=now + timedelta(seconds=1),
                    status="answered",
                    preferences_used=(saved.preference_id,),
                ),
            ),
        )
    )
    notes = web.personal_memory.notes(web.runtime.actor)
    note, _ = notes.save(
        "## WNC\n\n**RF** 主管是王小明，下週二確認 BOM。",
        actor=f"{web.runtime.actor} via web",
        source_kind="answer",
        source_session="mem-1",
        source_message="mem-a",
        tags=["WNC"],
    )
    other, _ = notes.save(
        "樣品 10/30 到", actor=f"{web.runtime.actor} via web", source_kind="answer", tags=["樣品"]
    )
    service = web.memory_page.service()
    service.owned(CONTACTS_ORG).advance_sync(
        "mail:Inbox",
        "wnc.com.tw",
        last_message_date="2026-10-19T08:00:00+00:00",
        message_ids=["m-1"],
        extractor_version="sig-3",
        actor=f"{web.runtime.actor} via web",
    )
    with service.connect() as con:
        con.execute(
            "INSERT INTO spaces (space, manager, table_prefix, declaration_json, rules_json, "
            "registered_at, updated_at) SELECT 'projects/readiness', 'gone/readiness', "
            "'projects_readiness__', REPLACE(declaration_json, 'personal/notes', "
            "'projects/readiness'), rules_json, registered_at, updated_at FROM spaces "
            "WHERE space = 'personal/notes'"
        )
    return {
        "store": store,
        "person_id": first.person_id,
        "preference": saved.preference_id,
        "note": note.note_id,
        "other": other.note_id,
    }


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_every_section_renders_and_acts_in_a_real_browser(
    served: Any,  # noqa: F811
    tmp_path: Path,
) -> None:
    from integrations.browser import Browser

    web, server, _recorder, _ = served
    seeded = _seed(web)
    store = seeded["store"]
    actor = web.runtime.actor
    notes = web.personal_memory.notes(actor)
    prefs = web.personal_memory.preferences(actor)
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
            expression
            + " | "
            + str(run("document.getElementById('boot-error').textContent"))
            + " | "
            + str(run("document.getElementById('mem-notice').textContent"))
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

    def notice(words: str) -> None:
        wait(
            "document.getElementById('mem-notice').textContent.includes(" + json.dumps(words) + ")"
        )

    def pane(name: str) -> None:
        run(f"document.querySelector('#mem-tabs [data-mem={name}]').click()")
        wait(f"!document.getElementById('mem-pane-{name}').hidden")

    def no_side_scroll() -> None:
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )

    def small_targets() -> list[str]:
        found = run(
            "JSON.stringify([...document.querySelectorAll('#panel-memory button, "
            "#panel-memory select, #panel-memory input.mem-field')]"
            ".filter(b => b.offsetParent !== null).map(b => { const r = "
            "b.getBoundingClientRect(); return [b.textContent.trim() || b.getAttribute("
            "'aria-label') || b.tagName, Math.round(r.width), Math.round(r.height)]; })"
            ".filter(([, w, h]) => w < 44 || h < 44))"
        )
        return list(json.loads(str(found)))

    def shoot(name: str) -> None:
        run("document.getElementById('mem-tabs').scrollIntoView({block: 'start'})")
        time.sleep(0.2)
        browser.screenshot(shots / f"{name}.png")

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
        # Destructive steps ask first; the test answers yes, and downloads
        # are kept on the page instead of being saved.
        run(
            "window.confirm = () => true; window.__downloads = [];"
            " memDownload = (name, body) => window.__downloads.push([name, body]);"
        )
        run("document.getElementById('nav-memory').click()")
        wait("!!document.querySelector('#mem-confirm-list .mem-item')")
        assert run("document.getElementById('nav-memory').hasAttribute('aria-current')")
        counts = run(
            "[...document.querySelectorAll('#mem-tabs .mem-count')].map(s => s.textContent)"
            ".join(',')"
        )
        assert counts == "1,1,2,4,1,", counts

        # -- 待確認 ------------------------------------------------------------
        shown = str(run("document.getElementById('mem-pane-confirm').innerText"))
        for words in (
            "王小明（範例科技股份有限公司） · Email",
            "聯絡人與組織",
            "hm.wang@example.com",
            "hm.wamg@example.com",
            "名片 · 2026-02-01",
            "保留原值",
            "改用新值",
            "開啟該聯絡人",
        ):
            assert words in shown, (words, shown)
        assert small_targets() == []
        no_side_scroll()
        shoot("confirm-light")
        click("#mem-confirm-list", "改用新值")
        notice("已改用新值")
        assert store.view(seeded["person_id"]).email == "hm.wamg@example.com"
        wait("!!document.querySelector('#mem-confirm-list .empty')")
        click("#mem-notice", "復原")
        notice("已復原")
        wait("!!document.querySelector('#mem-confirm-list .mem-item')")
        assert store.view(seeded["person_id"]).email == "hm.wang@example.com"
        click("#mem-confirm-list", "保留原值")
        notice("已保留原值")
        assert store.proposals(None, limit=10)[0] == []
        history = store.history(PersonRef(person_id=seeded["person_id"]), limit=10).history
        assert history[0].actor == f"{actor} via web"

        # -- 偏好 --------------------------------------------------------------
        pane("preferences")
        shown = str(run("document.getElementById('mem-pane-preferences').innerText"))
        for words in ("名片／組織圖", "執行時不需要問是否包含在職人員", "來源對話", "用過 1 次"):
            assert words in shown, (words, shown)
        assert small_targets() == []
        shoot("preferences-light")
        item = f"[data-preference='{seeded['preference']}']"
        click(item, "修改")
        run(
            f"document.querySelector({json.dumps(item + ' textarea')}).value ="
            " '執行時不需要問是否包含離職人員'"
        )
        click(item, "儲存")
        notice("已修改")
        edited = prefs.get(seeded["preference"])
        assert edited is not None and edited.text == "執行時不需要問是否包含離職人員"
        click("#mem-notice", "復原")
        notice("已復原")
        assert prefs.get(seeded["preference"]).text == "執行時不需要問是否包含在職人員"
        wait(f"!!document.querySelector({json.dumps(item)})")
        click(item, "刪除")
        notice("已刪除")
        assert prefs.listed() == []
        click("#mem-notice", "復原")
        notice("已復原")
        assert [p.preference_id for p in prefs.listed()] == [seeded["preference"]]

        # -- 筆記 --------------------------------------------------------------
        pane("notes")
        wait("document.querySelectorAll('#mem-notes-list .mem-item').length === 2")
        assert run("!!document.querySelector('#mem-notes-list .mem-note-body h2')")
        shoot("notes-light")
        run(
            "{ const t = document.getElementById('mem-note-tag'); t.value = '樣品';"
            " t.dispatchEvent(new Event('change')); }"
        )
        wait("document.querySelectorAll('#mem-notes-list .mem-item').length === 1")
        run(
            "{ const t = document.getElementById('mem-note-tag'); t.value = '';"
            " t.dispatchEvent(new Event('change')); }"
        )
        wait("document.querySelectorAll('#mem-notes-list .mem-item').length === 2")
        card = f"[data-note='{seeded['note']}']"
        click(card, "加標籤")
        run(f"document.querySelector({json.dumps(card + ' input.mem-field')}).value = 'RF'")
        click(card, "加入")
        notice("已儲存")
        assert notes.get(seeded["note"]).tags == ("WNC", "RF")
        wait(f"!!document.querySelector({json.dumps(card)})")
        click(card, "連結聯絡人")
        run(f"document.querySelector({json.dumps(card + ' input.mem-field')}).value = '王小明'")
        click(card, "搜尋")
        wait(f"!!document.querySelector({json.dumps(card + ' .mem-results button')})")
        run(f"document.querySelector({json.dumps(card + ' .mem-results button')}).click()")
        notice("已儲存")
        ref = f"contacts/org:person:{seeded['person_id']}"
        assert notes.get(seeded["note"]).entities == (ref,)
        wait(f"!!document.querySelector({json.dumps(card + ' .mem-chip.entity')})")
        assert "王小明（範例科技股份有限公司）" in str(
            run(f"document.querySelector({json.dumps(card + ' .mem-chip.entity')}).innerText")
        )
        click(card, "修改")
        run(f"document.querySelector({json.dumps(card + ' textarea')}).value = '**RF** 改過了'")
        click(card, "儲存")
        notice("已儲存")
        assert notes.get(seeded["note"]).text == "**RF** 改過了"
        click("#mem-notice", "復原")
        notice("已復原")
        # Unlink by the chip's ×.
        wait(f"!!document.querySelector({json.dumps(card + ' .mem-chip.entity button')})")
        run(f"document.querySelector({json.dumps(card + ' .mem-chip.entity button')}).click()")
        notice("已儲存")
        assert notes.get(seeded["note"]).entities == ()
        # Export the selection as Markdown.
        wait(f"!!document.querySelector({json.dumps(card + ' input[type=checkbox]')})")
        run(f"document.querySelector({json.dumps(card + ' input[type=checkbox]')}).click()")
        run("document.getElementById('mem-note-export').click()")
        notice("已匯出 1 則筆記")
        name, body = run("window.__downloads[0]")
        assert name.endswith(".md") and seeded["note"] in body and seeded["other"] not in body
        # Delete and 復原.
        click(card, "刪除")
        notice("已刪除")
        assert [n.note_id for n in notes.listed()] == [seeded["other"]]
        click("#mem-notice", "復原")
        notice("已復原")
        assert len(notes.listed()) == 2
        assert small_targets() == []
        no_side_scroll()

        # -- 資料 --------------------------------------------------------------
        pane("data")
        shown = str(run("document.getElementById('mem-spaces-list').innerText"))
        for words in (
            "聯絡人與組織",
            "名片／組織圖（engineering/business-cards）",
            "已開啟",
            "projects/readiness",
            "無主：管理的 Skill 已不在這台電腦",
            "機密（CONFIDENTIAL）",
            "保留到刪除",
            "聯絡人 1",
        ):
            assert words in shown, (words, shown)
        shoot("data-light")
        click("#mem-spaces-list", "開啟聯絡人")
        wait("!!document.querySelector('#mem-people-list .mem-item')")
        assert "在職" in str(run("document.getElementById('mem-people-list').innerText"))
        click("#mem-people-list", "歷史")
        wait("!!document.getElementById('mem-person-panel')")
        assert "王小明 的歷史" in str(run("document.getElementById('mem-person').innerText"))
        assert small_targets() == []
        no_side_scroll()
        browser.screenshot(shots / "data-people-light.png")

        # -- 同步進度 ----------------------------------------------------------
        pane("sync")
        shown = str(run("document.getElementById('mem-sync-list').innerText"))
        for words in ("wnc.com.tw", "mail:Inbox", "sig-3", "2026-10-19 16:00"):
            assert words in shown, (words, shown)
        shoot("sync-light")
        click("#mem-sync-list", "重新整理")
        notice("已重設")
        space = web.memory_page.service().owned(CONTACTS_ORG)
        assert space.sync_state("mail:Inbox", "wnc.com.tw") is None
        wait("document.getElementById('mem-sync-list').innerText.includes('已重設')")
        click("#mem-sync-list", "復原上次重設")
        notice("已復原上次重設")
        assert space.sync_state("mail:Inbox", "wnc.com.tw") is not None

        # -- 紀錄 --------------------------------------------------------------
        pane("records")
        shown = str(run("document.getElementById('mem-records').innerText"))
        for words in ("保留到你刪除", "100 則", "30 天", "500 MB", "匯出 JSON", "刪除資料"):
            assert words in shown, (words, shown)
        run("document.getElementById('mem-experience-days').value = '45'")
        click("#mem-records", "儲存")
        notice("已儲存：經驗回顧案例保留 45 天")
        record = "[data-record-space='contacts/org']"
        click(record, "匯出 JSON")
        notice("已匯出『聯絡人與組織』")
        name, body = run("window.__downloads[1]")
        assert name.startswith("memory-contacts-org-") and json.loads(body)["space"] == (
            CONTACTS_ORG
        )
        shoot("records-light")
        click(record, "刪除資料…")
        assert run(
            f"document.querySelector({json.dumps(record + ' .mem-danger button.danger')}).disabled"
        )
        run(
            f"{{ const i = document.querySelector({json.dumps(record + ' .mem-danger input')});"
            " i.value = 'contacts/org'; i.dispatchEvent(new Event('input')); }"
        )
        browser.screenshot(shots / "records-delete-asked.png")
        click(record, "確定刪除")
        notice("已刪除『聯絡人與組織』的資料")
        assert store.list_people(company="", source="", status="any", limit=5) == ([], 0)
        wait(
            "document.getElementById('mem-records').innerText.includes('聯絡人與組織（contacts/org）')"
        )
        assert len(notes.listed()) == 2  # other spaces keep their data

        # -- dark mode and 390 px --------------------------------------------
        light = run(
            "getComputedStyle(document.querySelector('#mem-records .mem-item')).backgroundColor"
        )
        browser.page().call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": "dark"}],
        )
        dark = run(
            "getComputedStyle(document.querySelector('#mem-records .mem-item')).backgroundColor"
        )
        assert light != dark, (light, dark)
        for name in ("confirm", "preferences", "notes", "data", "sync", "records"):
            pane(name)
            shoot(f"{name}-dark")
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=390,
            height=844,
            deviceScaleFactor=1,
            mobile=True,
        )
        browser.page().call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": "light"}],
        )
        for name in ("confirm", "preferences", "notes", "data", "sync", "records"):
            pane(name)
            time.sleep(0.2)
            no_side_scroll()
            assert small_targets() == [], name
            shoot(f"{name}-390")
        # A source link opens the original conversation at that message.
        pane("preferences")
        click(f"[data-preference='{seeded['preference']}']", "來源對話")
        wait("!!document.querySelector('.turn.sg-target')")
        assert run("activeConversation") == "mem-1"
        assert run("document.querySelector('.turn.sg-target').dataset.askedId") == "mem-q"
        browser.screenshot(shots / "opened-conversation-390.png")
    finally:
        browser.close()
        browser.discard_profile()


def test_the_routes_need_the_page_token(served: Any) -> None:  # noqa: F811
    import urllib.error
    import urllib.request

    web, server, _recorder, _ = served
    base = f"http://127.0.0.1:{server.server_address[1]}"
    for path, body in (
        ("/api/memory/overview", None),
        ("/api/memory/export?space=personal/notes", None),
        ("/api/memory/space/delete", {"space": "personal/notes", "confirm": "personal/notes"}),
    ):
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(base + path, data=data, method="POST" if data else "GET")
        if data:
            request.add_header("Content-Type", "application/json")
        with pytest.raises(urllib.error.HTTPError) as refused:
            urllib.request.urlopen(request, timeout=10)
        assert refused.value.code == 401, path
    request = urllib.request.Request(base + "/api/memory/overview")
    request.add_header("Authorization", f"Bearer {server.token}")
    with urllib.request.urlopen(request, timeout=10) as answer:
        overview = json.loads(answer.read().decode("utf-8"))
    assert overview["ok"] and overview["actor"] == web.runtime.actor
    assert web.memory_page.service().deletions() == []
