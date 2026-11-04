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
            _shown(page, 4)
            page.click("#bi-b-cands button")
            page.wait("!!document.querySelector('#bi-b-cand-src mark')")
            page.shoot("phone-detail")
            assert _rect(page, "#bi-b-cand")["top"] >= _rect(page, "#bi-b-cands")["bottom"] - 1
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
