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
