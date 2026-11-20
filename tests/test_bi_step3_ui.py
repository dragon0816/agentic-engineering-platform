"""Step 3 of the BI page: the owner's requests of 2026-11-05 in a real browser.

Benchmark and Dashboard are collapsed sections with a status; 跑測試 is in view without
opening either; a question row opens an editor beside the table; the Dashboard sits beside
the results; a card opens beside what it came from; a jump to another tab has a way back to
the same place. The real Agent Web server in a temporary workspace, joined to a copy of the
fixture vault. All data is fictional.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from aep_bi.cards import vault_checks
from aep_bi.cards.store import BiStore
from aep_bi.host import bi_bench, bi_cards_api
from scripts import bi_feed_fixtures as fixtures

VAULT = fixtures.VAULT_ID
DATASET = f"vault-{VAULT}"
SCROLL = "biScroller().scrollTop"


def _questions(workspace: Path) -> dict[str, dict[str, Any]]:
    return {q["unit"]: q for q in vault_checks.listing(workspace, VAULT)["questions"]}


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_step_3(
    served: Any,  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    web, server, _recorder, _ = served
    workspace = web.runtime.layout.workspace_root
    copy = tmp_path / "shared" / "vault"
    shutil.copytree(fixtures.VAULT_DIR, copy)
    fixtures.join(workspace, copy)
    monkeypatch.setattr(
        bi_cards_api,
        "web_bench_runtime",
        lambda _web: bi_bench.BenchRuntime(
            ask_for=lambda _v, _a: lambda q, s: {"ok": True, "answer": "FicTech"},
            extract_for=lambda _v, _a: lambda case: [],
            background=lambda _title, work: work(),
        ),
    )
    shots = os.environ.get("AEP_UI_SHOTS")
    folder = Path(shots) / "bi-step3" if shots else None
    with BiPage(tmp_path / "browser", server.address, folder) as page:
        page.run(f"bi.want = {DATASET!r}; biLoad()")
        page.wait(f"document.getElementById('bi-dataset').value === {DATASET!r}")
        page.click("#bi-views [data-bi-view=build]")
        page.click("#bi-stepper [data-stage=test]")
        page.wait("!document.querySelector('#bi-view-build .kp-stage[data-stage=test]').hidden")
        # A question and a panel belong to a domain: 全部領域 only reads.
        page.wait("(bi.build.homes || []).length > 0")
        page.choose("bi-b-src-folder", str(page.run("bi.build.homes[0].folder")))

        # -- two collapsed sections with a status; the button in view without opening them --
        page.wait("document.getElementById('bi-b-an-state').textContent.includes('個分析')")
        page.wait("document.getElementById('bi-b-bench-state').textContent.includes('題')")
        # One tab at a time (owner 2026-11-20): Benchmark in front, the Dashboard one tab away.
        page.wait("document.getElementById('bi-b-bench').open")
        assert page.run("document.getElementById('bi-b-an').classList.contains('bi-tab-off')")
        run_button = "document.getElementById('bi-b-bench-run')"
        assert page.run(f"{run_button}.closest('details') === null")
        assert page.run(f"{run_button}.offsetHeight >= 52")
        assert page.run(f"{run_button}.getBoundingClientRect().top < innerHeight")
        # Benchmark and Dashboard are tabs of the main area (owner 2026-11-20); the share step
        # is not in the main area but opens beside it.
        page.wait("!document.getElementById('bi-b-tabs').hidden")
        tabs = page.run("[...document.querySelectorAll('#bi-b-tabs [role=tab]')]"
                        ".map((t) => t.textContent)")  # fmt: skip
        assert tabs == ["Benchmark", "Dashboard"]
        assert page.run("document.getElementById('bi-b-ver').offsetParent === null")
        assert page.run("!document.getElementById('bi-b-ver-bar').hidden")
        page.see("bi-b-run-why", "還沒有測試題")
        assert page.run(f"{run_button}.disabled")
        page.shoot("collapsed")

        # -- the question table: a new one, a row opens the editor on the right --------------
        page.run("document.getElementById('bi-b-bench').open = true")
        page.set_value("bi-b-bq-q", "FicTech 是什麼？")
        page.set_value("bi-b-bq-must", "FicTech")
        page.set_value("bi-b-bq-not", "ETSI")
        page.click("#bi-b-bq-form button[type=submit]")
        page.see("bi-b-bq-list", "FicTech 是什麼")
        page.see("bi-b-bench-state", "1 題")
        page.wait(f"!{run_button}.disabled")
        assert "這次跑" in page.text_of("bi-b-run-why")
        (unit,) = _questions(workspace)
        page.click("#bi-b-bq-list tbody tr")
        page.see("bi-b-bq-title", "修改題目")
        assert page.run("document.getElementById('bi-b-bq-q').value") == "FicTech 是什麼？"
        assert page.run("document.getElementById('bi-b-bq-must').value") == "FicTech"
        assert page.run("document.getElementById('bi-b-bq-not').value") == "ETSI"
        assert (
            page.run(
                "document.querySelector('#bi-b-bq-list tbody tr').getAttribute('aria-selected')"
            )
            == "true"
        )
        beside = (
            "document.getElementById('bi-b-bq-pane').getBoundingClientRect().left"
            " >= document.getElementById('bi-b-bq-list').getBoundingClientRect().right"
        )
        assert page.run(beside)
        page.shoot("question-editor")

        # Saving overwrites the same question, by its set and slug.
        page.set_value("bi-b-bq-q", "FicTech 這家公司是什麼？")
        page.set_value("bi-b-bq-must", "FicTech, 公司")
        page.click("#bi-b-bq-form button[type=submit]")
        page.see("bi-b-bq-list", "這家公司")
        assert set(_questions(workspace)) == {unit}
        saved = _questions(workspace)[unit]
        assert saved["question"] == "FicTech 這家公司是什麼？"
        assert saved["must"] == ["FicTech", "公司"] and saved["must_not"] == ["ETSI"]
        page.see("bi-b-bq-title", "修改題目")  # still on it

        # Another set is a move: the old one goes, and the row stays selected.
        page.set_value("bi-b-bq-set", "market")
        page.click("#bi-b-bq-form button[type=submit]")
        page.wait("document.querySelector('#bi-b-bq-list tbody tr').textContent.includes('market')")
        ((moved, value),) = _questions(workspace).items()
        assert moved != unit and value["set"] == "market" and value["slug"] == saved["slug"]
        page.wait("document.querySelector('#bi-b-bq-list tbody tr[aria-selected=true]') !== null")

        # Delete in the editor; then a new one again.
        page.click("#bi-b-bq-add")
        page.see("bi-b-bq-title", "新增題目")
        assert page.run("document.getElementById('bi-b-bq-q').value") == ""
        assert page.run("document.getElementById('bi-b-bq-del').hidden")
        page.click("#bi-b-bq-list tbody tr")
        page.click("#bi-b-bq-del")  # no confirmation: undone by not committing
        page.see("bi-b-bench-state", "0 題")
        assert _questions(workspace) == {}
        page.see("bi-b-bq-title", "新增題目")
        page.set_value("bi-b-bq-q", "FicTech 是什麼？")
        page.set_value("bi-b-bq-must", "FicTech")
        page.click("#bi-b-bq-form button[type=submit]")
        page.see("bi-b-bq-list", "FicTech 是什麼")

        # -- the run: a bar beside the button, the numbers on top, details beside the page ---
        page.run("document.getElementById('bi-b-bench').open = false")
        page.wait(f"!{run_button}.disabled")
        page.click("#bi-b-bench-run")
        page.see("bi-b-bench-report", "完成")
        page.wait("!document.getElementById('bi-b-run-progress').hidden")
        page.see("bi-b-run-text", "完成：1/1 題")
        assert page.run("document.getElementById('bi-b-run-progress').parentElement.id") == (
            "bi-b-run"
        ), "the bar is beside 跑測試"
        page.see("bi-b-bench-sum", "通過率")
        summary = page.text_of("bi-b-bench-sum")
        assert "題數1" in summary and "最近一次" in summary
        assert page.run("document.querySelector('#bi-b-bench-report table') === null")
        page.click_text("#bi-b-bench-report", "看每題結果")
        page.wait("sideHas('bi-bench-detail')")
        page.see("extra-panel-bi-bench-detail", "FicTech 是什麼")
        page.shoot("results-and-details")
        page.click("#bi-b-tab-dash-tab")
        page.wait(
            "document.getElementById('bi-b-test-dash').contains("
            "document.getElementById('bi-dash-sections'))"
        )
        page.wait("document.getElementById('bi-dash-sections').children.length > 0")
        assert page.run("document.getElementById('bi-b-bench-report').offsetParent === null")
        assert page.run("document.getElementById('bi-b-to-dash') === null")
        page.shoot("dashboard-tab")
        page.click("#bi-b-tab-bench-tab")
        # 看歷史紀錄 and 分享 open as tabs of the side area.
        page.click("#bi-b-hist-open")
        page.wait("sideHas('bi-history')")
        page.click("#bi-b-ver-open")
        page.wait("document.getElementById('bi-b-ver').closest('.extra-panel') !== null")
        assert page.run(
            "[...document.querySelectorAll('#extra-tabs [role=tab]')].map((t) => t.textContent)"
        ) == [  # fmt: skip
            "Benchmark 每題結果",
            "歷史紀錄",
            "分享",
        ]
        page.shoot("side-tabs")

        # -- delete added questions: one or several ticked, at once; past results stay ------
        page.run("document.getElementById('bi-b-bench').open = true")
        for text in ("第二題？", "第三題？"):
            page.set_value("bi-b-bq-q", text)
            page.set_value("bi-b-bq-must", "FicTech")
            page.click("#bi-b-bq-form button[type=submit]")
            page.see("bi-b-bq-list", text)
        page.see("bi-b-bench-state", "3 題")
        assert page.run("document.getElementById('bi-b-bq-bulk') === null")
        rows = "[...document.querySelectorAll('#bi-b-bq-list tbody tr')]"
        row_of = f"{rows}.find((r) => r.textContent.includes('FicTech 是什麼'))"
        page.run(f"{row_of}.querySelector('.bi-bq-tick').click()")
        assert page.text_of("bi-b-bq-title") == "新增題目"  # ticking does not open the row
        page.see("bi-b-bq-bulk", "刪除選取的 1 題")
        page.click_text("#bi-b-bq-bulk", "刪除選取的 1 題")
        page.see("bi-b-bench-state", "2 題")
        assert all(q["question"] != "FicTech 是什麼？" for q in _questions(workspace).values())
        # The run's result for it stays readable, marked as deleted.
        page.see("extra-panel-bi-bench-detail", "FicTech 是什麼？（已刪除）")
        # Pending until commit and push, like any edit.
        page.see("bi-b-ver-pending", "測試題")
        page.run("document.querySelectorAll('#bi-b-bq-list .bi-bq-tick').forEach((t) => t.click())")
        page.see("bi-b-bq-bulk", "刪除選取的 2 題")
        page.click_text("#bi-b-bq-bulk", "刪除選取的 2 題")
        page.see("bi-b-bench-state", "0 題")
        assert _questions(workspace) == {}
        assert page.run("document.getElementById('bi-b-bq-bulk') === null")
        page.see("extra-panel-bi-bench-detail", "（已刪除）")
        page.run("document.getElementById('bi-b-bench').open = false")
        page.run("['bi-bench-detail', 'bi-history', 'bi-share'].forEach(sideClose)")

        # -- a card opens beside what it came from: no tab change, same scroll ---------------
        page.run("document.getElementById('bi-b-run').scrollIntoView()")
        before = float(page.run(SCROLL))
        assert before > 0
        card = BiStore(workspace, DATASET).card_rows()[0]
        page.run(f"biOpenCard({card['id']!r})")
        page.wait("!document.getElementById('bi-card-peek').hidden")
        page.see("bi-detail-body", str(card["name"]))
        assert page.run("bi.view") == "build"
        assert page.run("document.getElementById('bi-card-peek').contains("
                        "document.getElementById('bi-detail'))")  # fmt: skip
        assert page.run(
            "document.getElementById('bi-b-run').getBoundingClientRect().right"
            " <= document.getElementById('bi-card-peek').getBoundingClientRect().left"
        )
        page.shoot("card-beside")
        page.click("#bi-card-peek-close")
        assert page.run("document.getElementById('bi-card-peek').hidden")
        assert abs(float(page.run(SCROLL)) - before) < 400  # the page gave back its room
        # In the cards tab, the pane is the one beside its list again.
        page.run("document.getElementById('bi-b-run').scrollIntoView()")
        before = float(page.run(SCROLL))

        # -- a jump that stays has a way back to the same step and scroll position -----------
        # Step 3 has no 看卡片 of its own (G1: the 卡片 tab is above); the jump the other
        # steps' buttons make (e.g. 到卡片查看 after an import) keeps the way back.
        assert page.run("document.getElementById('bi-b-to-cards') === null")
        page.run("biJump('cards')")
        page.wait("bi.view === 'cards' && !document.getElementById('bi-back').hidden")
        page.see("bi-back-go", "步驟 3・測試")
        assert page.run("document.getElementById('bi-card-split').contains("
                        "document.getElementById('bi-detail'))")  # fmt: skip
        page.shoot("way-back")
        page.click("#bi-back-go")
        page.wait("bi.view === 'build'")
        assert page.run("document.getElementById('bi-back').hidden")
        assert page.run(
            "!document.querySelector('#bi-view-build .kp-stage[data-stage=test]').hidden"
        )
        assert abs(float(page.run(SCROLL)) - before) < 2
        assert page.run(
            "document.getElementById('bi-b-test-dash').contains("
            "document.getElementById('bi-dash-sections'))"
        )

        # The tabs do the same, and the Dashboard moves to its tab and back.
        page.click("#bi-views [data-bi-view=dashboard]")
        page.wait("bi.view === 'dashboard'")
        # The working domain is the Dashboard's domain: nothing to choose (owner 2026-11-19).
        assert page.run("document.getElementById('bi-domain-box').hidden")
        assert page.run("document.getElementById('bi-view-dashboard').contains("
                        "document.getElementById('bi-dash-sections'))")  # fmt: skip
        assert page.run("document.getElementById('bi-back').hidden")  # the tabs are the way back
        page.click("#bi-views [data-bi-view=build]")
        page.wait("bi.view === 'build'")
        assert abs(float(page.run(SCROLL)) - before) < 2

        # -- each analysis follows the working domain: no 領域 per analysis, rarer actions in 更多
        # This vault's domains are library entries (no card domain), and its analyses narrow only
        # by the card domain: each says so instead of offering a run into an empty chart.
        page.click("#bi-b-tab-dash-tab")
        page.run("document.getElementById('bi-b-an').open = true")
        rows = "[...document.querySelectorAll('#bi-b-an-list tbody tr:not(.bi-detail-row)')]"
        page.wait(f"{rows}.length > 0")
        unsupported = f"{rows}.filter((r) => r.textContent.includes('不支援依資料夾篩選'))"
        assert page.run(f"{unsupported}.length") > 0
        assert page.run(
            f"{unsupported}.every((r) => ![...r.querySelectorAll("
            "':scope td > .bi-actions > button')].some((b) => b.textContent === '執行'))"
        )
        assert page.run(f"{rows}[0].querySelector('details.bi-row-menu').textContent"
                        ".includes('和 AI 一起修改')")  # fmt: skip
        assert page.run("document.querySelector('#bi-b-an-list [data-param=domain]') === null")
        assert page.run("biDashDomain()") == page.run(
            "biScopeDomain() || biScope().split('/').pop()"
        )

        # -- every analysis action works (owner 2026-11-20: 加到這個領域 and 刪除 did nothing) ---
        buttons = "[...document.querySelectorAll('#bi-b-an-list button')]"
        add = f"{buttons}.find((b) => b.textContent === '加到這個領域')"
        if page.run(f"Boolean({add})"):
            label = page.run(f"{add}.getAttribute('aria-label')")
            page.run(f"{add}.click()")
            page.notice("已改 Dashboard 的順序")
            gone = f"!{buttons}.some((b) => b.getAttribute('aria-label') === {label!r})"
            page.wait(gone)
        count = int(page.run(f"{rows}.length"))
        page.run(f"{buttons}.find((b) => b.textContent === '刪除').click()")
        page.notice("已刪除分析")
        page.wait(f"{rows}.length === {count - 1}")

        # -- the AI sessions of the step open as tabs of the side area -----------------------
        tabs = "[...document.querySelectorAll('#extra-tabs [role=tab]')].map((t) => t.textContent)"
        page.run(f"{buttons}.find((b) => b.textContent === '和 AI 一起修改').click()")
        page.wait(f"{tabs}.includes('和 AI 修改分析')")
        assert page.run("document.getElementById('bi-ai').closest('.extra-panel') !== null")
        page.run(f"{buttons}.find((b) => b.textContent === '和 AI 一起修改').click()")
        assert page.run(f"{tabs}.length") == 1, "the same session again only focuses its tab"
        page.shoot("analysis-ai-tab")
        page.click("#bi-b-tab-bench-tab")
        page.run("document.getElementById('bi-b-bench').open = true")
        page.click("#bi-b-qa-open")
        page.wait(f"{tabs}.includes('和 AI 出測試題')")
        _two_sessions_side_by_side(page, tabs)

        # -- no tab left, and the page's panel is back home -------------------------------------
        page.wait("document.getElementById('extra-area').hidden")
        assert page.run("document.getElementById('bi-ai').closest('#kn-pane-bi') !== null")


def _two_sessions_side_by_side(page: BiPage, tabs: str) -> None:
    """Two AI sessions open at once, each in its own side tab (owner 2026-11-20).

    The analysis session uses the page's #bi-ai; the questions session a copy whose ids end in
    its own suffix. A send in one shows its progress and reply only in its own panel, even with
    the other tab in front; re-opening focuses; closing one leaves the other working.
    """
    # Both stay open: the second did not take the place of the first.
    assert page.run(f"{tabs}") == ["和 AI 修改分析", "和 AI 出測試題"]
    of = "bi.ais.get([...bi.ais.keys()].find((k) => k.includes(':{}:'))).sfx"
    sfx = page.run(of.format("questions"))
    assert sfx, "the second session has its own ids"
    assert page.run(of.format("analysis")) == ""
    for base in ("bi-ai", "bi-ai-msg", "bi-ai-log", "bi-ai-send", "bi-ai-status"):
        assert page.run(f"document.querySelectorAll('[id={base}]').length") == 1, base
        assert page.run(f"document.querySelectorAll('[id={base}{sfx}]').length") == 1, base
    assert page.run(f"document.getElementById('bi-ai{sfx}').closest('.extra-panel') !== null")
    assert page.run("document.getElementById('bi-ai').closest('.extra-panel') !== null")
    assert page.run(f"document.querySelector('label[for=bi-ai-msg{sfx}]') !== null")

    # The model is held back so the questions turn is still running while the person goes on.
    page.run(
        "window.__biCall = biCall; window.__held = []; window.__auto = false;"
        "biCall = (path, body) => {"
        "  if (!(path === '/api/bi/sessions' || path.endsWith('/turns')))"
        "    return window.__biCall(path, body);"
        "  const answer = path.endsWith('/turns')"
        "    ? {session: {id: 's-q', turns: [{role: 'user', text: body.message},"
        "       {role: 'assistant', sent: {}}]}}"
        "    : {session: {id: 's-q', turns: []}};"
        "  if (window.__auto) return Promise.resolve(answer);"
        "  return new Promise((resolve) => window.__held.push(() => resolve(answer)));"
        "};"
    )
    page.run("document.getElementById('bi-ai-msg').value = '分析這邊還沒送出'")
    page.set_value(f"bi-ai-msg{sfx}", "出兩題")
    page.click(f"#bi-ai-send{sfx}")
    # Its progress (AGENTS.md 23) beside its own 送出, and nothing in the other panel.
    page.wait(f"document.getElementById('bi-ai-status{sfx}').textContent.includes('秒')")
    assert page.run(f"document.getElementById('bi-ai-send{sfx}').disabled")
    assert page.run("document.getElementById('bi-ai-status').hidden")
    assert not page.run("document.getElementById('bi-ai-send').disabled")
    analysis_log = page.text_of("bi-ai-log")

    # The other tab comes to the front while the reply is still on its way.
    page.run(
        "[...document.querySelectorAll('#extra-tabs [role=tab]')]"
        ".find((t) => t.textContent === '和 AI 修改分析').click()"
    )
    assert page.run("document.getElementById('bi-ai').offsetParent !== null")
    page.wait("window.__held.length > 0")
    page.run("window.__auto = true; window.__held.splice(0).forEach((go) => go())")
    page.wait(f"document.getElementById('bi-ai-log{sfx}').textContent.includes('出兩題')")
    page.wait(f"document.getElementById('bi-ai-status{sfx}').hidden")
    assert not page.run(f"document.getElementById('bi-ai-send{sfx}').disabled")
    assert page.text_of("bi-ai-log") == analysis_log
    assert "出兩題" not in page.text_of("bi-ai-log")
    assert page.run("document.getElementById('bi-ai-msg').value") == "分析這邊還沒送出"

    # Opening the questions session again focuses its tab, and adds none.
    page.click("#bi-b-qa-open")
    page.wait(f"document.getElementById('bi-ai{sfx}').offsetParent !== null")
    assert page.run(f"{tabs}.length") == 2
    assert "出兩題" in page.text_of(f"bi-ai-log{sfx}")

    # Closing the analysis tab ends only that session; the questions one still sends.
    page.click("#bi-ai-close")
    page.wait(f"{tabs}.length === 1")
    assert page.run(f"{tabs}") == ["和 AI 出測試題"]
    assert page.run("document.getElementById('bi-ai').hidden")
    assert page.run("[...bi.ais.keys()].every((k) => k.includes(':questions:'))")
    page.set_value(f"bi-ai-msg{sfx}", "再出一題")
    page.click(f"#bi-ai-send{sfx}")
    page.wait(f"document.getElementById('bi-ai-log{sfx}').textContent.includes('再出一題')")
    page.wait(f"document.getElementById('bi-ai-status{sfx}').hidden")

    # Closing the last one removes its copy; nothing keeps running for it.
    page.click(f"#bi-ai-close{sfx}")
    page.wait(f"document.getElementById('bi-ai{sfx}') === null")
    assert page.run("bi.ais.size") == 0
    assert page.run("document.querySelectorAll('tr.bi-ai-from').length") == 0
    page.run("biCall = window.__biCall")
