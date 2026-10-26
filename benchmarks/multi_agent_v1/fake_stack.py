"""The fake-model bench host for multi_agent_v1: real AEP code, fake edges.

Everything that decides is the product's own: the Gateway tool loop, its
guards and claim check, `DelegationService` (`agent__delegate`), the Bridge
policy, the Workflow engine, the data policy and the session ledger. What is
fake: the model (a script per conversation), and the capabilities' handlers
(synthetic documents, a reference log parser over the coding_v1 fixtures, the
business_workflow_lab data, the mock CMP180). No network, no hardware.

A fake run therefore checks the plumbing and the measurements, not a model's
judgement: the live mode (`live.py`) measures that.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mock_cmp180 import MockCmp180

from agent.contracts import AgentProfile
from agent.delegation import DelegationCatalog, DelegationService, DelegationTarget
from agent.gateway import Gateway, GatewayConversationResult
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import (
    CapabilityGrant,
    InstalledCapabilities,
    LocalPolicy,
    TransientCapabilityError,
)
from common.assets import AssetIdentity, ExecutionDependencies, WorkflowManifest
from common.base import Contract
from common.execution import RequestContext, TraceIdentifiers
from models.contracts import ModelMessage, ModelRequest, ModelResponse, ModelToolCall
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURES = HERE / "fixtures"
CODING = ROOT / "benchmarks" / "coding_v1"
LAB_SOURCE = ROOT / "benchmarks" / "business_workflow_lab" / "operator" / "data" / "source.json"
ACTOR = "engineer"
NAMESPACE = "bench"  # skills are discovered by the request namespace
POLICY = "bench-policy"
#: The marker of a sub-run's system message (`agent.delegation._role`).
SUB_MARK = "delegated specialist sub-agent"
#: What each fake model call reports as usage.
INPUT_TOKENS, OUTPUT_TOKENS = 100, 25


def identity(name: str) -> AssetIdentity:
    return AssetIdentity(namespace="bench", name=name, version="1.0.0")


# -- capability contracts ------------------------------------------------------------


class DocRequest(Contract):
    doc_id: str


class DocText(Contract):
    doc_id: str
    text: str


class LookupRequest(Contract):
    topic: str


class Passage(Contract):
    source_id: str
    text: str


class ParseRequest(Contract):
    task: str


class ParseResult(Contract):
    task: str
    records: int
    warnings: int


class MeasureRequest(Contract):
    band: str
    channel: int


class Measurement(Contract):
    band: str
    channel: int
    tx_power_dbm: float
    simulated: bool


class OrderQuery(Contract):
    status: str
    month: str


class OrderSummary(Contract):
    status: str
    month: str
    order_ids: tuple[str, ...]
    count: int


class ExportReceipt(Contract):
    path: str
    count: int


# -- handlers --------------------------------------------------------------------------


@dataclass
class Counters:
    """What the handlers did, for the scenario checks."""

    calls: dict[str, int] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def hit(self, name: str) -> None:
        with self.lock:
            self.calls[name] = self.calls.get(name, 0) + 1

    def __getitem__(self, name: str) -> int:
        return self.calls.get(name, 0)


_V1 = re.compile(r"^\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[(PASS|FAIL)\]$")


def reference_parse(task: str, workspace: Path) -> tuple[int, int]:
    """The parser the coding sub-agent stands for in fake mode (coding_v1 T15
    and T16, read from `workspace/input`, written to `workspace/output`)."""
    out = workspace / "output"
    out.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    status = {"PASS": "Pass", "FAIL": "Fail"}
    if task == "T15":
        lines = (workspace / "input" / "test.log").read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            match = _V1.match(line.strip())
            if match is None:
                warnings.append({"line": number, "raw": line, "reason": "unrecognised line"})
                continue
            stamp, device, test, result = match.groups()
            records.append(
                {
                    "timestamp": stamp,
                    "device_id": device,
                    "test_name": test,
                    "status": status[result],
                }
            )
        (out / "parsed.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        (out / "warnings.json").write_text(json.dumps(warnings, indent=2), encoding="utf-8")
        return len(records), len(warnings)
    for path in sorted((workspace / "input" / "logs").glob("*.log")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            match = _V1.match(line.strip())
            if match is not None:
                stamp, device, test, result = match.groups()
                version = "V1"
            else:
                try:
                    item = json.loads(line)
                    stamp, device, test, result = (
                        item["ts"],
                        item["dut"],
                        item["case"],
                        item["result"],
                    )
                    version = "V2"
                except (ValueError, KeyError, TypeError):
                    warnings.append({"file": path.name, "line": number, "reason": "unknown format"})
                    continue
            records.append(
                {
                    "timestamp": stamp,
                    "device_id": device,
                    "test_name": test,
                    "status": status[result],
                    "source_file": path.name,
                    "format_version": version,
                }
            )
    (out / "unified.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    (out / "warnings.json").write_text(json.dumps(warnings, indent=2), encoding="utf-8")
    return len(records), len(warnings)


def lab_orders(status: str, month: str) -> list[str]:
    """business_workflow_lab sales orders of `month` (YYYY-MM) with `status`."""
    source = json.loads(LAB_SOURCE.read_text(encoding="utf-8"))
    return sorted(
        order["OrderID"]
        for order in source["sales_orders"]
        if order["Status"] == status and order["OrderDate"].startswith(month)
    )


@dataclass
class BenchHandlers:
    workspace: Path
    counters: Counters = field(default_factory=Counters)
    instrument: MockCmp180 = field(default_factory=MockCmp180)
    #: Export attempts that fail before writing (the injected fault).
    export_faults: int = 0

    async def read_doc(self, context: RequestContext, inputs: Contract) -> Contract:
        assert isinstance(inputs, DocRequest)
        self.counters.hit("read_doc")
        files = {"doc-q": "vendor_q_mlo.md", "doc-m": "vendor_m_mlo.md"}
        if inputs.doc_id not in files:
            raise ValueError("unknown document")
        text = (FIXTURES / files[inputs.doc_id]).read_text(encoding="utf-8")
        return DocText(doc_id=inputs.doc_id, text=text)

    async def lookup(self, context: RequestContext, inputs: Contract) -> Contract:
        assert isinstance(inputs, LookupRequest)
        self.counters.hit("lookup")
        return Passage(
            source_id="kb-wifi7-mlo",
            text="Wi-Fi 7 Multi-Link Operation lets one device use several links at once; "
            "STR sends and receives on two links simultaneously, eMLSR listens on several "
            "and switches to one for a frame exchange.",
        )

    async def parse_logs(self, context: RequestContext, inputs: Contract) -> Contract:
        assert isinstance(inputs, ParseRequest)
        if inputs.task not in ("T15", "T16"):
            raise ValueError("unknown task")
        self.counters.hit("parse_logs")
        target = self.workspace / inputs.task
        records, warnings = await asyncio.to_thread(reference_parse, inputs.task, target)
        return ParseResult(task=inputs.task, records=records, warnings=warnings)

    async def measure(self, context: RequestContext, inputs: Contract) -> Contract:
        assert isinstance(inputs, MeasureRequest)
        self.counters.hit("measure")
        found = self.instrument.measure_tx_power(inputs.band, inputs.channel)
        return Measurement(
            band=inputs.band,
            channel=inputs.channel,
            tx_power_dbm=float(str(found["tx_power_dbm"])),
            simulated=True,
        )

    async def query_orders(self, context: RequestContext, inputs: Contract) -> Contract:
        assert isinstance(inputs, OrderQuery)
        self.counters.hit("query_orders")
        ids = lab_orders(inputs.status, inputs.month)
        return OrderSummary(
            status=inputs.status, month=inputs.month, order_ids=tuple(ids), count=len(ids)
        )

    async def export_report(self, context: RequestContext, inputs: Contract) -> Contract:
        # A Workflow step gets the run's arguments (the query), not the
        # previous step's output, so the export reads the orders itself.
        assert isinstance(inputs, OrderQuery)
        self.counters.hit("export_attempt")
        if self.export_faults > 0:
            self.export_faults -= 1
            raise TransientCapabilityError("injected fault before the write")
        ids = lab_orders(inputs.status, inputs.month)
        summary = OrderSummary(
            status=inputs.status, month=inputs.month, order_ids=tuple(ids), count=len(ids)
        )
        out = self.workspace / "lab" / f"open_orders_{inputs.month}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary.model_dump(mode="json"), indent=2), encoding="utf-8")
        self.counters.hit("export_written")
        return ExportReceipt(path=out.name, count=len(ids))


# -- the host ------------------------------------------------------------------------------

#: (capability name, side effect, permission, input, output, handler attribute)
CAPABILITIES: tuple[tuple[str, str, str, type[Contract], type[Contract], str], ...] = (
    ("read-doc", "read", "bench.docs.read", DocRequest, DocText, "read_doc"),
    ("kb-lookup", "read", "bench.kb.read", LookupRequest, Passage, "lookup"),
    ("log-parser", "write", "bench.code.write", ParseRequest, ParseResult, "parse_logs"),
    (
        "cmp180-measure",
        "external_side_effect",
        "bench.instrument.operate",
        MeasureRequest,
        Measurement,
        "measure",
    ),
    ("lab-query-orders", "read", "bench.lab.read", OrderQuery, OrderSummary, "query_orders"),
    ("lab-export", "write", "bench.lab.write", OrderQuery, ExportReceipt, "export_report"),
)
#: The skills the parent turn has, as `alias__command` tools.
SKILLS: tuple[tuple[str, str, tuple[tuple[str, str, str], ...]], ...] = (
    ("docs-skill", "docs", (("read", "capability", "read-doc"),)),
    ("kb-skill", "kb", (("lookup", "capability", "kb-lookup"),)),
    ("parser-skill", "parser", (("run", "capability", "log-parser"),)),
    ("cmp180-skill", "cmp180", (("measure", "capability", "cmp180-measure"),)),
    ("lab-skill", "lab", (("report", "workflow", "open-orders-report"),)),
)
#: Delegation targets: (profile name, skills, capabilities, description).
PROFILES: tuple[tuple[str, tuple[str, ...], tuple[str, ...], str], ...] = (
    (
        "researcher",
        ("docs-skill", "kb-skill"),
        ("read-doc", "kb-lookup"),
        "Reads one technical document and reports its key facts with sources.",
    ),
    ("coder", ("parser-skill",), ("log-parser",), "Writes and runs log parsers."),
    (
        "instrument-operator",
        ("cmp180-skill",),
        ("cmp180-measure",),
        "Runs RF measurements on the lab tester.",
    ),
    (
        "lab-operator",
        ("lab-skill",),
        ("lab-query-orders", "lab-export"),
        "Runs the open-orders report Workflow.",
    ),
)


def spec(name: str, side_effect: str, permission: str) -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "identity": identity(name).model_dump(),
            "name": "bench." + name.replace("-", "_"),
            "description": f"multi_agent_v1 bench capability {name}",
            "input_contract": f"bench.{name}.input.v1",
            "output_contract": f"bench.{name}.output.v1",
            "side_effect": side_effect,
            "policy": {"required_permissions": [permission], "policy_refs": [POLICY]},
        }
    )


def _skill(name: str, alias: str, commands: Sequence[tuple[str, str, str]]) -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {
                "identity": identity(name).model_dump(),
                "owner": {"type": "team", "id": "bench"},
                "visibility": "private",
                "lifecycle": "draft",
            },
            "alias": alias,
            "instructions": f"multi_agent_v1 bench skill {alias}.",
            "commands": [
                {"name": command, "kind": kind, "target": identity(target).model_dump()}
                for command, kind, target in commands
            ],
            "default_command": commands[0][0],
        }
    )


def _workflow() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {
                "identity": identity("open-orders-report").model_dump(),
                "owner": {"type": "team", "id": "bench"},
                "visibility": "private",
                "lifecycle": "draft",
            },
            "kind": "workflow",
            "description": "Query the month's orders of a status, then export the report",
            "execution": {"mode": "local"},
            "dependencies": {"central_required": False},
            "input_contract": "bench.lab-query-orders.input.v1",
            "output_contract": "bench.lab-export.output.v1",
            "steps": [
                identity("lab-query-orders").model_dump(),
                identity("lab-export").model_dump(),
            ],
        }
    )


def profile(name: str) -> AgentProfile:
    found = next(item for item in PROFILES if item[0] == name)
    _, skills, capabilities, description = found
    return AgentProfile.model_validate(
        {
            "metadata": {
                "identity": {"namespace": "bench", "name": name, "version": "1.0.0"},
                "owner": {"type": "team", "id": "bench"},
                "visibility": "team",
                "lifecycle": "published",
            },
            "description": description,
            "skills": [identity(item).model_dump() for item in skills],
            "allowed_capabilities": [identity(item).model_dump() for item in capabilities],
            "selector_hint": description,
        }
    )


Script = Callable[[ModelRequest, int], ModelResponse]


def reply(*calls: tuple[str, dict[str, Any]], text: str = "") -> ModelResponse:
    return ModelResponse(
        trace=TraceIdentifiers(trace_id="x", request_id="x", span_id="x"),
        model_alias="routing",
        text=text,
        tool_calls=tuple(
            ModelToolCall(call_id=f"c{index}", name=name, arguments=arguments)
            for index, (name, arguments) in enumerate(calls)
        ),
    )


class ScriptedModel:
    """Answers each conversation from its script: the parent turn under the
    key "parent", each sub-run under the first line of its objective. Usage is
    reported per call. Thread-safe; records which conversations overlapped."""

    def __init__(
        self,
        scripts: dict[str, list[ModelResponse]],
        hook: Callable[[str, int], None] | None = None,
    ) -> None:
        self.scripts = scripts
        self.hook = hook
        self.lock = threading.Lock()
        self.calls: list[ModelRequest] = []
        self.by_key: dict[str, list[ModelRequest]] = {}
        self.inside = 0
        self.most_inside = 0

    @staticmethod
    def key(item: ModelRequest) -> str:
        if not item.messages or SUB_MARK not in item.messages[0].text:
            return "parent"
        first = next(message for message in item.messages if message.role == "user")
        return first.text.split("\n", 1)[0]

    def generate(self, item: ModelRequest) -> ModelResponse:
        key = self.key(item)
        with self.lock:
            self.calls.append(item)
            seen = self.by_key.setdefault(key, [])
            seen.append(item)
            index = len(seen) - 1
            self.inside += 1
            self.most_inside = max(self.most_inside, self.inside)
        try:
            if self.hook is not None:
                self.hook(key, index)
            script = self.scripts[key]
            answer = script[min(index, len(script) - 1)]
        finally:
            with self.lock:
                self.inside -= 1
        return answer.model_copy(
            update={
                "trace": item.trace,
                "model_alias": item.model_alias,
                "input_tokens": INPUT_TOKENS,
                "output_tokens": OUTPUT_TOKENS,
            }
        )

    def stream(self, item: ModelRequest) -> Any:
        raise AssertionError("the bench never streams")


@dataclass
class BenchHost:
    gateway: Gateway
    service: DelegationService
    handlers: BenchHandlers
    policy: LocalPolicy
    bridge: BridgeExecutor

    def tool_names(self, request: ModelRequest) -> set[str]:
        return {tool.name for tool in request.tools}

    def converse(
        self, message: str, *, actor: str = ACTOR, session_id: str = "bench-session"
    ) -> tuple[GatewayConversationResult, float]:
        context = RequestContext(
            trace=TraceIdentifiers(trace_id="bench", request_id="bench-1", span_id="span-1"),
            actor=actor,
            namespace=NAMESPACE,
            channel="test",
            message=message,
            session_id=session_id,
        )
        started = time.perf_counter()
        result = asyncio.run(
            self.gateway.converse(context, (ModelMessage(role="user", text=message),))
        )
        return result, time.perf_counter() - started


def build(
    workspace: Path,
    model: Any,
    *,
    ungranted: frozenset[str] = frozenset({"cmp180-measure"}),
    targets: Sequence[str] = ("researcher", "coder", "instrument-operator", "lab-operator"),
    ledger: Any = None,
) -> BenchHost:
    """The bench host: every capability installed, granted to the actor except
    `ungranted`, the delegation flag on and `targets` listed for the parent."""
    handlers = BenchHandlers(workspace)
    installed = InstalledCapabilities()
    grants = []
    for name, side_effect, permission, inputs, outputs, attribute in CAPABILITIES:
        installed.register(
            spec(name, side_effect, permission),
            getattr(handlers, attribute),
            inputs,
            outputs,
            ExecutionDependencies(central_required=False),
        )
        if name not in ungranted:
            grants.append(
                CapabilityGrant(
                    actor=ACTOR,
                    asset=identity(name),
                    permissions=(permission,),
                    policy_refs=(POLICY,),
                    approval_ref="bench-approval",
                )
            )
    policy = LocalPolicy(tuple(grants))
    bridge = BridgeExecutor(installed, policy)
    skills = SkillRegistry()
    for name, alias, commands in SKILLS:
        skills.register(_skill(name, alias, commands))
    workflows = InstalledWorkflows()
    workflows.register(_workflow())
    router = RequestRouter(CommandRouter(skills), model=model)
    gateway = Gateway(router, bridge, WorkflowEngine(workflows, bridge))
    catalog = DelegationCatalog(
        targets=tuple(DelegationTarget(profile=profile(name), listed=True) for name in targets)
    )
    service = DelegationService(
        gateway, enabled=lambda: True, catalog=lambda: catalog, ledger=ledger
    )
    gateway.host_tools = service.tools
    return BenchHost(gateway, service, handlers, policy, bridge)


def prepare_coding(workspace: Path, task: str) -> Path:
    """coding_v1's fixture inputs for `task`, copied into a fresh folder."""
    target = workspace / task
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(CODING / "fixtures" / task / "input", target / "input")
    return target
