"""G1: a result that failed Host checks is not rewritten by the model (owner 2026-10-18).

A domain Harness result that is not validated but has output (for Knowledge, a
partial answer whose claims are supported while facets or relations are
missing) is the turn's answer as the Harness wrote it, Host note included, with
its record and evidence kept: the same text the direct route shows. Only when
the Harness produced nothing does the model answer, and then the Host appends a
visible "not verified" note. Workflow results follow the same rule: the model
explains a failed run, the Host's note keeps it failed unless a later call of
the same tool in the turn succeeded.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any

from test_gateway import request
from test_knowledge_vault_tools import CallsVault, Recording, gateway
from test_routing import FakeModel
from test_workflow_harness import engine_with

from agent.gateway import Gateway
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from models.contracts import ModelMessage, ModelRequest, ModelResponse, ModelToolCall

BENCH = Path(__file__).resolve().parents[1] / "benchmarks" / "knowledge_v1"
sys.path.insert(0, str(BENCH))
knowledge_use: Any = importlib.import_module("evidence").knowledge_use

# What KnowledgeHarness.ask returns for U7's Q1041 on both routes: the Bridge
# record is grounded and its claims are supported, a facet is missing, so the
# run is not validated and the visible answer names the gap.
PARTIAL_ANSWER = (
    "已查到可引用的部分資料：\n\nAn eye diagram is a signal-integrity measurement [1].\n\n"
    "來源：\n[1] `raw/si.md`\n\n未能以證據支持：product_option_spec。"
    "因此不能把上列資料當成完整的推薦或比較。"
)
RECORD = {
    "answer": {
        "text": "An eye diagram is a signal-integrity measurement [1].",
        "passages": [{"text": "eye diagram", "citation": {"kind": "raw", "raw_ref": "raw/si.md"}}],
    },
    "cited_passages": [{"text": "eye diagram", "citation": {"kind": "raw"}}],
}
EVIDENCE = {
    "raw_citations": 1,
    "facet_status": "missing",
    "missing_facets": ["product_option_spec"],
    "relation_status": "not_requested",
    "claim_status": "supported",
}


def partial(*_: Any) -> dict[str, Any]:
    return {
        "ok": False,
        "answer": PARTIAL_ANSWER,
        "record": RECORD,
        "outcome": {"capability": {"status": "succeeded", "failure": None}},
        "harness": {"phase": "failed"},
        "evidence": EVIDENCE,
    }


def nothing(*_: Any) -> dict[str, Any]:
    return {
        "ok": False,
        "answer": "No sufficient evidence was found (knowledge_insufficient_evidence)",
        "record": None,
        "outcome": {"capability": {"failure": {"code": "knowledge_insufficient_evidence"}}},
        "harness": {"phase": "needs_input"},
        "evidence": None,
    }


def ask(built: Gateway, text: str = "What is an eye diagram?") -> Any:
    return asyncio.run(built.converse(request(text), (ModelMessage(role="user", text=text),)))


def test_a_partial_knowledge_answer_is_the_turn_answer_as_the_harness_wrote_it() -> None:
    model = CallsVault("knowledge__rs-knowledge", {"question": "What is an eye diagram?"})
    built = gateway(model, Recording())
    built.knowledge_harness = partial
    result = ask(built)
    # Exactly the direct route's visible answer, gap note included; no rewrite.
    assert result.status == "answered" and result.text == PARTIAL_ANSWER
    assert len(model.calls) == 1
    host = result.tools[0].host
    assert host is not None and isinstance(host.data, dict)
    data = host.data
    assert (
        data["knowledge_harness"] == "not_validated" and data["harness_verdict"] == "not_validated"
    )
    assert data["harness_output"] is True
    assert data["record"] == RECORD and data["evidence"] == EVIDENCE
    assert host.failure is not None and host.failure.code == "knowledge_not_validated"


def test_the_benchmark_grades_a_partial_tool_answer_like_the_direct_route() -> None:
    model = CallsVault("knowledge__rs-knowledge", {"question": "What is an eye diagram?"})
    built = gateway(model, Recording())
    built.knowledge_harness = partial
    result = ask(built)
    tool = knowledge_use(
        {"reply": {"answer": {"outcome": {"conversation": result.model_dump(mode="json")}}}}
    )
    direct = knowledge_use(
        {
            "reply": {
                "answer": {
                    "answer": PARTIAL_ANSWER,
                    "outcome": {"capability": {"status": "succeeded", "data": RECORD}},
                    "harness": {"phase": "failed"},
                    "evidence": EVIDENCE,
                }
            }
        }
    )
    # The grader reaches the same branch: a completed call with a record whose
    # cited passages are checked and reviewed, not a VALIDATION_GAP.
    assert tool["status"] == direct["status"] == "succeeded"
    assert tool["record"] == direct["record"] == RECORD
    assert tool["text"] == direct["text"] == PARTIAL_ANSWER


def test_when_the_harness_produced_nothing_the_models_answer_carries_a_host_note() -> None:
    model = CallsVault("knowledge__rs-knowledge", {"question": "What is an eye diagram?"})
    built = gateway(model, Recording())
    built.knowledge_harness = nothing
    result = ask(built)
    assert len(model.calls) == 2
    assert result.text.startswith("answered")
    assert "Host 註記" in result.text and "knowledge_insufficient_evidence" in result.text
    assert "未經知識庫驗證" in result.text
    host = result.tools[0].host
    assert host is not None and host.status == "failed"


class _Calls(FakeModel):
    """Calls the named tools in order, one per turn, then answers."""

    def __init__(self, calls: list[tuple[str, dict[str, Any]]], answer: str) -> None:
        super().__init__()
        self.planned, self.answer = calls, answer

    def generate(self, item: ModelRequest) -> ModelResponse:
        self.calls.append(item)
        if len(self.calls) <= len(self.planned):
            name, arguments = self.planned[len(self.calls) - 1]
            return ModelResponse(
                trace=item.trace,
                model_alias=item.model_alias,
                tool_calls=(
                    ModelToolCall(call_id=f"c{len(self.calls)}", name=name, arguments=arguments),
                ),
            )
        return ModelResponse(trace=item.trace, model_alias=item.model_alias, text=self.answer)


def workflow_gateway(model: FakeModel) -> Gateway:
    engine, manifest = engine_with(
        [{"check_id": "report_written", "step_index": 0, "kind": "files_nonempty"}]
    )
    skills = SkillRegistry()
    skills.register(
        SkillManifest.model_validate(
            {
                "metadata": {
                    "identity": {"namespace": "engineering", "name": "reports", "version": "1.0.0"},
                    "owner": {"type": "team", "id": "engineering"},
                    "visibility": "organization",
                    "lifecycle": "published",
                },
                "alias": "reports",
                "instructions": "Make the weekly report.",
                "commands": [
                    {
                        "name": "make",
                        "kind": "workflow",
                        "target": manifest.metadata.identity.model_dump(),
                    }
                ],
            }
        )
    )
    return Gateway(RequestRouter(CommandRouter(skills), model=model), engine.bridge, engine)


def owner(text: str) -> Any:
    from common.execution import RequestContext, TraceIdentifiers

    return RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor="owner",
        namespace="engineering",
        channel="local",
        message=text,
    )


def test_a_failed_workflow_check_stays_failed_whatever_the_model_writes() -> None:
    model = _Calls([("reports__make", {"size": 0})], "The report is ready and complete.")
    built = workflow_gateway(model)
    text = "make the report"
    result = asyncio.run(built.converse(owner(text), (ModelMessage(role="user", text=text),)))
    workflow = result.tools[0].workflow
    assert workflow is not None and workflow.run.status == "failed"
    assert result.text.startswith("The report is ready and complete.")
    assert "Host 註記" in result.text and "workflow_output_check_failed" in result.text


def test_a_repaired_workflow_run_in_the_same_turn_clears_the_note() -> None:
    model = _Calls(
        [("reports__make", {"size": 0}), ("reports__make", {"size": 10})], "The report is ready."
    )
    built = workflow_gateway(model)
    text = "make the report"
    result = asyncio.run(built.converse(owner(text), (ModelMessage(role="user", text=text),)))
    assert [item.workflow.run.status for item in result.tools if item.workflow] == [
        "failed",
        "succeeded",
    ]
    assert result.text == "The report is ready."
