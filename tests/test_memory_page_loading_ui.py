"""The 記憶 tab while it loads, in a real browser (live check B3, 2026-10-21).

On the owner's PC the overview took many seconds and each sub-tab showed
only its help text and empty counts, as if there were no data. Now each
pane shows 「載入中…」 (aria-busy) and the counts 「…」 until its sections
arrive; a failure is shown inline with 重試; an action reloads only the
sections it changed (`?only=`). The overview is held back by a gate so the
loading state is seen deterministically. Light, dark and 390 px; screenshots
in `.scratch/memory-perf/`.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from host_runtime.web_page import PAGE

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "memory-perf"
PANES = ("confirm", "preferences", "notes", "data", "sync", "records")


def test_every_pane_has_a_status_line_and_actions_name_their_sections() -> None:
    memory = PAGE.split('<section id="panel-memory"', 1)[1].split("</section>", 1)[0]
    for pane in PANES:
        assert f'id="mem-status-{pane}"' in memory, pane
    assert "載入中…" in PAGE and "載入失敗" in PAGE
    assert '"?only="' in PAGE


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_panes_show_loading_errors_inline_and_refresh_only_what_changed(
    served: Any,  # noqa: F811
    tmp_path: Path,
) -> None:
    from integrations.browser import Browser

    web, server, _recorder, _ = served
    actor = web.runtime.actor
    notes = web.personal_memory.notes(actor)
    note, _ = notes.save("樣品 10/30 到", actor=f"{actor} via web", source_kind="answer")
    page = web.memory_page
    real_overview = page.overview
    gate = threading.Event()
    asked: list[list[str]] = []
    failing = {"on": False}

    def held_overview(only: Sequence[str] = ()) -> dict[str, Any]:
        asked.append(list(only))
        gate.wait(30)
        if failing["on"]:
            return {"ok": False, "code": "test_failure", "message": "測試用的失敗"}
        answer: dict[str, Any] = real_overview(only)
        return answer

    page.overview = held_overview
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
            time.sleep(0.1)
        raise AssertionError(expression)

    def counts() -> list[str]:
        return list(
            json.loads(
                str(
                    run(
                        "JSON.stringify([...document.querySelectorAll('#mem-tabs .mem-count')]"
                        ".map(n => n.textContent))"
                    )
                )
            )
        )

    def status(pane: str) -> str:
        return str(
            run(
                f"(() => {{ const s = document.getElementById('mem-status-{pane}');"
                " return s.hidden ? '' : s.textContent; })()"
            )
        )

    def pane(name: str) -> None:
        run(f"document.querySelector('#mem-tabs [data-mem={name}]').click()")
        wait(f"!document.getElementById('mem-pane-{name}').hidden")

    def shoot(name: str) -> None:
        time.sleep(0.2)
        browser.screenshot(shots / f"{name}.png")

    def no_side_scroll() -> None:
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )

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
        # -- the first load, held back: every pane says so ------------------------
        run("document.getElementById('nav-memory').click()")
        wait("document.getElementById('mem-status-confirm').textContent.includes('載入中…')")
        for name in PANES:
            assert "載入中…" in status(name), name
            assert run(f"document.getElementById('mem-pane-{name}').getAttribute('aria-busy')")
        assert counts() == ["…"] * len(PANES)
        assert run("document.getElementById('mem-health-run').disabled")
        shoot("loading-light")
        browser.page().call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": "dark"}],
        )
        pane("notes")
        assert "載入中…" in status("notes")
        shoot("loading-dark")
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=390,
            height=844,
            deviceScaleFactor=1,
            mobile=True,
        )
        no_side_scroll()
        shoot("loading-dark-390")
        browser.page().call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": "light"}],
        )
        pane("confirm")
        no_side_scroll()
        shoot("loading-390")
        # -- released: the counts and the lists arrive ------------------------------
        gate.set()
        wait("document.getElementById('mem-status-confirm').hidden")
        assert all(status(name) == "" for name in PANES)
        shown = counts()
        assert shown[2] == "1" and "…" not in shown, shown
        assert not run("document.getElementById('mem-pane-confirm').hasAttribute('aria-busy')")
        assert asked[0] == []  # the first load asks for everything
        # -- an action reloads only the sections it changed --------------------------
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=1280,
            height=900,
            deviceScaleFactor=1,
            mobile=False,
        )
        pane("notes")
        gate.clear()
        before = len(asked)
        run(
            "[...document.querySelectorAll('[data-note=\""
            + note.note_id
            + "\"] button')].find(b => b.textContent.trim() === '刪除').click()"
        )
        wait("document.getElementById('mem-status-notes').textContent.includes('更新中…')")
        assert status("preferences") == ""  # untouched panes are not reloaded
        shoot("updating-notes")
        gate.set()
        wait("document.getElementById('mem-notice').textContent.includes('復原')")
        assert asked[before:] == [["notes", "spaces"]], asked[before:]
        wait("document.getElementById('mem-status-notes').hidden")
        assert counts()[2] == "0"
        # -- a failure is shown inline, with 重試 -------------------------------------
        failing["on"] = True
        run("document.getElementById('mem-refresh').click()")
        wait("document.getElementById('mem-status-notes').textContent.includes('載入失敗')")
        for name in PANES:
            assert "測試用的失敗" in status(name), name
        assert run("document.getElementById('boot-error').hidden")
        assert counts()[2] == "0"  # the counts already shown stay
        shoot("load-failed")
        failing["on"] = False
        run(
            "[...document.querySelectorAll('#mem-status-notes button')]"
            ".find(b => b.textContent.trim() === '重試').click()"
        )
        wait("document.getElementById('mem-status-notes').hidden")
        assert all(status(name) == "" for name in PANES)
        assert counts()[2] == "0"
    finally:
        gate.set()
        browser.close()
        browser.discard_profile()
