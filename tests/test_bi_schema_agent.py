"""Session A on the Agent harness (`docs/phases/BI_BUILD_FLOW.md` §5).

The turn is a Host sub-run of `Gateway.converse` with read-only tools for that
turn only. Here the Agent looks at the sources and cards, tries operations on a
copy of the draft (the impact on the existing cards, example cards checked
against the result, a trial run of a source under the unsaved schema), submits
an invalid suggestion, is told why, and submits a valid one. Nothing changes until
the person applies it. Both models are scripted; all data is fictional.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from test_bi_extract import MEETING_ANSWER, NOTE, Scripted
from test_bi_vault import _call, _ok
from test_business_cards_conversation import Conversation
from test_host_wiring import ready

from capabilities.bi_cards import schema_session, schema_versions
from capabilities.bi_cards.ai_runs import AiRuntime
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStore, PlannedRow
from host_runtime import bi_bench, bi_schema_agent, skill_packs
from host_runtime.assets import shipped
from host_runtime.bi_cards_api import route
from host_runtime.host import build_runtime

BUDGET = {"name": "budget_band", "label": "預算級距", "kind": "str", "class": "sourced"}
ADD_BUDGET = [{"op": "add_field", "type": "Signal", "field": BUDGET}]
TOOLS = {
    "bi_schema__sources",
    "bi_schema__read_source",
    "bi_schema__cards",
    "bi_schema__try",
    "bi_schema__suggest",
    "bi__query",
}


def _technology(name: str, standard_body: str) -> PlannedRow:
    return PlannedRow(
        row=1,
        entity_type="Technology",
        canonical_key=name.lower(),
        name=name,
        values={"name": name, "standard_body": standard_body},
        synthetic=False,
    )


def _turn(tmp_path: Path, *script: dict[str, Any]) -> dict[str, Any]:
    config, layout = ready(tmp_path)
    skill_packs.install_bundle(layout, None, shipped=shipped())
    ws = layout.workspace_root
    dataset = "lab"
    _ok(_call(ws, "POST", "/api/bi/datasets", {"name": dataset, "schema": "bi.schema/v1.1"}))
    store = BiStore(ws, dataset)
    store.apply([_technology("TSN", "IEEE")], filename="t.csv", entity_type="Technology", actor="x")
    source = _ok(
        _call(
            ws,
            "POST",
            "/api/bi/sources",
            {
                "dataset": dataset,
                "name": "meeting.md",
                "text": NOTE,
                "classification": "UNCLASSIFIED",
            },
        )
    )["source"]["id"]
    draft_id = schema_versions.create_draft(ws, "bi.schema/v1.1", "試", "alice")["draft"]["id"]
    before = store.path.read_bytes()
    extractor = Scripted(MEETING_ANSWER)
    ai = AiRuntime(
        model=lambda: (extractor, "test-model"),
        background=lambda _t, work: work(),
        approved=lambda: ("UNCLASSIFIED", "INTERNAL"),
    )
    opened = {"dataset": dataset, "kind": "schema", "target": draft_id}
    session = _ok(_call(ws, "POST", "/api/bi/sessions", opened))["session"]
    with build_runtime(config, layout=layout) as runtime:
        gateway = runtime.agent.gateway
        agent = Conversation()
        gateway.router.model = agent
        agent.then(*[_with_source(step, source) for step in script])
        bench = bi_bench.BenchRuntime(
            ask_for=lambda _v, _a: lambda q, s: {},
            extract_for=lambda _v, _a: lambda c: [],
            background=lambda _t, work: work(),
            schema_asker_for=lambda d, draft, a: bi_schema_agent.harness_asker(
                gateway, ws, d, draft, ai, a, "engineering"
            ),
        )
        body = {"dataset": dataset, "message": "訊號卡要記預算級距"}
        status, answer = route(
            ws,
            "alice",
            "POST",
            f"/api/bi/sessions/{session['id']}/turns",
            {},
            body,
            None,
            ai,
            bench,
        )
        assert status == 200, answer
    return {
        "ws": ws,
        "dataset": dataset,
        "draft_id": draft_id,
        "session": answer["session"],
        "turn": answer["session"]["turns"][-1],
        "agent": agent,
        "before": before,
        "store": store,
    }


def _with_source(step: dict[str, Any], source: str) -> dict[str, Any]:
    tools = step.get("tools")
    if not tools:
        return step
    filled = [
        (name, {**args, "source_id": source} if args.get("source_id") == "?" else args)
        for name, args in tools
    ]
    return {"tools": filled}


def _result(agent: Conversation, request: int) -> dict[str, Any]:
    """What the last tool returned to the model before model call `request`."""
    told = json.loads(agent.requests[request].messages[-1].text)
    data: dict[str, Any] = told["host"]["data"] or told["host"]["failure"]
    return data


def test_the_agent_tries_its_operations_and_its_suggestion_is_checked(tmp_path: Path) -> None:
    samples = [
        {
            "entity_type": "Signal",
            "name": "好",
            "fields": {"budget_band": "高", "summary": "評估 TSN", "so_what": "要測同步"},
        },
        {"entity_type": "Signal", "name": "壞", "fields": {"no_such_field": "x"}},
        {"entity_type": "NoSuchType", "name": "錯"},
    ]
    found = _turn(
        tmp_path,
        {"tools": [("bi_schema__sources", {})]},
        {"tools": [("bi_schema__read_source", {"source_id": "?"})]},
        {"tools": [("bi_schema__cards", {"type": "Technology"})]},
        {"tools": [("bi_schema__try", {"changes": ADD_BUDGET, "samples": samples})]},
        {"tools": [("bi_schema__try", {"changes": ADD_BUDGET, "source_id": "?"})]},
        {
            "tools": [
                (
                    "bi_schema__suggest",
                    {
                        "reply": "錯的",
                        "verdict": "extend",
                        "changes": [{"op": "add_field", "type": "NoSuchType", "field": BUDGET}],
                    },
                )
            ]
        },
        {
            "tools": [
                (
                    "bi_schema__suggest",
                    {
                        "reply": "訊號卡加上預算級距。",
                        "verdict": "extend",
                        "reasons": ["會議紀錄常提預算"],
                        "changes": ADD_BUDGET,
                    },
                )
            ]
        },
        {"text": "我試過了：既有卡片不受影響，試跑找到一則訊號。"},
    )
    turn, agent, ws, dataset = found["turn"], found["agent"], found["ws"], found["dataset"]
    assert turn["error"] is None, turn
    assert turn["suggestion"]["verdict"] == "extend"
    assert turn["suggestion"]["changes"] == ADD_BUDGET
    assert turn["suggestion"]["result"]["valid"] is True
    assert turn["attempts"] == 2  # the invalid suggestion was told why and fixed
    sent = turn["sent"]
    assert sent["harness"] is True
    assert [t["name"] for t in sent["tools"]] == [
        "bi_schema__sources",
        "bi_schema__read_source",
        "bi_schema__cards",
        "bi_schema__try",
        "bi_schema__try",
        "bi_schema__suggest",
        "bi_schema__suggest",
    ]
    assert [t["ok"] for t in sent["tools"]] == [True] * 5 + [False, True]
    # Only these tools were offered, and the model sees the data it asked for.
    assert {t.name for t in agent.requests[0].tools} == TOOLS
    assert "客戶 A 公司表示正在評估 TSN" in _result(agent, 2)["text"]
    assert "IEEE" in _result(agent, 3)["cards"]
    tried = _result(agent, 4)
    assert any(d.get("field") == "budget_band" for d in tried["diff"])
    assert tried["impact"]["blocked"] == []
    assert "document" not in tried
    assert tried["samples"][0]["problems"] == []
    assert "no_such_field" in tried["samples"][1]["problems"][0]
    assert "NoSuchType" in tried["samples"][2]["problems"][0]
    assert "NoSuchType" in agent.requests[6].messages[-1].text
    # The trial ran under the unsaved schema and wrote no card.
    staging = Staging(ws, dataset)
    (run,) = [r for r in staging.run_rows() if r["kind"] == "trial"]
    assert run["schema_ref"] == f"draft:{found['draft_id']}@rev1"
    assert (staging.layout(run["id"]) or {})["trial_schema"]["schema_id"]
    assert "A 公司評估 TSN" in _result(agent, 5)["trial"]["result"]
    # Nothing changed: the cards, and the draft until the person applies it.
    assert found["store"].path.read_bytes() == found["before"]
    assert schema_versions.draft(ws, found["draft_id"])["revision"] == 1
    applied = schema_session.apply_suggestion(
        ws, dataset, found["session"]["id"], len(found["session"]["turns"]) - 1, "alice"
    )
    assert applied["revision"] == 2


def test_a_question_gets_an_answer_with_nothing_to_apply(tmp_path: Path) -> None:
    found = _turn(tmp_path, {"text": "技術卡有 standard_body 欄位。"})
    suggestion = found["turn"]["suggestion"]
    assert suggestion["verdict"] == "answer" and suggestion["changes"] == []
    assert suggestion["result"]["diff"] == []


def test_an_answer_verdict_cannot_carry_changes() -> None:
    answer = {"reply": "只是回答", "verdict": "answer", "changes": ADD_BUDGET}
    assert any("stay empty" in problem for problem in schema_session._shape(answer))


def test_an_invalid_try_reports_without_a_trial(tmp_path: Path) -> None:
    bad = [{"op": "add_field", "type": "NoSuchType", "field": BUDGET}]
    found = _turn(
        tmp_path,
        {"tools": [("bi_schema__try", {"changes": bad, "source_id": "?"})]},
        {"text": "這個類型不存在，所以不建議。"},
    )
    told = _result(found["agent"], 1)
    assert told["valid"] is False and "NoSuchType" in told["problems"][0]
    assert "trial" not in told
    assert Staging(found["ws"], found["dataset"]).run_rows() == []
