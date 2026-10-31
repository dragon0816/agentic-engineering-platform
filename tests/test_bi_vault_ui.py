"""The 「知識庫」 panel of 「建立與匯入」 and the coverage matrix, in a real browser.

BI vaults V4/V5 pages (`docs/phases/BI_VAULT.md` §6.2, §7.1): the real Agent
Web server and routes in a temporary workspace, with a temporary folder
standing in for the SharePoint folder. The Dashboard shows the segment x
technology-area matrix (the owner's chart) and says when the schema has no
field to place cards with; a cell opens its summary. In step 1 the demo
dataset is converted into a vault (the original dataset is left as it was),
the vault's status and 「立即同步」 work, a new vault is created and chosen,
and joining a folder that is not a vault is refused inline. Screenshots in
`.scratch/bi-vault/`.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from test_bi_extract import Scripted
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from capabilities.bi_cards import analyses, sessions, vault
from capabilities.bi_cards.ai_runs import AiRuntime
from capabilities.bi_cards.store import BiStore
from host_runtime import bi_bench, bi_cards_api

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "bi-vault"


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_vault_panel_and_coverage_in_a_browser(
    served: Any,  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from integrations.browser import Browser, BrowserError

    # The skill's Session B is answered by a scripted model (no tools, one call).
    model = Scripted(
        {
            "reply": "把虛構電源廠的規則寫清楚。",
            "changes": {"body": "虛構電源廠是 Account；額定功率放在 specs。"},
            "reasons": ["規格表常寫額定功率"],
        }
    )
    monkeypatch.setattr(
        bi_cards_api,
        "web_ai_runtime",
        lambda _web: AiRuntime(model=lambda: (model, "test-model"), background=lambda t, w: w()),
    )
    by_type = "SELECT entity_type AS type, count(*) AS n FROM cards GROUP BY 1 ORDER BY 2 DESC"

    def analysis_asker(dataset: str, _actor: str) -> Any:
        # The analysis AI (BI T3): a scripted Agent that ran the SQL and proposes it.
        def asker(_context: str, _turns: Any, _check: Any) -> Any:
            db = vault.Vault(workspace, dataset[len("vault-") :]).db_path
            answer = {
                "reply": "TestSolution 的卡片最多。",
                "analysis": {"title": "各類型的卡片數", "slug": "by-type", "kind": "sql",
                             "code": by_type, "chart": {"type": "bar", "x": "type", "y": "n"}},
                "preview": analyses.run_sql(db, by_type),
            }  # fmt: skip
            used = [{"name": "bi_analysis__sql", "ok": True},
                    {"name": "bi_analysis__propose", "ok": True}]  # fmt: skip
            return sessions.Asked(answer=answer, attempts=1), "test-agent", used

        return asker

    # The benchmark asks a scripted Agent: the working copy answers worse (BI T1).
    monkeypatch.setattr(
        bi_cards_api,
        "web_bench_runtime",
        lambda _web: bi_bench.BenchRuntime(
            ask_for=lambda _v, _a: (
                lambda q, side: {
                    "ok": True,
                    "answer": "虛構答案 IEEE" if side == "published" else "虛構答案",
                }
            ),
            extract_for=lambda _v, _a: lambda case: [],
            background=lambda _title, work: work(),
            analysis_asker_for=analysis_asker,
        ),
    )
    web, server, _recorder, _ = served
    workspace = web.runtime.layout.workspace_root
    shared = tmp_path / "sharepoint"  # stands in for the synced SharePoint folder
    shared.mkdir()
    shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
    shots.mkdir(parents=True, exist_ok=True)
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()

    def run(expression: str) -> Any:
        return browser._evaluate(expression)

    def wait(expression: str, seconds: float = 60) -> Any:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                value = run(expression)
            except BrowserError:
                value = None
            if value:
                return value
            time.sleep(0.1)
        raise AssertionError(expression)

    def click(selector: str) -> None:
        run(f"document.querySelector({json.dumps(selector)}).click()")

    def text_of(element_id: str) -> str:
        return str(run(f"document.getElementById('{element_id}').textContent"))

    def set_value(element_id: str, value: str) -> None:
        run(f"document.getElementById('{element_id}').value = {json.dumps(value)}")

    def size(width: int, height: int, mobile: bool) -> None:
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=width,
            height=height,
            deviceScaleFactor=1,
            mobile=mobile,
        )

    def shoot(name: str) -> None:
        time.sleep(0.25)
        browser.screenshot(shots / f"{name}.png")

    demo_db = workspace / "bi" / "demo" / "bi.sqlite"
    try:
        size(1366, 1000, False)
        browser.navigate(server.address)
        wait('!document.getElementById("send").disabled')
        click("#nav-knowledge")
        click("#kn-tabs [data-kn=bi]")
        wait("document.getElementById('bi-status-bar').hidden")
        # The page opens on 「建立與匯入」, dataset management folded away; this test
        # starts on the Dashboard.
        assert not run("document.getElementById('bi-view-build').hidden")
        assert not run("document.getElementById('bi-manage').open")
        run("document.querySelector('#bi-views [data-bi-view=dashboard]').click()")
        click("#bi-demo")
        wait("document.getElementById('bi-notice').textContent.includes('示範資料已載入')")

        # -- the coverage matrix on the Dashboard -----------------------------------------
        wait("document.querySelectorAll('#bi-cov-body td button').length === 55")
        assert "schema 沒有 segments、tech_areas" in text_of("bi-cov-body")
        assert "預設矩陣" in text_of("bi-cov-sub")
        head = text_of("bi-cov-body")
        for label in ("Wireless Devices & Chipsets", "Cell Phone（重點）", "OSAT", "EMC"):
            assert label in head, label
        click("#bi-cov-body td button")
        # One wait for both: the cell panel re-renders, so a second read can land on it empty.
        wait(
            "(() => { const t = document.getElementById('bi-cov-cell').textContent;"
            " return t.includes('還沒有卡片') && t.includes('Cell Phone × Wireless & Comm.'); })()"
        )
        shoot("coverage")
        size(390, 844, True)
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shoot("coverage-phone")
        size(1366, 1000, False)

        # -- per-domain configuration (BI vault V10) ------------------------------------------
        wait("document.getElementById('bi-dom-sub').textContent.includes('尚未設定')")
        click("#bi-dom summary")
        click("#bi-dom-sample")
        assert "aidc-computing" in str(run("document.getElementById('bi-dom-text').value"))
        click("#bi-dom-save")
        wait("document.getElementById('bi-notice').textContent.includes('領域設定已儲存')")
        wait("document.getElementById('bi-cov-sub').textContent.includes('領域設定的矩陣')")
        # Schema v4 has no `segments` field: said so, the configuration is kept.
        wait("document.getElementById('bi-dom-warn').textContent.includes('schema 沒有欄位')")
        assert "第 1 版" in text_of("bi-dom-sub")
        shoot("domains")

        # -- step 1: the demo dataset becomes a vault ----------------------------------------
        click("#bi-views [data-bi-view=build]")
        wait("document.getElementById('bi-b-v-state').textContent.includes('只在這台電腦')")
        assert run("document.getElementById('bi-b-ds').value") == "demo"
        assert run("document.getElementById('bi-b-v-sync').hidden")
        before = hashlib.sha256(demo_db.read_bytes()).hexdigest()
        click("#bi-b-v-convert")
        assert run("document.getElementById('bi-b-v-convert').getAttribute('aria-expanded')") == (
            "true"
        )
        assert run("document.getElementById('bi-b-v-title').parentElement.hidden")
        set_value("bi-b-v-path", str(shared))
        set_value("bi-b-v-purpose", "虛構範例：示範資料轉成共用知識庫")
        click("#bi-b-v-go")
        wait("document.getElementById('bi-notice').textContent.includes('已轉成共用知識庫')")
        wait("document.getElementById('bi-dataset').value.startsWith('vault-')")
        wait(
            "document.getElementById('bi-b-v-state').textContent.includes('還沒 push 的 commit 0')"
        )
        state = text_of("bi-b-v-state")
        assert "虛構範例" in state and str(shared) in state
        assert not run("document.getElementById('bi-b-v-sync').hidden")
        assert run("document.getElementById('bi-b-v-convert').hidden")
        # A vault is shared by commit and push in step 3, not by the platform copy.
        assert run("document.getElementById('bi-publish').hidden")
        assert hashlib.sha256(demo_db.read_bytes()).hexdigest() == before
        (folder,) = [p for p in shared.iterdir() if p.is_dir()]
        assert (folder / "repo.json").is_file()
        # The whole dataset travels as one import commit.
        assert len(list((folder / "commits").rglob("*.json"))) == 1
        assert not list(folder.rglob("*.sqlite"))  # no database in the shared folder
        assert "共用：" in str(
            run("document.getElementById('bi-dataset').selectedOptions[0].textContent")
        )
        shoot("vault-converted")
        click("#bi-b-v-sync")
        wait("document.getElementById('bi-notice').textContent.includes('已同步')")

        # -- the 「版本」 area (knowledge repositories R5), in step 3 ------------------------
        click("#bi-stepper [data-stage=test]")
        wait("!document.querySelector('#bi-view-build .kp-stage[data-stage=test]').hidden")
        assert run("document.getElementById('bi-b-ver-none').hidden")
        wait("document.getElementById('bi-b-ver-history').textContent.includes('轉成知識庫')")
        assert "還沒有發佈過" in text_of("bi-b-ver-reads")
        assert run("document.getElementById('bi-b-ver-commit').disabled")
        dataset = str(run("document.getElementById('bi-dataset').value"))
        store = BiStore(workspace, dataset)
        card = store.card_rows()[0]
        store.set_field(card["id"], "notes", "虛構備註", base_version=card["version"], actor="t")
        click("#bi-b-v-sync")
        wait("document.getElementById('bi-b-ver-pending').textContent.includes('notes')")
        assert "虛構備註" in text_of("bi-b-ver-pending")
        click("#bi-b-ver-commit")
        wait("document.getElementById('bi-notice').textContent.includes('請先寫這次改動的目的')")
        set_value("bi-b-ver-purpose", "補上虛構備註")
        click("#bi-b-ver-commit")
        wait("document.getElementById('bi-notice').textContent.includes('已 commit')")
        wait("!document.getElementById('bi-b-ver-push').disabled")
        click("#bi-b-ver-push")
        wait("document.getElementById('bi-notice').textContent.includes('已 push 1 個 commit')")
        wait("document.getElementById('bi-b-ver-history').textContent.includes('補上虛構備註')")
        assert len(list((folder / "commits").rglob("*.json"))) == 2
        assert "補上虛構備註" in (folder / "REPO.md").read_text(encoding="utf-8")
        click("#bi-b-ver-history li .bi-actions button:nth-child(1)")
        wait("document.querySelector('#bi-b-ver-history li').textContent.includes('虛構備註')")
        run(
            "[...document.querySelectorAll('#bi-b-ver-history li:first-child button')]"
            ".find((b) => b.textContent === '加 tag').click()"
        )
        run("document.querySelector('#bi-b-ver-history .bi-ver-ask input').value = 'v1'")
        click("#bi-b-ver-history .bi-ver-ask button.go")
        wait("document.getElementById('bi-notice').textContent.includes('已建立 tag「v1」')")
        run("window.confirm = () => true")
        wait(
            "[...document.querySelectorAll('#bi-b-ver-history button')]"
            ".some((b) => b.textContent === '發佈 v1')"
        )
        run(
            "[...document.querySelectorAll('#bi-b-ver-history button')]"
            ".find((b) => b.textContent === '發佈 v1').click()"
        )
        wait("document.getElementById('bi-b-ver-reads').textContent.includes('發佈版本「v1」')")
        wait("document.getElementById('bi-b-ver-history').textContent.includes('發佈中')")
        shoot("vault-versions")
        size(390, 844, True)
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shoot("vault-versions-phone")
        size(1366, 1000, False)

        # -- skills in the vault (knowledge repositories R3), in step 2 ---------------------
        click("#bi-stepper [data-stage=ingest]")
        wait("!document.querySelector('#bi-view-build .kp-stage[data-stage=schema]').hidden")
        assert not run("document.getElementById('bi-b-skills').hidden")
        wait("document.getElementById('bi-b-sk-list').textContent.includes('依 schema 產生')")
        assert "classify" in text_of("bi-b-sk-list")
        assert not run("document.getElementById('bi-b-folder-box').hidden")
        assert run(
            "[...document.getElementById('bi-b-folder').options]"
            ".some((o) => o.value === 'sources/applications/aidc-power')"
        )
        click("#bi-b-sk-new")
        set_value("bi-b-sk-name", "power-extract")
        set_value("bi-b-sk-applies", "sources/applications/aidc-power")
        set_value("bi-b-sk-body", "虛構電源廠是 Account。")
        click("#bi-b-sk-form button.go")
        wait("document.getElementById('bi-notice').textContent.includes('存成第 1 版')")
        wait("document.getElementById('bi-b-ver-pending').textContent.includes('power-extract')")
        wait("document.getElementById('bi-b-sk-list').textContent.includes('power-extract')")
        assert run("document.getElementById('bi-b-sk-form').hidden")
        shoot("vault-skills")

        # -- Session B on a skill: suggest, apply as the next revision ------------------------
        run(
            "[...document.querySelectorAll('#bi-b-sk-list li')]"
            ".find((li) => li.textContent.includes('power-extract'))"
            ".querySelector('button[aria-label*=\"AI\"]').click()"
        )
        wait("!document.getElementById('bi-b-ska').hidden")
        assert "power-extract" in text_of("bi-b-ska-target")
        wait("document.getElementById('bi-b-ska-model').textContent.includes('test-model')")
        set_value("bi-b-ska-msg", "額定功率放在 specs")
        click("#bi-b-ska-send")
        wait("document.getElementById('bi-b-ska-log').textContent.includes('套用後的變化')")
        assert "判讀規則第 1 版" in text_of("bi-b-ska-log")
        click("#bi-b-ska-log button.go")
        wait("document.getElementById('bi-notice').textContent.includes('存成第 2 版')")
        wait("document.getElementById('bi-b-ska-log').textContent.includes('已套用為第 2 版')")
        wait("document.getElementById('bi-b-sk-list').textContent.includes('第 2 版')")
        assert "第 2 版" in text_of("bi-b-ska-target")
        shoot("vault-skill-ai")
        click("#bi-stepper [data-stage=test]")  # the applied revision waits for a commit
        wait("document.getElementById('bi-b-ver-pending').textContent.includes('power-extract')")
        shoot("vault-step3")

        # -- 題目與擷取測試 in step 3 (BI T1) ---------------------------------------------
        wait("!document.getElementById('bi-b-bench').hidden")
        assert "還沒有跑過測試" in text_of("bi-b-bench-report")
        assert run("document.getElementById('bi-b-bench-run').disabled")
        set_value("bi-b-bq-q", "TSN 的標準組織是誰？")
        set_value("bi-b-bq-must", "IEEE")
        click("#bi-b-bq-form button[type=submit]")
        wait("document.getElementById('bi-b-bq-list').textContent.includes('TSN 的標準組織')")
        wait("document.getElementById('bi-b-ver-pending').textContent.includes('測試題')")
        click("#bi-b-bench-run")
        wait("document.getElementById('bi-b-bench-report').textContent.includes('完成')")
        report = text_of("bi-b-bench-report")
        assert "工作版本 0/1、發佈版本 1/1" in report and "退步 1 題" in report
        assert "沒提到 IEEE" in report
        shoot("vault-bench")
        size(390, 844, True)
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shoot("vault-bench-phone")
        size(1366, 1000, False)

        # -- 分析與圖表 in step 3, then on the Dashboard (BI T3) ---------------------------
        wait("!document.getElementById('bi-b-an').hidden")
        # A converted vault starts with the default analysis pack (BI P2).
        assert "6. 缺口" in text_of("bi-b-an-list")
        click("#bi-b-an-new")
        wait("!document.getElementById('bi-b-ana').hidden")
        set_value("bi-b-ana-msg", "各類型各有幾張卡？畫長條圖")
        click("#bi-b-ana-send")
        wait("document.getElementById('bi-b-ana-log').textContent.includes('存成分析')")
        assert run("!!document.querySelector('#bi-b-ana-log svg.bi-chart')")
        assert "Agent 用了：SQL、提出分析" in text_of("bi-b-ana-log")
        shoot("vault-analysis-ai")
        click("#bi-b-ana-log button.go")
        wait("document.getElementById('bi-b-an-list').textContent.includes('各類型的卡片數')")
        wait("document.getElementById('bi-b-ver-pending').textContent.includes('分析')")
        click("#bi-views [data-bi-view=dashboard]")
        # A vault's Dashboard is its analyses (BI P3): the saved bar chart is a section.
        wait("!!document.querySelector(\"#bi-dash-sections details[data-section='by-type'] svg\")")
        assert "6. 缺口" in text_of("bi-dash-sections")  # the default pack's analyses
        shoot("vault-analysis-dashboard")

        # -- parameters and the Dashboard's order (BI P1) ----------------------------------
        vault_id = str(run("bi.verVault"))
        one_type = "SELECT entity_type AS type, count(*) AS n FROM cards WHERE entity_type = :t"
        analyses.save(workspace, vault_id, {
            "title": "某類型的卡片數", "slug": "one-type", "kind": "sql",
            "code": one_type + " GROUP BY 1", "chart": {"type": "table"},
            "params": {"t": {"type": "enum", "values": ["Technology", "TestSolution"],
                             "default": "Technology", "label": "類型"}}})  # fmt: skip
        # Put the two first (the pack's analyses follow), then hide one on the page.
        analyses.set_dashboard(
            workspace, vault_id, {"order": ["by-type", "one-type"], "hidden": []}
        )
        click("#bi-views [data-bi-view=build]")
        run("biAnalyses(bi.verVault)")
        wait("!!document.querySelector('#bi-b-an-list select[data-param=t]')")
        click("#bi-b-an-list button[aria-label='執行分析 某類型的卡片數']")
        wait("document.getElementById('bi-b-an-list').textContent.includes('Technology')")
        run(
            "(() => { const s = document.querySelector('#bi-b-an-list select[data-param=t]');"
            " s.value = 'TestSolution'; s.dispatchEvent(new Event('change')); })()"
        )
        wait("[...document.querySelectorAll('#bi-b-an-list td')]"
             ".some((td) => td.textContent === 'TestSolution')")  # fmt: skip
        click("#bi-b-an-list button[aria-label='在 Dashboard 隱藏分析 各類型的卡片數']")
        wait("document.getElementById('bi-notice').textContent.includes('Dashboard 的順序')")
        wait("document.getElementById('bi-b-an-list').textContent.includes('Dashboard 不顯示')")
        wait("document.getElementById('bi-b-ver-pending').textContent.includes('Dashboard 的順序')")
        shoot("vault-analysis-params")
        click("#bi-b-an-pack")  # again: changes nothing; the notice lists what v4 cannot use
        wait("document.getElementById('bi-notice').textContent.includes('已加入')")
        click("#bi-b-an-export")
        wait("document.getElementById('bi-notice').textContent.includes('已匯出')")
        click("#bi-views [data-bi-view=dashboard]")
        # Its parameter is at the top; the hidden analysis is not drawn.
        wait("!!document.querySelector('#bi-dash-params select[data-param=t]')")
        one = "#bi-dash-sections details[data-section='one-type']"
        wait(f"!!document.querySelector({json.dumps(one)})")
        assert not run("!!document.querySelector(\"#bi-dash-sections [data-section='by-type']\")")
        wait(f"document.querySelector({json.dumps(one)}).textContent.includes('Technology')")
        run(
            "(() => { const s = document.querySelector('#bi-dash-params select[data-param=t]');"
            " s.value = 'TestSolution'; s.dispatchEvent(new Event('change')); })()"
        )
        wait(f"document.querySelector({json.dumps(one)}).textContent.includes('TestSolution')")
        assert run("document.querySelectorAll('#bi-dash-summary .bi-stat').length") == 3
        shoot("vault-analysis-dashboard-params")
        click("#bi-views [data-bi-view=build]")
        click("#bi-stepper [data-stage=source]")

        # -- a new, empty vault ---------------------------------------------------------------
        click("#bi-b-v-new")
        assert not run("document.getElementById('bi-b-v-title').parentElement.hidden")
        set_value("bi-b-v-path", "")
        click("#bi-b-v-go")
        wait("document.getElementById('bi-b-v-err').textContent.includes('請填資料夾路徑')")
        set_value("bi-b-v-path", str(shared))
        click("#bi-b-v-go")
        wait("document.getElementById('bi-b-v-err').textContent.includes('請填知識庫名稱')")
        set_value("bi-b-v-path", str(shared))
        set_value("bi-b-v-title", "Market Signals")
        set_value("bi-b-v-purpose", "虛構範例")
        click("#bi-b-v-go")
        wait("document.getElementById('bi-notice').textContent.includes('已建立共用知識庫')")
        wait("document.getElementById('bi-b-v-state').textContent.includes('Market Signals')")
        assert run("document.getElementById('bi-dataset').value").startswith("vault-market-signals")
        assert len([p for p in shared.iterdir() if p.is_dir()]) == 2

        # -- joining a folder that is not a vault ------------------------------------------
        click("#bi-b-v-join")
        set_value("bi-b-v-path", str(tmp_path))
        click("#bi-b-v-go")
        wait("document.getElementById('bi-b-v-err').textContent.includes('repo.json')")
        size(390, 844, True)
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shoot("vault-join-error-phone")
    finally:
        browser.close()
