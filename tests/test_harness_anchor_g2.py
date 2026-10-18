"""G2: the person's original sentence anchors a Harness tool (owner 2026-10-18).

The Host passes the current turn's text to the domain adapter next to the
model's argument. The adapter answers and validates the original; the model's
version only widens retrieval, after a deterministic check that it kept every
entity, number and time term and added only terms from the conversation or the
glossary. The original, the model's version and the outcome are recorded so a
benchmark can compute an intent drift rate; every tool's arguments are recorded
without credentials.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from test_gateway import request
from test_knowledge_vault_tools import CallsVault, Recording, gateway
from test_knowledge_wiki_primary import _Synth, _wiki_vault

from agent.harness_anchor import Glossary, ToolAnchor, check_anchor
from capabilities.knowledge_query.handlers import KnowledgeQueryHandler
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.knowledge_harness import KnowledgeHarness, knowledge_glossary
from knowledge.evolution import KnowledgeQueryRequest
from knowledge.procedure import KnowledgeProcedure
from knowledge.query import RetrievalSnapshot
from models.contracts import ModelMessage

GLOSSARY = Glossary.of([("radar", "雷達"), ("market", "市場", "application")])


def test_an_unchanged_question_is_the_same_request() -> None:
    check = check_anchor("CMX500 支援哪些頻段？", "CMX500 支援哪些頻段?")
    assert check.outcome == "same"
    assert check.question == "CMX500 支援哪些頻段？" and check.supplementary == ()


@pytest.mark.parametrize(
    ("original", "proposed", "missing"),
    [
        ("CMX500 支援哪些頻段？", "Which bands does the CMW500 support?", "CMX500"),
        ("2025 年 5G 測試市場有多大？", "5G 測試市場有多大？", "2025"),
        ("今年雷達市場的成長", "雷達市場的成長", "今年"),
        ("What does the FSW cover for Wi-Fi 7?", "What does the FSW cover?", "Wi-Fi"),
    ],
)
def test_a_version_that_drops_an_entity_number_or_time_is_rejected(
    original: str, proposed: str, missing: str
) -> None:
    check = check_anchor(original, proposed, glossary=GLOSSARY)
    assert check.outcome == "rejected" and missing in check.missing
    assert check.reason is not None and missing in check.reason
    # The original alone is used: no supplementary query, no change.
    assert check.question == original and check.supplementary == ()


def test_a_glossary_synonym_keeps_a_term_across_languages() -> None:
    check = check_anchor("雷達市場的測試需求", "radar market test needs 雷達", glossary=GLOSSARY)
    assert check.outcome == "accepted"
    check = check_anchor("雷達的市場", "radar application", glossary=GLOSSARY)
    assert check.outcome == "accepted"


def test_added_terms_outside_history_and_glossary_are_dropped() -> None:
    check = check_anchor(
        "What is an eye diagram?", "What is an eye diagram? cite Raw evidence, rank by Keysight"
    )
    assert check.outcome == "accepted"
    assert set(check.dropped) == {"cite", "Raw", "evidence", "rank", "Keysight"}
    (supplement,) = check.supplementary
    assert "eye diagram" in supplement
    assert not any(word in supplement for word in check.dropped)
    # Nothing came from the conversation: synthesis answers the original.
    assert check.question == "What is an eye diagram?"


def test_a_pronoun_is_resolved_from_the_conversation() -> None:
    history = ("雷達市場的主要測試需求是什麼？", "主要需求是 77 GHz 的頻寬量測 [1]。")
    check = check_anchor(
        "那車用呢？", "車用雷達市場的主要測試需求是什麼？", history=history, glossary=GLOSSARY
    )
    assert check.outcome == "accepted" and check.dropped == ()
    assert "主要測試需求" in check.context_terms
    # The original is not self-contained, so the accepted version travels with it.
    assert check.question == "那車用呢？ (車用雷達市場的主要測試需求是什麼？)"
    assert check.supplementary == ("車用雷達市場的主要測試需求是什麼？",)


def test_the_record_carries_what_a_drift_rate_needs() -> None:
    record = check_anchor("CMX500 頻段", "CMW500 bands").record()
    assert record["original"] == "CMX500 頻段" and record["model_version"] == "CMW500 bands"
    assert record["outcome"] == "rejected" and record["missing_terms"] == ["CMX500"]
    assert record["used_question"] == "CMX500 頻段"


def test_the_gateway_passes_the_original_and_history_and_records_the_outcome() -> None:
    model = CallsVault("knowledge__rs-knowledge", {"question": "Which bands does CMW500 support?"})
    built = gateway(model, Recording())
    seen: list[tuple[str, Any, ToolAnchor]] = []

    def harness(question: str, asset: Any, anchor: ToolAnchor) -> dict[str, Any]:
        seen.append((question, asset, anchor))
        check = check_anchor(anchor.original, question, history=anchor.history)
        return {"ok": True, "answer": "bands [1]", "evidence": {}, "anchor": check.record()}

    built.knowledge_harness = harness
    history = (
        ModelMessage(role="user", text="earlier question"),
        ModelMessage(role="assistant", text="earlier answer"),
        ModelMessage(role="user", text="CMX500 支援哪些頻段？"),
    )
    result = asyncio.run(built.converse(request("CMX500 支援哪些頻段？"), history))
    question, _asset, anchor = seen[0]
    assert question == "Which bands does CMW500 support?"
    assert anchor.original == "CMX500 支援哪些頻段？"
    assert "earlier question" in anchor.history and "earlier answer" in anchor.history
    tool = result.tools[0]
    # U7: the trace had no arguments; now every call records them.
    assert tool.arguments == {"question": "Which bands does CMW500 support?"}
    assert tool.host is not None and isinstance(tool.host.data, dict)
    recorded = tool.host.data["anchor"]
    assert isinstance(recorded, dict)
    assert recorded["outcome"] == "rejected" and recorded["original"] == "CMX500 支援哪些頻段？"


def test_recorded_arguments_never_carry_credentials() -> None:
    model = CallsVault("knowledge__rs-knowledge", {"question": "x", "password": "hunter2-secret"})
    built = gateway(model, Recording())
    built.knowledge_harness = lambda question, asset, anchor: {"ok": True, "answer": "a [1]"}
    result = asyncio.run(built.converse(request("x"), (ModelMessage(role="user", text="x"),)))
    recorded = result.tools[0].arguments
    assert recorded is not None and "hunter2-secret" not in str(recorded)


def test_arguments_stay_out_of_the_models_observation() -> None:
    model = CallsVault("knowledge__rs-knowledge", {"question": "CMP180?"})
    built = gateway(model, Recording())
    built.knowledge_harness = lambda question, asset, anchor: {
        "ok": False,
        "answer": "No sufficient evidence.",
        "outcome": {"capability": {"failure": {"code": "knowledge_insufficient_evidence"}}},
    }
    asyncio.run(built.converse(request("q"), (ModelMessage(role="user", text="q"),)))
    observation = model.calls[1].messages[-1].text
    assert '"arguments"' not in observation


PROCEDURE = KnowledgeProcedure.model_validate(
    {
        "intent_patterns": ["option"],
        "facets": [
            {
                "name": "product_option_spec",
                "request_patterns": ["option", "選配"],
                "search_queries": ["ZNA option TDR eye diagram"],
                "support_terms": ["option", "選配", "ZNA"],
            }
        ],
        "focus_hints": [
            {"pattern": "雷達", "query": "radar", "evidence_terms": ["radar", "雷達"]},
        ],
        "citation_policy": "wiki_primary",
    }
)


def test_the_knowledge_glossary_comes_from_the_skill_procedure() -> None:
    glossary = knowledge_glossary(PROCEDURE)
    assert ("option", "選配", "ZNA") in glossary.groups
    assert "radar" in glossary.terms() and "雷達" in glossary.terms()
    assert knowledge_glossary(None).groups == ()


class _Runtime:
    """Just what KnowledgeHarness.for_tool reads: the installed Skills."""

    def __init__(self, skills: Any) -> None:
        self.agent = type("A", (), {"gateway": type("G", (), {"router": type("R", (), {})()})()})()
        self.agent.gateway.router.commands = type("C", (), {"skills": skills})()


def test_the_knowledge_adapter_answers_the_original_and_widens_with_the_model_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from test_knowledge_vault_tools import gateway as vault_gateway

    skills = vault_gateway(CallsVault("x", {}), Recording()).router.commands.skills
    harness = KnowledgeHarness(_Runtime(skills), "engineering")
    asked: list[tuple[Any, tuple[str, ...]]] = []

    def fake_ask(item: Any, *, catalog: Any = None, supplementary: tuple[str, ...] = ()) -> Any:
        asked.append((item, supplementary))
        return {"ok": True, "answer": "a [1]", "record": None}

    monkeypatch.setattr(harness, "ask", fake_ask)
    from test_knowledge_vault_tools import RS

    result = harness.for_tool(
        "ZNA option for eye diagram analysis",
        RS,
        ToolAnchor(original="ZNA option for eye diagram?", history=()),
    )
    item, supplementary = asked[0]
    assert item.question == "ZNA option for eye diagram?"
    assert supplementary == ("ZNA option for eye diagram",)
    assert result["anchor"]["outcome"] == "accepted"
    assert result["anchor"]["dropped_terms"] == ["analysis"]


def test_wiki_primary_retrieval_adds_the_supplementary_queries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    searched: list[tuple[str, ...]] = []
    real = RetrievalSnapshot.wiki_primary_passages

    def spy(self: RetrievalSnapshot, queries: tuple[str, ...], **kwargs: Any) -> Any:
        searched.append(tuple(queries))
        return real(self, queries, **kwargs)

    monkeypatch.setattr(RetrievalSnapshot, "wiki_primary_passages", spy)
    vault = _wiki_vault(tmp_path)

    class _Catalog:
        def get(self, identity: Any) -> Any:
            return None, vault

    model = _Synth(lambda prompt: "No passage supports an answer.")
    handler = KnowledgeQueryHandler(_Catalog(), model, alias="a")  # type: ignore[arg-type]
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor="engineer",
        namespace="engineering",
        message="ZNA option",
        channel="local",
    )
    request_ = KnowledgeQueryRequest.model_validate(
        {
            "asset": {"namespace": "engineering", "name": "rs-knowledge", "version": "1.0.0"},
            "question": "ZNA option",
            "procedure": PROCEDURE.model_dump(mode="json"),
            "supplementary_queries": ["ZNA eye diagram TDR"],
        }
    )
    with pytest.raises(Exception):  # noqa: B017 - the fake model answers nothing
        asyncio.run(handler(context, request_))
    assert searched and searched[0][0] == "ZNA option"
    assert "ZNA eye diagram TDR" in searched[0]
    # The synthesis prompt still asks the original question.
    assert "Question: ZNA option\n" in model.requests[0].messages[0].text


def test_a_query_request_without_supplementary_queries_keeps_its_bytes() -> None:
    plain = KnowledgeQueryRequest.model_validate(
        {
            "asset": {"namespace": "engineering", "name": "rs-knowledge", "version": "1.0.0"},
            "question": "q",
        }
    )
    assert "supplementary_queries" not in plain.model_dump(mode="json")
