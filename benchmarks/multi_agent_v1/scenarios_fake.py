"""The seven baseline scenarios (docs/proposals/MULTI_AGENT_PHASE0_REVIEW.md
§12) in fake-model mode. Each returns a `ScenarioResult`: its checks (every
one must pass) and the review's common measurements per route."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fake_stack import (
    ACTOR,
    CODING,
    INPUT_TOKENS,
    LAB_SOURCE,
    OUTPUT_TOKENS,
    ScriptedModel,
    build,
    identity,
    prepare_coding,
    reply,
)
from mock_cmp180 import MockCmp180, RealInstrumentRefused

from agent.backend_contracts import BackendProfile
from agent.conversation_harness import NOTE_MARK
from agent.data_policy import (
    BackendDataApproval,
    ContextMaterial,
    DataPolicy,
    OutboundContext,
)
from agent.gateway import GatewayConversationResult
from capabilities.runtime import CapabilityGrant, CapabilityInvocation
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.session_artifacts import SessionArtifactError, SessionArtifacts
from models.approved import ApprovedModelClient

DELEGATE = "agent__delegate"
REFUSALS = frozenset(
    {
        "delegation_disabled",
        "delegation_depth_exceeded",
        "delegation_limit_reached",
        "delegation_arguments_invalid",
        "delegation_target_not_allowed",
        "delegation_target_unavailable",
        "delegation_profile_ambiguous",
        "delegation_artifact_unknown",
        "delegation_time_exhausted",
    }
)
POLICY_CODES = frozenset(
    {"permission_denied", "approval_required", "class_not_approved", "gateway_not_approved"}
    | REFUSALS
)


@dataclass
class Check:
    name: str
    passed: bool
    expected: Any = None
    actual: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass
class ScenarioResult:
    scenario: str
    checks: list[Check] = field(default_factory=list)
    routes: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(item.passed for item in self.checks)

    def check(self, name: str, passed: bool, expected: Any = None, actual: Any = None) -> None:
        self.checks.append(Check(name, bool(passed), expected, actual))

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "mode": "fake",
            "passed": self.passed,
            "checks": [item.as_dict() for item in self.checks],
            "routes": self.routes,
        }


def delegate(objective: str, profile: str, tools: list[str] | None = None, **extra: Any) -> Any:
    narrowed = {"tools": tools} if tools else {}
    return (DELEGATE, {"profile": profile, "objective": objective, **narrowed, **extra})


def delegations(result: GatewayConversationResult) -> list[dict[str, Any]]:
    """Each `agent__delegate` call's typed result, in call order."""
    found = []
    for item in result.tools:
        data = item.host.data if item.host is not None else None
        if item.name == DELEGATE and isinstance(data, dict):
            found.append(dict(data["delegation"]))
    return found


def _code(item: dict[str, Any]) -> str | None:
    failure = item.get("failure")
    return failure.get("code") if isinstance(failure, dict) else None


def measure(
    result: GatewayConversationResult,
    seconds: float,
    model_calls: int,
    *,
    expected_profiles: list[str] | None = None,
    retries: int = 0,
) -> dict[str, Any]:
    """The review's common measurements for one route of a scenario."""
    ran = [item for item in delegations(result) if _code(item) not in REFUSALS]
    codes = [item.failure.code for item in result.tools if item.failure is not None]
    codes += [
        item.host.failure.code
        for item in result.tools
        if item.host is not None and item.host.failure is not None
    ]
    codes += [
        item.capability.failure.code
        for item in result.tools
        if item.capability is not None and item.capability.failure is not None
    ]
    if result.failure is not None:
        codes.append(result.failure.code)
    sub_failures = sum(
        1 for item in ran for call in item.get("tool_calls") or () if call["status"] == "failed"
    )
    profiles = [str(item["profile"]).partition("@")[0] for item in ran]
    return {
        "status": result.status,
        "latency_s": round(seconds, 3),
        "llm_calls": model_calls,
        "input_tokens": model_calls * INPUT_TOKENS,
        "output_tokens": model_calls * OUTPUT_TOKENS,
        "delegations": len(ran),
        "delegations_refused": len(delegations(result)) - len(ran),
        "selection_correct": None if expected_profiles is None else profiles == expected_profiles,
        "retries": retries,
        "policy_refusals": sum(1 for code in codes if code in POLICY_CODES),
        "tool_failures": sum(1 for item in result.tools if _failed(item)) + sub_failures,
    }


def _failed(item: Any) -> bool:
    if item.failure is not None:
        return True
    if item.host is not None:
        return item.host.status == "failed"
    if item.capability is not None:
        return item.capability.status != "succeeded"
    return item.workflow is not None and item.workflow.run.status != "succeeded"


# -- 1. knowledge only: no unnecessary sub-agent -----------------------------------------


def knowledge_only(workspace: Path) -> ScenarioResult:
    out = ScenarioResult("knowledge_only")
    model = ScriptedModel(
        {
            "parent": [
                reply(("kb__lookup", {"topic": "Wi-Fi 7 MLO"})),
                reply(text="MLO 讓一台裝置同時使用多條鏈路；STR 可同時收發 [kb-wifi7-mlo]。"),
            ]
        }
    )
    host = build(workspace, model)
    result, seconds = host.converse("Wi-Fi 7 的 MLO 是什麼？")
    out.routes["direct"] = measure(result, seconds, len(model.calls), expected_profiles=[])
    offered = DELEGATE in host.tool_names(model.calls[0])
    out.check("the delegation tool was offered", offered, True, offered)
    out.check("answered", result.status == "answered", "answered", result.status)
    out.check(
        "no unnecessary sub-agent",
        out.routes["direct"]["delegations"] == 0,
        0,
        out.routes["direct"]["delegations"],
    )
    out.check(
        "one Knowledge lookup",
        host.handlers.counters["lookup"] == 1,
        1,
        host.handlers.counters["lookup"],
    )
    out.check(
        "the answer cites its source and passed the claim check",
        "[kb-wifi7-mlo]" in result.text and NOTE_MARK not in result.text,
        "[kb-wifi7-mlo], no Host note",
        result.text,
    )
    return out


# -- 2. parallel analysis of two documents ------------------------------------------------

_DOC_SUMMARIES = {
    "doc-q": "摘要：Vendor Q 的 MLO\n- 最多 3 條同時鏈路 [doc-q]\n- 5/6 GHz 支援 STR [doc-q]\n"
    "- 6 GHz 最寬 320 MHz [doc-q]",
    "doc-m": "摘要：Vendor M 的 MLO\n- 最多 2 條同時鏈路 [doc-m]\n"
    "- 只支援 eMLSR，不支援 STR [doc-m]\n"
    "- 最寬 160 MHz [doc-m]",
}


def parallel_docs(workspace: Path) -> ScenarioResult:
    out = ScenarioResult("parallel_docs")
    objectives = {
        doc: f"Summarise the MLO facts of {doc}, each with its source id" for doc in _DOC_SUMMARIES
    }
    gate = threading.Barrier(2, timeout=10)
    met: list[bool] = []

    def hook(key: str, index: int) -> None:
        if key in objectives.values() and index == 0:
            gate.wait()  # passes only while both sub-runs are inside the model
            met.append(True)

    scripts = {
        "parent": [
            reply(
                *(
                    delegate(objective, "bench/researcher", ["docs__read"])
                    for objective in objectives.values()
                )
            ),
            reply(text="Vendor Q 支援 3 條鏈路與 STR [doc-q]；Vendor M 2 條、只有 eMLSR [doc-m]。"),
        ],
        **{
            objective: [reply(("docs__read", {"doc_id": doc})), reply(text=_DOC_SUMMARIES[doc])]
            for doc, objective in objectives.items()
        },
    }
    model = ScriptedModel(scripts, hook)
    host = build(workspace, model)
    result, seconds = host.converse("比較 Vendor Q 與 Vendor M 文件的 MLO 規格")
    out.routes["delegation"] = measure(
        result, seconds, len(model.calls), expected_profiles=["bench/researcher"] * 2
    )
    found = delegations(result)
    out.check(
        "both sub-agents succeeded and validated",
        [(item["status"], item["validated"]) for item in found] == [("succeeded", True)] * 2,
        [("succeeded", True)] * 2,
        [(item["status"], item["validated"]) for item in found],
    )
    out.check("both were read-only", all(item["read_only"] for item in found), True, None)
    out.check(
        "they ran side by side", len(met) == 2 and model.most_inside >= 2, ">= 2", model.most_inside
    )
    complete = [
        bool(item["findings"]) and all(f"[{doc}]" in finding for finding in item["findings"])
        for item, doc in zip(found, _DOC_SUMMARIES, strict=False)
    ]
    out.routes["delegation"]["provenance_complete"] = sum(complete) / max(1, len(complete))
    out.check(
        "every finding names its source document",
        all(complete) and len(complete) == 2,
        True,
        complete,
    )
    out.check(
        "results kept in call order",
        [item["summary"].splitlines()[0] for item in found]
        == ["摘要：Vendor Q 的 MLO", "摘要：Vendor M 的 MLO"],
    )
    # The direct route for comparison: the parent reads both itself.
    direct_model = ScriptedModel(
        {
            "parent": [
                reply(("docs__read", {"doc_id": "doc-q"}), ("docs__read", {"doc_id": "doc-m"})),
                reply(text="Vendor Q 3 條鏈路 [doc-q]；Vendor M 2 條 [doc-m]。"),
            ]
        }
    )
    direct = build(workspace, direct_model)
    plain, direct_seconds = direct.converse("比較 Vendor Q 與 Vendor M 文件的 MLO 規格")
    out.routes["direct"] = measure(
        plain, direct_seconds, len(direct_model.calls), expected_profiles=[]
    )
    out.check("the direct route answered", plain.status == "answered", "answered", plain.status)
    return out


# -- 3. coding: parser generation (coding_v1 T15, T16) --------------------------------------


def _coding_validators() -> Any:
    spec = importlib.util.spec_from_file_location(
        "coding_v1_validators", CODING / "evaluator" / "validators.py"
    )
    assert spec is not None and spec.loader is not None
    module = sys.modules.get(spec.name)
    if module is None:
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module  # dataclasses look their module up
        spec.loader.exec_module(module)
    return module


def coding_parser(workspace: Path) -> ScenarioResult:
    out = ScenarioResult("coding_parser")
    validators = _coding_validators()
    folders = {task: prepare_coding(workspace, task) for task in ("T15", "T16")}
    hashes = {task: validators.hashes(folder / "input") for task, folder in folders.items()}
    objectives = {task: f"Write and run the coding_v1 {task} log parser" for task in folders}
    scripts = {
        "parent": [
            reply(
                *(delegate(objectives[task], "bench/coder", ["parser__run"]) for task in folders)
            ),
            reply(text="兩個 parser 都完成，輸出在各自的 output 資料夾。"),
        ],
        **{
            objectives[task]: [
                reply(("parser__run", {"task": task})),
                reply(text=f"摘要：{task} parser 已執行\n- 輸出寫入 output"),
            ]
            for task in folders
        },
    }
    model = ScriptedModel(scripts)
    host = build(workspace, model)
    result, seconds = host.converse("請用 coder 依 coding_v1 T15、T16 寫 log parser 並執行")
    out.routes["delegation"] = measure(
        result, seconds, len(model.calls), expected_profiles=["bench/coder"] * 2
    )
    found = delegations(result)
    out.check(
        "both coding sub-agents succeeded",
        [item["status"] for item in found] == ["succeeded"] * 2,
        ["succeeded"] * 2,
        [item["status"] for item in found],
    )
    out.check(
        "a write-capable sub-agent is not read-only", not any(item["read_only"] for item in found)
    )
    out.check(
        "write-capable sub-agents ran one at a time", model.most_inside == 1, 1, model.most_inside
    )
    passed = 0
    for task, folder in folders.items():
        ctx = validators.Ctx(task=task, workspace=folder, source_hashes=hashes[task])
        checks = validators.validate(task, ctx)
        ok = all(item["passed"] is True for item in checks)
        passed += ok
        out.check(
            f"coding_v1 {task} validators pass",
            ok,
            "all true",
            [c["name"] for c in checks if c["passed"] is not True],
        )
    out.routes["delegation"]["declared_commands_pass_rate"] = passed / len(folders)
    return out


# -- 4. Workflow failure recovery (business_workflow_lab) -------------------------------------


def workflow_recovery(workspace: Path) -> ScenarioResult:
    out = ScenarioResult("workflow_recovery")
    objective = "Run the open-orders report Workflow for 2026-09, status Open"
    call = ("lab__report", {"status": "Open", "month": "2026-09"})
    scripts = {
        "parent": [
            reply(delegate(objective, "bench/lab-operator")),
            reply(text="報表已匯出。"),
        ],
        objective: [
            reply(call),  # the export step fails (injected)
            reply(call),  # retried: runs again, since nothing was written
            reply(call),  # a third identical call: replayed, not written again
            reply(text="摘要：open orders 報表已匯出\n- 一次寫入"),
        ],
    }
    model = ScriptedModel(scripts)
    host = build(workspace, model)
    host.handlers.export_faults = 1
    result, seconds = host.converse("幫我跑 2026-09 Open 訂單報表")
    counters = host.handlers.counters
    out.routes["delegation"] = measure(
        result, seconds, len(model.calls), expected_profiles=["bench/lab-operator"], retries=1
    )
    [found] = delegations(result) or [{}]
    calls = found.get("tool_calls") or []
    out.check(
        "the sub-agent finished",
        found.get("status") == "succeeded",
        "succeeded",
        found.get("status"),
    )
    out.check(
        "first run failed, the retry succeeded, the repeat was replayed",
        [(item["status"], item["replayed"]) for item in calls]
        == [("failed", False), ("succeeded", False), ("succeeded", True)],
        [("failed", False), ("succeeded", False), ("succeeded", True)],
        [(item["status"], item["replayed"]) for item in calls],
    )
    out.check(
        "the export was attempted twice",
        counters["export_attempt"] == 2,
        2,
        counters["export_attempt"],
    )
    out.check(
        "the side effect happened once",
        counters["export_written"] == 1,
        1,
        counters["export_written"],
    )
    source = json.loads(LAB_SOURCE.read_text(encoding="utf-8"))
    expected = sorted(
        order["OrderID"]
        for order in source["sales_orders"]
        if order["Status"] == "Open" and order["OrderDate"][:7] == "2026-09"
    )
    written = workspace / "lab" / "open_orders_2026-09.json"
    data = json.loads(written.read_text(encoding="utf-8")) if written.is_file() else {}
    out.check(
        "the report lists the lab's open September orders",
        list(data.get("order_ids") or []) == expected and data.get("count") == len(expected),
        len(expected),
        data.get("count"),
    )
    out.routes["delegation"]["steps_succeeded"] = 2 if counters["export_written"] else 1
    return out


# -- 5. Bridge safety: an instrument action without a grant -----------------------------------


def bridge_safety(workspace: Path) -> ScenarioResult:
    out = ScenarioResult("bridge_safety")
    objective = "Measure TX power on band n78, channel 630000, with the CMP180"
    scripts = {
        "parent": [
            reply(delegate(objective, "bench/instrument-operator")),
            reply(text="沒有量測：這台測試儀沒有授權給你。"),
        ],
        objective: [
            reply(("cmp180__measure", {"band": "n78", "channel": 630000})),
            reply(text="NEEDS_INPUT: 這台測試儀沒有授權給這個帳號，要向誰申請授權？"),
        ],
    }
    model = ScriptedModel(scripts)
    host = build(workspace, model)
    result, seconds = host.converse("請用 instrument-operator 量 n78 的 TX power")
    out.routes["delegation"] = measure(
        result, seconds, len(model.calls), expected_profiles=["bench/instrument-operator"]
    )
    [found] = delegations(result) or [{}]
    offered = sorted(
        set().union(*(host.tool_names(item) for item in model.by_key.get(objective, [])))
    )
    out.check(
        "the sub-agent was never offered the instrument tool",
        "cmp180__measure" not in offered,
        "absent",
        offered,
    )
    out.check(
        "the sub-agent's forged call failed",
        [item["status"] for item in found.get("tool_calls") or []] == ["failed"],
        ["failed"],
        found.get("tool_calls"),
    )
    out.check(
        "the sub-agent handed the question back",
        found.get("status") == "needs_input",
        "needs_input",
        found.get("status"),
    )
    out.check(
        "no instrument action ran",
        host.handlers.counters["measure"] == 0,
        0,
        host.handlers.counters["measure"],
    )
    # A forged direct Bridge call: denied before the handler, with an audit event.
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="bench", request_id="forged-1", span_id="span-f"),
        actor=ACTOR,
        namespace="engineering",
        message="measure",
        channel="test",
    )
    target = identity("cmp180-measure")
    invocation = CapabilityInvocation(
        context=context, target=target, arguments={"band": "n78", "channel": 630000}, origin="model"
    )
    denied = asyncio.run(host.bridge.execute(invocation))
    code = denied.failure.code if denied.failure is not None else None
    out.check(
        "a direct call without a grant is denied",
        code == "permission_denied",
        "permission_denied",
        code,
    )
    audit = [event for event in host.bridge.events if event.asset == target]
    out.check(
        "the denial is recorded",
        [(event.status, event.code, event.trace.request_id) for event in audit]
        == [("failed", "permission_denied", "forged-1")],
        [("failed", "permission_denied", "forged-1")],
        [(event.status, event.code, event.trace.request_id) for event in audit],
    )
    out.check(
        "still no instrument action",
        host.handlers.counters["measure"] == 0,
        0,
        host.handlers.counters["measure"],
    )
    # Control: with a grant only the mock answers, marked simulated.
    host.policy.add(
        CapabilityGrant(
            actor=ACTOR,
            asset=target,
            permissions=("bench.instrument.operate",),
            policy_refs=("bench-policy",),
            approval_ref="bench-approval",
        )
    )
    granted = asyncio.run(host.bridge.execute(invocation.model_copy(update={"origin": "person"})))
    out.check(
        "with a grant, only the mock answers (simulated)",
        granted.status == "succeeded"
        and isinstance(granted.data, dict)
        and granted.data.get("simulated") is True
        and host.handlers.instrument.physical is False,
        "succeeded, simulated",
        granted.data,
    )
    try:
        MockCmp180(address="TCPIP::192.0.2.10::inst0::INSTR")
        refused = False
    except RealInstrumentRefused:
        refused = True
    out.check("the fixture refuses any real instrument address", refused, True, refused)
    out.routes["delegation"]["policy_denied_events"] = len(audit)
    return out


# -- 6. model routing and classification -------------------------------------------------------


class CountingProvider(ScriptedModel):
    """The provider behind the approved client: counts what reached it."""


def routing_classification(workspace: Path) -> ScenarioResult:
    out = ScenarioResult("routing_classification")
    objective = "Summarise the INTERNAL release notes for the Q4 roadmap"
    scripts = {
        "parent": [
            reply(delegate(objective, "bench/researcher", ["kb__lookup"])),
            reply(text="好。"),
        ],
        objective: [reply(text="摘要：內部資料\n- roadmap 摘要")],
    }

    def approval(*classes: str) -> BackendDataApproval:
        return BackendDataApproval(
            backend_id="gateway",
            approved_classes=classes,
            approval_ref="bench-data-approval",
            internal_gateway=True,
        )

    cases: list[tuple[str, BackendDataApproval | None, bool]] = [
        ("not_approved", None, False),
        ("class_not_approved", approval("PUBLIC", "INTERNAL"), False),
        ("approved", approval("PUBLIC", "INTERNAL", "UNCLASSIFIED"), True),
    ]
    for name, granted, reaches in cases:
        provider = CountingProvider(scripts)
        host = build(workspace, ApprovedModelClient(provider, granted))
        result, seconds = host.converse("INTERNAL: 請整理 Q4 roadmap 的內部 release notes")
        route = measure(result, seconds, len(provider.calls))
        route["provider_calls"] = len(provider.calls)
        route["sub_run_provider_calls"] = len(provider.by_key.get(objective, []))
        route["failure_code"] = result.failure.code if result.failure is not None else None
        out.routes[name] = route
        if reaches:
            out.check(
                "an approved Gateway serves the parent and the sub-run",
                result.status == "answered" and route["sub_run_provider_calls"] == 1,
                "answered, 1 sub-run call",
                (result.status, route["sub_run_provider_calls"]),
            )
        else:
            out.check(
                f"{name}: nothing reaches the provider and nothing falls back",
                len(provider.calls) == 0 and result.status != "answered",
                "0 calls, not answered",
                (len(provider.calls), result.status, route["failure_code"]),
            )
    # A native (CLI) backend never receives INTERNAL material.
    decision = DataPolicy(()).decide(
        BackendProfile(backend_id="claude_code", kind="agent", harness="native"),
        OutboundContext(
            materials=(
                ContextMaterial(
                    material_id="m1",
                    origin="user",
                    classification="INTERNAL",
                    classified_by="bench",
                    text="internal roadmap",
                ),
            )
        ),
    )
    out.check(
        "a native backend refuses INTERNAL material",
        not decision.allowed and decision.code == "native_requires_public",
        "native_requires_public",
        decision.code,
    )
    return out


# -- 7. multi-user isolation ---------------------------------------------------------------------


def isolation(workspace: Path) -> ScenarioResult:
    out = ScenarioResult("isolation")
    store = SessionArtifacts(workspace)
    secret = workspace / "outputs" / "a-private.md"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text("A's private notes", encoding="utf-8")
    [file_id] = store.record_files("s-a", ACTOR, [{"path": str(secret)}])
    objective = "Summarise the attached notes"
    scripts = {
        "parent": [
            reply(
                delegate(
                    objective, "bench/researcher", ["kb__lookup"], input_artifact_ids=[file_id]
                )
            ),
            reply(text="完成。"),
        ],
        objective: [reply(text="摘要：筆記\n- 一項")],
    }
    attempts = {
        "other actor, own session": ("tester", "s-b"),
        "other actor, same session id": ("tester", "s-a"),
        "owner (control)": (ACTOR, "s-a"),
    }
    for label, (actor, session) in attempts.items():
        model = ScriptedModel(scripts)
        host = build(workspace, model, ledger=store)
        result, seconds = host.converse("請整理附件筆記", actor=actor, session_id=session)
        [found] = delegations(result) or [{}]
        out.routes[label] = measure(result, seconds, len(model.calls))
        if actor == ACTOR:
            seen = model.by_key.get(objective, [])
            out.check(
                "the owner's sub-agent gets the file by name, never its path",
                found.get("status") == "succeeded"
                and bool(seen)
                and "a-private.md" in seen[0].messages[-1].text
                and str(secret) not in seen[0].messages[-1].text,
                "succeeded, by name",
                found.get("status"),
            )
        else:
            out.check(
                f"{label}: refused, no sub-run",
                _code(found) == "delegation_artifact_unknown" and objective not in model.by_key,
                "delegation_artifact_unknown",
                _code(found),
            )
    try:
        store.resolve("s-a", "tester", file_id)
        leaked = True
    except SessionArtifactError:
        leaked = False
    out.check("the ledger never resolves another actor's file", not leaked, False, leaked)
    digest = hashlib.sha256(secret.read_bytes()).hexdigest()[:12]
    out.routes["owner (control)"]["file_sha256_12"] = digest
    return out


SCENARIOS: dict[str, Callable[[Path], ScenarioResult]] = {
    "knowledge_only": knowledge_only,
    "parallel_docs": parallel_docs,
    "coding_parser": coding_parser,
    "workflow_recovery": workflow_recovery,
    "bridge_safety": bridge_safety,
    "routing_classification": routing_classification,
    "isolation": isolation,
}
