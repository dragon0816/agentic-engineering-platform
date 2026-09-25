"""Bounded DUT development, external validation, and physical admission."""

from __future__ import annotations

from pydantic import TypeAdapter

from common.base import Symbol
from common.enrollment import admit_device
from common.execution import Failure, RequestContext, TraceIdentifiers
from common.local_agent import BridgeMembership
from dut.adapters import DutAdapter
from dut.contracts import (
    DutChangeReview,
    DutDevelopmentRequest,
    DutDevelopmentResult,
    DutPhysicalValidationRequest,
    DutTarget,
    DutValidationEvidence,
    DutValidationRequest,
    InstrumentTarget,
    ValidatorOutcome,
)
from harness.runtime import CodingHarness
from workflow.host_bridge import BridgeRegistration


class DutValidationRefused(Exception):
    def __init__(self, code: str) -> None:
        self.code = TypeAdapter(Symbol).validate_python(code)
        super().__init__(self.code)


class DutValidationService:
    def __init__(self, adapter: DutAdapter) -> None:
        self.adapter = adapter

    def run(self, trace: TraceIdentifiers, request: DutValidationRequest) -> DutValidationEvidence:
        checked = DutValidationRequest.model_validate(request)
        observations = tuple(self.adapter.execute(checked, command) for command in checked.commands)
        measurements = {
            item.name: item for observation in observations for item in observation.measurements
        }
        final_state: dict[str, object] = {}
        for observation in observations:
            final_state.update(observation.state)
        outcomes: list[ValidatorOutcome] = []
        for limit in checked.limits:
            observed = measurements.get(limit.name)
            passed = bool(
                observed is not None
                and observed.unit == limit.unit
                and (limit.minimum is None or observed.value >= limit.minimum)
                and (limit.maximum is None or observed.value <= limit.maximum)
            )
            outcomes.append(
                ValidatorOutcome(
                    criterion=limit.name,
                    kind="measurement",
                    passed=passed,
                    expected={
                        "unit": limit.unit,
                        "minimum": limit.minimum,
                        "maximum": limit.maximum,
                    },
                    observed=(observed.model_dump(mode="json") if observed is not None else None),
                )
            )
        for expected in checked.expected_state:
            observed_value = final_state.get(expected.field)
            outcomes.append(
                ValidatorOutcome(
                    criterion=expected.field,
                    kind="state",
                    passed=observed_value == expected.expected,
                    expected=expected.expected,
                    observed=observed_value,
                )
            )
        return DutValidationEvidence(
            trace=trace,
            mode=self.adapter.mode,
            evidence_level=("production_like" if self.adapter.mode == "physical" else "simulated"),
            bridge_id=checked.bridge_id,
            workspace_revision=checked.workspace_revision,
            skill=checked.skill,
            target=checked.target,
            instrument=checked.instrument,
            commands=checked.commands,
            observations=observations,
            outcomes=tuple(outcomes),
            status="passed" if all(item.passed for item in outcomes) else "failed",
        )


class DutDevelopmentService:
    def __init__(self, harness: CodingHarness, simulator: DutValidationService) -> None:
        if simulator.adapter.mode != "simulator":
            raise ValueError("DUT development requires a simulator adapter")
        self.harness = harness
        self.simulator = simulator

    def run(self, trace: TraceIdentifiers, request: DutDevelopmentRequest) -> DutDevelopmentResult:
        checked = DutDevelopmentRequest.model_validate(request)
        result = self.harness.run(trace, checked.coding)
        if result.status != "validated":
            return DutDevelopmentResult(
                trace=trace,
                status="failed",
                harness=result,
                failure=result.failure
                or Failure(code="harness_failed", message="DUT development did not validate"),
            )
        evidence = self.simulator.run(trace, checked.simulation)
        if evidence.status != "passed":
            return DutDevelopmentResult(
                trace=trace,
                status="failed",
                harness=result,
                simulation=evidence,
                failure=Failure(
                    code="simulation_failed",
                    message="The independent DUT simulator rejected the implementation",
                ),
            )
        return DutDevelopmentResult(
            trace=trace,
            status="simulated_validated",
            harness=result,
            simulation=evidence,
        )


class PhysicalDutValidationService:
    def __init__(
        self,
        membership: BridgeMembership,
        registration: BridgeRegistration,
        *,
        installed_skill: object,
        adapter: DutAdapter,
        physical_enabled: bool,
        installed_target: DutTarget | None = None,
        installed_instrument: InstrumentTarget | None = None,
    ) -> None:
        self.membership = BridgeMembership.model_validate(membership)
        self.registration = BridgeRegistration.model_validate(registration)
        self.installed_skill = installed_skill
        self.adapter = adapter
        self.physical_enabled = physical_enabled
        self.installed_target = installed_target
        self.installed_instrument = installed_instrument

    def run(
        self, context: RequestContext, request: DutPhysicalValidationRequest
    ) -> DutValidationEvidence:
        checked = DutPhysicalValidationRequest.model_validate(request).validation
        device = self.membership.device
        refused = admit_device(device, actor=context.actor, bridge_id=checked.bridge_id)
        if refused is not None:
            raise DutValidationRefused(refused)
        if self.membership.binding_for(context.actor) is None:
            raise DutValidationRefused("actor_not_bound")
        if (
            self.registration.bridge_id != device.bridge_id
            or self.registration.owner_id != device.registered_by
        ):
            raise DutValidationRefused("advertisement_identity_mismatch")
        if self.adapter.mode == "physical" and not self.physical_enabled:
            raise DutValidationRefused("physical_execution_disabled")
        if self.adapter.mode == "simulator":
            raise DutValidationRefused("physical_adapter_required")
        if self.installed_skill != checked.skill:
            raise DutValidationRefused("skill_not_installed")
        if self.installed_target is not None and checked.target != self.installed_target:
            raise DutValidationRefused("dut_identity_mismatch")
        if checked.instrument != self.installed_instrument and (
            checked.instrument is not None or self.installed_instrument is not None
        ):
            raise DutValidationRefused("instrument_identity_mismatch")
        resources = {item.resource_id: item for item in self.registration.local_resources}
        target = resources.get(checked.target.resource_id)
        if target is None or target.kind != "dut" or not target.available:
            raise DutValidationRefused("dut_unavailable")
        if checked.instrument is not None:
            instrument = resources.get(checked.instrument.resource_id)
            if instrument is None or instrument.kind != "instrument" or not instrument.available:
                raise DutValidationRefused("instrument_unavailable")
        return DutValidationService(self.adapter).run(context.trace, checked)


def review_dut_change(
    *,
    implementation_digest: str,
    evidence: DutValidationEvidence,
    reviewer: str,
    approval_ref: str,
    approved: bool,
) -> DutChangeReview:
    return DutChangeReview(
        implementation_digest=implementation_digest,
        evidence=evidence,
        reviewer=reviewer,
        approval_ref=approval_ref,
        status="approved" if approved else "rejected",
    )
