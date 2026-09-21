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
from common.assets import ExecutionDependencies, TaskManifest, WorkflowManifest
from common.base import Contract
from common.evaluation import EvaluationCase, ObservedRun
from common.execution import RequestContext, SideEffect
from models.contracts import ModelRequest, ModelResponse
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


def effects_of(bridge: BridgeExecutor, installed: InstalledCapabilities) -> tuple[SideEffect, ...]:
    """The declared side effect of everything the Bridge actually put in
    motion. A capability that ran and then failed still ran, so its effect
    counts; a dispatch refused before the handler was reached did not."""
    effects: list[SideEffect] = []
    for event in bridge.events:
        if event.status != "succeeded" and event.code not in INVOKED_CODES:
            continue
        binding = installed.get(event.asset)
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
    )


class GatewayRunner:
    """One `Gateway` per case, so one case's dispatches are never read as
    another's. The stack is rebuilt on every run rather than reset, because a
    Bridge's event log is its own and reusing it silently carries evidence
    forward."""

    def __init__(self) -> None:
        self.model = CountingModel()
        self.handler = RecordingHandler()
        self.installed = InstalledCapabilities()
        self.bridge = BridgeExecutor(self.installed)

    def _build(self) -> Gateway:
        self.model = CountingModel()
        self.handler = RecordingHandler()
        skills = SkillRegistry()
        for name in SKILL_FILES:
            for data in json.loads((ROOT / "skills" / name).read_text(encoding="utf-8")):
                skills.register(SkillManifest.model_validate(data))
        installed = InstalledCapabilities()
        installed.register(
            validate_release_spec(),
            self.handler,
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
        return Gateway(
            RequestRouter(CommandRouter(skills), model=self.model),
            self.bridge,
            WorkflowEngine(workflows, self.bridge),
        )

    def run(self, case: EvaluationCase) -> ObservedRun:
        gateway = self._build()
        result = asyncio.run(gateway.handle(case.request))
        workflow = result.workflow
        return ObservedRun(
            decision=result.routing.decision,
            origin=result.routing.origin,
            model_calls=len(self.model.calls),
            side_effects=effects_of(self.bridge, self.installed),
            observable=WATCHED,
            dispatched=tuple(event.asset for event in self.bridge.events),
            status=workflow.run.status if workflow is not None else None,
            completed_steps=workflow.run.completed_steps if workflow is not None else 0,
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


class RepositoryRunner:
    """Every case in the repository, sent to the wiring that can answer it.
    A fresh Gateway per case, so one case's dispatches are never read as
    another's."""

    def run(self, case: EvaluationCase) -> ObservedRun:
        if case.case_id in DISCOVERY_CASES:
            return DiscoveryRunner().run(case)
        return GatewayRunner().run(case)
