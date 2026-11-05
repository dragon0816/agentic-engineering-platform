"""The build tab shows the step first, and asks for what that step needs before the rest.

On market-intel, the page started about twenty reads at once and the source table waited 12 s for
what takes 5 s alone. A real browser on fictional data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _ok
from test_vault_asking_e2e import _bi_host, _Model, _served

LOG = """(() => {
  const log = window.__log = [], was = window.fetch;
  window.fetch = async (...args) => {
    log.push(['start', String(args[0]).split('?')[0]]);
    const reply = await was(...args);
    log.push(['end', String(args[0]).split('?')[0]]);
    return reply;
  };
})()"""


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_sources_come_before_the_reads_for_other_steps(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    shared = tmp_path / "shared"
    shared.mkdir()
    made = _ok(
        _call(
            workspace,
            "POST",
            "/api/bi/vaults",
            {"path": str(shared), "title": "Market", "schema": "bi.schema/v1.1",
             "author": "alice"},
        )
    )  # fmt: skip
    dataset, vault_id = str(made["vault"]["dataset"]), str(made["vault"]["id"])
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            page.choose("bi-dataset", dataset)
            page.click("#bi-views [data-bi-view=build]")
            page.wait("(bi.build.homes || []).length > 0")
            page.wait("window.__aepWatch.open.length === 0", 60)
            page.run(LOG)
            page.run(f"bi.view = 'build'; bi.want = {dataset!r}; biLoad()")
            page.wait("window.__log.length > 0", 60)
            page.wait("window.__aepWatch.open.length === 0 && !!bi.verVault", 60)
            page.wait(f"window.__log.some((e) => e[1].endsWith('/{vault_id}/checks'))", 60)
            log = [tuple(e) for e in json.loads(str(page.run("JSON.stringify(window.__log)")))]
            sources_done = log.index(("end", "/api/bi/sources"))
            for later in ("checks", "analyses", "history", "pending", "status"):
                asked = log.index(("start", f"/api/bi/vaults/{vault_id}/{later}"))
                assert asked > sources_done, f"{later} was asked before the sources came back"

            # A person who left step 3 comes back to it, without waiting for its data.
            page.stage("test")
            page.wait("window.__aepWatch.open.length === 0", 60)
            page.reload()
            page.run(
                "(() => { const was = window.fetch; window.fetch = async (...args) => {"
                " if (String(args[0]).includes('/api/bi/sources')) {"
                " await new Promise((go) => { window.__go = go; }); }"
                " return was(...args); }; })()"
            )
            page.run(f"bi.view = 'build'; bi.want = {dataset!r}; biLoad()")
            page.wait("!!window.__go", 60)
            page.wait(
                "!document.querySelector('#bi-view-build .kp-stage[data-stage=test]').hidden", 30
            )
            page.run("window.__go()")
            page.wait("window.__aepWatch.open.length === 0", 60)
            assert not page.run(
                "document.querySelector('#bi-view-build .kp-stage[data-stage=test]').hidden"
            )
