"""Agent Web follow-ups from the 2026-10-21 live checks (#233), in a real browser.

The real Agent Web server and page and a headless browser when one is
installed:
- New session: Send waits until the new session has loaded, and a message
  sent right after goes into the new session, not the previous one.
- A 「為什麼？」 link (memGoto) shows the target pane at once with its loading
  line, never the previous tab or person.
- 復原 under a health finding's fix shows the finding again at once.
- Settings > Teams: a light example placeholder; not editable, and saying
  so, while the shared platform decides the teams.
- The status line after the Harness passed reads 「整理回答中…」.
Light, dark and 390 px; screenshots in `.scratch/followups-233/`.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from host_runtime.web import AgentWeb
from host_runtime.web_page import PAGE

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "followups-233"
SCOPE = "skill:engineering/business-cards"
COMPANY = "範例科技股份有限公司"


def test_the_page_carries_the_follow_up_hooks() -> None:
    for hook in (
        "let startingSession = false;",
        # F26 (3b5c460a): early sends wait in the queue, then target the ready session.
        "return !send.disabled && !!activeConversation "
        "&& !startingSession && uploadingFiles === 0;",
        "let sendQueued = false;",
        'queueSend(uploadingFiles > 0 ? "附件還在上傳" : "對話還在準備中")',
        "form.requestSubmit();",
        '"整理回答中…"',
        'id="team-unused"',
        'placeholder="for example: engineering, qa"',
        "#team-card input::placeholder",
        '"開啟中…"',
        '"/api/memory/health/undo"',
    ):
        assert hook in PAGE, hook
    submit = PAGE.split('form.addEventListener("submit", (event) => {', 1)[1].split("\n});", 1)[0]
    assert (
        "if (!sendReady()) {\n"
        '    queueSend(uploadingFiles > 0 ? "附件還在上傳" : "對話還在準備中");\n'
        "    return;\n"
        "  }"
    ) in submit
    assert submit.index("if (!sendReady())") < submit.index('field.value = "";')


def _seed(web: AgentWeb) -> dict[str, str]:
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
    web.memory_health.model_source = lambda: None
    web.memory_health.run(actor)
    return {"person": person, "preference": rule.preference_id}


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


class _Page:
    def __init__(self, browser: Any, shots: Path) -> None:
        self.browser = browser
        self.shots = shots

    def run(self, expression: str) -> Any:
        return self.browser._evaluate(expression)

    def wait(self, expression: str, seconds: float = 30) -> Any:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = self.run(expression)
            if value:
                return value
            time.sleep(0.1)
        raise AssertionError(expression)

    def size(self, width: int, height: int, *, mobile: bool = False) -> None:
        self.browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=width,
            height=height,
            deviceScaleFactor=1,
            mobile=mobile,
        )

    def dark(self, on: bool) -> None:
        self.browser.page().call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": "dark" if on else "light"}],
        )

    def shoot(self, name: str) -> None:
        time.sleep(0.2)
        self.browser.screenshot(self.shots / f"{name}.png")

    def no_side_scroll(self) -> None:
        assert not self.run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )

    def status(self, pane: str) -> str:
        return str(
            self.run(
                f"(() => {{ const s = document.getElementById('mem-status-{pane}');"
                " return s.hidden ? '' : s.textContent; })()"
            )
        )

    def visible_pane(self) -> list[str]:
        return list(
            json.loads(
                str(
                    self.run(
                        "JSON.stringify([...document.querySelectorAll('.mem-pane')]"
                        ".filter(p => !p.hidden).map(p => p.id))"
                    )
                )
            )
        )


@pytest.fixture
def page(served: Any, tmp_path: Path) -> Any:  # noqa: F811
    from integrations.browser import Browser

    shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
    shots.mkdir(parents=True, exist_ok=True)
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()
    shown = _Page(browser, shots)
    try:
        shown.size(1280, 900)
        yield served, shown
    finally:
        browser.close()
        browser.discard_profile()


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_send_waits_for_the_new_session_and_goes_into_it(page: Any) -> None:
    (web, server, _recorder, _), ui = page
    ui.browser.navigate(server.address)
    ui.wait('!document.getElementById("send").disabled')
    previous = str(ui.run("activeConversation"))
    # Hold the creation of the new session back; record where turns go.
    ui.run(
        "window.__sent = []; window.__release = null;"
        "window.__hold = new Promise(resolve => { window.__release = resolve; });"
        "const realCall = call;"
        "window.call = async (path, body) => {"
        "  if (path === '/api/conversations' && body) await window.__hold;"
        "  if (path === '/api/conversations/turn') {"
        "    window.__sent.push(body.session_id); throw new Error('held in the test'); }"
        "  return realCall(path, body); };"
    )
    ui.run("document.getElementById('new-conversation').click()")
    ui.wait("document.getElementById('send').disabled")
    assert ui.run("document.getElementById('send').getAttribute('aria-busy')") == "true"
    # A message sent now is not sent at all, and stays in the field.
    ui.run(
        "document.getElementById('message').value = '新的問題';"
        "document.getElementById('ask').requestSubmit();"
    )
    time.sleep(0.3)
    assert ui.run("window.__sent") == []
    assert ui.run("document.getElementById('message').value") == "新的問題"
    ui.dark(True)
    ui.size(390, 844, mobile=True)
    ui.no_side_scroll()
    ui.shoot("new-session-waiting-dark-390")
    ui.dark(False)
    ui.size(1280, 900)
    ui.run("window.__release()")
    ui.wait("!document.getElementById('send').disabled")
    created = str(ui.run("activeConversation"))
    assert created and created != previous
    assert not ui.run("document.getElementById('send').hasAttribute('aria-busy')")
    ui.run("document.getElementById('ask').requestSubmit()")
    ui.wait("window.__sent.length === 1")
    assert ui.run("window.__sent") == [created]
    assert len(web.runtime.state.conversations(web.runtime.actor)) >= 2


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_a_memory_link_shows_its_place_at_once_while_the_page_loads(page: Any) -> None:
    (web, server, _recorder, _), ui = page
    seeded = _seed(web)
    memory = web.memory_page
    real_overview = memory.overview
    gate = threading.Event()
    gate.set()

    def held_overview(only: Sequence[str] = ()) -> dict[str, Any]:
        gate.wait(30)
        answer: dict[str, Any] = real_overview(only)
        return answer

    memory.overview = held_overview
    ui.browser.navigate(server.address)
    ui.wait('!document.getElementById("send").disabled')
    # The 記憶 page was open before on a person's history (資料).
    ui.run("selectPrimaryTab('memory')")
    ui.wait("document.getElementById('mem-status-confirm').hidden && !!memData")
    ui.run(f"memOpenPerson({json.dumps(seeded['person'])})")
    ui.wait("!!document.getElementById('mem-person-panel')")
    ui.run("selectPrimaryTab('ask')")
    # A link to a preference while the overview is slow.
    gate.clear()
    ui.run(f"memGoto({{kind: 'preference', id: {json.dumps(seeded['preference'])}}})")
    ui.wait("!document.getElementById('mem-pane-preferences').hidden")
    assert ui.visible_pane() == ["mem-pane-preferences"]
    assert ui.status("preferences") in ("開啟中…", "更新中…")
    assert ui.run("document.getElementById('mem-pane-preferences').getAttribute('aria-busy')")
    # The person's history is not on screen (its pane is hidden).
    assert ui.run("document.getElementById('mem-person-panel').offsetParent === null")
    ui.shoot("goto-loading")
    ui.dark(True)
    ui.size(390, 844, mobile=True)
    ui.no_side_scroll()
    ui.shoot("goto-loading-dark-390")
    ui.dark(False)
    ui.size(1280, 900)
    gate.set()
    target = f"#mem-pane-preferences .mem-target[data-preference='{seeded['preference']}']"
    ui.wait(f"!!document.querySelector({json.dumps(target)})")
    ui.wait("document.getElementById('mem-status-preferences').hidden")
    assert ui.visible_pane() == ["mem-pane-preferences"]
    # A link to a person while the preferences pane shows: 資料 at once, the
    # earlier history gone, the loading line until the person arrives.
    ui.run("selectPrimaryTab('ask')")
    gate.clear()
    ui.run(f"memGoto({{kind: 'person', id: {json.dumps(seeded['person'])}}})")
    ui.wait("!document.getElementById('mem-pane-data').hidden")
    assert ui.visible_pane() == ["mem-pane-data"]
    assert ui.status("data") in ("開啟中…", "更新中…")
    assert not ui.run("!!document.querySelector('.mem-item.mem-target')")
    # The earlier person's history is gone before the new one arrives.
    assert not ui.run("!!document.getElementById('mem-person-panel')")
    gate.set()
    ui.wait("!!document.getElementById('mem-person-panel')")
    ui.wait("document.getElementById('mem-status-data').hidden")
    assert "王小明 的歷史" in str(ui.run("document.getElementById('mem-person').innerText"))


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_undo_under_a_health_fix_shows_the_finding_again_at_once(page: Any) -> None:
    (web, server, _recorder, _), ui = page
    _seed(web)
    store = web.memory_page.cards()
    ui.browser.navigate(server.address)
    ui.wait('!document.getElementById("send").disabled')
    ui.run("window.confirm = () => true;")
    ui.run("selectPrimaryTab('memory')")
    ui.wait("!!document.querySelector('#mem-health-list .mem-health')")
    merge = (
        "[...document.querySelectorAll('#mem-health-list button')]"
        ".find(b => b.textContent.trim().startsWith('合併'))"
    )
    finding = str(ui.run(f"{merge}.closest('.mem-health').dataset.finding"))
    selector = json.dumps(f"#mem-health-list .mem-health[data-finding='{finding}']")
    ui.run(f"{merge}.click()")
    ui.wait("document.getElementById('mem-notice').textContent.includes('已合併')")
    ui.wait(f"!document.querySelector({selector})")
    assert len(store.list_people(company="", source="", status="any", limit=50)[0]) == 1
    ui.run(
        "[...document.querySelectorAll('#mem-notice button')]"
        ".find(b => b.textContent.trim() === '復原').click()"
    )
    ui.wait("document.getElementById('mem-notice').textContent.includes('已復原')")
    ui.wait(f"!!document.querySelector({selector})")
    assert len(store.list_people(company="", source="", status="any", limit=50)[0]) == 2
    count = ui.run("document.querySelector('#mem-tabs [data-mem=confirm] .mem-count').textContent")
    assert count != "0"
    ui.dark(True)
    ui.size(390, 844, mobile=True)
    ui.no_side_scroll()
    ui.shoot("health-reopened-dark-390")


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_teams_placeholder_is_light_and_platform_teams_lock_the_field(page: Any) -> None:
    (web, server, _recorder, _), ui = page
    answer: dict[str, Any] = {
        "ok": True,
        "declared_teams": [],
        "teams": [],
        "source": "none",
    }
    web.team_settings = lambda: dict(answer)
    ui.browser.navigate(server.address)
    ui.wait('!document.getElementById("send").disabled')
    ui.run("selectPrimaryTab('settings')")
    ui.wait("document.getElementById('team-status').textContent.length > 0")
    field = "document.getElementById('team-declared')"
    assert ui.run(f"{field}.placeholder") == "for example: engineering, qa"
    assert not ui.run(f"{field}.disabled") and ui.run(
        "document.getElementById('team-unused').hidden"
    )
    # The example is lighter than typed text.
    placeholder = json.loads(
        str(
            ui.run(
                f"(() => {{ const p = getComputedStyle({field}, '::placeholder');"
                f" const t = getComputedStyle({field});"
                " return JSON.stringify([p.opacity, p.fontStyle, p.color, t.color]); })()"
            )
        )
    )
    assert float(placeholder[0]) < 1 and placeholder[1] == "italic", placeholder
    assert placeholder[2] != placeholder[3], placeholder
    ui.run(f"{field}.scrollIntoView({{block: 'center'}})")
    ui.shoot("teams-declared")
    # The platform decides: the field and Save are disabled, and the card says why.
    answer.update(source="platform", teams=["engineering"], declared_teams=["qa"])
    ui.run("loadTeams()")
    ui.wait(f"{field}.disabled")
    assert ui.run("document.getElementById('team-save').disabled")
    unused = "document.getElementById('team-unused')"
    assert not ui.run(f"{unused}.hidden")
    assert "Not used" in str(ui.run(f"{unused}.textContent"))
    assert ui.run(f"{field}.getAttribute('aria-describedby')") == "team-unused"
    assert ui.run(f"{field}.value") == "qa"
    for dark in (False, True):
        ui.dark(dark)
        ui.size(390, 844, mobile=True)
        ui.run(f"{field}.scrollIntoView({{block: 'center'}})")
        ui.no_side_scroll()
        ui.shoot("teams-platform" + ("-dark" if dark else "") + "-390")
    # Back to declared teams: editable again.
    answer.update(source="declared", teams=["qa"])
    ui.run("loadTeams()")
    ui.wait(f"!{field}.disabled")
    assert not ui.run("document.getElementById('team-save').disabled")
    assert ui.run(f"{unused}.hidden")


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_status_line_after_validated_says_the_answer_is_being_written(page: Any) -> None:
    (_web, server, _recorder, _), ui = page
    ui.browser.navigate(server.address)
    ui.wait('!document.getElementById("send").disabled')

    def status(progress: dict[str, Any]) -> str:
        return str(ui.run(f"progressStatus({json.dumps(progress)})"))

    steps = [{"stage": "plan", "label": "規劃", "state": "done"}]
    validated = {"label": "程式修改", "phase": "validated", "done": True, "retry": 0}
    tools = [{"name": "coding__run", "status": "ok", "duration_s": 1.0}]
    assert status({"tool_count": 3, "tools": tools, "harness": {**validated, "steps": steps}}) == (
        "整理回答中…"
    )
    # Not before it passed, and not when it ended otherwise.
    failed = {**validated, "phase": "failed", "steps": steps}
    assert status({"tool_count": 3, "tools": tools, "harness": failed}) == "思考下一步…"
    assert status({"tool_count": 3, "tools": tools, "harness": None}) == "思考下一步…"
    running = {**validated, "done": False, "phase": "validating", "steps": steps}
    assert status({"tool_count": 3, "tools": tools, "harness": running}).startswith("程式修改：")
    waiting = [{"name": "mail", "status": "waiting", "duration_s": 0.0}]
    harness = {**validated, "steps": steps}
    assert status({"tool_count": 4, "tools": waiting, "harness": harness}) == "等待你確認：mail"
