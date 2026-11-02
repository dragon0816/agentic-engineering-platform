"""Ingest into a vault, and the K1 and K2 page parts, in a real browser.

`docs/phases/BI_BUILD_FLOW.md` B6: the real Agent Web server and routes in a
temporary workspace, joined to a copy of the fixture vault. A table source goes
through the steps into the vault's working copy, where the write waits as a local
commit for the push; the analysis AI (scripted) proposes a Dashboard, applied in one step (K1);
a stand-in Atlas's dashboard order is previewed and confirmed (K2). All data is
fictional.
"""

from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_atlas_import import atlas  # noqa: F401 - the stand-in Atlas fixture
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from capabilities.bi_cards import analyses, sessions, vault
from capabilities.bi_cards.store import BiStore
from host_runtime import bi_bench, bi_cards_api
from scripts import bi_feed_fixtures as fixtures

VAULT = fixtures.VAULT_ID
DATASET = f"vault-{VAULT}"
TECH_CSV = "技術,領域,成熟度\nFicTech,robotics,mature\n"
COUNT = "SELECT entity_type AS type, count(*) AS n FROM cards GROUP BY 1 ORDER BY 1"
BY_TYPE = {
    "title": "各類型的卡片數",
    "slug": "by-type",
    "kind": "sql",
    "code": COUNT,
    "chart": {"type": "bar", "x": "type", "y": "n"},
}


def _layout(workspace: Path) -> dict[str, list[str]]:
    return analyses.dashboard_layout(vault.Vault(workspace, VAULT).repo.working_units())


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_ingest_into_a_vault_and_both_dashboard_sources(
    served: Any,  # noqa: F811
    atlas: int,  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    web, server, _recorder, _ = served
    workspace = web.runtime.layout.workspace_root
    copy = tmp_path / "shared" / "vault"
    shutil.copytree(fixtures.VAULT_DIR, copy)
    fixtures.join(workspace, copy)

    def analysis_asker(dataset: str, _actor: str) -> Any:
        # The analysis AI (BI K1): a scripted Agent that ran the SQL and proposes a Dashboard.
        def asker(_context: str, _turns: Any, _check: Any) -> Any:
            db = vault.Vault(workspace, dataset[len("vault-") :]).db_path
            answer = {
                "reply": "先看類型，再看技術更新。",
                "dashboard": {
                    "analyses": [BY_TYPE],
                    "order": ["by-type", "tech-updates"],
                    "previews": {"by-type": analyses.run_sql(db, COUNT)},
                },
            }
            used = [{"name": "bi_analysis__propose_dashboard", "ok": True}]
            return sessions.Asked(answer=answer, attempts=1), "test-agent", used

        return asker

    monkeypatch.setattr(
        bi_cards_api,
        "web_bench_runtime",
        lambda _web: bi_bench.BenchRuntime(
            ask_for=lambda _v, _a: lambda q, s: {"ok": True, "answer": ""},
            extract_for=lambda _v, _a: lambda case: [],
            # A run writes its first report a moment after the page's first read.
            background=lambda _title, work: threading.Timer(1.5, work).start(),
            analysis_asker_for=analysis_asker,
        ),
    )
    store = BiStore(workspace, DATASET)
    with BiPage(tmp_path / "browser", server.address) as page:
        page.run(f"bi.want = {DATASET!r}; biLoad()")
        page.wait(f"document.getElementById('bi-dataset').value === {DATASET!r}")
        page.click("#bi-views [data-bi-view=build]")
        page.see("bi-b-target", VAULT)
        # A vault with no benchmark run yet opens without an error notice.
        page.click("#bi-stepper [data-stage=test]")
        page.see("bi-b-bench-report", "還沒有跑過測試")
        assert "讀不到測試" not in page.text_of("bi-notice")
        page.click("#bi-stepper [data-stage=source]")

        # -- ingest into the vault: the same steps, and the write is a local change -------
        before = len(store.card_rows())

        def shared_commits() -> set[Path]:
            return set((copy / "commits").rglob("*.json"))

        commits = shared_commits()
        page.upload("tech.csv", TECH_CSV, "text/csv")
        page.stage("method")
        page.click("#bi-b-trial")
        page.see("bi-b-trial-result", "試跑完成")
        assert "FicTech" in page.text_of("bi-b-trial-result")
        assert len(store.card_rows()) == before
        page.click("[data-stage=method] [data-bi-next=review]")
        page.wait("!document.querySelector('#bi-view-build .kp-stage[data-stage=review]').hidden")
        page.click("#bi-b-start")
        page.wait("document.querySelectorAll('#bi-b-cands button').length === 1")
        page.click("#bi-b-accept-clean")
        page.see("bi-b-chips", "已接受 1")
        assert len(store.card_rows()) == before
        page.click("#bi-b-next4")
        page.wait("!document.querySelector('#bi-view-build .kp-stage[data-stage=commit]').hidden")
        page.click("#bi-b-commit-go")
        page.see("bi-b-done", "已寫入")
        assert "FicTech" in [c["name"] for c in store.card_rows()]
        page.click("#bi-stepper [data-stage=test]")
        page.wait("!document.getElementById('bi-b-ver').hidden")
        page.see("bi-b-ver-pending", "匯入 tech.csv")
        # A local commit, shown as waiting for the push: nothing new in the shared folder.
        assert shared_commits() == commits

        # -- K1: the analysis AI's Dashboard, applied in one step -----------------------------
        page.wait("!document.getElementById('bi-b-an').hidden")
        page.click("#bi-b-an-new")
        page.wait("!document.getElementById('bi-b-ana').hidden")
        page.set_value("bi-b-ana-msg", "幫我排一個 Dashboard")
        page.click("#bi-b-ana-send")
        page.see("bi-b-ana-log", "套用 Dashboard")
        assert page.run("!!document.querySelector('#bi-b-ana-log svg.bi-chart')")  # its preview
        assert "by-type" not in _layout(workspace)["order"]  # nothing before the click
        page.click_text("#bi-b-ana-log", "套用 Dashboard")
        page.notice("已套用 Dashboard")
        page.see("bi-b-an-list", "各類型的卡片數")
        page.see("bi-b-ver-pending", "分析")
        layout = _layout(workspace)
        assert layout["order"] == ["by-type", "tech-updates"]
        assert set(layout["hidden"]) >= {"node-coverage", "accounts-by-region"}

        # -- K2: an Atlas dashboard's order, previewed and confirmed --------------------------
        page.run("document.getElementById('bi-b-atl').open = true")
        page.set_value("bi-b-atl-port", str(atlas))
        page.click("#bi-b-atl-load")
        page.notice("Atlas 有 2 個 Dashboard")
        assert page.run("document.getElementById('bi-b-atl-name').options.length") == 2
        page.set_value("bi-b-atl-name", "Mixed BI layout")
        page.click("#bi-b-atl-preview")
        page.see("bi-b-atl-plan", "確認匯入順序")
        plan = page.text_of("bi-b-atl-plan")
        assert "tech-updates" in plan and "重複，略過" in plan and "別的知識庫，略過" in plan
        assert _layout(workspace)["order"] == ["by-type", "tech-updates"]  # a dry run wrote nothing
        page.click_text("#bi-b-atl-plan", "確認匯入順序")
        page.notice("已匯入 Atlas")
        page.wait("document.getElementById('bi-b-atl-plan').textContent === ''")
        layout = _layout(workspace)
        assert layout["order"] == ["tech-updates", "node-coverage", "accounts-by-region"]
        assert "by-type" in layout["hidden"]  # hidden, never deleted
        assert "by-type" in {a["slug"] for a in analyses.listing(workspace, VAULT)["analyses"]}

        # -- a bench run the page's first read cannot see yet still reports when it ends ------
        page.set_value("bi-b-bq-q", "FicTech 是什麼？")
        page.set_value("bi-b-bq-must", "FicTech")
        page.click("#bi-b-bq-form button[type=submit]")
        page.see("bi-b-bq-list", "FicTech 是什麼")
        page.wait("!document.getElementById('bi-b-bench-run').disabled")
        page.click("#bi-b-bench-run")
        page.see("bi-b-bench-report", "完成")
