"""The review table with 180 candidates, in a real browser (`docs/phases/BI_PAGE_SIMPLE.md` §8).

A reading run started through the API, as the real one is, an ordinary ingest run beside it and
a reading trial, all on fictional cards in a vault. The combobox opens each; a selected row shows
its source and quote beside the table; a decision moves on to the next row still undecided.
Screenshots in `review-table/` with `AEP_UI_SHOTS`.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_ai_runs import Jobs, _runtime
from test_bi_build_ui import TECH_CSV
from test_bi_card_page_import import _apply, _preview
from test_bi_extract import Scripted
from test_bi_vault import _call, _ok
from test_bi_vault_sources import FOLDER
from test_vault_asking_e2e import _bi_host, _Model, _served

from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStore
from host_runtime.bi_cards_api import route

MANY = 180
ACCOUNTS = 30  # of MANY; the rest are Technology


def _page(index: int) -> dict[str, str]:
    kind = "account" if index < ACCOUNTS else "technology"
    text = (
        f"---\ntype: {kind}\nname: FAKE-{index:03d}\n---\n\n## 說明\n"
        + "前面的一段文字。\n" * 12
        + f"虛構項目 {index} 用於虛構工廠的即時控制。\n"
        + "後面的一段文字。\n" * 12
    )
    return {"path": f"BI/Fake/p{index}.md", "text": text}


def _answer(text: str) -> dict[str, Any]:
    found = re.search(r"虛構項目 (\d+) 用於虛構工廠的即時控制", text)
    assert found is not None
    return {"summary": {"value": f"虛構項目 {found[1]} 的讀法。", "quote": found[0], "reason": "r"}}


def _reading(workspace: Path, dataset: str, **given: Any) -> str:
    jobs = Jobs()
    body = {"dataset": dataset, "reading": True, "fresh": True, **given}
    ai = _runtime(Scripted(_answer), jobs)
    answer = route(workspace, "alice", "POST", "/api/bi/runs", {}, body, None, ai)
    run_id = str(_ok(answer)["run"]["id"])
    jobs.run_all()
    return run_id


def _vault(tmp_path: Path, workspace: Path, pages: list[dict[str, str]]) -> str:
    shared = tmp_path / "sharepoint"
    shared.mkdir()
    made = _ok(
        _call(workspace, "POST", "/api/bi/vaults",
              {"path": str(shared), "title": "Fake", "schema": "bi.schema/v1.1",
               "author": "alice"})
    )  # fmt: skip
    dataset = str(made["vault"]["dataset"])
    _apply(workspace, _preview(workspace, dataset, pages, folder=FOLDER)["preview_id"])
    return dataset


def _review(page: BiPage, dataset: str) -> None:
    page.click("#bi-views [data-bi-view=build]")
    page.run(
        f"window.__opened = false; bi.want = {json.dumps(dataset)};"
        " biLoad().then(() => { window.__opened = true; }); 0"
    )
    page.wait("window.__opened")
    page.click("#bi-stepper [data-stage=ingest]")
    page.wait("!document.querySelector('#bi-build-steps [data-stage=review]').disabled")
    page.stage("review")


def _rows(page: BiPage) -> int:
    return int(page.run("document.querySelectorAll('#bi-b-cands tbody tr[data-candidate]').length"))


def _choose(page: BiPage, select: str, value: str) -> None:
    page.run(
        f"(() => {{ const s = document.getElementById({json.dumps(select)});"
        f" s.value = {json.dumps(value)}; s.dispatchEvent(new Event('change')); }})()"
    )


def _selected(page: BiPage) -> str:
    return str(
        page.run(
            "(document.querySelector('#bi-b-cands tr[aria-selected=true] button') || {})"
            ".textContent || ''"
        )
    )


def _press(page: BiPage, label: str) -> None:
    page.click_text("#bi-b-cand", label)


def _rect(page: BiPage, selector: str) -> dict[str, float]:
    found = page.run(
        f"JSON.stringify(document.querySelector({json.dumps(selector)}).getBoundingClientRect())"
    )
    return dict(json.loads(str(found)))


def _counted(page: BiPage, text: str) -> None:
    page.wait(page.shows("bi-b-cand-count", text))


def _shown(page: BiPage, count: int) -> None:
    page.wait(f"document.querySelectorAll('#bi-b-cands tbody tr').length === {count}")


def _stage_shown(page: BiPage, stage: str) -> None:
    page.wait(f"!document.querySelector('#bi-view-build .kp-stage[data-stage={stage}]').hidden")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_reading_run_of_180_is_opened_worked_through_and_written(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    dataset = _vault(tmp_path, workspace, [_page(i) for i in range(MANY)])
    run_id = _reading(workspace, dataset, kind="ingest")
    store = BiStore(workspace, dataset)
    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "review-table" if shots else None
        ) as page:
            # No source chosen, and still the step opens: this run has no one source.
            started = time.monotonic()
            _review(page, dataset)
            _shown(page, MANY)
            print(f"\n{MANY} candidates open in {time.monotonic() - started:.2f} s")
            drawing = page.run(
                "(() => { const t = performance.now(); biBuildRenderRun();"
                " return performance.now() - t; })()"
            )
            print(f"one redraw of {MANY} rows: {float(drawing):.0f} ms")
            assert float(drawing) < 1000
            assert page.run("document.getElementById('bi-b-run-pick').value") == run_id
            assert "補摘要" in page.text_of("bi-b-run-pick")
            assert page.text_of("bi-b-cand-count") == f"顯示 {MANY}／{MANY}・待決定 {MANY}"
            heads = page.run(
                "[...document.querySelectorAll('#bi-b-cands thead th')]"
                ".map(h => h.textContent).join()"
            )
            assert heads == "卡片,欄位,提議值,狀態"
            page.shoot("opened")

            # -- its own scroller: 180 rows do not push the page ------------------------------
            split, table = _rect(page, "#bi-b-review-split"), _rect(page, "#bi-b-cands")
            assert table["height"] > split["height"]
            assert page.run("document.documentElement.scrollHeight < 3 * innerHeight")

            # -- a selected row: the value, then the source with the quote marked, beside it --
            page.click("#bi-b-cands tbody tr[data-candidate]:nth-child(100) button")
            page.wait("!!document.querySelector('#bi-b-cand-src mark')")
            chosen = _selected(page)
            number = int(chosen.removeprefix("FAKE-"))
            assert chosen in page.text_of("bi-b-cand")
            assert f"虛構項目 {number} 的讀法" in page.text_of("bi-b-cand")
            assert page.text_of("bi-b-cand-src").count("前面的一段文字") == 12
            assert str(page.run("document.querySelector('#bi-b-cand-src mark').textContent")) == (
                f"虛構項目 {number} 用於虛構工廠的即時控制"
            )
            assert _rect(page, "#bi-b-cand")["left"] > _rect(page, "#bi-b-cands")["right"] - 1
            mark, source = _rect(page, "#bi-b-cand-src mark"), _rect(page, "#bi-b-cand-src")
            assert source["top"] <= mark["top"] < source["top"] + source["height"] / 2, (
                "the quote is not brought near the top of the source"
            )
            assert 0 <= _rect(page, "#bi-b-cand")["top"]
            assert _rect(page, "#bi-b-cand")["bottom"] <= 1001, "the pair is not in view"
            page.shoot("selected")

            # -- a decision moves on to the next row, and keeps the row in sight -------------
            _press(page, "接受")
            _counted(page, f"待決定 {MANY - 1}")
            second = _selected(page)
            assert second and second != chosen
            page.wait("!!document.querySelector('#bi-b-cand-src mark')")
            page.see("bi-b-cand", second)
            _press(page, "拒絕")
            _counted(page, f"待決定 {MANY - 2}")
            third = _selected(page)
            assert third not in ("", chosen, second)
            row = _rect(page, "#bi-b-cands tr[aria-selected=true]")
            scroller = _rect(page, "#bi-b-review-split .bi-scroller")
            assert scroller["top"] <= row["top"] < scroller["bottom"]

            # -- filters: by type, then what is not decided ----------------------------------
            _choose(page, "bi-b-cand-type", "Account")
            _counted(page, f"顯示 {ACCOUNTS}／{MANY}")
            shown = page.text_of("bi-b-cands")
            assert "FAKE-000" in shown and f"FAKE-{ACCOUNTS:03d}" not in shown
            assert _rows(page) == ACCOUNTS
            _choose(page, "bi-b-cand-type", "")
            _choose(page, "bi-b-cand-state", "pending")
            _shown(page, MANY - 2)
            assert chosen not in page.text_of("bi-b-cands")
            page.shoot("filtered")
            _choose(page, "bi-b-cand-state", "rejected")
            _shown(page, 1)
            assert second in page.text_of("bi-b-cands")
            _choose(page, "bi-b-cand-state", "")

            # -- back here later, it is still open with what was decided ----------------------
            page.run("bi.loaded = {}; biShowView('build'); 0")
            page.wait("document.getElementById('bi-status-build').hidden")
            _shown(page, MANY)
            assert page.run("document.getElementById('bi-b-run-pick').value") == run_id
            assert f"待決定 {MANY - 2}" in page.text_of("bi-b-cand-count")

            # -- everything without an error, measured ---------------------------------------
            one = str(store.card_rows()[0]["id"])
            before = store.fields(one)
            started = time.monotonic()
            page.click("#bi-b-accept-clean")
            page.notice(f"已接受 {MANY - 2} 張")
            print(f"accepted {MANY - 2} in {time.monotonic() - started:.1f} s")
            assert page.run("document.getElementById('bi-b-accept-clean').textContent.trim()") == (
                "接受所有沒有錯誤的候選卡"
            )
            assert "待決定 0" in page.text_of("bi-b-cand-count")
            page.see("bi-b-chips", f"已接受 {MANY - 1}")
            assert store.fields(one) == before  # review writes nothing

            # -- written through the ordinary commit: only the empty field, on those accepted --
            page.click("#bi-b-next4")
            _stage_shown(page, "commit")
            page.click("#bi-b-commit-go")
            _stage_shown(page, "result")
            page.see("bi-b-done", "已寫入")
            filled = [
                str(c["name"]) for c in store.card_rows() if "summary" in store.fields(str(c["id"]))
            ]
            assert len(filled) == MANY - 1 and second not in filled

            # -- written, it no longer waits ---------------------------------------------------
            page.run("bi.build.run = null; biBuildStage('review'); 0")
            page.see("bi-b-run-pick", "沒有待審核的執行")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_combobox_opens_an_ordinary_run_and_a_reading_trial_too(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    dataset = _vault(tmp_path, workspace, [_page(i) for i in range(40, 44)])
    source = Staging(workspace, dataset).add_source(
        "tech.csv", text=TECH_CSV, actor="alice", folder=FOLDER
    )
    reading = _reading(workspace, dataset, kind="ingest")
    trial = _reading(workspace, dataset, kind="trial")
    # A page's own trial of a source is read in its step, and is no entry here.
    ordinary_trial = _ok(
        _call(workspace, "POST", "/api/bi/runs",
              {"dataset": dataset, "kind": "trial", "source_id": source["id"]})
    )["run"]["id"]  # fmt: skip
    ordinary = _ok(
        _call(workspace, "POST", "/api/bi/runs",
              {"dataset": dataset, "kind": "ingest", "source_id": source["id"]})
    )["run"]["id"]  # fmt: skip
    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "review-table" if shots else None
        ) as page:
            _review(page, dataset)
            page.wait("document.querySelectorAll('#bi-b-run-pick option').length === 3")
            ids = page.run(
                "[...document.querySelectorAll('#bi-b-run-pick option')].map(o => o.value)"
            )
            assert sorted(ids) == sorted([reading, trial, ordinary])
            assert ordinary_trial not in ids

            # An ordinary run: its evidence, its source, and its commit are as before.
            _choose(page, "bi-b-run-pick", ordinary)
            _shown(page, 2)
            assert "EtherCAT" in page.text_of("bi-b-cands")
            assert "tech.csv" in page.text_of("bi-b-run-pick")
            page.click("#bi-b-cands button")
            page.see("bi-b-cand", "有出處")
            page.wait("!!document.getElementById('bi-b-cand-src')")
            page.shoot("ordinary")
            assert "EtherCAT" in page.text_of("bi-b-cand-src")
            _press(page, "接受")
            _counted(page, "待決定 1")
            assert _selected(page), "the next row opens"
            page.wait("!document.getElementById('bi-b-next4').disabled")

            # Another run opens with no filter left behind and nothing selected.
            _choose(page, "bi-b-cand-state", "accepted")
            _shown(page, 1)
            _choose(page, "bi-b-run-pick", reading)
            _shown(page, 4)
            assert _selected(page) == ""
            assert page.run("document.getElementById('bi-b-cand-state').value") == ""
            assert page.run("document.getElementById('bi-b-next4').disabled")

            # A trial is read, and cannot be decided or written.
            _choose(page, "bi-b-run-pick", trial)
            page.see("bi-b-chips", "試跑，不能寫入")
            _shown(page, 4)
            page.click("#bi-b-cands button")
            page.wait("!!document.querySelector('#bi-b-cand-src mark')")
            page.shoot("trial")
            detail = page.text_of("bi-b-cand")
            assert "接受" not in detail and "拒絕" not in detail
            assert page.run("document.getElementById('bi-b-accept-clean').disabled")
            assert page.run(
                "document.querySelector('#bi-build-steps [data-stage=commit]').disabled"
            )

            # On a phone the pair stacks, and nothing runs off the side.
            page.browser.page().call(
                "Emulation.setDeviceMetricsOverride",
                width=390,
                height=844,
                deviceScaleFactor=1,
                mobile=False,
            )
            page.wait("innerWidth === 390")
            _choose(page, "bi-b-run-pick", reading)
            page.wait(f"bi.build.run.id === {json.dumps(reading)}")
            page.wait("document.querySelectorAll('#bi-b-cand-src').length === 0")
            page.click("#bi-b-cands button")
            page.wait("!!document.querySelector('#bi-b-cand-src mark')")
            page.shoot("phone-detail")
            assert _rect(page, "#bi-b-cand")["top"] >= _rect(page, "#bi-b-cands")["bottom"] - 1
            assert 0 <= _rect(page, "#bi-b-cand")["top"] < 844, "the pane is out of view"
            page.wait(
                "document.querySelector('#bi-b-review-split').getBoundingClientRect().right <= 391"
            )


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_with_no_run_the_step_stays_shut_until_a_source_is_chosen(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    _ok(_call(workspace, "POST", "/api/bi/datasets", {"name": "lab", "schema": "bi.schema/v1.1"}))
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            page.click("#bi-views [data-bi-view=build]")
            page.wait("document.getElementById('bi-status-build').hidden")
            assert page.run(
                "document.querySelector('#bi-build-steps [data-stage=review]').disabled"
            )


def _hold(page: BiPage, part: str) -> None:
    """Requests naming `part` wait until `_free`."""
    page.run(
        "(() => { const real = window.__realFetch = window.fetch; let free;"
        " const gate = new Promise((go) => { free = go; }); window.__free = free;"
        " window.fetch = async (u, o) => {"
        f" if (String(u).includes({json.dumps(part)})) await gate; return real(u, o); }}; }})()"
    )


def _free(page: BiPage) -> None:
    page.run("window.__free(); window.fetch = window.__realFetch")


def _row(name: str) -> str:
    """An expression for the row of the card named `name`."""
    return (
        "[...document.querySelectorAll('#bi-b-cands tbody tr')]"
        f".find((r) => r.textContent.includes({json.dumps(name)}))"
    )


def _button(row: str, label: str) -> str:
    """An expression for the button in `row` whose text holds `label`."""
    return f"[...{row}.querySelectorAll('button')].find((b) => b.textContent.includes('{label}'))"


def _colour(page: BiPage, selector: str) -> str:
    return str(page.run(f"getComputedStyle(document.querySelector({json.dumps(selector)})).color"))


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_decision_shows_at_once_stays_after_a_reload_and_a_failure_says_so(
    tmp_path: Path,
) -> None:
    """Owner: 「按接受沒反應，是不是可以有藍色小勾勾之類的東西，來代表被接受過」."""
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    dataset = _vault(tmp_path, workspace, [_page(i) for i in range(40, 46)])
    _reading(workspace, dataset, kind="ingest")
    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "review-table" if shots else None
        ) as page:
            _review(page, dataset)
            _shown(page, 6)
            page.click("#bi-b-cands tbody tr[data-candidate]:nth-child(2) button")
            page.see("bi-b-cand", "FAKE-041")

            # -- with the request still out, the row already says so, and moving on is shut ----
            _hold(page, "/candidates/")
            _press(page, "接受")
            assert page.run(f"!!{_row('FAKE-041')}.querySelector('.bi-state-accepted')")
            assert "已接受" in str(page.run(f"{_row('FAKE-041')}.textContent"))
            assert "✓" in str(page.run(f"{_row('FAKE-041')}.textContent"))
            assert "FAKE-041" in page.text_of("bi-b-cand-last")
            assert "已接受" in page.text_of("bi-b-cand-last")
            assert _selected(page) == "FAKE-042"
            assert page.run("document.getElementById('bi-b-next4').disabled")
            _free(page)
            page.wait("!document.getElementById('bi-b-next4').disabled")
            page.see("bi-b-chips", "已接受 1")

            # -- rejecting has its own mark; the check is blue, and neither is the other ------
            _press(page, "拒絕")
            page.wait(f"!!{_row('FAKE-042')}.querySelector('.bi-state-rejected')")
            assert "✕" in str(page.run(f"{_row('FAKE-042')}.textContent"))
            page.wait("!bi.build.saving")
            accepted = _colour(page, "#bi-b-cands .bi-state-accepted .bi-state-icon")
            rejected = _colour(page, "#bi-b-cands .bi-state-rejected .bi-state-icon")
            accent = page.run(
                "(() => { const probe = document.createElement('span');"
                " probe.style.color = 'var(--accent)'; document.body.append(probe);"
                " const seen = getComputedStyle(probe).color; probe.remove(); return seen; })()"
            )
            assert accepted == accent and rejected != accepted
            page.shoot("decided")

            # -- reopened, the pane says what was decided --------------------------------------
            page.run(f"{_row('FAKE-041')}.querySelector('button').click()")
            page.see("bi-b-cand", "FAKE-041")
            assert page.run("!!document.querySelector('#bi-b-cand .bi-state-accepted')")
            page.shoot("reopened")

            # -- a real reload: the decisions, the run, the step and the row are all still there -
            page.browser.navigate(server.address)
            page.wait('!document.getElementById("send").disabled')
            page.click("#nav-knowledge")
            page.click("#kn-tabs [data-kn=bi]")
            page.click("#bi-views [data-bi-view=build]")
            _stage_shown(page, "review")
            _shown(page, 6)
            assert page.run(f"!!{_row('FAKE-041')}.querySelector('.bi-state-accepted')")
            assert page.run(f"!!{_row('FAKE-042')}.querySelector('.bi-state-rejected')")
            page.wait(f"{_row('FAKE-041')}.getAttribute('aria-selected') === 'true'")
            page.see("bi-b-cand", "FAKE-041")
            assert page.run("!!document.querySelector('#bi-b-cand .bi-state-accepted')")
            page.shoot("reloaded")

            # -- a decision the server refused is not left looking made ------------------------
            page.run(f"{_row('FAKE-043')}.querySelector('button').click()")
            page.see("bi-b-cand", "FAKE-043")
            page.run(
                "(() => { const real = window.fetch; window.__realFetch = real;"
                " window.fetch = (u, o) => String(u).includes('/candidates/')"
                ' ? Promise.resolve(new Response(\'{"code":"boom","message":"存不了"}\','
                " {status: 500})) : real(u, o); })()"
            )
            _press(page, "接受")
            page.notice("存不了")
            page.run("window.fetch = window.__realFetch")
            assert not page.run(f"!!{_row('FAKE-043')}.querySelector('.bi-state-accepted')")
            assert _selected(page) == "FAKE-043"
            assert "待決定 4" in page.text_of("bi-b-cand-count")


LINKED_NOTE = (
    "# 會議\n\n日期：2026-10-01\n前面的文字。\n客戶提到 FAKE-040 正在評估。\n"
    + "後面的文字。\n" * 40
)
LINKED = {
    "candidates": [
        {
            "entity_type": "Signal",
            "name": f"訊號-{index}",
            "fields": {
                "date": {"value": "2026-10-01", "basis": "fact", "quote": "日期：2026-10-01"},
                "summary": {
                    "value": f"摘要 {index}",
                    "basis": "fact",
                    "quote": "客戶提到 FAKE-040 正在評估",
                },
                "source": {"value": "會議", "basis": "fact", "quote": "前面的文字"},
                "related": {
                    "value": ["FAKE-040", "沒有這張卡"],
                    "basis": "fact",
                    "quote": "FAKE-040",
                },
            },
        }
        for index in range(30)
    ]
}


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_links_in_the_card_under_review_open_beside_it_and_keep_the_place(tmp_path: Path) -> None:
    """Owner: 「卡片中要有連結，以方便使用者review」; the table and the row stay as they were."""
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    dataset = _vault(tmp_path, workspace, [_page(40), _page(41)])
    source = Staging(workspace, dataset).add_source(
        "會議.md", text=LINKED_NOTE, actor="alice", folder=FOLDER
    )
    jobs = Jobs()
    body = {"dataset": dataset, "kind": "ingest", "source_id": source["id"], "path": "ai"}
    ai = _runtime(Scripted(LINKED), jobs)
    _ok(route(workspace, "alice", "POST", "/api/bi/runs", {}, body, None, ai))
    jobs.run_all()
    target = "FAKE-040"
    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "review-table" if shots else None
        ) as page:
            _review(page, dataset)
            _shown(page, 30)
            page.run(f"{_row('訊號-20')}.querySelector('button').click()")
            page.wait("!!document.querySelector('#bi-b-cand-src mark')")
            page.see("bi-b-cand", "第 ")  # a place in the source, in words
            assert "line_start" not in page.text_of("bi-b-cand")
            place = "document.querySelector('#bi-b-review-split .bi-scroller').scrollTop"
            page.run(f"{place} = 400; 0")

            def in_place() -> None:
                assert _selected(page) == "訊號-20"
                assert page.run(f"{place}") == 400
                assert not page.run(
                    "document.querySelector('#bi-view-build .kp-stage[data-stage=review]').hidden"
                )

            # -- a value naming a card links to it; one naming no card stays plain text --------
            links = "[...document.querySelectorAll('#bi-b-cand .bi-card-link')]"
            page.wait(f"{links}.length === 1")
            assert page.run(f"{links}[0].textContent") == target
            assert "沒有這張卡" in page.text_of("bi-b-cand")

            # -- it opens beside the table, with a way back --------------------------------------
            page.run(f"{links}[0].click()")
            page.wait("!!document.getElementById('bi-b-peek')")
            page.see("bi-b-peek", target)
            page.see("bi-b-peek", "回到候選卡")
            in_place()
            page.shoot("linked-card")
            page.click("#bi-b-peek-back")
            page.see("bi-b-cand", "訊號-20")
            page.wait("!!document.querySelector('#bi-b-cand-src mark')")
            assert not page.run("!!document.getElementById('bi-b-peek')")
            in_place()

            # -- the card under review is new here, so no link to a card that is not there -------
            assert not page.run("!!document.getElementById('bi-b-cand-current')")

            # -- a source's name opens that source, at that field's quote -------------------------
            sources = "[...document.querySelectorAll('#bi-b-cand .bi-source-link')]"
            page.wait(f"{sources}.length >= 2")
            assert page.run(f"{sources}.every((b) => b.textContent === '會議.md')")
            page.run(
                f"{sources}.find((b) => b.closest('td').textContent.includes('前面的文字')).click()"
            )
            page.wait("document.querySelector('#bi-b-cand-src mark').textContent === '前面的文字'")
            page.see("bi-b-cand", "原文：會議.md")
            in_place()
            page.shoot("source-link")

            # -- pressing another row while a card is open goes to that row, no dead end ---------
            page.run(f"{links}[0].click()")
            page.wait("!!document.getElementById('bi-b-peek')")
            page.run(f"{_row('訊號-21')}.querySelector('button').click()")
            page.see("bi-b-cand", "訊號-21")
            assert not page.run("!!document.getElementById('bi-b-peek')")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_card_being_updated_links_to_itself_as_it_stands_now(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    dataset = _vault(tmp_path, workspace, [_page(40), _page(41)])
    _reading(workspace, dataset, kind="ingest")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            _review(page, dataset)
            _shown(page, 2)
            page.click("#bi-b-cands button")
            page.wait("!!document.getElementById('bi-b-cand-current')")
            page.click("#bi-b-cand-current")
            page.wait("!!document.getElementById('bi-b-peek')")
            page.see("bi-b-peek", "FAKE-040")
            # Its page came in as a source: that opens here as well, back still there.
            page.wait("!!document.querySelector('#bi-b-peek .bi-source-link')")
            page.click("#bi-b-peek .bi-source-link")
            page.wait("!!document.getElementById('bi-b-cand-src')")
            page.see("bi-b-cand-src", "虛構項目 40")
            assert page.run("!!document.getElementById('bi-b-peek-back')")
            assert _selected(page) == "FAKE-040"


LONG_BODY = "這段長文是虛構卡片目前的內容，有它自己的出處。" * 12
SHORT_BODY = "一句話。"
LONG_NOTE = f"# 長文\n\n{LONG_BODY}\n"
SHORT_NOTE = f"# 短文\n\n{SHORT_BODY}\n"


def _replacing(index: int, value: str) -> dict[str, Any]:
    return {
        "candidates": [
            {
                "entity_type": "Technology",
                "name": f"FAKE-{index:03d}",
                "fields": {"body": {"value": value, "basis": "fact", "quote": value}},
            }
        ]
    }


def _written_run(workspace: Path, dataset: str, name: str, note: str, answer: Any) -> None:
    """An AI run through the routes, accepted and written."""
    source = Staging(workspace, dataset).add_source(name, text=note, actor="alice", folder=FOLDER)
    jobs = Jobs()
    body = {"dataset": dataset, "kind": "ingest", "source_id": source["id"], "path": "ai"}
    ai = _runtime(Scripted(answer), jobs)
    run = _ok(route(workspace, "alice", "POST", "/api/bi/runs", {}, body, None, ai))["run"]
    jobs.run_all()
    found = _ok(_call(workspace, "GET", f"/api/bi/runs/{run['id']}", dataset=dataset))
    for candidate in found["candidates"]:
        _ok(
            _call(workspace, "POST", f"/api/bi/runs/{run['id']}/candidates/{candidate['id']}",
                  {"dataset": dataset, "review": "accepted"})
        )  # fmt: skip
    _ok(_call(workspace, "POST", f"/api/bi/runs/{run['id']}/commit", {"dataset": dataset}))


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_accepting_a_proposal_shows_what_it_loses_and_then_that_it_was_done(
    tmp_path: Path,
) -> None:
    """A long sourced value was replaced by one line through this list, with no visible answer."""
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    dataset = _vault(tmp_path, workspace, [_page(40), _page(41), _page(42)])
    for index in (40, 41, 42):
        # Each note its own: the same text is one source, and repeats the same kept answer.
        long_note, short_note = f"{LONG_NOTE}\n{index}\n", f"{SHORT_NOTE}\n{index}\n"
        _written_run(workspace, dataset, f"長{index}.md", long_note, _replacing(index, LONG_BODY))
        _written_run(workspace, dataset, f"短{index}.md", short_note, _replacing(index, SHORT_BODY))
    store = BiStore(workspace, dataset)
    found = store.find("Technology", "FAKE-040")
    assert found is not None
    card = str(found["id"])
    shots = os.environ.get("AEP_UI_SHOTS")
    row = (
        "[...document.querySelectorAll('#bi-b-props-list > li')]"
        ".find((r) => r.textContent.includes('FAKE-040'))"
    )
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "review-table" if shots else None
        ) as page:
            _review(page, dataset)
            page.wait(f"!!{row}")

            # -- with no run, nothing stands between the step's top and the list ----------------
            assert _rect(page, "#bi-b-review-split")["height"] == 0
            page.click("#bi-b-props-jump")
            assert page.text_of("bi-b-props-jump") == "待審提案 3 筆"
            head = _rect(page, "#bi-b-props-h")
            assert -1 <= head["top"] < 500, "the list is out of view"

            # -- side by side, whole, and what would go is said in numbers --------------------
            cells = f"[...{row}.querySelectorAll('.bi-prop-sides td')]"
            assert page.run(f"{cells}.length") == 2
            assert page.run(f"{cells}[0].textContent.includes({json.dumps(LONG_BODY)})")
            assert page.run(f"{cells}[1].textContent.includes({json.dumps(SHORT_BODY)})")
            one = page.run(f"{cells}[0].getBoundingClientRect().top")
            assert one == page.run(f"{cells}[1].getBoundingClientRect().top"), "not side by side"
            warning = str(page.run(f"{row}.querySelector('.bi-prop-loss').textContent"))
            assert f"{len(SHORT_BODY)} 字" in warning and f"{len(LONG_BODY)} 字" in warning
            assert "出處" in str(page.run(f"{row}.textContent"))
            page.shoot("proposal-before")

            # -- a value that loses text takes a second, named press --------------------------
            page.run(f"{_button(row, '接受')}.click()")
            confirm = _button(row, "確定取代")
            page.wait(f"!!{confirm}")
            assert store.fields(card)["body"]["value"] == LONG_BODY

            # -- pressed: an answer at once, and then the blue check, in the row ----------------
            _hold(page, "/proposals/")
            page.run(f"{confirm}.click()")
            assert "儲存中" in str(page.run(f"{row}.textContent"))
            _free(page)
            page.wait(f"!!{row}.querySelector('.bi-state-accepted')")
            page.see("bi-b-props-list", "要 commit")
            mark = page.run(
                f"{row}.querySelector('.bi-state-accepted').getBoundingClientRect().top"
            )
            assert 0 <= float(mark) < 1000, "the answer is out of view of the press"
            assert store.fields(card)["body"]["value"] == SHORT_BODY

            # -- it stays where it was, through the refresh that follows ------------------------
            page.wait("document.getElementById('bi-b-props-h').textContent.includes('2 筆')")
            page.wait(f"!!{row} && !!{row}.querySelector('.bi-state-accepted')")
            assert not page.run(f"[...{row}.querySelectorAll('button')].length")
            page.shoot("proposal-accepted")

            # -- rejecting has its own mark ------------------------------------------------------
            other = (
                "[...document.querySelectorAll('#bi-b-props-list > li')]"
                ".find((r) => r.textContent.includes('FAKE-041'))"
            )
            page.run(f"{other}.querySelector('input').value = '虛構的理由'; 0")
            page.run(f"{_button(other, '否決')}.click()")
            page.wait(f"!!{other}.querySelector('.bi-state-rejected')")
            kept = store.find("Technology", "FAKE-041")
            assert kept is not None and store.fields(str(kept["id"]))["body"]["value"] == LONG_BODY

            # -- the last one decided does not take the list away with its marks -----------------
            last = (
                "[...document.querySelectorAll('#bi-b-props-list > li')]"
                ".find((r) => r.textContent.includes('FAKE-042'))"
            )
            page.run(f"{last}.querySelector('input').value = '虛構的理由'; 0")
            page.run(f"{_button(last, '否決')}.click()")
            page.wait(f"!!{last}.querySelector('.bi-state-rejected')")
            page.wait("document.getElementById('bi-b-props-h').textContent.includes('0 筆')")
            assert not page.run("document.getElementById('bi-b-props').hidden")
            assert page.run(f"!!{row}.querySelector('.bi-state-accepted')")

            # -- a failure says so in the row, and nothing looks done ----------------------------
            page.run(
                "(() => { const real = window.fetch; window.__realFetch = real;"
                " window.fetch = (u, o) => String(u).includes('/proposals/')"
                ' ? Promise.resolve(new Response(\'{"code":"boom","message":"存不了"}\','
                " {status: 500})) : real(u, o); })()"
            )
            page.run(
                "el('bi-b-props-list').prepend(biProposalRow("
                "{...bi.proposalsDecided[0].item, card_name: 'FAKE-999'}, biDataset())); 0"
            )
            failing = (
                "[...document.querySelectorAll('#bi-b-props-list > li')]"
                ".find((r) => r.textContent.includes('FAKE-999'))"
            )
            page.run(f"{_button(failing, '接受')}.click()")
            confirm_failing = _button(failing, "確定取代")
            page.wait(f"!!{confirm_failing}")
            page.run(f"{confirm_failing}.click()")
            page.wait(f"{failing}.textContent.includes('存不了')")
            assert not page.run(f"!!{failing}.querySelector('.bi-state-accepted')")
            assert page.run(
                f"[...{failing}.querySelectorAll('button')].some(b => b.textContent === '接受')"
            )
            page.run("window.fetch = window.__realFetch")


def test_what_accepting_a_proposal_does_to_the_fields_evidence(tmp_path: Path) -> None:
    """As it stands, and worth knowing: the old citation stays, and the new one does not come."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    dataset = _vault(tmp_path, workspace, [_page(40)])
    _written_run(workspace, dataset, "長.md", LONG_NOTE, _replacing(40, LONG_BODY))
    _written_run(workspace, dataset, "短.md", SHORT_NOTE, _replacing(40, SHORT_BODY))
    store = BiStore(workspace, dataset)
    found = store.find("Technology", "FAKE-040")
    assert found is not None
    card = str(found["id"])
    pending = _ok(_call(workspace, "GET", "/api/bi/proposals", dataset=dataset))["proposals"]
    item = next(p for p in pending if p["field"] == "body")
    assert item["evidence"] and item["current_evidence"]
    _ok(
        _call(workspace, "POST", f"/api/bi/cards/{card}/proposals/{item['id']}",
              {"dataset": dataset, "action": "accept", "base_version": item["version"]})
    )  # fmt: skip
    field = store.fields(card)["body"]
    assert field["value"] == SHORT_BODY and field["kind"] == "human"
    cited = [e["source_name"] for e in store.evidence(card) if e["field"] == "body"]
    assert "長.md" in cited, "the replaced value's citation stays on the field"
    assert "短.md" not in cited, "the accepted value's own citation is not carried over"
    history = [h for h in store.history(card) if h["field"] == "body"]
    assert any(LONG_BODY in str(h.get("old")) for h in history), "the old value stays in history"
