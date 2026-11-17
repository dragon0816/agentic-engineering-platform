"""Step 2a's 建議 schema in a browser (acceptance F5, F6): a press asks the model, the
answer is a table with a quote on every row, a field is added on the version and the page
says so readably, and the AI panel opens with a suggestion written. All fictional."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_extract import Scripted
from test_bi_vault import _call, _ok, _use_homes
from test_vault_asking_e2e import _bi_host, _Model, _served

from aep_bi.cards import vault
from aep_bi.cards.ai_runs import AiRuntime
from aep_bi.cards.store import BiStore
from aep_bi.host import bi_cards_api

FOLDER = "applications/aidc/sources"
NOTE = "# 虛構筆記\n\nFAKE-RACK 的冷卻方式是浸沒式液冷。\n太空任務 FAKE-MISSION 要追蹤里程碑。\n"
ITEMS = {
    "items": [
        {
            "summary": "機櫃的冷卻方式",
            "action": ["create_card", "extend_schema"],
            "reason": "沒有欄位放冷卻方式",
            "quote": "FAKE-RACK 的冷卻方式是浸沒式液冷",
            "card": "FAKE-RACK",
            "proposal": {
                "type": "Technology",
                "field": "cooling",
                "definition": {"label": "冷卻方式", "kind": "str", "class": "sourced"},
            },
        },
        {
            "summary": "太空任務",
            "action": "propose_type",
            "reason": "任務要獨立追蹤",
            "quote": "太空任務 FAKE-MISSION 要追蹤里程碑",
            "proposal": {
                "name": "Mission",
                "definition": "一個任務",
                "unit_boundary": "一個任務一張卡",
                "why_not_existing": "沒有卡型有里程碑",
                "why_independent": "有自己的時程",
                "business_use": "查任務進度",
            },
        },
        {"summary": "價格", "action": "extend_schema", "reason": "x", "quote": "不在來源裡的話"},
    ]
}


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_press_suggests_with_quotes_and_a_field_is_added_on_the_version(
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
    dataset, vault_id = str(made["vault"]["dataset"]), str(made["vault"]["id"])
    # Only homes something is in are listed (acceptance F22): this test works in these.
    _use_homes(workspace, vault_id, "AIDC")
    model = Scripted(lambda _chunk: ITEMS)
    monkeypatch.setattr(
        bi_cards_api,
        "web_ai_runtime",
        lambda _web: AiRuntime(
            model=lambda: (model, "test-model"),
            background=lambda _t, work: work(),
            approved=lambda: ("UNCLASSIFIED", "INTERNAL"),
        ),
    )
    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "suggest" if shots else None
        ) as page:
            page.wait(
                "[...document.getElementById('bi-dataset').options]"
                f".some((o) => o.value === {json.dumps(dataset)})"
            )
            page.choose("bi-dataset", dataset)
            page.click("#bi-views [data-bi-view=build]")
            page.wait("!document.getElementById('bi-b-src-folder-box').hidden")
            page.wait(
                "[...document.getElementById('bi-b-src-folder').options]"
                f".some((o) => o.value === {json.dumps(FOLDER)})"
            )
            page.set_value("bi-b-src-folder", FOLDER)
            page.upload("raw.md", NOTE, "text/markdown")
            page.stage("schema")
            page.see("bi-b-schema-now", "目前的 schema：5.0")
            assert not model.requests, "nothing is asked before the press"

            page.click("#bi-b-sg-run")
            page.see("bi-b-sg-sum", "看了 1 份來源")
            page.wait("bi.build.suggest && bi.build.suggest.status === 'done'")
            summary = page.text_of("bi-b-sg-sum")
            assert "raw.md" in summary and "秒" in summary and "1 項找不到原文" in summary
            table = page.text_of("bi-b-sg-table")
            assert "新增欄位 Technology.cooling（冷卻方式）" in table
            assert "FAKE-RACK 的冷卻方式是浸沒式液冷" in table and "新增類型 Mission" in table
            assert "不在來源裡的話" not in table
            assert BiStore(workspace, dataset).card_rows() == [], "a suggestion writes no card"
            page.shoot("1-suggested")

            row = "#bi-b-sg-table tr[data-row=s1]"
            page.click_text(row, "加入 schema")
            page.notice("相容的新增，不是新版本")
            assert "5.0 加 1 項新增" in page.text_of("bi-notice")
            page.see("bi-b-schema-now", "5.0 加 1 項新增")
            assert not re.search(r"[0-9a-f]{12}", page.text_of("bi-b-schema-now"))
            page.see("bi-b-sg-table", "已加入")
            units = vault.Vault(workspace, vault_id).repo.working_units()
            assert "schema_change:field:Technology.cooling" in units
            assert units["schema"] == "bi.schema/v1.1@5.0.0"
            page.shoot("2-added")

            # A new type is talked through: the one AI panel opens with it written.
            page.click_text("#bi-b-sg-table tr[data-row=s2]", "和 AI 討論")
            page.ai_opened("schema")
            page.wait("document.getElementById('bi-ai-msg').value.includes('Mission')")
            asked = page.run("document.getElementById('bi-ai-msg').value")
            assert "新增類型 Mission" in asked and "太空任務 FAKE-MISSION 要追蹤里程碑" in asked
            assert not re.search(r"[0-9a-f]{12}", page.text_of("bi-ai")), "no digest (F6)"
            page.shoot("3-ai")
            page.click("#bi-ai-close")
            page.click_text("#bi-b-sg-table tr[data-row=s2]", "不要")
            page.see("bi-b-sg-table", "✕ 不要")
            assert len(model.requests) == 1, "one press, one question to the model"
            # A reload shows the same suggestion and its decisions again.
            page.reload()
            page.click("#bi-views [data-bi-view=build]")
            page.stage("schema")
            page.see("bi-b-sg-table", "已加入")
            assert "✕ 不要" in page.text_of("bi-b-sg-table")
