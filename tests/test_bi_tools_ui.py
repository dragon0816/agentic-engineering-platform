"""A home's tool in a browser (`BI_CARD_MODEL.md` P2-a): the person reads and approves its
code, runs it on a source, and its output goes through the same trial and review. All fictional.
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

from capabilities.bi_cards import vault
from capabilities.bi_cards.ai_runs import AiRuntime
from capabilities.bi_cards.store import BiStore
from host_runtime import bi_cards_api

FOLDER = "applications/aidc/sources"
MARK = "NORMALIZED-BY-THE-TOOL"
TOOL = f"""import os
text = open(INPUT, encoding="utf-8").read()
with open(os.path.join(OUTPUT, "normalized.md"), "w", encoding="utf-8") as out:
    out.write("<!-- {MARK} -->" + chr(10) + text)
"""


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_tool_is_approved_run_and_its_output_previewed(
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
    vault_id, dataset = str(made["vault"]["id"]), str(made["vault"]["dataset"])
    # Only homes something is in are listed (acceptance F22): this test works in these.
    _use_homes(workspace, vault_id, "AIDC")
    extractor = Scripted(lambda _chunk: MEETING_ANSWER)
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
            page.stage("schema")

            # Saved code can run immediately, without a local approval step.
            page.see("bi-b-tl-list", "還沒有資料處理程式")
            page.set_value("bi-b-tl-name", "aidc/normalize")
            page.set_value("bi-b-tl-code", TOOL)
            page.click("#bi-b-tl-save")
            page.see("bi-b-tl-list", "不需核准")
            page.see("bi-b-tl-list", "直接執行工具；若環境不支援，會顯示實際錯誤。")
            page.see("bi-b-tl-list", MARK)
            assert "看過了，核准" not in page.text_of("bi-b-tl-list")
            assert "對選取的來源執行" in page.text_of("bi-b-tl-list")
            page.click_text("#bi-b-tl-list", "對選取的來源執行")

            # The output is a new source, chosen for the steps that follow.
            page.see("bi-b-sources", "normalized.md")
            page.wait(
                "(bi.build.sources.find((s) => s.id === bi.build.sourceId) || {}).name"
                " === 'normalized.md'"
            )
            store = BiStore(workspace, dataset)
            assert store.card_rows() == []

            # The same trial, preview and review as any source; it reads the tool's output.
            page.stage("method")
            page.click("#bi-b-trial")
            page.see("bi-b-trial-result", "試跑完成")
            assert MARK in extractor.requests[-1].messages[1].text
            assert store.card_rows() == []
            page.click("[data-stage=method] [data-bi-next=review]")
            page.wait(
                "!document.querySelector('#bi-view-build .kp-stage[data-stage=review]').hidden"
            )
            page.click("#bi-b-start")
            page.wait("document.querySelectorAll('#bi-b-cands button').length > 0")
            assert store.card_rows() == []
    units = vault.Vault(workspace, vault_id).repo.working_units()
    derived = [v for k, v in units.items() if k.startswith("source:") and "derived_from" in v]
    assert [d["name"] for d in derived] == ["normalized.md"]
    assert derived[0]["folder"] == FOLDER and derived[0]["derived_from"]["tool"] == "aidc/normalize"
