"""「存成筆記」 and 「存選取內容」 in a real browser (accumulated memory M3).

The real Agent Web server and page, a real headless browser when one is
installed: the 存成筆記 button under an answer saves the whole answer, 復原
takes it back, and selecting part of an answer offers 存選取內容, which
saves only the selection. Every save goes through the token-checked
`/api/memory/notes/save`. Screenshots in `.scratch/notes-ui/`.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from host_runtime.conversations import ConversationMessage, ConversationRecord
from host_runtime.web import AgentWeb
from host_runtime.web_page import PAGE

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "notes-ui"
SESSION = "notes-ui-1"
ANSWER = (
    "## WNC 重點\n\n**WNC** 的 RF 主管是王小明，下週二要再確認 BOM。\n\n"
    "樣品預計 10/30 到，到貨後通知測試組。\n"
)
PARAGRAPH = "WNC 的 RF 主管是王小明，下週二要再確認 BOM。"


def _seed(web: AgentWeb) -> None:
    now = datetime.now(UTC)
    web.runtime.state.create_conversation(
        ConversationRecord(
            session_id=SESSION,
            actor=web.runtime.actor,
            title="WNC",
            created_at=now,
            updated_at=now + timedelta(seconds=1),
            messages=(
                ConversationMessage(
                    message_id="nu-q",
                    role="user",
                    text="整理 WNC 的重點",
                    created_at=now,
                    status="submitted",
                ),
                ConversationMessage(
                    message_id="nu-a",
                    role="assistant",
                    text=ANSWER,
                    created_at=now + timedelta(seconds=1),
                    status="answered",
                ),
            ),
        )
    )


def test_the_page_has_the_note_actions() -> None:
    for hook in (
        'keep.title = "存成筆記"',
        '"/api/memory/notes/save"',
        '"/api/memory/undo"',
        'selectionNote.id = "save-selection"',
        "存選取內容",
    ):
        assert hook in PAGE, hook


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_save_an_answer_undo_it_and_save_a_selection_in_a_real_browser(
    served: Any,  # noqa: F811
    tmp_path: Path,
) -> None:
    from integrations.browser import Browser

    web, server, _recorder, _ = served
    _seed(web)
    notes = web.personal_memory.notes(web.runtime.actor)
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
        raise AssertionError(expression)

    turn = '.turn[data-message-id="nu-a"]'
    try:
        browser.navigate(server.address)
        wait('!document.getElementById("send").disabled')
        time.sleep(1.5)
        run(f"loadConversations({json.dumps(SESSION)})")
        wait(f"activeConversation === {json.dumps(SESSION)}")
        wait(f"!!document.querySelector({json.dumps(turn + ' .save-note')})")
        # The action under the answer, shown on focus like the other tools.
        run(f"document.querySelector({json.dumps(turn)}).focus()")
        assert run(
            f"document.querySelector({json.dumps(turn + ' .save-note')}).getAttribute('aria-label')"
        ) == ("存成筆記")
        browser.screenshot(shots / "answer-tools.png")
        # 存成筆記: the whole answer, through the page's token-checked call.
        run(f"document.querySelector({json.dumps(turn + ' .save-note')}).click()")
        wait(
            f"(document.querySelector({json.dumps(turn + ' .note-saved')}) || {{}})"
            ".textContent && document.querySelector("
            f"{json.dumps(turn + ' .note-saved')}).textContent.includes('已存成筆記')"
        )
        (saved,) = notes.listed()
        assert saved.text == ANSWER.strip() and saved.source_kind == "answer"
        assert (saved.source_session, saved.source_message) == (SESSION, "nu-a")
        assert saved.created_by == f"{web.runtime.actor} via web"
        browser.screenshot(shots / "answer-saved.png")
        # 復原 takes it back.
        run(f"document.querySelector({json.dumps(turn + ' .note-undo')}).click()")
        wait(
            f"document.querySelector({json.dumps(turn + ' .note-saved')})"
            ".textContent.includes('已復原')"
        )
        assert notes.listed() == []
        browser.screenshot(shots / "answer-undone.png")
        # Selecting part of the answer offers 存選取內容 next to it.
        run(
            "(() => { const said = document.querySelector("
            + json.dumps(turn + " .said")
            + "); const p = [...said.querySelectorAll('p')].find(item => "
            "item.textContent.includes('RF')); const chosen = window.getSelection(); "
            "chosen.removeAllRanges(); const range = document.createRange(); "
            "range.selectNodeContents(p); chosen.addRange(range); return true; })()"
        )
        wait("!document.getElementById('save-selection').hidden")
        box = run(
            "JSON.stringify(document.getElementById('save-selection').getBoundingClientRect())"
        )
        placed = json.loads(str(box))
        assert placed["height"] >= 36 and placed["top"] > 0, placed
        browser.screenshot(shots / "selection-offered.png")
        run("document.getElementById('save-selection').click()")
        wait(
            f"[...document.querySelectorAll({json.dumps(turn + ' .note-saved')})]"
            ".some(item => item.textContent.includes('已存成筆記'))"
        )
        (picked,) = notes.listed()
        assert picked.text == PARAGRAPH and picked.source_kind == "selection"
        assert picked.excerpt is not None
        start, end = picked.excerpt["start"], picked.excerpt["end"]
        assert ANSWER[start:end] == "WNC** 的 RF 主管是王小明，下週二要再確認 BOM"
        assert run("document.getElementById('save-selection').hidden") is True
        browser.screenshot(shots / "selection-saved.png")
        # A selection outside an answer offers nothing.
        run(
            "(() => { const asked = document.querySelector("
            + json.dumps(turn + " .asked")
            + "); const chosen = window.getSelection(); chosen.removeAllRanges(); "
            "const range = document.createRange(); range.selectNodeContents(asked); "
            "chosen.addRange(range); return true; })()"
        )
        time.sleep(0.6)
        assert run("document.getElementById('save-selection').hidden") is True
    finally:
        browser.close()
