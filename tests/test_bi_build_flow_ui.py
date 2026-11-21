"""The whole BI build flow in one browser test (`docs/phases/BI_BUILD_FLOW.md` §8).

The real Agent Web server, routes and harness wiring in a temporary workspace,
with a temporary folder as the shared folder and scripted Agent and extractor
models: upload → Markdown → convert to a vault → a schema draft edited in Ingest's ⚙,
published and the vault moved to it → a judging rule changed in the rule form → ingest
trial, review and write → AI benchmark questions → AI dashboard (K1), each AI session in
its own side tab → bench run working vs published → 分享 in its side tab (commit, push,
tag, publish in one step), ending with what the Agent reads. The step-2 AI sessions
(schema and rule) left the page on 2026-11-20 and are asserted gone.
Each AI step gets its next replies just before the person sends the message. All
data is fictional. Screenshots in `.scratch/bi-flow/` with `AEP_UI_SHOTS`.
"""

from __future__ import annotations

import json
import os
import re
import threading
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_ai_proposed_changes import _config
from test_bi_extract import MEETING_ANSWER, NOTE, Scripted
from test_bi_skill_benchmark import _Grounded
from test_draft_install_cards import _AuthoringClaude, _lab
from test_host_wiring import host_json

from aep_bi.cards import analyses, schema_versions, vault, vault_checks
from aep_bi.cards.ai_runs import AiRuntime
from aep_bi.cards.store import BiStore
from aep_bi.host import bi_bench, bi_cards_api
from host_runtime import skill_packs
from host_runtime.assets import shipped
from host_runtime.conversation_backends import LocalConversationBackends
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer

BUDGET = {"name": "budget_band", "label": "預算級距", "kind": "str", "class": "sourced"}
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
    answer: dict[str, Any] = {"now": MEETING_ANSWER}
    extractor = Scripted(lambda _chunk: answer["now"])  # the same note in every run
    monkeypatch.setattr(
        bi_cards_api,
        "web_ai_runtime",
        lambda _web: AiRuntime(
            model=lambda: (extractor, "test-model"),
            background=lambda _t, work: work(),
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
        # A row of the dataset just left, still on screen, cannot be picked (it would be
        # dropped as the new list arrives, leaving step 2's later parts shut).
        assert page.run(
            "(() => { const real = biDataset, before = bi.build.sourceId;"
            " const row = document.querySelector('#bi-b-sources tbody input');"
            " biDataset = () => 'another'; bi.build.sourceId = null; row.checked = false;"
            " row.click(); const untouched = bi.build.sourceId === null && !row.checked;"
            " biDataset = real; bi.build.sourceId = before; row.checked = true;"
            " return untouched; })()"
        )
        page.shoot("1-converted")

        # -- step 2a: the schema draft in Ingest's gear: edit, publish, upgrade --------------
        page.stage("schema")
        # The schema AI session left the page (owner 2026-11-20, dfa6d025): a draft is edited
        # in the gear, or a schema file comes in through 匯入.
        assert page.run("document.getElementById('bi-b-sa-open') === null")
        page.click("#bi-b-draft-new")
        page.wait("!document.getElementById('bi-b-draft').hidden")
        page.see("bi-b-draft-info", "第 1 版")
        page.run(
            "(() => { const box = document.getElementById('bi-b-draft-text');"
            " const doc = JSON.parse(box.value);"
            " doc.types.find((t) => t.name === 'Signal').fields.push("
            + json.dumps(BUDGET, ensure_ascii=False)
            + "); box.value = JSON.stringify(doc, null, 1); })()"
        )
        page.set_value("bi-b-draft-note", "訊號卡加上預算級距")
        page.click("#bi-b-draft-save")
        page.see("bi-b-draft-info", "第 2 版")
        assert "訊號卡加上預算級距" in page.text_of("bi-b-draft-info")
        page.shoot("2a-draft")
        # The draft on the main path is a table of what changes; its JSON is under 進階 (F8).
        page.see("bi-b-draft-table", "budget_band")
        assert "新增欄位" in page.text_of("bi-b-draft-table")
        assert "都是新增" in page.text_of("bi-b-draft-sum")
        page.shoot("2a-draft-table")
        # 套用到資料集 on the main path: publish, then the same preview and confirm.
        page.click("#bi-b-draft-use")
        page.see("bi-b-upgrade", "套用升級")
        assert "版本不變" in page.text_of("bi-b-upgrade")
        page.click_text("#bi-b-upgrade", "套用升級")
        # What really happened, readable, never a digest (acceptance F6).
        page.notice("相容的新增，不是新版本")
        assert "5.0 加 1 項新增" in page.text_of("bi-notice")
        page.see("bi-b-schema-now", "5.0 加 1 項新增")
        assert "+" not in page.text_of("bi-b-schema-now")
        assert "5.0" not in page.text_of("bi-b-versions"), "plain 5.0 would drop the addition"
        # A new field is an addition on the version, not a version of its own (§4.3).
        assert BiStore(workspace, dataset).schema_ref().startswith("bi.schema/v1.1@5.0.0+")
        assert schema_versions.drafts(workspace)  # the draft itself stays

        # -- step 2a: a judging rule changed in the rule form, saved as a new revision ---------
        # 和 AI 一起修改 left the rule list (dfa6d025); 修改 opens the rule form.
        page.see("bi-b-sk-list", "classify")
        classify = (
            "[...document.querySelectorAll('#bi-b-sk-list tbody tr')]"
            ".find((r) => r.textContent.includes('classify'))"
        )
        assert page.run(f"{classify}.textContent.includes('和 AI')") is False
        page.run(
            f"[...{classify}.querySelectorAll('button')]"
            ".find((b) => b.textContent === '修改').click()"
        )
        page.wait("!document.getElementById('bi-b-sk-form').hidden")
        assert page.run("document.getElementById('bi-b-sk-name').value") == "classify"
        assert page.run("document.getElementById('bi-b-sk-name').readOnly") is True
        page.set_value("bi-b-sk-body", RULE)
        page.click("#bi-b-sk-form button[type=submit]")
        page.notice("判讀規則「classify」存成第")
        page.wait("document.getElementById('bi-b-sk-form').hidden")
        revision = re.search(r"存成第 (\d+) 版", page.text_of("bi-notice"))
        assert revision is not None
        page.wait(f"{classify}.textContent.includes('第 {revision.group(1)} 版')")
        page.shoot("2a-rule")

        # -- steps 2b–2e: trial → ingest → review → write --------------------------------------
        store = BiStore(workspace, dataset)
        before = len(store.card_rows())
        page.stage("method")
        page.shoot("2b-ingest")
        # A run that makes nothing says why, in the model's words, not just an empty list.
        answer["now"] = {"candidates": [], "notes": "這份來源沒有客戶說的話"}
        page.click("#bi-b-trial")
        page.see("bi-b-trial-result", "AI 沒有建立候選卡，它的說明：這份來源沒有客戶說的話")
        answer["now"] = MEETING_ANSWER
        # The same request would repeat the empty answer; the person asks anew.
        page.click("#bi-b-fresh")
        page.click("#bi-b-trial")
        page.see("bi-b-trial-result", "A 公司評估 TSN")
        page.click("#bi-b-fresh")
        page.see("bi-b-trial-result", "試跑完成")
        assert "A 公司評估 TSN" in page.text_of("bi-b-trial-result")
        assert len(store.card_rows()) == before  # a trial writes nothing
        page.click("#bi-b-start")
        page.wait("!document.querySelector('#bi-view-build .kp-stage[data-stage=review]').hidden")
        page.wait("document.querySelectorAll('#bi-b-cands button').length > 0")
        page.shoot("2c-review")
        page.click("#bi-b-apply-all")
        page.wait("!document.getElementById('bi-b-next4').disabled")
        assert len(store.card_rows()) == before  # review writes nothing
        page.click("#bi-b-next4")
        page.wait("!document.querySelector('#bi-view-build .kp-stage[data-stage=commit]').hidden")
        page.click("#bi-b-commit-go")
        page.see("bi-b-done", "已寫入")
        assert "A 公司評估 TSN" in {c["name"] for c in store.card_rows()}
        # Every accepted candidate was written, not only those accepted before moving on.
        accepted = int(str(page.run("bi.build.run.summary.accepted")))
        assert accepted >= 2 and len(store.card_rows()) - before == accepted

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
        # A question belongs to a domain: 全部領域 only reads.
        page.wait("(bi.build.homes || []).length > 0")
        page.choose("bi-b-src-folder", str(page.run("bi.build.homes[0].folder")))
        # Questions are set in the stage's ⚙ tab; the AI session opens as a side tab of its own
        # (owner 2026-11-20): chosen, in the side area, and the main view keeps only its run.
        page.gear("test")
        page.click("#bi-b-qa-open")
        page.ai_opened("questions")
        side_tabs = "[...document.querySelectorAll('#extra-tabs [role=tab]')]"
        side_tab = side_tabs + ".find((t) => t.textContent === {!r})"
        page.wait(f"{side_tabs}.map((t) => t.textContent).includes('和 AI 出測試題')")
        assert page.run(f"{side_tab.format('和 AI 出測試題')}.getAttribute('aria-selected')") == (
            "true"
        )
        assert page.run("document.getElementById('bi-ai').closest('.extra-panel') !== null")
        assert page.run("!document.getElementById('kn-pane-bi').contains("
                        "document.getElementById('bi-ai'))")  # fmt: skip
        # The step's own tabs stay Benchmark | Dashboard: no AI tab among them.
        assert "AI" not in page.text_of("bi-b-tabs")
        visible = (
            "(() => { const r = document.getElementById('bi-ai-send').getBoundingClientRect();"
            " return r.height > 0 && r.bottom <= innerHeight && r.top >= 0; })()"
        )
        assert page.run(visible)
        # What is typed stays across tab switches; the ⚙ tab shows the questions.
        page.set_value("bi-ai-msg", "還沒送出的草稿")
        page.run(f"{side_tab.format('Benchmark testing 設定')}.click()")
        page.wait("document.getElementById('bi-b-bq-list').offsetParent !== null")
        assert page.run("document.getElementById('bi-b-bench').open")
        assert page.run("document.getElementById('bi-ai').offsetParent === null")
        page.run(f"{side_tab.format('和 AI 出測試題')}.click()")
        page.wait("document.getElementById('bi-ai').offsetParent !== null")
        assert page.run("document.getElementById('bi-ai-msg').value") == "還沒送出的草稿"
        assert page.run(visible)
        page.set_value("bi-ai-msg", "出題")
        page.click("#bi-ai-send")
        page.see("bi-ai-log", "加入測試題")
        assert "必須提到：A 公司" in page.text_of("bi-ai-log")
        assert vault_checks.listing(workspace, vault_id)["questions"] == []  # not yet
        page.run("document.querySelectorAll('#bi-ai-log input[type=checkbox]')[1].checked = false")
        page.click_text("#bi-ai-log", "加入測試題")
        page.notice("已加入 1 題")
        page.see("bi-b-bq-list", "哪家客戶在評估 TSN")
        assert [q["question"] for q in vault_checks.listing(workspace, vault_id)["questions"]] == [
            QUESTION["question"]
        ]
        # The log shows what was added, not what was offered.
        assert (
            page.run(
                "[...document.querySelectorAll('#bi-ai-log input[type=checkbox]')]"
                ".map((t) => t.checked).join()"
            )
            == "true,false"
        )
        page.shoot("3-questions")
        # Closing the session removes its side tab only; the panel goes back to its home.
        page.click("#bi-ai-close")
        page.wait("document.getElementById('bi-ai').hidden")
        page.wait(f"!{side_tabs}.some((t) => t.textContent === '和 AI 出測試題')")
        # The stages' ⚙ tabs opened above stay.
        assert page.run(f"{side_tabs}.map((t) => t.textContent)") == [
            "Ingest 設定",
            "Benchmark testing 設定",
        ]
        assert page.run("document.getElementById('kn-pane-bi').contains("
                        "document.getElementById('bi-ai'))")  # fmt: skip
        assert page.run("bi.ais.size") == 0

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
        page.ai_opened("analysis")
        # The Dashboard's AI is a side tab too, chosen as it opens.
        page.wait(f"{side_tabs}.map((t) => t.textContent).includes('和 AI 做新分析')")
        assert page.run(f"{side_tab.format('和 AI 做新分析')}.getAttribute('aria-selected')") == (
            "true"
        )
        assert page.run("document.getElementById('bi-ai').closest('.extra-panel') !== null")
        page.set_value("bi-ai-msg", "幫我排一個 Dashboard")
        page.click("#bi-ai-send")
        page.see("bi-ai-log", "套用 Dashboard")
        page.click_text("#bi-ai-log", "套用 Dashboard")
        page.notice("已套用 Dashboard")
        # Applied in a working domain, it is that domain's Dashboard.
        layout = analyses.dashboard_layout(
            vault.Vault(workspace, vault_id).repo.working_units(), str(page.run("biScope()"))
        )
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

        # -- step 3: 分享, one step: commit → push → tag → publish ----------------------------
        latest = bi_bench.latest(workspace, vault_id)
        assert latest is not None and latest["units_sha256"] == bi_bench.units_digest(
            vault.Vault(workspace, vault_id).repo.working_units()
        )  # the share's content is exactly what was tested
        # 分享 opens as a tab of the side area (owner 2026-11-20).
        page.click("#bi-b-ver-open")
        page.wait("document.getElementById('bi-b-ver').closest('.extra-panel') !== null")
        page.see("bi-b-share-list", "還沒 commit 的改動")
        page.see("bi-b-share-tests", "通過")
        today = date.today().isoformat()
        assert page.run("document.getElementById('bi-b-share-tag').value") == today
        page.set_value("bi-b-ver-purpose", "加入客戶訊號、測試題與 Dashboard")
        page.click("#bi-b-share-go")
        page.wait("!!document.querySelector('#bi-b-share-act .bi-confirm')")
        page.click_text("#bi-b-share-act .bi-confirm", "確定分享")
        page.wait(
            "[...document.querySelectorAll('#bi-b-share-progress li')]"
            ".every((li) => li.dataset.state === 'done')"
        )
        page.see("bi-b-ver-reads", "發佈版本「" + today + "」")
        page.see("bi-b-ver-history", "加入客戶訊號")
        page.see("bi-b-share-list", "沒有新的內容")
        page.shoot("3-published")

    # -- what users get: the published version has it all ------------------------------------
    assert agent.script == []  # every scripted AI step ran
    target = vault.Vault(workspace, vault_id)
    assert target.reads()["tag"] == date.today().isoformat()
    published = vault.reading_store(workspace, dataset)
    assert "A 公司評估 TSN" in {c["name"] for c in published.card_rows()}
    assert published.schema_ref().startswith("bi.schema/v1.1@5.0.0+")
    # Nothing is left to commit or push.
    assert target.status()["ahead"] == 0 and target.status()["uncommitted"] == 0
