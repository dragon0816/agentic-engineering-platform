"""The skill AI of a BI vault on the Agent harness (BI T2).

`docs/phases/BI_TEST_AND_TOOLS.md` §4: the turn is a Host sub-run of
`Gateway.converse` with BI tools for that turn only. Here the Agent lists the
sources, tries its draft rule on one (a trial with the draft in place of the
skill: nothing is staged and no card is written), submits an invalid
suggestion, is told why, and submits a valid one. Applying stays the person's.
Both models are scripted; all data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_extract import MEETING_ANSWER, NOTE, Scripted
from test_bi_vault import _call, _ok
from test_business_cards_conversation import Conversation
from test_host_wiring import ready

from capabilities.bi_cards.ai_runs import AiRuntime
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStore
from host_runtime import bi_bench, bi_skill_agent, skill_packs
from host_runtime.assets import shipped
from host_runtime.bi_cards_api import route
from host_runtime.host import build_runtime

NEW_BODY = "類型與資料夾照 schema。\n會議紀錄裡客戶親口說的評估，一律建一張 Signal。"
TOOLS = {
    "bi_skill__sources",
    "bi_skill__read_source",
    "bi_skill__try",
    "bi_skill__compare",
    "bi_skill__test_cases",
    "bi_skill__suggest",
    "bi__query",
}


def test_the_agent_tries_its_draft_and_its_suggestion_is_checked(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    skill_packs.install_bundle(layout, None, shipped=shipped())
    ws = layout.workspace_root
    shared = tmp_path / "shared"
    shared.mkdir()
    made = _ok(_call(ws, "POST", "/api/bi/vaults", {
        "path": str(shared), "title": "Market", "purpose": "虛構", "schema": "bi.schema/v1.1",
        "author": "alice"}))  # fmt: skip
    dataset = made["vault"]["dataset"]
    source = _ok(_call(ws, "POST", "/api/bi/sources", {
        "dataset": dataset, "name": "meeting.md", "text": NOTE,
        "classification": "UNCLASSIFIED"}))["source"]["id"]  # fmt: skip
    extractor = Scripted(MEETING_ANSWER)
    ai = AiRuntime(
        model=lambda: (extractor, "test-model"),
        background=lambda _t, work: work(),
        approved=lambda: ("UNCLASSIFIED", "INTERNAL"),
    )
    opened = {"dataset": dataset, "kind": "skill", "target": "classify"}
    session = _ok(_call(ws, "POST", "/api/bi/sessions", opened))["session"]
    with build_runtime(config, layout=layout) as runtime:
        gateway = runtime.agent.gateway
        agent = Conversation()
        gateway.router.model = agent
        agent.then(
            {"tools": [("bi_skill__sources", {})]},
            {"tools": [("bi_skill__try", {"source_id": source, "changes": {"body": NEW_BODY}})]},
            {
                "tools": [
                    (
                        "bi_skill__suggest",
                        {"reply": "改類型", "changes": {"card_types": ["NoSuchType"]}},
                    )
                ]
            },  # fmt: skip
            {
                "tools": [
                    (
                        "bi_skill__suggest",
                        {
                            "reply": "加上會議紀錄的規則。",
                            "changes": {"body": NEW_BODY},
                            "reasons": ["試跑找到客戶的評估訊號"],
                        },
                    )
                ]
            },  # fmt: skip
            {"text": "我用草稿試跑了會議紀錄，找到一則 Signal；建議如上。"},
        )
        bench = bi_bench.BenchRuntime(
            ask_for=lambda _v, _a: lambda q, s: {},
            extract_for=lambda _v, _a: lambda c: [],
            background=lambda _t, work: work(),
            skill_asker_for=lambda d, s, a: bi_skill_agent.harness_asker(
                gateway, ws, d, s, ai, a, "engineering"
            ),
        )
        body = {"dataset": dataset, "message": "會議紀錄裡客戶說在評估的，要建 Signal"}
        status, answer = route(ws, "alice", "POST", f"/api/bi/sessions/{session['id']}/turns",
                               {}, body, None, ai, bench)  # fmt: skip
        assert status == 200, answer
        live = {t.tool.name for t in gateway.host_tools()} if gateway.host_tools else set()
    turn: dict[str, Any] = answer["session"]["turns"][-1]
    assert turn["error"] is None, turn
    assert turn["suggestion"]["changes"] == {"body": NEW_BODY}
    assert turn["suggestion"]["reasons"] == ["試跑找到客戶的評估訊號"]
    assert turn["attempts"] == 2  # the invalid suggestion was told why and fixed
    sent = turn["sent"]
    assert sent["harness"] is True
    assert [t["name"] for t in sent["tools"]] == [
        "bi_skill__sources", "bi_skill__try", "bi_skill__suggest", "bi_skill__suggest"
    ]  # fmt: skip
    assert [t["ok"] for t in sent["tools"]] == [True, True, False, True]
    # Only the BI tools were offered, and only for that turn.
    assert {t.name for t in agent.requests[0].tools} == TOOLS
    assert not any(name.startswith("bi_skill__") for name in live)
    # The model was told what was wrong with the first suggestion.
    told = "\n".join(m.text for m in agent.requests[3].messages if m.role == "tool")
    assert "NoSuchType" in told
    # The trial read the draft in place of the skill and wrote no card.
    tried = "\n".join(m.text for m in agent.requests[2].messages if m.role == "tool")
    assert "A 公司評估 TSN" in tried
    staging = Staging(ws, dataset)
    (run,) = [r for r in staging.run_rows() if r["kind"] == "trial"]
    rules = (staging.layout(run["id"]) or {})["skills"]
    assert NEW_BODY in rules["text"] and any(s.get("draft") for s in rules["skills"])
    assert BiStore(ws, dataset).card_rows() == []
    # Nothing changed in the vault until the person applies it.
    listed = _ok(_call(ws, "GET", f"/api/bi/vaults/{made['vault']['id']}/skills"))
    classify = next(s for s in listed["skills"] if s["name"] == "classify")
    assert classify["revision"] == 1 and classify["body"] != NEW_BODY
