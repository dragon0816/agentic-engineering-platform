"""Schema fit in a browser. The page no longer offers the tick (owner 2026-11-19, E1:
decided in BI_PAGE_SIMPLE.md §5 S2; 「建議 schema」 replaced it), so a run from the page never
asks for it; a run that does ask (the API's `check_fit`) still shows in the review what needs
a person. All fictional.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_extract import MEETING_ANSWER, NOTE, Scripted
from test_bi_vault import _call, _ok, _use_homes
from test_vault_asking_e2e import _bi_host, _Model, _served

from aep_bi.cards.ai_runs import AiRuntime
from aep_bi.host import bi_cards_api

FOLDER = "applications/aidc/sources"
QUESTION = "虛構的待釐清內容"
FITTED = {
    **MEETING_ANSWER,
    "items": [
        {
            "summary": QUESTION,
            "action": "needs_clarification",
            "reason": "無法判斷放在哪裡",
            "questions": ["這是哪一類？"],
            "quote": NOTE.strip().splitlines()[0],
        }
    ],
}


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_page_never_asks_for_the_fit_and_the_review_still_shows_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    shared = tmp_path / "sharepoint"
    shared.mkdir()
    made: dict[str, Any] = _ok(
        _call(workspace, "POST", "/api/bi/vaults",
              {"path": str(shared), "title": "Market", "schema": "bi.schema/v1.1",
               "author": "alice"})
    )  # fmt: skip
    dataset = str(made["vault"]["dataset"])
    # Only homes something is in are listed (acceptance F22): this test works in these.
    _use_homes(workspace, str(made["vault"]["id"]), "AIDC")
    extractor = Scripted(lambda _chunk: FITTED)
    monkeypatch.setattr(
        bi_cards_api,
        "web_ai_runtime",
        lambda _web: AiRuntime(
            model=lambda: (extractor, "test-model"),
            background=lambda _t, work: work(),
        ),
    )
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            page.wait(
                "[...document.getElementById('bi-dataset').options]"
                f".some((o) => o.value === {json.dumps(dataset)})"
            )
            page.run(
                "(() => { const s = document.getElementById('bi-dataset');"
                f" s.value = {json.dumps(dataset)}; s.dispatchEvent(new Event('change')); }})()"
            )
            page.click("#bi-views [data-bi-view=build]")
            page.wait("!document.getElementById('bi-b-src-folder-box').hidden")
            page.wait(
                "[...document.getElementById('bi-b-src-folder').options]"
                f".some((o) => o.value === {json.dumps(FOLDER)})"
            )
            page.set_value("bi-b-src-folder", FOLDER)
            page.upload("raw.md", NOTE, "text/markdown")
            page.stage("method")

            # No tick on the page, and a run from it does not ask the model.
            assert page.run("document.getElementById('bi-b-fit') === null")
            assert "check_fit" not in str(page.run("JSON.stringify(biRunBody('trial'))"))
            page.click("#bi-b-trial")
            page.see("bi-b-trial-result", "試跑完成")
            assert "Schema fit" not in extractor.requests[-1].messages[0].text

            # A run that asks for it (as the API allows): the review shows what needs a person.
            page.run(
                "(() => { const plain = biRunBody;"
                " biRunBody = (...given) => Object.assign(plain(...given), {check_fit: true});"
                " })()"
            )
            # 審核 shows with Ingest (owner 2026-11-20).
            page.wait(
                "!document.querySelector('#bi-view-build .kp-stage[data-stage=review]').hidden"
            )
            page.click("#bi-b-start")
            page.see("bi-b-chips", QUESTION)
            page.see("bi-b-chips", "不適合現有 schema")
            assert any("Schema fit" in r.messages[0].text for r in extractor.requests)
