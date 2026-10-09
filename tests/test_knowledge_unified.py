"""Knowledge on the shared Harness for both routes (unification U5, owner 2026-10-09).

The tool route runs the Knowledge Harness and returns its validated answer as
the turn's answer; a retry, budgeted by the Knowledge Skill, asks again with
wider retrieval."""

from __future__ import annotations

from typing import Any

from test_knowledge_vault_tools import RS, CallsVault, Recording, converse, gateway

from host_runtime.knowledge_harness import broaden
from host_runtime.knowledge_observation import KnowledgeBridgeActions
from knowledge.procedure import KnowledgeProcedure

PROCEDURE = KnowledgeProcedure.model_validate({
    "intent_patterns": ["CMP180"],
    "facets": [{"name": "technical", "request_patterns": ["standard"],
                "search_queries": ["CMP180 standards"], "support_terms": ["standard"]}],
})


def test_a_validated_harness_answer_is_the_turn_answer_without_a_rewrite() -> None:
    model, handler = CallsVault("knowledge__rs-knowledge", {"question": "CMP180?"}), Recording()
    built = gateway(model, handler)
    asked: list[Any] = []

    def harness(question: str, asset: Any) -> dict[str, Any]:
        asked.append((question, asset))
        return {"ok": True, "answer": "CMP180 supports 5G NR [1].", "evidence": {}}

    built.knowledge_harness = harness
    import asyncio

    from test_gateway import request

    from models.contracts import ModelMessage

    result = asyncio.run(built.converse(request("CMP180 支援哪些標準？"),
                                        (ModelMessage(role="user", text="CMP180?"),)))
    assert result.text == "CMP180 supports 5G NR [1]." and len(model.calls) == 1
    assert asked == [("CMP180?", RS)] and handler.inputs == []  # no raw capability call


def test_a_validated_tool_answer_keeps_its_cited_passages_for_checking() -> None:
    model, handler = CallsVault("knowledge__rs-knowledge", {"question": "CMP180?"}), Recording()
    built = gateway(model, handler)
    record = {"answer": {"passages": [{"text": "CMP180 supports 5G NR",
                                       "citation": {"kind": "wiki", "wiki_page": "wiki/a.md"}}]}}
    built.knowledge_harness = lambda question, asset: {
        "ok": True, "answer": "CMP180 supports 5G NR [1].", "evidence": {}, "record": record,
        "harness": {"phase": "validated"}, "outcome": {"failure": None}}
    import asyncio

    from test_gateway import request

    from models.contracts import ModelMessage

    result = asyncio.run(built.converse(request("q"), (ModelMessage(role="user", text="q"),)))
    data = result.tools[0].host.data
    assert data["record"] == record and data["phase"] == "validated"
    assert data["failure_code"] is None


def test_an_unvalidated_answer_goes_back_to_the_model_marked_as_such() -> None:
    model, handler = CallsVault("knowledge__rs-knowledge", {"question": "CMP180?"}), Recording()
    built = gateway(model, handler)
    built.knowledge_harness = lambda question, asset: {
        "ok": False, "answer": "No sufficient evidence.", "evidence": None,
        "outcome": {"capability": {"failure": {"code": "knowledge_insufficient_evidence"}}}}
    import asyncio

    from test_gateway import request

    from models.contracts import ModelMessage

    result = asyncio.run(built.converse(request("q"), (ModelMessage(role="user", text="q"),)))
    assert result.text == "answered" and len(model.calls) == 2
    observation = model.calls[1].messages[-1].text
    assert "not_validated" in observation and "not from the knowledge base" in observation
    assert '"record"' not in observation  # the model's observation stays small
    assert '"failure_code": "knowledge_insufficient_evidence"' in observation


def test_without_a_harness_the_tool_route_keeps_the_bridge_call() -> None:
    model, handler = CallsVault("knowledge__rs-knowledge", {"question": "CMP180?"}), Recording()
    converse(model, handler)
    assert handler.inputs and handler.inputs[0].asset == RS


def test_a_retry_widens_retrieval_and_the_skill_budget_bounds_it() -> None:
    wider = broaden(PROCEDURE, 1)
    assert wider.facets[0].collect_all_queries and wider.facets[0].max_passages == 5
    assert wider.wiki_index_hits == 16 and wider.citation_policy == PROCEDURE.citation_policy

    def failing(code: str) -> dict[str, Any]:
        return {"ok": False, "outcome": {"capability": {"failure": {"code": code}}}}

    asked: list[int] = []

    def again(attempt: int) -> dict[str, Any]:
        asked.append(attempt)
        return {"ok": True, "answer": "x", "record": None}

    actions = KnowledgeBridgeActions(lambda: failing("knowledge_insufficient_evidence"),
                                     required_evidence=("raw_citations",), broadened=again,
                                     retry_budget=1)
    assert actions.execute() == "bridge_knowledge_answer" and asked == [1]
    none_left = KnowledgeBridgeActions(lambda: failing("knowledge_insufficient_evidence"),
                                       required_evidence=(), broadened=again, retry_budget=0)
    try:
        none_left.execute()
        raise AssertionError("expected a stop")
    except Exception as error:  # noqa: BLE001 - HarnessActionFailure
        assert getattr(error, "code", "") == "knowledge_insufficient_evidence"
    assert asked == [1]
