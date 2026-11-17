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
        assert page.run("!document.getElementById('bi-b-bench').open")
        assert page.run("!document.getElementById('bi-b-an').open")
        run_button = "document.getElementById('bi-b-bench-run')"
        assert page.run(f"{run_button}.closest('details') === null")
        assert page.run(f"{run_button}.offsetHeight >= 52")
        assert page.run(
            f"{run_button}.getBoundingClientRect().top < innerHeight"
            f" && {run_button}.getBoundingClientRect().top"
            " > document.getElementById('bi-b-an').getBoundingClientRect().bottom"
        )
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
        page.click("#bi-b-bq-del")
        page.see("bi-b-bench-state", "0 題")
        assert _questions(workspace) == {}
        page.see("bi-b-bq-title", "新增題目")
        page.set_value("bi-b-bq-q", "FicTech 是什麼？")
        page.set_value("bi-b-bq-must", "FicTech")
        page.click("#bi-b-bq-form button[type=submit]")
        page.see("bi-b-bq-list", "FicTech 是什麼")

        # -- the run, and the results beside the Dashboard, with nothing opened ---------------
        page.run("document.getElementById('bi-b-bench').open = false")
        page.wait(f"!{run_button}.disabled")
        page.click("#bi-b-bench-run")
        page.see("bi-b-bench-report", "完成")
        assert page.run("document.querySelector('#bi-b-bench-report table') !== null")
        page.wait(
            "document.getElementById('bi-b-test-dash').contains("
            "document.getElementById('bi-dash-sections'))"
        )
        page.wait("document.getElementById('bi-dash-sections').children.length > 0")
        assert page.run(
            "document.getElementById('bi-b-test-dash').getBoundingClientRect().left"
            " >= document.getElementById('bi-b-bench-report').getBoundingClientRect().right"
        )
        assert page.run("document.getElementById('bi-b-to-dash') === null")
        # The commit decision stays right below.
        assert page.run(
            "document.getElementById('bi-b-ver').getBoundingClientRect().top"
            " >= document.getElementById('bi-b-test-results').getBoundingClientRect().bottom"
        )
        page.shoot("results-and-dashboard")

        # -- a card opens beside what it came from: no tab change, same scroll ---------------
        page.run("document.getElementById('bi-b-ver').scrollIntoView()")
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
            "document.getElementById('bi-b-ver').getBoundingClientRect().right"
            " <= document.getElementById('bi-card-peek').getBoundingClientRect().left"
        )
        page.shoot("card-beside")
        page.click("#bi-card-peek-close")
        assert page.run("document.getElementById('bi-card-peek').hidden")
        assert abs(float(page.run(SCROLL)) - before) < 400  # the page gave back its room
        # In the cards tab, the pane is the one beside its list again.
        page.run("document.getElementById('bi-b-ver').scrollIntoView()")
        before = float(page.run(SCROLL))

        # -- a jump that stays has a way back to the same step and scroll position -----------
        page.click("#bi-b-to-cards")
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
        assert page.run("document.getElementById('bi-view-dashboard').contains("
                        "document.getElementById('bi-dash-sections'))")  # fmt: skip
        assert page.run("document.getElementById('bi-back').hidden")  # the tabs are the way back
        page.click("#bi-views [data-bi-view=build]")
        page.wait("bi.view === 'build'")
        assert abs(float(page.run(SCROLL)) - before) < 2
