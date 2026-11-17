"""Benchmark questions from an AI conversation (`docs/phases/BI_BUILD_FLOW.md` §7).

The Agent reads the working cards and analyses, tries a draft question, submits
a proposal with an unsupported term, is told why, and submits a valid one.
Nothing is staged until the person ticks questions and adds them; they are then
ordinary `check:question:` units a benchmark run asks. The model is scripted;
all data is fictional.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _ok
from test_business_cards_conversation import Conversation
from test_host_wiring import ready

from aep_bi.cards import analyses, questions_session, vault, vault_checks
from aep_bi.cards.store import BiStore, BiStoreError, PlannedRow
from aep_bi.host import bi_bench, bi_questions_agent
from aep_bi.host.bi_cards_api import route
from host_runtime import skill_packs
from host_runtime.assets import shipped
from host_runtime.host import build_runtime

GOOD = {"question": "TSN 的標準組織是誰？", "must": ["IEEE"], "must_not": ["IETF"]}
SECOND = {"question": "有哪些技術卡？", "must": ["TSN"]}
NOT_THERE = {"question": "TSN 的價格？", "must": ["三千萬"]}
TOOLS = {"bi_questions__analyses", "bi_questions__try", "bi_questions__propose", "bi__query"}


def _vault(ws: Path, tmp_path: Path) -> tuple[str, str]:
    shared = tmp_path / "shared"
    shared.mkdir()
    given = {"path": str(shared), "title": "Market", "purpose": "虛構", "schema": "bi.schema/v1.1"}
    made = _ok(_call(ws, "POST", "/api/bi/vaults", {**given, "author": "alice"}))
    dataset, vault_id = made["vault"]["dataset"], made["vault"]["id"]
    BiStore(ws, dataset).apply(
        [
            PlannedRow(
                row=1,
                entity_type="Technology",
                canonical_key="tsn",
                name="TSN",
                values={"name": "TSN", "standard_body": "IEEE 802.1"},
                synthetic=False,
            )
        ],
        filename="t.csv",
        entity_type="Technology",
        actor="alice",
    )
    return dataset, vault_id


def _add_card(ws: Path, dataset: str) -> None:
    BiStore(ws, dataset).apply(
        [
            PlannedRow(
                row=1,
                entity_type="Technology",
                canonical_key="ethercat",
                name="EtherCAT",
                values={"name": "EtherCAT"},
                synthetic=False,
            )
        ],
        filename="u.csv",
        entity_type="Technology",
        actor="alice",
    )


def _propose(*questions: Any) -> dict[str, Any]:
    args = {
        "reply": "這幾題涵蓋目前的卡片。",
        "questions": list(questions),
        "reasons": ["卡片有寫"],
    }
    return {"tools": [("bi_questions__propose", args)]}


def test_the_agent_proposes_and_only_ticked_questions_are_staged(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    skill_packs.install_bundle(layout, None, shipped=shipped())
    ws = layout.workspace_root
    dataset, vault_id = _vault(ws, tmp_path)
    opened = {"dataset": dataset, "kind": "questions", "target": "main"}
    session = _ok(_call(ws, "POST", "/api/bi/sessions", opened))["session"]
    units_before = vault.Vault(ws, vault_id).repo.working_units()
    with build_runtime(config, layout=layout) as runtime:
        gateway = runtime.agent.gateway
        agent = Conversation()
        gateway.router.model = agent
        agent.then(
            {"tools": [("bi__query", {"dataset": dataset, "entity_type": "Technology"})]},
            {"tools": [("bi_questions__analyses", {})]},
            {"tools": [("bi_questions__try", GOOD)]},
            # The draft question, asked on the working and the published version.
            {"text": "標準組織是 IEEE 802.1。"},
            {"text": "發佈版本查不到。"},
            _propose(GOOD, NOT_THERE),
            _propose(GOOD, SECOND),
            {"text": "出了兩題。"},
        )
        bench = bi_bench.BenchRuntime(
            ask_for=lambda _v, _a: lambda q, s: {},
            extract_for=lambda _v, _a: lambda c: [],
            background=lambda _t, work: work(),
            questions_asker_for=lambda d, a: bi_questions_agent.harness_asker(
                gateway, ws, d, a, "engineering"
            ),
        )
        body = {"dataset": dataset, "message": "出兩題"}
        path = f"/api/bi/sessions/{session['id']}/turns"
        status, answer = route(ws, "alice", "POST", path, {}, body, None, None, bench)
        assert status == 200, answer
    turns = answer["session"]["turns"]
    turn: dict[str, Any] = turns[-1]
    assert turn["error"] is None, turn
    assert turn["attempts"] == 2  # the unsupported term was told and fixed
    assert [q["question"] for q in turn["suggestion"]["questions"]] == [
        GOOD["question"],
        SECOND["question"],
    ]
    assert turn["suggestion"]["questions"][0]["unit"].startswith("check:question:main/")
    assert turn["sent"]["harness"] is True
    assert {t.name for t in agent.requests[0].tools} == TOOLS
    # The try graded both sides and the model saw the grades.
    tried = json.loads(agent.requests[5].messages[-1].text)["host"]["data"]
    assert tried["working"]["passed"] is True and tried["published"]["passed"] is False
    told = json.loads(agent.requests[6].messages[-1].text)["host"]["failure"]["message"]
    assert "三千萬" in told
    # Nothing is staged by the conversation.
    assert vault.Vault(ws, vault_id).repo.working_units() == units_before
    # Only the ticked question is staged, as an ordinary question of the set.
    apply_path = f"/api/bi/sessions/{session['id']}/apply"
    index = len(turns) - 1

    def apply(picks: list[int]) -> tuple[int, dict[str, Any]]:
        given = {"dataset": dataset, "turn": index, "picks": picks}
        return route(ws, "alice", "POST", apply_path, {}, given, None, None, bench)

    refused = apply([])
    assert refused[0] != 200 and refused[1]["code"] == "picks_empty"
    status, applied = apply([1])
    assert status == 200, applied
    listed = vault_checks.listing(ws, vault_id)["questions"]
    assert [q["question"] for q in listed] == [SECOND["question"]]
    assert listed[0]["must"] == ["TSN"] and listed[0]["set"] == "main"
    assert applied["session"]["turns"][-1]["applied"]["units"] == [listed[0]["unit"]]


def _check(answer: dict[str, Any], existing: set[str] | None = None) -> list[str]:
    return questions_session.check_proposal(answer, "main", existing or set(), lambda: "tsn ieee")


def test_what_a_proposal_may_not_be() -> None:
    assert _check({"reply": "只是回答"}) == []
    assert _check({"questions": []})  # no reply
    assert _check({"reply": "r", "questions": ["not an object"]})
    assert _check({"reply": "r", "questions": [{"question": "q", "must": ["TSN"]}] * 21})
    # Graded, and supported by what the knowledge base holds (case-insensitive).
    assert _check({"reply": "r", "questions": [{"question": "q", "must": ["ieee"]}]}) == []
    assert _check({"reply": "r", "questions": [{"question": "q", "must_not": ["x"]}]}) == []
    ungraded = _check({"reply": "r", "questions": [{"question": "q"}]})
    assert "cannot be graded" in ungraded[0]
    assert (
        "in no card" in _check({"reply": "r", "questions": [{"question": "q", "must": ["x"]}]})[0]
    )
    # A repeat of a saved question, or of one in the same proposal.
    unit, _ = vault_checks.checked_question({"question": "q", "must": ["TSN"], "set": "main"})
    one = {"question": "q", "must": ["TSN"]}
    assert "already" in _check({"reply": "r", "questions": [one]}, {unit})[0]
    assert "already" in _check({"reply": "r", "questions": [one, one]})[0]


def test_a_term_may_come_from_a_saved_analysis_result(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    ws = layout.workspace_root
    del config
    dataset, vault_id = _vault(ws, tmp_path)
    analyses.save(ws, vault_id, {
        "title": "類型", "slug": "types", "kind": "sql",
        "code": "SELECT 'only-in-analysis' AS word", "chart": {"type": "table"}})  # fmt: skip
    text = questions_session._corpus(ws, dataset)
    assert "only-in-analysis" in text and "ieee 802.1" in text


def test_results_are_run_again_only_when_something_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _config, layout = ready(tmp_path)
    ws = layout.workspace_root
    dataset, vault_id = _vault(ws, tmp_path)
    analyses.save(ws, vault_id, {
        "title": "類型", "slug": "types", "kind": "sql",
        "code": "SELECT 'one' AS word", "chart": {"type": "table"}})  # fmt: skip
    ran: list[Any] = []
    real = analyses.run_saved

    def counted(*args: Any, **kwargs: Any) -> Any:
        ran.append(args[2])
        return real(*args, **kwargs)

    monkeypatch.setattr(analyses, "run_saved", counted)
    first = questions_session.saved_results(ws, vault_id)
    count = len(ran)
    assert count == len(first) > 0
    first[0]["table"]["rows"] = "changed by a caller"  # a caller's copy, not the kept one
    second = questions_session.saved_results(ws, vault_id)
    assert len(ran) == count and second[0]["table"]["rows"] != "changed by a caller"
    # A new analysis or new cards run them again.
    analyses.save(ws, vault_id, {
        "title": "另一個", "slug": "other", "kind": "sql",
        "code": "SELECT 'two' AS word", "chart": {"type": "table"}})  # fmt: skip
    assert "other" in {e["slug"] for e in questions_session.saved_results(ws, vault_id)}
    assert len(ran) > count
    count = len(ran)
    _add_card(ws, dataset)
    questions_session.saved_results(ws, vault_id)
    assert len(ran) > count


def test_outside_agent_web_or_a_vault_there_is_no_turn(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    ws = layout.workspace_root
    del config
    dataset, _ = _vault(ws, tmp_path)
    made = questions_session.create_session(ws, dataset, "", "alice")
    assert made["target_ref"] == "questions:main"
    with pytest.raises(BiStoreError) as caught:
        questions_session.session_turn(
            ws, dataset, made["id"], message="出題", actor="a", asker=None
        )
    assert caught.value.code == "harness_unavailable"
    _ok(_call(ws, "POST", "/api/bi/datasets", {"name": "lab", "schema": "bi.schema/v1.1"}))
    with pytest.raises(BiStoreError) as refused:
        questions_session.create_session(ws, "lab", "main", "alice")
    assert refused.value.code == "not_a_vault"
