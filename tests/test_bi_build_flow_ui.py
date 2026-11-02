"""The whole BI build flow in one browser test (`docs/phases/BI_BUILD_FLOW.md` §8).

The real Agent Web server, routes and harness wiring in a temporary workspace,
with a temporary folder as the shared folder and scripted Agent and extractor
models: upload → Markdown → convert to a vault → Session A's suggestion, applied,
published and the vault moved to it → Session B's suggestion applied → ingest
trial, review and write → AI benchmark questions → AI dashboard (K1) → bench run
working vs published → commit → push → publish, ending with what the Agent reads.
Each AI step gets its next replies just before the person sends the message. All
data is fictional. Screenshots in `.scratch/bi-flow/` with `AEP_UI_SHOTS`.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from bi_page_driver import BiPage, browser_missing
from test_ai_proposed_changes import _config
from test_bi_extract import MEETING_ANSWER, NOTE, Scripted
from test_bi_skill_benchmark import _Grounded
from test_draft_install_cards import _AuthoringClaude, _lab
from test_host_wiring import host_json

from capabilities.bi_cards import analyses, schema_versions, vault, vault_checks
from capabilities.bi_cards.ai_runs import AiRuntime
from capabilities.bi_cards.store import BiStore
from host_runtime import bi_bench, bi_cards_api, skill_packs
from host_runtime.assets import shipped
from host_runtime.conversation_backends import LocalConversationBackends
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer

BUDGET = {"name": "budget_band", "label": "預算級距", "kind": "str", "class": "sourced"}
ADD_BUDGET = [{"op": "add_field", "type": "Signal", "field": BUDGET}]
RULE = "類型與資料夾照 schema。\n會議紀錄裡客戶親口說的評估，一律建一張 Signal。"
QUESTION = {"question": "哪家客戶在評估 TSN？", "must": ["A 公司"], "must_not": ["B 公司"]}
COUNT = "SELECT entity_type AS type, count(*) AS n FROM cards GROUP BY 1 ORDER BY 1"
BY_TYPE = {
    "title": "各類型的卡片數",
    "slug": "by-type",
    "kind": "sql",
    "code": COUNT,
    "chart": {"type": "bar", "x": "type", "y": "n"},
}


@pytest.fixture
def flow(tmp_path: Path) -> Iterator[tuple[AgentWeb, AgentWebServer, _Grounded]]:
    config, layout = _config(tmp_path)
    skill_packs.install_bundle(layout, None, shipped=shipped())
    path = host_json(tmp_path, config)
    with build_runtime(config, layout=layout) as runtime:
        backends = LocalConversationBackends(
            layout.workspace_root,
            which=lambda name: f"C:/fake/{name}.exe",
            runner=_AuthoringClaude(),
        )
        web = AgentWeb(runtime, config_path=path, conversation_backends=backends)
        web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        _lab(web)
        agent = _Grounded()
        web.runtime.agent.gateway.router.model = agent
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield web, server, agent
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_whole_build_flow(
    flow: tuple[AgentWeb, AgentWebServer, _Grounded],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    web, server, agent = flow
    workspace = web.runtime.layout.workspace_root
    shared = tmp_path / "sharepoint"  # stands in for the synced SharePoint folder
    shared.mkdir()
    extractor = Scripted(lambda _chunk: MEETING_ANSWER)  # the same note in every run
    monkeypatch.setattr(
        bi_cards_api,
        "web_ai_runtime",
        lambda _web: AiRuntime(
            model=lambda: (extractor, "test-model"),
            background=lambda _t, work: work(),
            approved=lambda: ("UNCLASSIFIED", "INTERNAL"),
        ),
    )
    shots = os.environ.get("AEP_UI_SHOTS")
    with BiPage(
        tmp_path / "browser", server.address, Path(shots) / "bi-flow" if shots else None
    ) as page:
        page.run(
            "biCall('/api/bi/datasets', {name: 'lab', schema: 'bi.schema/v1.1'})"
            ".then(() => { bi.want = 'lab'; return biLoad(); })"
        )
        page.wait("document.getElementById('bi-dataset').value === 'lab'")
        page.click("#bi-views [data-bi-view=build]")
        page.see("bi-b-target", "lab")

        # -- step 1: upload → Markdown → convert the dataset to a vault -----------------------
        page.upload("meeting.md", NOTE, "text/markdown")
        assert "第 1 版" in page.text_of("bi-b-sources")
        page.click_text("#bi-b-sources", "看／改")
        page.wait("!document.getElementById('bi-b-md').hidden")
        page.wait(
            "document.getElementById('bi-b-md-text').value.includes('客戶 A 公司表示正在評估 TSN')"
        )
        page.click("#bi-b-v-convert")
        page.set_value("bi-b-v-path", str(shared))
        page.set_value("bi-b-v-purpose", "虛構：客戶訊號")
        page.set_value("bi-b-v-author", "alice")
        page.click("#bi-b-v-go")
        page.notice("帶過 1 份來源")
        page.wait("document.getElementById('bi-dataset').value.startsWith('vault-')")
        dataset = str(page.run("document.getElementById('bi-dataset').value"))
        vault_id = dataset[len("vault-") :]
        page.wait(page.shows("bi-b-sources", "meeting.md"))  # the source came along
        # The person picks what to work on; the table may still be drawn again as the vault loads.
        page.wait(
            "(() => { const pick = document.querySelector('#bi-b-sources tbody input');"
            " if (pick && !pick.checked) pick.click();"
            " return pick && pick.checked && bi.build.sourceId; })()"
        )
        source = str(page.run("bi.build.sourceId"))
        page.shoot("1-converted")

        # -- step 2a: Session A on the harness: suggestion, draft, publish, upgrade -----------
        page.stage("schema")
        page.click("#bi-b-draft-new")
        page.wait("!document.getElementById('bi-b-draft').hidden")
        page.see("bi-b-sa-model", "harness")
        agent.then(
            {"tools": [("bi_schema__cards", {})]},
            {"tools": [("bi_schema__read_source", {"source_id": source})]},
            {"tools": [("bi_schema__try", {"changes": ADD_BUDGET, "source_id": source})]},
            {
                "tools": [
                    (
                        "bi_schema__suggest",
                        {
                            "reply": "訊號卡加上預算級距。",
                            "verdict": "extend",
                            "changes": ADD_BUDGET,
                        },
                    )
                ]
            },
            {"text": "我試過了，既有卡片不受影響。"},
        )
        page.set_value("bi-b-sa-goal", "追蹤客戶預算")
        page.set_value("bi-b-sa-msg", "訊號卡要記預算級距")
        page.click("#bi-b-sa-send")
        page.see("bi-b-sa-log", "擴充這份 schema")
        log = page.text_of("bi-b-sa-log")
        assert "Agent 用了" in log and "試草稿" in log and "budget_band" in log
        page.shoot("2a-session-a")
        page.click_text("#bi-b-sa-log", "套用到草稿")
        page.see("bi-b-draft-info", "第 2 版")
        page.click("#bi-b-draft-publish")
        page.notice("bi.schema/v1.1@3.1.0")
        page.see("bi-b-versions", "3.1.0")
        page.run(
            "[...document.querySelectorAll('#bi-b-versions .bi-actions')]"
            ".find(r => r.textContent.includes('@3.1.0')).querySelector('button').click()"
        )
        page.see("bi-b-upgrade", "套用升級")
        page.click_text("#bi-b-upgrade", "套用升級")
        page.notice("已升級")
        assert BiStore(workspace, dataset).schema_ref() == "bi.schema/v1.1@3.1.0"
        assert schema_versions.drafts(workspace)  # the draft itself stays

        # -- step 2a: Session B on the harness: the skill, applied as a new revision ----------
        page.see("bi-b-sk-list", "classify")
        agent.then(
            {"tools": [("bi_skill__try", {"source_id": source, "changes": {"body": RULE}})]},
            {
                "tools": [
                    (
                        "bi_skill__suggest",
                        {"reply": "加上會議紀錄的規則。", "changes": {"body": RULE}},
                    )
                ]
            },
            {"text": "試跑找到訊號卡。"},
        )
        page.run(
            "[...document.querySelectorAll('#bi-b-sk-list li')]"
            ".find(li => li.textContent.includes('classify'))"
            ".querySelector('button[aria-label*=\"AI\"]').click()"
        )
        page.wait("!document.getElementById('bi-b-ska').hidden")
        page.see("bi-b-ska-model", "test-model")
        page.set_value("bi-b-ska-msg", "會議紀錄裡客戶說在評估的，要建 Signal")
        page.click("#bi-b-ska-send")
        page.see("bi-b-ska-log", "套用後的變化")
        assert "草稿試跑" in page.text_of("bi-b-ska-log")
        page.click("#bi-b-ska-log button.go")
        page.see("bi-b-ska-log", "已套用為第")
        page.shoot("2a-session-b")

        # -- steps 2b–2e: trial → ingest → review → write --------------------------------------
        store = BiStore(workspace, dataset)
        before = len(store.card_rows())
        page.stage("method")
        page.click("#bi-b-trial")
        page.see("bi-b-trial-result", "試跑完成")
        assert "A 公司評估 TSN" in page.text_of("bi-b-trial-result")
        assert len(store.card_rows()) == before  # a trial writes nothing
        page.click("[data-stage=method] [data-bi-next=review]")
        page.wait("!document.querySelector('#bi-view-build .kp-stage[data-stage=review]').hidden")
        page.click("#bi-b-start")
        page.wait("document.querySelectorAll('#bi-b-cands button').length > 0")
        page.click("#bi-b-accept-clean")
        page.wait("!document.getElementById('bi-b-next4').disabled")
        assert len(store.card_rows()) == before  # review writes nothing
        page.click("#bi-b-next4")
        page.wait("!document.querySelector('#bi-view-build .kp-stage[data-stage=commit]').hidden")
        page.click("#bi-b-commit-go")
        page.see("bi-b-done", "已寫入")
        assert "A 公司評估 TSN" in {c["name"] for c in store.card_rows()}

        # -- step 3: AI benchmark questions, added by the person ------------------------------
        page.click("#bi-stepper [data-stage=test]")
        page.wait("!document.getElementById('bi-b-bench').hidden")
        page.see("bi-b-ver-pending", "匯入 meeting.md")
        agent.then(
            {"tools": [("bi__query", {"dataset": dataset, "entity_type": "Signal"})]},
            {"tools": [("bi_questions__analyses", {})]},
            {
                "tools": [
                    (
                        "bi_questions__propose",
                        {
                            "reply": "這題問得到卡片上的客戶。",
                            "questions": [QUESTION, {**QUESTION, "question": "不要這一題？"}],
                        },
                    )
                ]
            },
            {"text": "出了兩題。"},
        )
        page.click("#bi-b-qa-open")
        page.wait("!document.getElementById('bi-b-qa').hidden")
        page.set_value("bi-b-qa-msg", "出題")
        page.click("#bi-b-qa-send")
        page.see("bi-b-qa-log", "加入測試題")
        assert "必須提到：A 公司" in page.text_of("bi-b-qa-log")
        assert vault_checks.listing(workspace, vault_id)["questions"] == []  # not yet
        page.run(
            "document.querySelectorAll('#bi-b-qa-log input[type=checkbox]')[1].checked = false"
        )
        page.click_text("#bi-b-qa-log", "加入測試題")
        page.notice("已加入 1 題")
        page.see("bi-b-bq-list", "哪家客戶在評估 TSN")
        assert [q["question"] for q in vault_checks.listing(workspace, vault_id)["questions"]] == [
            QUESTION["question"]
        ]
        # The log shows what was added, not what was offered.
        assert (
            page.run(
                "[...document.querySelectorAll('#bi-b-qa-log input[type=checkbox]')]"
                ".map((t) => t.checked).join()"
            )
            == "true,false"
        )
        page.shoot("3-questions")

        # -- step 3: AI dashboard, applied in one step (K1) -----------------------------------
        agent.then(
            {"tools": [("bi_analysis__sql", {"sql": COUNT})]},
            {
                "tools": [
                    (
                        "bi_analysis__propose_dashboard",
                        {"reply": "先看類型。", "analyses": [BY_TYPE], "order": ["by-type"]},
                    )
                ]
            },
            {"text": "排好了。"},
        )
        page.click("#bi-b-an-new")
        page.wait("!document.getElementById('bi-b-ana').hidden")
        page.set_value("bi-b-ana-msg", "幫我排一個 Dashboard")
        page.click("#bi-b-ana-send")
        page.see("bi-b-ana-log", "套用 Dashboard")
        page.click_text("#bi-b-ana-log", "套用 Dashboard")
        page.notice("已套用 Dashboard")
        layout = analyses.dashboard_layout(vault.Vault(workspace, vault_id).repo.working_units())
        assert layout["order"] == ["by-type"]

        # -- step 3: the bench run, working vs published --------------------------------------
        query = [("bi__query", {"dataset": dataset, "entity_type": "Signal"})]
        agent.then(
            {"tools": query},
            {"grounded": True},  # the working copy: the card is there
            {"tools": query},
            {"grounded": True},  # the pushed version: not yet
        )
        page.wait("!document.getElementById('bi-b-bench-run').disabled")
        page.click("#bi-b-bench-run")
        page.see("bi-b-bench-report", "完成")
        report = page.text_of("bi-b-bench-report")
        assert "工作版本 1/1、發佈版本 0/1" in report and "退步" not in report.replace("退步 0", "")
        page.shoot("3-bench")

        # -- step 3: commit → push → publish ----------------------------------------------------
        page.set_value("bi-b-ver-purpose", "加入客戶訊號、測試題與 Dashboard")
        page.click("#bi-b-ver-commit")
        page.notice("已 commit")
        page.wait("!document.getElementById('bi-b-ver-push').disabled")
        latest = bi_bench.latest(workspace, vault_id)
        assert latest is not None and latest["units_sha256"] == bi_bench.units_digest(
            vault.Vault(workspace, vault_id).repo.working_units()
        )  # the push's content is exactly what was tested
        page.click("#bi-b-ver-push")
        page.notice("已 push")
        page.see("bi-b-ver-history", "加入客戶訊號")
        page.run(
            "[...document.querySelectorAll('#bi-b-ver-history li:first-child button')]"
            ".find((b) => b.textContent === '加 tag').click()"
        )
        page.run("document.querySelector('#bi-b-ver-history .bi-ver-ask input').value = 'v1'")
        page.click("#bi-b-ver-history .bi-ver-ask button.go")
        page.notice("已建立 tag「v1」")
        page.run("window.confirm = () => true")
        page.wait(
            "[...document.querySelectorAll('#bi-b-ver-history button')]"
            ".some((b) => b.textContent === '發佈 v1')"
        )
        page.run(
            "[...document.querySelectorAll('#bi-b-ver-history button')]"
            ".find((b) => b.textContent === '發佈 v1').click()"
        )
        page.see("bi-b-ver-reads", "發佈版本「v1」")
        page.shoot("3-published")

    # -- what users get: the published version has it all ------------------------------------
    assert agent.script == []  # every scripted AI step ran
    target = vault.Vault(workspace, vault_id)
    assert target.reads()["tag"] == "v1"
    published = vault.reading_store(workspace, dataset)
    assert "A 公司評估 TSN" in {c["name"] for c in published.card_rows()}
    assert published.schema_ref() == "bi.schema/v1.1@3.1.0"
    # Nothing is left to commit or push.
    assert target.status()["ahead"] == 0 and target.status()["uncommitted"] == 0
