"""An analysis the schema keeps off the Dashboard is named on the page with why. Fictional."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _ok
from test_vault_asking_e2e import _bi_host, _Model, _served


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_dashboard_says_what_it_does_not_show(tmp_path: Path) -> None:
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
    _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/analyses", {"save": {
        "title": "Needs more", "slug": "needs-more", "kind": "sql",
        "code": "SELECT count(*) AS n FROM cards", "chart": {"type": "table"},
        "requires": {"fields": ["cards.entity_type"]}}}))  # fmt: skip
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
            page.click("#bi-views [data-bi-view=dashboard]")
            page.see("bi-dash-not-shown", "Needs more")
            page.see("bi-dash-not-shown", "cards.entity_type")
            assert page.run("document.getElementById('bi-dash-not-shown').hidden") is False
