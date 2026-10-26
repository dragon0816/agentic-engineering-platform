"""G5: cross-domain negative acceptance on the shared Harness (multi-agent Phase 0.5).

`docs/archive/HARNESS_GAP_PLAN.zh-TW.md` P2-1 and
`docs/phases/HARNESS_6_LAYER_INCREMENTAL.md` G5: a deliberately wrong output
fails in every domain, and a pass needs observed evidence and Host checks,
never a model's or a Skill's word. The same negative cases run through each
domain's real adapter on the shared state machine (`agent.harness_run`,
`agent.harness_runner`):

- conversation: `agent.conversation_harness.checked_turn`;
- knowledge: `host_runtime.knowledge_harness.KnowledgeHarness`;
- workflow: `workflow.harness.run_workflow_checked`;
- coding: `harness.runtime.CodingHarness`.

For each domain the suite proves: a failed Host check never ends `validated`;
G1, a failed result is not rewritten as success; G2, the anchor and the
model's claims are verified; the completed-action claim check
(`no_unbacked_action_claim`) blocks an unbacked claim; an output cap is never
silent (handoff rule G4); retries are bounded; and `needs_input` stays honest.
Everything is a fake: no real model, Bridge or hardware.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import test_workflow_harness as workflow_tests
from test_gateway import request
from test_harness_handoff_g1 import _Calls, nothing, owner, workflow_gateway
from test_knowledge_vault_tools import RS, CallsVault, Recording
from test_knowledge_vault_tools import gateway as knowledge_gateway
from test_routing import FakeModel
from test_workflow_harness import context as workflow_context
from test_workflow_harness import engine_with

import agent.conversation_harness as conversation_module
import harness.runtime as coding_module
import host_runtime.knowledge_harness as knowledge_module
import telemetry.recorder as telemetry
import workflow.harness as workflow_module
from agent.conversation_harness import (
    CLAIM_CHECK,
    CLAIM_NOTE,
    NOTE_MARK,
    check_answer,
    checked_turn,
)
from agent.gateway import (
    MAX_TOOL_OBSERVATION_CHARS,
    MAX_TRUNCATED_RETRIES,
    ConversationToolExecution,
    Gateway,
    GatewayConversationResult,
    HostToolOutcome,
)
from agent.harness_handoff import UNVERIFIED_NOTE, capped, unverified, with_unverified_note
from agent.harness_plan import build_plan
from agent.harness_run import AgentHarnessRun
from agent.harness_runner import HarnessActionFailure, run_harness
from agent.routing import CommandRouter, RequestRouter
from agent.skills import HarnessDomain, SkillHarnessGuidance, SkillManifest, SkillRegistry
from capabilities.contracts import CapabilitySpec
from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from capabilities.runtime import (
    CapabilityGrant,
    CapabilityRefused,
    InstalledCapabilities,
    LocalPolicy,
)
from common.assets import AssetIdentity, ExecutionDependencies
from common.base import Contract
from common.execution import (
    CapabilityResult,
    Failure,
    RequestContext,
    RouteDecision,
    TraceIdentifiers,
)
from harness.contracts import (
    CandidateChange,
    CodingHarnessRequest,
    HarnessBudget,
    HarnessPlan,
    PlannedChange,
    ValidationCase,
    ValidationFailure,
    WorkspaceSnapshot,
)
from harness.runtime import CodingHarness, DeclaredCommands
from harness.workspace import BoundedWorkspace
from host_runtime.agent import LocalAgentOutcome
from host_runtime.contracts import KnowledgeAskRequest
from host_runtime.knowledge_harness import KnowledgeHarness
from knowledge.evidence import FacetEvidenceSummary, KnowledgeEvidenceSummary
from knowledge.evolution import grounded_record
from knowledge.query import Answer, Citation, Passage
from models.contracts import ModelMessage, ModelRequest, ModelResponse
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine
from workflow.harness import run_workflow_checked

DOMAINS: tuple[HarnessDomain, ...] = ("conversation", "knowledge", "workflow", "coding")
TRACE = TraceIdentifiers(trace_id="g5-trace", request_id="g5-request", span_id="g5-span")

# --------------------------------------------------------------------------
# Spies: the shared run each adapter ended with, and the runner's telemetry.
# --------------------------------------------------------------------------


@pytest.fixture
def runs(monkeypatch: pytest.MonkeyPatch) -> list[AgentHarnessRun]:
    """Every shared-Harness run any domain adapter finished, in order."""
    seen: list[AgentHarnessRun] = []

    def sync_spy(original: Callable[..., AgentHarnessRun]) -> Callable[..., AgentHarnessRun]:
        def spy(*args: Any, **kwargs: Any) -> AgentHarnessRun:
            run = original(*args, **kwargs)
            seen.append(run)
            return run

        return spy

    def async_spy(original: Callable[..., Any]) -> Callable[..., Any]:
        async def spy(*args: Any, **kwargs: Any) -> AgentHarnessRun:
            run: AgentHarnessRun = await original(*args, **kwargs)
            seen.append(run)
            return run

        return spy

    # Each adapter's own import of the shared runner (module, name, async).
    for module, name, is_async in (
        (conversation_module, "run_harness_async", True),
        (workflow_module, "run_harness_async", True),
        (knowledge_module, "run_harness", False),
        (coding_module, "run_harness", False),
    ):
        original = getattr(module, name)
        monkeypatch.setattr(module, name, async_spy(original) if is_async else sync_spy(original))
    return seen


@pytest.fixture
def emitted(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Telemetry events, as (kind, fields); the recorder still runs."""
    events: list[tuple[str, dict[str, Any]]] = []
    original = telemetry.emit

    def spy(kind: str, **fields: Any) -> Any:
        events.append((kind, fields))
        return original(kind, **fields)

    monkeypatch.setattr(telemetry, "emit", spy)
    return events


# --------------------------------------------------------------------------
# Conversation: the turn is the `execute` stage; fake turns, no model.
# --------------------------------------------------------------------------


class Turns:
    """A scripted `run_turn`: one Gateway result per pass, the last repeated."""

    def __init__(self, *results: GatewayConversationResult) -> None:
        self.results, self.calls = results, 0

    async def __call__(self, history: tuple[Any, ...], retry: tuple[Any, ...]) -> Any:
        self.calls += 1
        return self.results[min(self.calls, len(self.results)) - 1]


def answered(text: str, *tools: ConversationToolExecution) -> GatewayConversationResult:
    return GatewayConversationResult(
        trace=TRACE, status="answered", text=text, model_turns=1, tools=tools
    )


def stopped(status: str, code: str) -> GatewayConversationResult:
    return GatewayConversationResult.model_validate(
        {
            "trace": TRACE.model_dump(),
            "status": status,
            "text": "What period should the report cover?",
            "model_turns": 1,
            "tools": [],
            "failure": {"code": code, "message": code},
        }
    )


def converse_checked(turns: Turns, person: str = "make the report") -> Any:
    return asyncio.run(
        checked_turn(
            turns,
            (),
            (),
            lambda role, text: ModelMessage(role=role, text=text),
            "g5-request",
            person=person,
        )
    )


# --------------------------------------------------------------------------
# Knowledge: the real KnowledgeHarness over a fake runtime and Bridge.
# --------------------------------------------------------------------------

PROCEDURE = {
    "intent_patterns": ["CMP180"],
    "facets": [
        {
            "name": "technical",
            "request_patterns": ["standard"],
            "search_queries": ["CMP180 standards"],
            "support_terms": ["standard"],
        }
    ],
}
QUESTION = "Which standard does the CMP180 support?"
SOURCE = "The CMP180 supports the 5G NR standard and the LTE standard for signalling tests."


def knowledge_skill(*, fallback: str = "needs_input", max_retries: int = 0) -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {
                "identity": {"namespace": "engineering", "name": "ask", "version": "1.0.0"},
                "owner": {"type": "team", "id": "engineering"},
                "visibility": "organization",
                "lifecycle": "published",
            },
            "alias": "ask",
            "instructions": "Answer from the vault with citations.",
            "commands": [
                {
                    "name": "ask",
                    "kind": "capability",
                    "target": KNOWLEDGE_QUERY_SPEC.identity.model_dump(),
                }
            ],
            "harness_guidance": {
                "domains": ["knowledge"],
                "fallback": fallback,
                "max_retries": max_retries,
            },
            "procedure": PROCEDURE,
        }
    )


def record(text: str, source: str = SOURCE) -> dict[str, Any]:
    """A grounded Bridge record whose one facet cites the one Raw passage."""
    citation = Citation(kind="raw", raw_ref="raw/cmp180.md")
    passage = Passage(text=source, citation=citation, score=1)
    answer = Answer(question=QUESTION, status="answered", passages=(passage,), text=text)
    assessment = KnowledgeEvidenceSummary(
        status="covered",
        facets=(FacetEvidenceSummary(name="technical", citations=(citation,), attempts=1),),
    )
    data: dict[str, Any] = json.loads(
        grounded_record(RS, TRACE, answer, assessment=assessment).model_dump_json()
    )
    return data


class FakeBridge:
    """The Knowledge query capability as the Bridge would return it."""

    def __init__(self, data: dict[str, Any] | None = None, refusal: str | None = None) -> None:
        self.data, self.refusal = data, refusal
        self.questions: list[str] = []
        self.supplementary: list[tuple[str, ...]] = []

    async def __call__(self, local: Any) -> LocalAgentOutcome:
        self.questions.append(str(local.arguments["question"]))
        self.supplementary.append(tuple(local.arguments.get("supplementary_queries") or ()))
        if self.refusal is not None:
            result = CapabilityResult(
                trace=local.trace,
                status="failed",
                failure=Failure(code=self.refusal, message=self.refusal),
                handler_invoked=True,
            )
        else:
            result = CapabilityResult(
                trace=local.trace, status="succeeded", data=self.data, handler_invoked=True
            )
        return LocalAgentOutcome(
            trace=local.trace, ingress="local", actor="owner", capability=result
        )


def knowledge_harness(bridge: FakeBridge, skill: SkillManifest | None = None) -> KnowledgeHarness:
    skills = SkillRegistry()
    skills.register(skill or knowledge_skill())
    runtime = SimpleNamespace(
        actor="owner",
        config=SimpleNamespace(device=SimpleNamespace(bridge_id="bridge-1")),
        agent=SimpleNamespace(
            gateway=SimpleNamespace(
                router=SimpleNamespace(commands=SimpleNamespace(skills=skills))
            ),
            execute_capability=bridge,
        ),
    )
    return KnowledgeHarness(runtime, "engineering")


def ask(harness: KnowledgeHarness, skill: SkillManifest | None = None) -> dict[str, Any]:
    identity = (skill or knowledge_skill()).metadata.identity
    return harness.ask(KnowledgeAskRequest(asset=RS, question=QUESTION, skill=identity))


# The deliberately wrong Knowledge output: a number its cited source never states.
WRONG_KNOWLEDGE = "The CMP180 supports 99 standard profiles [1]."


# --------------------------------------------------------------------------
# Coding: the real CodingHarness over a temporary workspace, fake author.
# --------------------------------------------------------------------------

ARTIFACT = "controller.json"
COMMAND = "controller.validate"


class WrongAuthor:
    """Always proposes a controller the declared command rejects."""

    def __init__(self) -> None:
        self.repairs = 0

    def plan(self, request: CodingHarnessRequest) -> HarnessPlan:
        return HarnessPlan(
            summary="Set the gain.",
            changes=(PlannedChange(path=request.artifact_path, purpose="gain"),),
            validation_commands=(COMMAND,),
        )

    def initial_change(self, request: CodingHarnessRequest, plan: HarnessPlan) -> CandidateChange:
        return CandidateChange(path=request.artifact_path, content='{"gain": 1}')

    def repair(
        self, request: CodingHarnessRequest, plan: HarnessPlan, failure: object, attempt: int
    ) -> CandidateChange:
        self.repairs += 1
        return CandidateChange(path=request.artifact_path, content=f'{{"gain": {1 + attempt}}}')


def gain_is_ten(
    workspace: BoundedWorkspace, request: CodingHarnessRequest
) -> tuple[ValidationFailure, ...]:
    raw = workspace.read(request.artifact_path)
    gain = json.loads(raw or b"{}").get("gain")
    if gain == 10:
        return ()
    return (ValidationFailure(case="gain", code="output_mismatch", message=f"gain is {gain}"),)


def coding_request(root: Path, *, repairs: int = 1, revision: str | None = None) -> Any:
    (root / ARTIFACT).write_text('{"gain": 0}', encoding="utf-8")
    actual = BoundedWorkspace(str(root), (ARTIFACT,)).revision()
    return CodingHarnessRequest(
        workspace=WorkspaceSnapshot(root=str(root.resolve()), starting_revision=revision or actual),
        requirement="Set the controller gain to 10.",
        artifact_path=ARTIFACT,
        allowed_paths=(ARTIFACT,),
        allowed_commands=(COMMAND,),
        cases=(
            ValidationCase(name="gain", kind="new", input={}, expected={"gain": 10}),
            ValidationCase(name="ready", kind="regression", input={}, expected={}),
        ),
        skill_versions=("engineering/coding@1.0.0",),
        budget=HarnessBudget(max_repair_attempts=repairs, max_commands=8),
    )


def coding_harness(author: WrongAuthor) -> CodingHarness:
    commands = DeclaredCommands()
    commands.register(COMMAND, gain_is_ten)
    return CodingHarness(commands, author)


class CodingInput(Contract):
    requirement: str


class CodingOutput(Contract):
    summary: str


CODING_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "engineering", "name": "coding-change", "version": "1.0.0"},
        "name": "engineering.coding-change",
        "description": "Change one file and validate it with the declared commands",
        "input_contract": "engineering.coding-change.in.v1",
        "output_contract": "engineering.coding-change.out.v1",
        "side_effect": "read",
        "policy": {
            "approval_required": False,
            "required_permissions": ["engineering.coding"],
            "policy_refs": ["coding-policy"],
        },
    }
)
READ_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "engineering", "name": "read-file", "version": "1.0.0"},
        "name": "engineering.read-file",
        "description": "Read a file",
        "input_contract": "engineering.read-file.in.v1",
        "output_contract": "engineering.read-file.out.v1",
        "side_effect": "read",
        "policy": {
            "approval_required": False,
            "required_permissions": ["engineering.read"],
            "policy_refs": ["coding-policy"],
        },
    }
)


def coding_handler(root: Path, *, big: bool = False) -> Any:
    """What `capabilities.coding_change` does: run the Coding Harness and refuse
    with its failure code when the Host's declared commands did not pass."""

    async def handler(context: RequestContext, inputs: Contract) -> Contract:
        if big:
            return CodingOutput(summary="d" * (MAX_TOOL_OBSERVATION_CHARS + 500))
        result = coding_harness(WrongAuthor()).run(TRACE, coding_request(root))
        if result.status != "validated":
            assert result.failure is not None
            raise CapabilityRefused(result.failure.code)
        return CodingOutput(summary=result.plan.summary)

    return handler


async def read_file(context: RequestContext, inputs: Contract) -> Contract:
    return CodingOutput(summary="the controller sets the gain")


def coding_gateway(model: FakeModel, root: Path, *, big: bool = False) -> Gateway:
    installed = InstalledCapabilities()
    deps = ExecutionDependencies(central_required=False)
    installed.register(CODING_SPEC, coding_handler(root, big=big), CodingInput, CodingOutput, deps)
    installed.register(READ_SPEC, read_file, CodingInput, CodingOutput, deps)
    grants = tuple(
        CapabilityGrant(
            actor="engineer",
            asset=spec.identity,
            permissions=spec.policy.required_permissions,
            policy_refs=spec.policy.policy_refs,
        )
        for spec in (CODING_SPEC, READ_SPEC)
    )
    bridge = BridgeExecutor(installed, LocalPolicy(grants))
    skills = SkillRegistry()
    skills.register(
        SkillManifest.model_validate(
            {
                "metadata": {
                    "identity": {"namespace": "engineering", "name": "coder", "version": "1.0.0"},
                    "owner": {"type": "team", "id": "engineering"},
                    "visibility": "organization",
                    "lifecycle": "published",
                },
                "alias": "coder",
                "instructions": "Change code and validate it.",
                "commands": [
                    {
                        "name": "change",
                        "kind": "capability",
                        "target": CODING_SPEC.identity.model_dump(),
                    },
                    {
                        "name": "read",
                        "kind": "capability",
                        "target": READ_SPEC.identity.model_dump(),
                    },
                ],
            }
        )
    )
    return Gateway(
        RequestRouter(CommandRouter(skills), model=model, model_alias="company", local_only=False),
        bridge,
        WorkflowEngine(InstalledWorkflows(), bridge),
    )


def converse(built: Gateway, text: str, actor: str = "engineer") -> Any:
    context = request(text) if actor == "engineer" else owner(text)
    return asyncio.run(built.converse(context, (ModelMessage(role="user", text=text),)))


# --------------------------------------------------------------------------
# One deliberately wrong output per domain, through its real adapter.
# --------------------------------------------------------------------------


def wrong_output(domain: str, tmp_path: Path) -> tuple[Any, str]:
    """Run the domain's adapter on a deliberately wrong output; return what
    the adapter returned and the Host check that must have failed."""
    if domain == "conversation":
        # "Written" with no tool at all, on both passes.
        return converse_checked(Turns(answered("已經幫你寫入報表 report.xlsx。"))), CLAIM_CHECK
    if domain == "knowledge":
        return ask(knowledge_harness(FakeBridge(record(WRONG_KNOWLEDGE)))), "claim_support"
    if domain == "workflow":
        engine, manifest = engine_with(
            [{"check_id": "report_written", "step_index": 0, "kind": "files_nonempty"}]
        )
        snapshot = asyncio.run(
            run_workflow_checked(
                engine, workflow_context(), manifest.metadata.identity, {"size": 0}
            )
        )
        return snapshot, "report_written"
    return coding_harness(WrongAuthor()).run(TRACE, coding_request(tmp_path)), "declared_commands"


@pytest.mark.parametrize("domain", DOMAINS)
def test_a_wrong_output_never_ends_validated(
    domain: str, tmp_path: Path, runs: list[AgentHarnessRun]
) -> None:
    result, check = wrong_output(domain, tmp_path)
    (run,) = runs
    assert run.plan.domain == domain
    assert run.phase in ("failed", "needs_input")
    assert run.failure_code is not None
    kinds = [event.kind for event in run.events]
    assert "validation_failed" in kinds and "validated" not in kinds
    failed = {item.check_id for item in run.checks if item.status == "failed"}
    assert check in failed
    # And the adapter's own result agrees: nothing reads as a pass.
    if domain == "conversation":
        assert result.text.endswith(CLAIM_NOTE)
    elif domain == "knowledge":
        assert result["ok"] is False and "99" not in result["answer"]
        assert result["harness"]["phase"] == run.phase
    elif domain == "workflow":
        assert result.run.status == "failed"
        assert result.run.failure.code == "workflow_output_check_failed"
    else:
        assert result.status == "failed" and result.artifact is None
        assert result.failure.code == "repair_budget_exceeded"


@pytest.mark.parametrize("domain", DOMAINS)
def test_stop_reason_and_telemetry_phase_agree(
    domain: str,
    tmp_path: Path,
    runs: list[AgentHarnessRun],
    emitted: list[tuple[str, dict[str, Any]]],
) -> None:
    wrong_output(domain, tmp_path)
    (run,) = runs
    final = [
        fields
        for kind, fields in emitted
        if kind == "state.entered" and fields.get("status") in ("succeeded", "failed")
    ]
    assert final and final[-1]["status"] == "failed" and final[-1]["state"] == run.phase
    verdicts = [fields["status"] for kind, fields in emitted if kind == "verification.completed"]
    assert "failed" in verdicts


def test_the_shared_contract_refuses_validated_with_a_failed_check() -> None:
    plan = build_plan(
        task_id="g5",
        task_sha256="a" * 64,
        domain="workflow",
        skill=AssetIdentity(namespace="host", name="g5", version="1.0.0"),
        guidance=None,
        host_checks=("x",),
        max_retries=0,
    )
    forged = {
        "plan": plan.model_dump(mode="json"),
        "phase": "validated",
        "retry_count": 0,
        "events": [
            {"sequence": 0, "kind": "started"},
            {"sequence": 1, "kind": "validated", "evidence_ref": "e"},
        ],
        "checks": [{"check_id": "x", "status": "failed", "evidence_ref": "e"}],
    }
    with pytest.raises(ValueError, match="failed check"):
        AgentHarnessRun.model_validate(forged)
    forged["checks"] = []
    with pytest.raises(ValueError, match="observed Host checks"):
        AgentHarnessRun.model_validate(forged)


# --------------------------------------------------------------------------
# G1: a failed result is not rewritten as success.
# --------------------------------------------------------------------------


def test_g1_conversation_keeps_the_hosts_note_when_the_retry_pass_fails() -> None:
    turns = Turns(answered("我已經幫你產生報表。"), stopped("failed", "model_failed"))
    result = converse_checked(turns)
    assert turns.calls == 2
    # The first answer comes back marked, never a bare success nor a bare failure.
    assert result.status == "answered"
    assert result.text.startswith("我已經幫你產生報表。") and result.text.endswith(CLAIM_NOTE)


def test_g1_knowledge_without_output_carries_the_hosts_note() -> None:
    model = CallsVault("knowledge__rs-knowledge", {"question": "What is an eye diagram?"})
    built = knowledge_gateway(model, Recording())
    built.knowledge_harness = nothing
    result = converse(built, "What is an eye diagram?")
    assert UNVERIFIED_NOTE.strip() in result.text
    assert "knowledge_insufficient_evidence" in result.text


def test_g1_knowledge_with_partial_output_is_the_harness_text_not_a_rewrite() -> None:
    harness = knowledge_harness(FakeBridge(record(WRONG_KNOWLEDGE)))
    model = CallsVault("knowledge__rs-knowledge", {"question": QUESTION})
    built = knowledge_gateway(model, Recording())
    built.knowledge_harness = harness.for_tool
    result = converse(built, QUESTION)
    host = result.tools[0].host
    assert host is not None and host.data["harness_verdict"] == "not_validated"
    assert host.failure is not None and host.failure.code == "knowledge_not_validated"
    # The turn's answer is the Harness's text; the unsupported "99" is not in it.
    assert result.text == host.data["answer"] and "99" not in result.text
    assert len(model.calls) == 1


def test_g1_workflow_failure_stays_failed_whatever_the_model_writes() -> None:
    model = _Calls([("reports__make", {"size": 0})], "The report is complete.")
    result = converse(workflow_gateway(model), "make the report", actor="owner")
    assert result.text.startswith("The report is complete.")
    assert UNVERIFIED_NOTE.strip() in result.text
    assert "workflow_output_check_failed" in result.text


def test_g1_a_failed_coding_run_is_not_rewritten_as_success(tmp_path: Path) -> None:
    model = _Calls([("coder__change", {"requirement": "gain 10"})], "The change passed all tests.")
    result = converse(coding_gateway(model, tmp_path), "set the gain to 10")
    capability = result.tools[0].capability
    assert capability is not None and capability.status == "failed"
    assert capability.failure is not None
    assert capability.failure.code == "repair_budget_exceeded"
    # The Coding Harness's Host check failed; the model's "passed" keeps the note.
    assert result.text.startswith("The change passed all tests.")
    assert UNVERIFIED_NOTE.strip() in result.text and "coder__change" in result.text


def test_g1_a_successful_read_does_not_hide_a_failed_coding_run(tmp_path: Path) -> None:
    # The claim check passes (a tool succeeded); only G1 stands between the
    # failed Host check and the model's claim.
    model = _Calls(
        [("coder__read", {"requirement": "x"}), ("coder__change", {"requirement": "gain 10"})],
        "I have completed the change.",
    )
    result = converse(coding_gateway(model, tmp_path), "set the gain to 10")
    checks, _ = check_answer(result.text, result.tools, ())
    assert {c.check_id: c.status for c in checks}[CLAIM_CHECK] == "passed"
    assert UNVERIFIED_NOTE.strip() in result.text and "repair_budget_exceeded" in result.text


def test_g1_a_refusal_before_anything_ran_is_not_a_harness_verdict() -> None:
    refused = ConversationToolExecution(
        call_id="c1",
        name="coder__change",
        failure=Failure(code="permission_denied", message="no grant"),
    )
    # No Harness ran: G1 adds no "failed its Host checks" note; the claim
    # check is what covers an answer that says it was done.
    assert unverified((refused,)) == []
    assert with_unverified_note("text", (refused,)) == "text"
    checks, _ = check_answer("I have completed the change.", (refused,), ())
    assert {c.check_id: c.status for c in checks}[CLAIM_CHECK] == "failed"


# --------------------------------------------------------------------------
# G2: the anchor and the model's claims are verified.
# --------------------------------------------------------------------------


def test_g2_knowledge_answers_the_persons_sentence_not_the_models() -> None:
    bridge = FakeBridge(record("The CMP180 supports the 5G NR standard [1]."))
    harness = knowledge_harness(bridge)
    model = CallsVault(
        "knowledge__rs-knowledge",
        {
            "question": "Which standard does the CMW500 support?",
            "original_terms": ["Keysight"],
        },
    )
    built = knowledge_gateway(model, Recording())
    built.knowledge_harness = harness.for_tool
    result = converse(built, QUESTION)
    # The model's version dropped CMP180: rejected, the original alone is asked.
    assert bridge.questions == [QUESTION] and bridge.supplementary == [()]
    host = result.tools[0].host
    assert host is not None and isinstance(host.data, dict)
    anchor = host.data["anchor"]
    assert anchor["outcome"] == "rejected" and "CMP180" in anchor["missing_terms"]
    # A claimed "original term" that is not in the person's sentence is discarded.
    assert "Keysight" in anchor["discarded_terms"]


def test_g2_knowledge_claims_are_checked_against_the_cited_source(
    runs: list[AgentHarnessRun],
) -> None:
    good = ask(knowledge_harness(FakeBridge(record("The CMP180 supports the 5G NR standard [1]."))))
    assert good["ok"] is True and runs[-1].phase == "validated"
    bad = ask(knowledge_harness(FakeBridge(record(WRONG_KNOWLEDGE))))
    assert bad["ok"] is False and runs[-1].phase != "validated"
    claim = {c.check_id: c.status for c in runs[-1].checks}
    assert claim["claim_support"] == "failed"


@pytest.mark.parametrize("domain", ("workflow", "coding"))
def test_g2_every_tool_call_records_the_models_arguments_without_credentials(
    domain: str, tmp_path: Path
) -> None:
    secret = {"size": 0, "password": "hunter2-very-secret"}
    if domain == "workflow":
        model = _Calls([("reports__make", {"size": 0})], "done")
        plain = converse(workflow_gateway(model), "make the report", actor="owner")
        model = _Calls([("reports__make", secret)], "done")
        leaked = converse(workflow_gateway(model), "make the report", actor="owner")
        assert plain.tools[0].arguments == {"size": 0}
    else:
        model = _Calls([("coder__change", {"requirement": "gain 10"})], "done")
        plain = converse(coding_gateway(model, tmp_path), "set the gain")
        model = _Calls([("coder__change", {"requirement": "x", **secret})], "done")
        (tmp_path / "x").mkdir()
        leaked = converse(coding_gateway(model, tmp_path / "x"), "set the gain")
        assert plain.tools[0].arguments == {"requirement": "gain 10"}
    assert "hunter2" not in json.dumps(leaked.tools[0].arguments)


def test_g2_conversation_claims_are_checked_against_what_ran() -> None:
    # The model's own claim of work is the claim G2 verifies in a conversation:
    # it is passed only by a tool call that succeeded in this turn.
    turns = Turns(answered("I have created the report."), answered("Here is the plan."))
    result = converse_checked(turns)
    assert turns.calls == 2 and result.text == "Here is the plan."


# --------------------------------------------------------------------------
# The completed-action claim check, against each domain's failed tool.
# --------------------------------------------------------------------------


def failed_tool(domain: str) -> ConversationToolExecution:
    if domain == "knowledge":
        return ConversationToolExecution(
            call_id="c1",
            name="knowledge__rs-knowledge",
            host=HostToolOutcome(
                status="failed",
                data={"knowledge_harness": "not_validated", "harness_verdict": "not_validated"},
                failure=Failure(code="knowledge_not_validated", message="not validated"),
            ),
        )
    if domain == "workflow":
        model = _Calls([("reports__make", {"size": 0})], "x")
        result = converse(workflow_gateway(model), "make the report", actor="owner")
        item: ConversationToolExecution = result.tools[0]
        return item
    if domain == "coding":
        return ConversationToolExecution(
            call_id="c1",
            name="coder__change",
            decision=RouteDecision(
                kind="capability", target=CODING_SPEC.identity, reason="model selected"
            ),
            capability=CapabilityResult(
                trace=TRACE,
                status="failed",
                failure=Failure(code="repair_budget_exceeded", message="x"),
                handler_invoked=True,
            ),
        )
    raise AssertionError(domain)


@pytest.mark.parametrize("domain", ("knowledge", "workflow", "coding"))
@pytest.mark.parametrize(
    "claim", ("已經幫你完成報表。", "I have completed the report.", "我已成功執行分析。")
)
def test_an_unbacked_claim_fails_after_each_domains_failed_tool(domain: str, claim: str) -> None:
    checks, reasons = check_answer(claim, (failed_tool(domain),), ())
    assert {c.check_id: c.status for c in checks}[CLAIM_CHECK] == "failed"
    assert reasons


def test_an_unbacked_claim_fails_with_no_tool_at_all() -> None:
    checks, _ = check_answer("我已經幫你寄出郵件。", (), ())
    assert {c.check_id: c.status for c in checks}[CLAIM_CHECK] == "failed"
    # A conditional offer is not a claim (owner report 2026-10-25).
    checks, _ = check_answer("如果你要，我可以幫你寄出郵件。", (), ())
    assert {c.check_id: c.status for c in checks}[CLAIM_CHECK] == "passed"


def test_a_lasting_change_after_a_knowledge_read_is_not_backed() -> None:
    read = ConversationToolExecution(
        call_id="c1",
        name="knowledge__rs-knowledge",
        host=HostToolOutcome(status="succeeded", data={"knowledge_harness": "validated"}),
    )
    checks, _ = check_answer("規則我已改成每週一寄出。", (read,), ())
    assert {c.check_id: c.status for c in checks}[CLAIM_CHECK] == "failed"


# --------------------------------------------------------------------------
# Handoff rule G4: an output cap is never silent.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("limit", (None, 0, -5, True, "40", 1_000))
def test_g4_every_cut_says_so(limit: Any) -> None:
    text = "q" * 20_000
    shown, cut = capped(text, limit)
    assert cut is not None and cut["full_chars"] == 20_000
    assert len(shown) < len(text) and "Host 註記" in shown
    assert str(cut["limit_chars"]) in shown


def test_g4_knowledge_answer_over_its_limit_is_cut_visibly() -> None:
    model = CallsVault("knowledge__rs-knowledge", {"question": "q"})
    built = knowledge_gateway(model, Recording())
    long = "k [1]. " * 1_000
    built.knowledge_harness = lambda question, asset, anchor: {
        "ok": True,
        "answer": long,
        "output_limit_chars": 500,
    }
    result = converse(built, "q")
    assert "Host 註記" in result.text and "500" in result.text
    assert result.tools[0].host.data["truncated"]["full_chars"] == len(long)


@pytest.mark.parametrize("domain", ("workflow", "coding"))
def test_g4_a_large_tool_result_reaches_the_model_marked_truncated(
    domain: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = "w" * (MAX_TOOL_OBSERVATION_CHARS + 500)
    if domain == "coding":
        model = _Calls([("coder__change", {"requirement": "x"})], "done")
        converse(coding_gateway(model, tmp_path, big=True), "change it")
    else:

        async def large(context: RequestContext, inputs: Contract) -> Contract:
            return workflow_tests.Out(
                files=[{"path": "output/report.xlsx", "bytes": 1, "x": payload}]
            )

        monkeypatch.setattr(workflow_tests, "writer", large)
        model = _Calls([("reports__make", {"size": 1})], "done")
        converse(workflow_gateway(model), "make the report", actor="owner")
    observation = model.calls[-1].messages[-1].text
    assert len(observation) <= MAX_TOOL_OBSERVATION_CHARS + 200
    assert json.loads(observation)["truncated"] is True


def test_g4_conversation_never_returns_a_cut_model_answer_as_complete() -> None:
    class Truncates(FakeModel):
        def generate(self, item: ModelRequest) -> ModelResponse:
            self.calls.append(item)
            return ModelResponse(
                trace=item.trace,
                model_alias=item.model_alias,
                failure=Failure(code="model_output_truncated", message="cut"),
            )

    model = Truncates()
    built = workflow_gateway(model)
    result = converse(built, "write a long essay", actor="owner")
    assert result.status == "failed"
    assert result.failure is not None and result.failure.code == "model_output_truncated"
    assert len(model.calls) == MAX_TRUNCATED_RETRIES + 1


# --------------------------------------------------------------------------
# Retries are bounded.
# --------------------------------------------------------------------------


def test_conversation_retries_once_then_stops() -> None:
    turns = Turns(answered("我已經幫你寫入報表。"))
    converse_checked(turns)
    assert turns.calls == 2


def test_knowledge_retries_within_the_skill_budget(runs: list[AgentHarnessRun]) -> None:
    skill = knowledge_skill(fallback="retry", max_retries=2)
    bridge = FakeBridge(record(WRONG_KNOWLEDGE))
    result = ask(knowledge_harness(bridge, skill), skill)
    (run,) = runs
    assert run.retry_count == 2 == run.plan.retry_budget
    assert len(bridge.questions) == 3  # the first ask plus two retries
    assert run.phase == "failed" and result["ok"] is False


def test_knowledge_insufficient_evidence_is_asked_again_at_most_once_per_budget(
    runs: list[AgentHarnessRun],
) -> None:
    skill = knowledge_skill(fallback="retry", max_retries=2)
    bridge = FakeBridge(refusal="knowledge_insufficient_evidence")
    result = ask(knowledge_harness(bridge, skill), skill)
    assert len(bridge.questions) == 2
    assert runs[-1].phase == "needs_input" and result["ok"] is False


def test_a_workflow_is_never_retried_as_a_whole(
    runs: list[AgentHarnessRun], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    original = workflow_tests.writer

    async def counting(context: RequestContext, inputs: Contract) -> Contract:
        calls.append(1)
        return await original(context, inputs)

    monkeypatch.setattr(workflow_tests, "writer", counting)
    engine, manifest = engine_with(
        [{"check_id": "report_written", "step_index": 0, "kind": "files_nonempty"}]
    )
    asyncio.run(
        run_workflow_checked(engine, workflow_context(), manifest.metadata.identity, {"size": 0})
    )
    assert calls == [1] and runs[-1].retry_count == 0 and runs[-1].plan.retry_budget == 0


@pytest.mark.parametrize("repairs", (0, 1, 3))
def test_coding_repairs_stop_at_the_hosts_budget(
    repairs: int, tmp_path: Path, runs: list[AgentHarnessRun]
) -> None:
    author = WrongAuthor()
    result = coding_harness(author).run(TRACE, coding_request(tmp_path, repairs=repairs))
    assert author.repairs == repairs and runs[-1].retry_count == repairs
    assert len(result.commands) == repairs + 1
    assert result.status == "failed"


def test_a_skill_cannot_raise_the_hosts_retry_budget() -> None:
    for domain in DOMAINS:
        plan = build_plan(
            task_id="g5",
            task_sha256="b" * 64,
            domain=domain,
            skill=AssetIdentity(namespace="host", name="g5", version="1.0.0"),
            guidance=SkillHarnessGuidance(domains=(domain,), fallback="retry", max_retries=3),
            host_checks=("x",),
            max_retries=1,
        )
        assert plan.retry_budget == 1


# --------------------------------------------------------------------------
# needs_input stays honest.
# --------------------------------------------------------------------------


def test_conversation_question_is_needs_input_not_validated(
    runs: list[AgentHarnessRun],
) -> None:
    turns = Turns(stopped("needs_input", "clarification_needed"))
    result = converse_checked(turns)
    assert turns.calls == 1 and result.status == "needs_input"
    assert runs[-1].phase == "needs_input"
    assert runs[-1].failure_code == "clarification_needed"
    assert NOTE_MARK not in result.text


def test_knowledge_without_evidence_asks_and_claims_nothing(
    runs: list[AgentHarnessRun],
) -> None:
    result = ask(knowledge_harness(FakeBridge(refusal="knowledge_insufficient_evidence")))
    assert runs[-1].phase == "needs_input" and result["ok"] is False
    assert runs[-1].failure_code == "knowledge_insufficient_evidence"
    # It says it has no validated answer, and names what is unverified.
    assert result["answer"].startswith("The Knowledge query did not produce a validated answer")


def test_workflow_missing_input_is_needs_input_not_failed_or_succeeded(
    runs: list[AgentHarnessRun],
) -> None:
    engine, manifest = engine_with(
        [{"check_id": "report_written", "step_index": 0, "kind": "files_nonempty"}]
    )
    snapshot = asyncio.run(
        run_workflow_checked(engine, workflow_context(), manifest.metadata.identity, {})
    )
    assert snapshot.run.status == "needs_input"
    assert runs[-1].phase == "needs_input"
    assert runs[-1].failure_code == "workflow_input_missing"
    assert not runs[-1].checks


def test_coding_asks_only_at_a_governed_boundary(
    tmp_path: Path, runs: list[AgentHarnessRun]
) -> None:
    changed = coding_harness(WrongAuthor()).run(TRACE, coding_request(tmp_path, revision="c" * 64))
    assert changed.status == "needs_input" and changed.artifact is None
    assert changed.failure is not None
    assert changed.failure.code == "workspace_revision_changed"
    assert runs[-1].phase == "failed"  # the shared run is stopped, never validated
    # A failed Host check is never turned into a question for the person.
    (tmp_path / "x").mkdir()
    failed = coding_harness(WrongAuthor()).run(TRACE, coding_request(tmp_path / "x"))
    assert failed.status == "failed" and failed.failure is not None


def test_a_stopped_run_cannot_be_restarted_or_validated() -> None:
    plan = build_plan(
        task_id="g5",
        task_sha256="d" * 64,
        domain="conversation",
        skill=AssetIdentity(namespace="host", name="g5", version="1.0.0"),
        guidance=None,
        host_checks=("x",),
        max_retries=0,
    )

    class Asks:
        def collect_context(self) -> str:
            return "c"

        def execute(self) -> str:
            raise HarnessActionFailure("needs_period", needs_input=True)

        def validate(self) -> Iterator[Any]:
            raise AssertionError("never validated after a stop")

    run = run_harness(plan, Asks())  # type: ignore[arg-type]
    assert run.phase == "needs_input" and run.failure_code == "needs_period"
    from agent.harness_run import stop_harness

    with pytest.raises(ValueError, match="terminal"):
        stop_harness(run, "again", needs_input=False)
