"""Step 2's advanced tools follow the working domain, in a real browser on fictional data
(owner 2026-11-19: 「選了應用資料夾了，為什麼還要勾以下這一大票檔案…上面已經有選工作領域了，這部份
應該要依照工作領域，只列出相關的資料」).

「改完規則後重跑」 lists only the working domain's sources, every one ticked, with one 全選 box
and the count; switching the domain lists the other domain's sources, nothing stale.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _ok, _use_homes
from test_vault_asking_e2e import _bi_host, _Model, _served

AIDC = "applications/aidc/sources"
WIRELESS = "applications/wireless/sources"


def _source(ws: Path, dataset: str, name: str, folder: str) -> None:
    body = {"dataset": dataset, "name": name, "text": f"# {name}\n\n虛構內容。\n", "folder": folder}
    _ok(_call(ws, "POST", "/api/bi/sources", body))


def _vault(tmp_path: Path) -> tuple[Any, Any, Path, str, str]:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    shared = tmp_path / "shared"
    shared.mkdir()
    made = _ok(
        _call(workspace, "POST", "/api/bi/vaults",
              {"path": str(shared), "title": "Market", "schema": "bi.schema/v1.1",
               "author": "alice", "default_pack": False})
    )  # fmt: skip
    dataset, vault_id = str(made["vault"]["dataset"]), str(made["vault"]["id"])
    _use_homes(workspace, vault_id, "AIDC", "Wireless")
    return config, layout, workspace, dataset, vault_id


def _open_step2(page: BiPage, dataset: str, folder: str) -> None:
    page.choose("bi-dataset", dataset)
    page.click("#bi-views [data-bi-view=build]")
    page.wait("!document.getElementById('bi-b-src-folder-box').hidden")
    page.choose("bi-b-src-folder", folder)
    page.stage("schema")
    page.run("document.getElementById('bi-b-adv-skills').open = true")


def _rerun_names(page: BiPage) -> list[str]:
    return list(
        page.run(
            "[...document.querySelectorAll('#bi-b-rr-sources .bi-rr-list label')]"
            ".map((l) => l.textContent.trim())"
        )
    )


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_rerun_lists_the_working_domains_sources_all_ticked(tmp_path: Path) -> None:
    config, layout, workspace, dataset, _vault_id = _vault(tmp_path)
    for name in ("a1.md", "a2.md"):
        _source(workspace, dataset, name, AIDC)
    _source(workspace, dataset, "w1.md", WIRELESS)
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            _open_step2(page, dataset, AIDC)
            page.wait("document.querySelectorAll('#bi-b-rr-sources .bi-rr-list input').length")
            assert sorted(_rerun_names(page)) == ["a1.md", "a2.md"]
            # Nothing to choose: the working domain is the application.
            assert page.run("document.getElementById('bi-b-rr-app-box').hidden")
            assert page.run(
                "[...document.querySelectorAll('#bi-b-rr-sources input')].every((i) => i.checked)"
            )
            assert "已選 2／2 份" in page.text_of("bi-b-rr-picked")
            # One box unticks all and ticks all again; a single file can still be left out.
            page.click("#bi-b-rr-sources input[aria-label='重跑：全選']")
            assert "已選 0／2 份" in page.text_of("bi-b-rr-picked")
            page.click("#bi-b-rr-count")
            page.see("bi-b-rr-out", "先勾要重跑的來源")
            page.click("#bi-b-rr-sources input[aria-label='重跑：全選']")
            page.click("#bi-b-rr-sources .bi-rr-list input")
            assert "已選 1／2 份" in page.text_of("bi-b-rr-picked")
            page.click("#bi-b-rr-count")
            page.see("bi-b-rr-out", "共 1 份來源")
            # Another domain: its own sources, every one ticked, none of the first one's.
            page.choose("bi-b-src-folder", WIRELESS)
            page.wait(
                "[...document.querySelectorAll('#bi-b-rr-sources .bi-rr-list label')]"
                ".map((l) => l.textContent.trim()).join() === 'w1.md'"
            )
            assert "已選 1／1 份" in page.text_of("bi-b-rr-picked")
            # 全部領域 chooses an application here instead.
            page.choose("bi-b-src-folder", "sources")
            page.wait("!document.getElementById('bi-b-rr-app-box').hidden")
            assert sorted(_rerun_names(page)) == ["a1.md", "a2.md", "w1.md"]
            page.choose("bi-b-rr-app", "wireless")
            page.wait("document.getElementById('bi-b-rr-picked').textContent.includes('1／1')")
            assert json.dumps(_rerun_names(page)) == json.dumps(["w1.md"])


TOOL = """import os
text = open(INPUT, encoding="utf-8").read()
with open(os.path.join(OUTPUT, "rows.csv"), "w", encoding="utf-8") as out:
    out.write("line" + chr(10) + "TRIED-IN-THE-PAGE" + chr(10))
"""


def _pick_py(page: BiPage, name: str, text: str) -> None:
    page.run(
        "(() => { const dt = new DataTransfer();"
        f" dt.items.add(new File([{json.dumps(text)}], {json.dumps(name)},"
        " {type: 'text/x-python'}));"
        " const f = document.getElementById('bi-b-tl-file'); f.files = dt.files;"
        " f.dispatchEvent(new Event('change')); })()"
    )


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_tool_is_picked_talked_through_tried_and_saved_in_the_working_domain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """「選檔 → 和 AI 討論 → 試跑 → 存成新版本」, all following the working domain."""
    from test_bi_extract import Scripted

    from aep_bi.cards.ai_runs import AiRuntime
    from aep_bi.host import bi_cards_api

    config, layout, workspace, dataset, vault_id = _vault(tmp_path)
    _source(workspace, dataset, "a1.md", AIDC)
    _source(workspace, dataset, "w1.md", WIRELESS)
    other = {"home": "wireless", "name": "split", "suffix": ".py", "text": TOOL}
    _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/tools", other))
    asks = {"reply": "要輸出哪些欄位？", "needs": ["輸出欄位"], "code": None, "notes": []}
    writes = {"reply": "這是程式。", "needs": [], "code": TOOL, "notes": []}
    model = Scripted(asks, writes)
    monkeypatch.setattr(
        bi_cards_api,
        "web_ai_runtime",
        lambda _web: AiRuntime(model=lambda: (model, "test-model"), background=lambda _t, w: w()),
    )
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            _open_step2(page, dataset, AIDC)
            # Only this domain's tools; the other domain's are counted.
            page.see("bi-b-tl-list", "其他領域還有 1 個")
            assert "wireless/split" not in page.text_of("bi-b-tl-list")
            # Prefilled from the working domain: only the name is typed.
            page.wait("document.getElementById('bi-b-tl-name').value === 'aidc/'")
            # 選擇 Python 檔: listed on the right, read-only, and in the editor.
            _pick_py(page, "Normalize Report.py", TOOL.replace("rows.csv", "first.csv"))
            page.wait("!document.getElementById('bi-b-tl-files').hidden")
            assert page.run("document.getElementById('bi-b-tl-name').value") == (
                "aidc/normalize-report"
            )
            assert "first.csv" in page.run("document.getElementById('bi-b-tl-code').value")
            files = page.text_of("bi-b-tl-files")
            assert "Normalize Report.py" in files and "唯讀" in files
            assert page.run("document.querySelector('#bi-b-tl-files pre').tagName") == "PRE"
            # The trial lists this domain's sources, one ticked.
            names = page.run(
                "[...document.querySelectorAll('#bi-b-tl-try-box label')]"
                ".map((l) => l.textContent.trim())"
            )
            assert names == ["a1.md"]
            assert "已選 1 份" in page.text_of("bi-b-tl-try-count")

            # 和 AI 討論: it asks first, then writes code the person puts in the editor.
            page.click("#bi-b-tl-ai")
            page.ai_opened("tool")
            assert "輸入檔長怎樣" in page.text_of("bi-ai-target")
            assert "aidc" in page.text_of("bi-ai-target")
            page.set_value("bi-ai-msg", "幫我轉成 CSV")
            page.click("#bi-ai-send")
            page.see("bi-ai-log", "請你提供")
            assert "輸出欄位" in page.text_of("bi-ai-log")
            first = model.requests[0].messages[1].text
            assert "Working domain: aidc" in first and "w1.md" not in first
            page.set_value("bi-ai-msg", "欄位：line")
            page.click("#bi-ai-send")
            page.see("bi-ai-log", "AI 提出的程式碼")
            page.click_text("#bi-ai-log", "放進編輯區")
            page.see("bi-ai-log", "已放進編輯區")
            page.wait("document.getElementById('bi-b-tl-code').value.includes('rows.csv')")
            page.click("#bi-ai-close")

            # 試跑: the output is shown, with the seconds while it runs; nothing is kept.
            page.click("#bi-b-tl-try")
            page.see("bi-b-tl-try-out", "試跑完成：1 份成功")
            assert "TRIED-IN-THE-PAGE" in page.run(
                "document.getElementById('bi-b-tl-try-out').textContent"
            )
            assert "秒" in page.text_of("bi-b-tl-try-state")
            assert "rows.csv" not in page.text_of("bi-b-sources")
            # A failing trial says why in the same place.
            page.set_value("bi-b-tl-code", "raise ValueError('BROKEN-ON-PURPOSE')")
            page.click("#bi-b-tl-try")
            page.see("bi-b-tl-try-out", "1 份失敗")
            assert "BROKEN-ON-PURPOSE" in page.text_of("bi-b-tl-try-out")

            # 存成新版本 under the prefilled name.
            page.set_value("bi-b-tl-code", TOOL)
            page.click("#bi-b-tl-save")
            page.notice("存成第 1 版")
            page.see("bi-b-tl-list", "aidc/normalize-report")

            # Another working domain: its prefix, its sources, its tools, no stale trial.
            page.choose("bi-b-src-folder", WIRELESS)
            page.wait(
                "document.getElementById('bi-b-tl-name').value === 'wireless/normalize-report'"
            )
            page.wait(
                "[...document.querySelectorAll('#bi-b-tl-try-box label')]"
                ".map((l) => l.textContent.trim()).join() === 'w1.md'"
            )
            assert page.text_of("bi-b-tl-try-out") == ""
            page.see("bi-b-tl-list", "wireless/split")
            assert "aidc/normalize-report" not in page.text_of("bi-b-tl-list")
            assert page.run("document.getElementById('bi-ai').hidden")
