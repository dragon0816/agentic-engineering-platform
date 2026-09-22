"""How a case is exercised, in one place.

Slice 1 chose a wiring per case inside the test body, and four of the six
cases were observed through a bare router or the registry proof, neither of
which can execute anything. `no_execution` therefore passed for them without
ever being able to fail, which is the shape of check this phase exists to
remove.

Every routed case now goes through one real `Gateway`: the repository's three
skill manifests, the release workflow it ships, and a Bridge whose `events`
record every dispatch. A capability the repository deliberately does not
install, such as `legacy/run-testing`, is still dispatched and still recorded,
because "the route resolved and nothing ran" is an observation while "nothing
was attempted" is not.

A host that wants the same guarantee copies this file and swaps its handlers.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from agent.gateway import Gateway
from agent.registry import InMemoryTaskRegistry
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from capabilities.contracts import CapabilitySpec
from capabilities.files import READ_FILE_SPEC, ReadFileHandler, ReadFileInput, ReadFileOutput
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from common.assets import AssetIdentity, ExecutionDependencies, TaskManifest, WorkflowManifest
from common.base import Contract
from common.evaluation import EvaluationCase, ObservedRun
from common.execution import RequestContext, RouteDecision, SideEffect
from common.trace import ExecutionTrace
from models.catalog import ModelEndpoint
from models.contracts import ModelClient, ModelRequest, ModelResponse
from models.openai_compatible import OpenAICompatible
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine
from workflow.host_bridge import BridgeRegistration
from workflow.proof import advertise_sample

ROOT = Path(__file__).resolve().parents[1]
SKILL_FILES = ("file-read.json", "release-workflow.json", "source-routing.json")
# A Bridge sees every dispatch and the installed catalog declares every side
# effect, so any of these would have been recorded had it happened.
WATCHED: tuple[SideEffect, ...] = ("read", "write", "execute", "external_side_effect")
# A dispatch that failed after the handler ran still caused whatever the
# handler caused. `BridgeExecutor` marks these `invoked`, and its event code
# is what distinguishes them from a dispatch refused before it began.
INVOKED_CODES = frozenset({"timeout", "transient_failure", "handler_error", "invalid_output"})
# Which cases are proofs about discovery rather than routed requests. Named
# rather than inferred, so a later case that legitimately omits a route is
# routed instead of being silently graded as the registry proof.
DISCOVERY_CASES = frozenset({"discover-sample-task"})
# The alias an `agent` case is routed under when the suite runs it once. A
# comparison across aliases supplies its own.
ROUTING_ALIAS = "routing"
# What the stub model answers for each agent case the suite runs. Named
# per case for the same reason DISCOVERY_CASES is: a fixture fixed to one
# answer must not be inferred onto a case it was never written for.
AGENT_PROPOSALS: dict[str, AssetIdentity] = {
    "agent-ambiguous-release": AssetIdentity(
        namespace="engineering", name="validate-release", version="1.0.0"
    ),
}


def invoked(bridge: BridgeExecutor) -> tuple[AssetIdentity, ...]:
    """What the Bridge actually reached a handler for. A capability that ran
    and then failed still ran; a dispatch refused before the handler did not.
    One definition, so effects and approvals read the same events."""
    seen: list[AssetIdentity] = []
    for event in bridge.events:
        if event.status != "succeeded" and event.code not in INVOKED_CODES:
            continue
        if event.asset not in seen:
            seen.append(event.asset)
    return tuple(seen)


def effects_of(bridge: BridgeExecutor, installed: InstalledCapabilities) -> tuple[SideEffect, ...]:
    """The declared side effect of everything the Bridge actually put in
    motion."""
    effects: list[SideEffect] = []
    for identity in invoked(bridge):
        binding = installed.get(identity)
        if binding is not None and binding.spec.side_effect not in effects:
            effects.append(binding.spec.side_effect)
    return tuple(effects)


class Probe(Contract):
    package: str = "sample"


class Report(Contract):
    validated: bool = True


class CountingModel:
    """Present so that reaching a model is visible. A deterministic case that
    gets here has already failed."""

    def __init__(self) -> None:
        self.calls: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        raise AssertionError("a deterministic case must not reach a model")

    def stream(self, request: ModelRequest) -> Any:
        raise NotImplementedError


class RecordingHandler:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        self.calls += 1
        return Report()


def validate_release_spec() -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "identity": {
                "namespace": "engineering",
                "name": "validate-release",
                "version": "1.0.0",
            },
            "name": "engineering.validate_release",
            "description": "Inert release validation fixture",
            "input_contract": "engineering.validate-release.input.v1",
            "output_contract": "engineering.validate-release.output.v1",
            "side_effect": "read",
            "policy": {
                "required_permissions": ["engineering.validate"],
                "policy_refs": ["release-policy"],
            },
        }
    )


def release_workflow() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {
                "identity": {
                    "namespace": "engineering",
                    "name": "release-validation",
                    "version": "1.0.0",
                },
                "owner": {"type": "team", "id": "engineering"},
                "visibility": "private",
                "lifecycle": "draft",
            },
            "kind": "workflow",
            "description": "Inert single-step release validation workflow",
            "execution": {"mode": "local"},
            "dependencies": {"central_required": False},
            "input_contract": "engineering.validate-release.input.v1",
            "output_contract": "engineering.validate-release.output.v1",
            "steps": [{"namespace": "engineering", "name": "validate-release", "version": "1.0.0"}],
        }
    )


def publish_artifact_spec() -> CapabilitySpec:
    """The irreversible half of the scenario. Declaring
    `external_side_effect` is what makes "was this approved?" a question the
    platform can answer."""
    return CapabilitySpec.model_validate(
        {
            "identity": {
                "namespace": "engineering",
                "name": "publish-artifact",
                "version": "1.0.0",
            },
            "name": "engineering.publish_artifact",
            "description": "Inert artifact publication fixture",
            "input_contract": "engineering.validate-release.input.v1",
            "output_contract": "engineering.validate-release.output.v1",
            "side_effect": "external_side_effect",
            "policy": {
                "required_permissions": ["engineering.publish"],
                "policy_refs": ["release-policy"],
                "risk": "high",
                "approval_required": True,
            },
        }
    )


def release_package_workflow() -> WorkflowManifest:
    """Two steps, so that "a mandatory step was skipped" is a thing that can
    be seen rather than asserted."""
    return WorkflowManifest.model_validate(
        {
            "metadata": {
                "identity": {
                    "namespace": "engineering",
                    "name": "release-package",
                    "version": "1.0.0",
                },
                "owner": {"type": "team", "id": "engineering"},
                "visibility": "private",
                "lifecycle": "draft",
            },
            "kind": "workflow",
            "description": "Inert two-step release fixture: validate, then publish",
            "execution": {"mode": "local"},
            "dependencies": {"central_required": False},
            "input_contract": "engineering.validate-release.input.v1",
            "output_contract": "engineering.validate-release.output.v1",
            "steps": [
                {"namespace": "engineering", "name": "validate-release", "version": "1.0.0"},
                {"namespace": "engineering", "name": "publish-artifact", "version": "1.0.0"},
            ],
        }
    )


def shipment_skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {
                "identity": {
                    "namespace": "engineering",
                    "name": "shipment-skill",
                    "version": "1.0.0",
                },
                "owner": {"type": "team", "id": "engineering"},
                "visibility": "private",
                "lifecycle": "draft",
            },
            "alias": "shipment",
            "instructions": "Trigger the inert two-step release fixture used by the scenario case.",
            "commands": [
                {
                    "name": "run",
                    "kind": "workflow",
                    "target": {
                        "namespace": "engineering",
                        "name": "release-package",
                        "version": "1.0.0",
                    },
                }
            ],
            "default_command": "run",
        }
    )


def grants() -> tuple[CapabilityGrant, ...]:
    """What the evaluation actor may do. The filesystem read is installed but
    never granted: a case about routing must not touch this machine's disk to
    prove that routing did not execute anything."""
    return (
        CapabilityGrant.model_validate(
            {
                "actor": "engineer",
                "asset": validate_release_spec().identity,
                "permissions": ["engineering.validate"],
                "policy_refs": ["release-policy"],
                "approval_ref": "release-approval",
            }
        ),
        CapabilityGrant.model_validate(
            {
                "actor": "engineer",
                "asset": publish_artifact_spec().identity,
                "permissions": ["engineering.publish"],
                "policy_refs": ["release-policy"],
                # The scenario's irreversible step passes its prohibition
                # because somebody approved it, not because nothing ran.
                "approval_ref": "release-approval",
            }
        ),
    )


def approvals() -> dict[AssetIdentity, str | None]:
    """Which identities may run under an approval, read from the grants the
    Bridge policy actually holds."""
    return {grant.asset: grant.approval_ref for grant in grants()}


class GatewayRunner:
    """One `Gateway` per case, so one case's dispatches are never read as
    another's. The stack is rebuilt on every run rather than reset, because a
    Bridge's event log is its own and reusing it silently carries evidence
    forward."""

    def __init__(self) -> None:
        self.model = CountingModel()
        self.handler = RecordingHandler()
        self.publisher = RecordingHandler()
        self.installed = InstalledCapabilities()
        self.bridge = BridgeExecutor(self.installed)
        self.workflows = InstalledWorkflows()
        self.approved: tuple[AssetIdentity, ...] = ()

    def _build(self, model: ModelClient | None = None, alias: str = ROUTING_ALIAS) -> Gateway:
        self.model = CountingModel()
        self.handler = RecordingHandler()
        self.publisher = RecordingHandler()
        self.approved = ()
        skills = SkillRegistry()
        for name in SKILL_FILES:
            for data in json.loads((ROOT / "skills" / name).read_text(encoding="utf-8")):
                skills.register(SkillManifest.model_validate(data))
        skills.register(shipment_skill())
        installed = InstalledCapabilities()
        installed.register(
            validate_release_spec(),
            self.handler,
            Probe,
            Report,
            ExecutionDependencies(central_required=False),
        )
        installed.register(
            publish_artifact_spec(),
            self.publisher,
            Probe,
            Report,
            ExecutionDependencies(central_required=False),
        )
        installed.register(
            READ_FILE_SPEC,
            ReadFileHandler(ROOT),
            ReadFileInput,
            ReadFileOutput,
            ExecutionDependencies(central_required=False),
        )
        self.installed = installed
        self.bridge = BridgeExecutor(installed, LocalPolicy(grants()))
        workflows = InstalledWorkflows()
        workflows.register(release_workflow())
        workflows.register(release_package_workflow())
        self.workflows = workflows
        # A deterministic case keeps the model that refuses to be called; an
        # agent case supplies one that answers, and the router validates it.
        chosen: ModelClient = self.model if model is None else model
        return Gateway(
            RequestRouter(CommandRouter(skills), model=chosen, model_alias=alias),
            self.bridge,
            WorkflowEngine(workflows, self.bridge),
        )

    def gateway(self) -> Gateway:
        """The same wiring, for a host that drives the Gateway directly."""
        return self._build()

    def _declared_steps(self, decision: RouteDecision) -> int:
        """What the manifest the request triggered says must happen."""
        if decision.kind != "workflow" or decision.target is None:
            return 0
        manifest = self.workflows.get(decision.target)
        return len(manifest.steps) if manifest is not None else 0

    def _approvals(self) -> tuple[tuple[AssetIdentity, ...], tuple[AssetIdentity, ...]]:
        """What the request tried to run, split by whether an approval stood
        behind it: `(approved, unapproved)`, from one read of the grants and
        one pass over the events.

        `unapproved` makes two choices, both found by review. Only
        irreversible capabilities count, or a low-risk capability that
        legitimately needs no approval reads as a violation. And every
        *dispatch* counts, not only what ran: the policy refuses an unapproved
        high-risk dispatch today, so reading only what ran would make the
        grader unable to fail while the platform works and silent about the
        moment it stops. `approved` is every dispatch a grant with an approval
        reference stood behind, whatever its side effect, because the trace
        records who allowed what."""
        granted = approvals()
        approved: list[AssetIdentity] = []
        unapproved: list[AssetIdentity] = []
        for event in self.bridge.events:
            if granted.get(event.asset):
                if event.asset not in approved:
                    approved.append(event.asset)
                continue
            binding = self.installed.get(event.asset)
            if binding is None or binding.spec.side_effect != "external_side_effect":
                continue
            if event.asset not in unapproved:
                unapproved.append(event.asset)
        return tuple(approved), tuple(unapproved)

    def trace(self, case: EvaluationCase, observed: ObservedRun) -> ExecutionTrace:
        """The record of the run just made: joined to the case's request, and
        built from the same Bridge events and the same approvals the
        observation was read from, so the two cannot disagree."""
        return ExecutionTrace.build(
            case.request.trace, observed, self.bridge.events, approved=self.approved
        )

    def run(
        self,
        case: EvaluationCase,
        *,
        model: ModelClient | None = None,
        alias: str = ROUTING_ALIAS,
    ) -> ObservedRun:
        gateway = self._build(model, alias)
        result = asyncio.run(gateway.handle(case.request))
        workflow = result.workflow
        self.approved, unapproved = self._approvals()
        return ObservedRun(
            decision=result.routing.decision,
            origin=result.routing.origin,
            model_calls=len(self.model.calls),
            side_effects=effects_of(self.bridge, self.installed),
            observable=WATCHED,
            dispatched=tuple(event.asset for event in self.bridge.events),
            ran=invoked(self.bridge),
            status=workflow.run.status if workflow is not None else None,
            completed_steps=workflow.run.completed_steps if workflow is not None else 0,
            declared_steps=self._declared_steps(result.routing.decision),
            unapproved=unapproved,
            failure=result.routing.failure,
        )


class DiscoveryRunner:
    """The registry proof: a manifest becomes discoverable and a Bridge says
    it can run it, with nothing executed because nothing here can execute.

    It declares that it observes no effects at all. Claiming otherwise would
    move the hole this slice closed out of the grader and into the runner: a
    proof that never dispatches anything has not watched for an effect, and
    saying it did would be believed."""

    def run(self, case: EvaluationCase) -> ObservedRun:
        manifest = TaskManifest.model_validate_json(
            (ROOT / "tasks/inspect.json").read_text(encoding="utf-8")
        )
        bridge = BridgeRegistration.model_validate_json(
            (ROOT / "examples/bridge.json").read_text(encoding="utf-8")
        )
        registry = InMemoryTaskRegistry()
        advertisement = advertise_sample(manifest, registry, bridge)
        discovered = registry.discover(namespace=case.request.namespace)
        return ObservedRun(
            discovered=tuple(task.metadata.identity for task in discovered),
            # The lifecycle of what was registered, not of what a query
            # returned: `discover` already drops anything unpublished.
            lifecycle=(manifest.metadata.lifecycle,),
            advertised=tuple(item.identity for item in advertisement.capabilities),
            installed=advertisement.installed_tasks,
        )


class StubTransport:
    """An OpenAI-shaped reply, so an `agent` case exercises the real Phase 5
    adapter and the real router without a provider existing."""

    def __init__(self, content: str, status: int = 200) -> None:
        self.content = content
        self.status = status
        self.calls = 0

    def send(self, url: str, body: bytes, headers: Any, timeout_s: float) -> Any:
        self.calls += 1
        payload = json.dumps(
            {
                "choices": [{"message": {"content": self.content}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 5},
            }
        ).encode("utf-8")
        return _StubReply(self.status, payload)


class _StubReply:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def chunks(self) -> Any:
        yield self._body

    def close(self) -> None:
        return None


class RecordingClient:
    """Wraps a `ModelClient` so the evaluation can see what the call cost.
    The router returns a routing outcome, not the model's reply, and a
    comparison needs the latency and usage Phase 5 records."""

    def __init__(self, inner: ModelClient) -> None:
        self.inner = inner
        self.calls = 0
        self.responses: list[ModelResponse] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        # Counted before delegating: a call that raised was still a call, and
        # evidence that says no model was contacted must not be produced by
        # one that was.
        self.calls += 1
        response = self.inner.generate(request)
        self.responses.append(response)
        return response

    def stream(self, request: ModelRequest) -> Any:
        return self.inner.stream(request)


def routing_endpoint(alias: str) -> ModelEndpoint:
    return ModelEndpoint.model_validate(
        {
            "alias": alias,
            "provider": "openai_compatible",
            "model": "fixture",
            "base_url": "https://model.invalid/api",
            "capabilities": {"structured_output": True, "max_context_tokens": 32_000},
        }
    )


def proposing(target: AssetIdentity, kind: str = "capability") -> str:
    """What a model would have to answer for the router to accept it."""
    return json.dumps({"kind": kind, "target": target.model_dump(mode="json"), "arguments": {}})


class AgentRunner:
    """A case whose route the deterministic layer cannot resolve, so a model
    selects it. The model is a real Phase 5 adapter over a stub transport, so
    the wire, the contract check and the router's validation all run."""

    def __init__(self, alias: str, content: str) -> None:
        self.alias = alias
        self.transport = StubTransport(content)
        self.client = RecordingClient(
            OpenAICompatible(routing_endpoint(alias), transport=self.transport)
        )
        self.gateway = GatewayRunner()

    def run(self, case: EvaluationCase) -> ObservedRun:
        # The alias under comparison is the one the request carries, so two
        # aliases are never the same endpoint under two labels.
        observed = self.gateway.run(case, model=self.client, alias=self.alias)
        answered = self.client.responses[-1] if self.client.responses else None
        return ObservedRun.model_validate(
            {
                **observed.model_dump(),
                "model_calls": self.client.calls,
                "duration_ms": answered.duration_ms if answered is not None else None,
                "input_tokens": answered.input_tokens if answered is not None else 0,
                "output_tokens": answered.output_tokens if answered is not None else 0,
            }
        )


class RepositoryRunner:
    """Every case in the repository, sent to the wiring that can answer it.
    A fresh Gateway per case, so one case's dispatches are never read as
    another's. Every run leaves its trace in `traces`, keyed by case, so the
    suite can hold the records to the same standard as the observations."""

    def __init__(self) -> None:
        self.traces: dict[str, ExecutionTrace] = {}

    def run(self, case: EvaluationCase) -> ObservedRun:
        observed, _ = self.observe(case)
        return observed

    def observe(self, case: EvaluationCase) -> tuple[ObservedRun, ExecutionTrace]:
        if case.case_id in DISCOVERY_CASES:
            observed = DiscoveryRunner().run(case)
            # Nothing is dispatched by a discovery proof, so its record is a
            # route that was never taken and an outcome in which nothing ran.
            trace = ExecutionTrace.build(case.request.trace, observed, ())
        elif case.category == "agent":
            proposal = AGENT_PROPOSALS.get(case.case_id)
            if proposal is None:
                # Named, like the discovery cases: a stub fixed to one answer
                # must not silently grade a case it was never written for.
                raise LookupError(f"no stub proposal is registered for {case.case_id}")
            agent = AgentRunner(ROUTING_ALIAS, proposing(proposal))
            observed = agent.run(case)
            trace = agent.gateway.trace(case, observed)
        else:
            gateway = GatewayRunner()
            observed = gateway.run(case)
            trace = gateway.trace(case, observed)
        self.traces[case.case_id] = trace
        return observed, trace
