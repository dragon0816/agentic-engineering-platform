"""A vault's originals on two PCs, in a browser (`docs/phases/BI_SOURCES_IN_REPOSITORY.md` S8).

Alice's page adds a source to a chosen folder; after her commit and push, Bob's page
on another workspace lists it, opens its Markdown and warns while it is only in the
cloud. Each PC has its own real Agent Web; one temporary folder stands in for the
synced shared folder. All data is fictional.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _commit, _ok, _push
from test_vault_asking_e2e import _bi_host, _bi_join, _Model, _served

from capabilities.bi_cards import vault_sources

FOLDER = "sources/library/products"
REPORT = "# 虛構報告\n\n電源模組 FACT-TWOPC。\n"


def _open_build(page: BiPage, dataset: str) -> None:
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


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_source_added_on_one_pc_is_read_on_another(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_a, layout_a = _bi_host(tmp_path / "a")
    config_b, layout_b = _bi_host(tmp_path / "b")
    alice, bob = layout_a.workspace_root, layout_b.workspace_root
    shared = tmp_path / "sharepoint"
    shared.mkdir()
    made: dict[str, Any] = _ok(
        _call(alice, "POST", "/api/bi/vaults",
              {"path": str(shared), "title": "Market", "schema": "bi.schema/v1.1",
               "author": "alice"})
    )  # fmt: skip
    vault_id = str(made["vault"]["id"])
    dataset = f"vault-{vault_id}"
    with _served(config_a, layout_a, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser-a", server.address) as page:
            _open_build(page, dataset)
            assert page.run("!document.getElementById('bi-b-src-shared').hidden")
            page.wait(
                f"[...document.getElementById('bi-b-src-folder').options]"
                f".some((o) => o.value === {json.dumps(FOLDER)})"
            )
            page.set_value("bi-b-src-folder", FOLDER)
            page.upload("report.md", REPORT, "text/markdown")
            page.see("bi-b-sources", "commit、push 後才會放上去")
            assert FOLDER in page.text_of("bi-b-sources")
            assert not list((shared / vault_id).rglob("*-report.md"))
            _commit(alice, vault_id, "加入報告")
            _push(alice, vault_id)
            page.run("biBuildSources()")
            page.see("bi-b-sources", "已放上去")
    assert list((shared / vault_id / FOLDER).glob("*-report.md"))

    _bi_join(bob, shared / vault_id, "bob")
    monkeypatch.setattr(vault_sources, "cloud_only", lambda _path: True)
    with _served(config_b, layout_b, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser-b", server.address) as page:
            _open_build(page, dataset)
            page.see("bi-b-sources", "report.md")
            page.see("bi-b-sources", "只在雲端")
            page.see("bi-b-src-cloud", "一律保留在此裝置上")
            monkeypatch.undo()
            page.run("biBuildSources()")
            page.see("bi-b-sources", "已放上去")
            page.wait("document.getElementById('bi-b-src-cloud').hidden")
            page.click_text("#bi-b-sources", "看／改")
            page.wait("!document.getElementById('bi-b-md').hidden")
            page.wait("document.getElementById('bi-b-md-text').value.includes('FACT-TWOPC')")
