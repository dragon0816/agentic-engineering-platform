"""`bi_skill__benchmark`: the skill AI sees the effect on what users get.

`docs/phases/BI_BUILD_FLOW.md` §6. A draft skill changes only what is extracted
next, so its trial candidates go to a scratch copy of the working cards and the
vault's graded questions are asked on both. The scratch copy never becomes a
commit, the working cards do not move, and no T1 report is saved, so the result
never satisfies the push check. Both models are scripted; all data is fictional.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from test_bi_extract import MEETING_ANSWER, NOTE, Scripted
from test_bi_vault import _call, _ok
from test_business_cards_conversation import Conversation
from test_host_wiring import ready

from aep_bi.cards import vault
from aep_bi.cards.ai_runs import AiRuntime
from aep_bi.cards.store import BiStore
from aep_bi.host import bi_bench, bi_skill_agent
from aep_bi.host.bi_cards_api import route
from host_runtime import skill_packs
from host_runtime.assets import shipped
from host_runtime.host import build_runtime
from models.contracts import ModelRequest

NEW_BODY = "類型與資料夾照 schema。\n會議紀錄裡客戶親口說的評估，一律建一張 Signal。"


def _told(request: ModelRequest) -> str:
    return "\n".join(m.text for m in request.messages if m.role == "tool")


class _Grounded(Conversation):
    """Asked a question, answers only from what `bi__query` returned, as a grounded
    Agent would; a question it has not looked up yet looks it up."""

    def generate(self, request: ModelRequest) -> Any:
        if self.script[0].get("grounded"):
            self.script[0] = {
                "text": "A 公司正在評估 TSN" if "評估 TSN" in _told(request) else "查不到"
            }
        return super().generate(request)


def _run(
    tmp_path: Path, script: Callable[[str, str], list[dict[str, Any]]], *questions: Any
) -> Any:
    config, layout = ready(tmp_path)
    skill_packs.install_bundle(layout, None, shipped=shipped())
    ws = layout.workspace_root
    shared = tmp_path / "shared"
    shared.mkdir()
    given = {"path": str(shared), "title": "Market", "purpose": "虛構", "schema": "bi.schema/v1.1"}
    made = _ok(_call(ws, "POST", "/api/bi/vaults", {**given, "author": "alice"}))
    dataset, vault_id = made["vault"]["dataset"], made["vault"]["id"]
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
    for question in questions:
        _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/checks", question))
    extractor = Scripted(MEETING_ANSWER)
    ai = AiRuntime(
        model=lambda: (extractor, "test-model"),
        background=lambda _t, work: work(),
    )
    store = BiStore(ws, dataset)
    before = store.path.read_bytes()
    pending = vault.Vault(ws, vault_id).repo.working_units()
    opened = {"dataset": dataset, "kind": "skill", "target": "classify"}
    session = _ok(_call(ws, "POST", "/api/bi/sessions", opened))["session"]
    with build_runtime(config, layout=layout) as runtime:
        gateway = runtime.agent.gateway
        agent = _Grounded()
        gateway.router.model = agent
        agent.then(*script(source, dataset))
        bench = bi_bench.BenchRuntime(
            ask_for=lambda _v, _a: lambda q, s: {},
            extract_for=lambda _v, _a: lambda c: [],
            background=lambda _t, work: work(),
            skill_asker_for=lambda d, s, a: bi_skill_agent.harness_asker(
                gateway, ws, d, s, ai, a, "engineering"
            ),
        )
        body = {"dataset": dataset, "message": "會議紀錄裡客戶說在評估的，要建 Signal"}
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
        "vault_id": vault_id,
        "agent": agent,
        "turn": answer["session"]["turns"][-1],
        "store": store,
        "before": before,
        "pending": pending,
    }


def _tool_result(agent: Conversation, name: str) -> dict[str, Any]:
    for request in reversed(agent.requests):
        for message in reversed(request.messages):
            if message.role == "tool":
                told = json.loads(message.text)
                if told["name"] == name:
                    data: dict[str, Any] = told["host"]["data"]
                    return data
    raise AssertionError(name)


QUESTION = {"question": "哪家客戶在評估 TSN？", "must": "A 公司", "must_not": "B 公司"}


def test_the_tool_shows_the_draft_improves_an_answer(tmp_path: Path) -> None:
    def script(source: str, dataset: str) -> list[dict[str, Any]]:
        query = [("bi__query", {"dataset": dataset, "entity_type": "Signal"})]
        ask: list[dict[str, Any]] = [{"tools": query}, {"grounded": True}]
        return [
            {
                "tools": [
                    (
                        "bi_skill__benchmark",
                        {"changes": {"body": NEW_BODY}, "source_ids": [source]},
                    )
                ]
            },
            *ask,  # the question on the working cards
            *ask,  # the same question on the scratch copy
            {
                "tools": [
                    ("bi_skill__suggest", {"reply": "加上規則", "changes": {"body": NEW_BODY}})
                ]
            },
            {"text": "草稿讓這題答對了。"},
        ]

    found = _run(tmp_path, script, QUESTION)
    turn = found["turn"]
    assert turn["error"] is None, turn
    data = _tool_result(found["agent"], "bi_skill__benchmark")
    (result,) = data["questions"]
    assert result["before"]["passed"] is False  # no card yet: 「查不到」
    assert result["after"]["passed"] is True  # the draft's candidate answers it
    assert data["improved"] == [QUESTION["question"]]
    assert data["regressions"] == []
    assert data["candidates_added"] == 2  # the clean ones of the five candidates
    # The working cards did not move, and no T1 report satisfies the push check.
    assert found["store"].path.read_bytes() == found["before"]
    assert found["store"].card_rows() == []
    assert bi_bench.reports(found["ws"], found["vault_id"]) == []
    assert vault.Vault(found["ws"], found["vault_id"]).repo.working_units() == found["pending"]


def test_without_sources_or_questions_it_says_what_it_could_not_test(tmp_path: Path) -> None:
    found = _run(
        tmp_path,
        lambda _source, _dataset: [
            {"tools": [("bi_skill__benchmark", {"changes": {"body": NEW_BODY}})]},
            {"text": "沒有測試題，看不出影響。"},
        ],
    )
    data = _tool_result(found["agent"], "bi_skill__benchmark")
    assert data["questions"] == [] and data["candidates_added"] == 0
    assert any("測試題" in note for note in data["not_tested"])
    assert any("source_ids" in note for note in data["not_tested"])
