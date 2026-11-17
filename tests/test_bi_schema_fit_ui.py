"""Schema fit's tick in a browser: off by default, and on it shows what needs a person.
All fictional.
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
def test_a_run_checks_the_fit_only_when_ticked(
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
            approved=lambda: ("UNCLASSIFIED", "INTERNAL"),
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

            # Off unless ticked: the model is not asked.
            assert page.run("document.getElementById('bi-b-fit').checked") is False
            page.click("#bi-b-trial")
            page.see("bi-b-trial-result", "試跑完成")
            assert "Schema fit" not in extractor.requests[-1].messages[0].text

            # Ticked: it is asked, and the review shows what needs a person.
            page.click("#bi-b-fit")
            page.click("[data-stage=method] [data-bi-next=review]")
            page.wait(
                "!document.querySelector('#bi-view-build .kp-stage[data-stage=review]').hidden"
            )
            page.click("#bi-b-start")
            page.see("bi-b-chips", QUESTION)
            page.see("bi-b-chips", "不適合現有 schema")
            assert any("Schema fit" in r.messages[0].text for r in extractor.requests)
