"""Closed contracts for simulated and physical DUT validation."""

import math
from typing import Literal, Self

from pydantic import Field, JsonValue, StrictBool, field_validator, model_validator

from common.assets import AssetIdentity, reject_embedded_secrets
from common.base import Contract, Sha256, Symbol, Text
from common.execution import Failure, TraceIdentifiers
from harness.contracts import CodingHarnessRequest, CodingHarnessResult


def skill_ref(identity: AssetIdentity) -> str:
    return f"{identity.namespace}.{identity.name}@{identity.version}"


class DutTarget(Contract):
    resource_id: Symbol
    device_id: Symbol
    vendor: Symbol
    model: Text
    firmware: Text


class InstrumentTarget(Contract):
    resource_id: Symbol
    instrument_id: Symbol
    model: Text
    firmware: Text | None = None


class DutCommand(Contract):
    name: Symbol
    arguments: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def safe_arguments(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class Measurement(Contract):
    name: Symbol
    value: float
    unit: Text

    @field_validator("value")
    @classmethod
    def finite_value(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("measurement values must be finite")
        return value


class MeasurementLimit(Contract):
    name: Symbol
    unit: Text
    minimum: float | None = None
    maximum: float | None = None

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if self.minimum is None and self.maximum is None:
            raise ValueError("a measurement limit requires at least one bound")
        if self.minimum is not None and not math.isfinite(self.minimum):
            raise ValueError("measurement limits must be finite")
        if self.maximum is not None and not math.isfinite(self.maximum):
            raise ValueError("measurement limits must be finite")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("measurement minimum cannot exceed maximum")
        return self


class ExpectedState(Contract):
    field: Symbol
    expected: JsonValue

    @model_validator(mode="after")
    def safe_state(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class DutObservation(Contract):
    command: Symbol
    state: dict[str, JsonValue] = Field(default_factory=dict)
    measurements: tuple[Measurement, ...] = ()

    @model_validator(mode="after")
    def unique_and_safe(self) -> Self:
        names = [item.name for item in self.measurements]
        if len(names) != len(set(names)):
            raise ValueError("an observation records each measurement once")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class ValidatorOutcome(Contract):
    criterion: Symbol
    kind: Literal["measurement", "state"]
    passed: StrictBool
    expected: JsonValue
    observed: JsonValue


class DutValidationRequest(Contract):
    bridge_id: Symbol
    workspace_revision: Sha256
    skill: AssetIdentity
    target: DutTarget
    instrument: InstrumentTarget | None = None
    commands: tuple[DutCommand, ...] = Field(min_length=1)
    limits: tuple[MeasurementLimit, ...] = ()
    expected_state: tuple[ExpectedState, ...] = ()

    @model_validator(mode="after")
    def deterministic_acceptance(self) -> Self:
        if not self.limits and not self.expected_state:
            raise ValueError("DUT validation requires a measurement limit or expected state")
        command_names = [item.name for item in self.commands]
        if len(command_names) != len(set(command_names)):
            raise ValueError("DUT commands must be unique and ordered")
        limit_names = [item.name for item in self.limits]
        state_fields = [item.field for item in self.expected_state]
        if len(limit_names) != len(set(limit_names)) or len(state_fields) != len(set(state_fields)):
            raise ValueError("DUT validation criteria must be unique")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class DutValidationEvidence(Contract):
    trace: TraceIdentifiers
    mode: Literal["simulator", "recording", "physical"]
    evidence_level: Literal["simulated", "production_like"]
    bridge_id: Symbol
    workspace_revision: Sha256
    skill: AssetIdentity
    target: DutTarget
    instrument: InstrumentTarget | None = None
    commands: tuple[DutCommand, ...]
    observations: tuple[DutObservation, ...]
    outcomes: tuple[ValidatorOutcome, ...] = Field(min_length=1)
    status: Literal["passed", "failed"]

    @model_validator(mode="after")
    def externally_decided(self) -> Self:
        if (self.mode == "physical") != (self.evidence_level == "production_like"):
            raise ValueError("only physical execution produces production-like evidence")
        if len(self.commands) != len(self.observations):
            raise ValueError("each DUT command requires one observation")
        if any(
            command.name != observation.command
            for command, observation in zip(self.commands, self.observations, strict=True)
        ):
            raise ValueError("DUT observations must follow the requested commands")
        passed = all(item.passed for item in self.outcomes)
        if (self.status == "passed") != passed:
            raise ValueError("DUT status must match validator outcomes")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class DutDevelopmentRequest(Contract):
    coding: CodingHarnessRequest
    simulation: DutValidationRequest

    @model_validator(mode="after")
    def same_workspace_and_skill(self) -> Self:
        if self.coding.workspace.starting_revision != self.simulation.workspace_revision:
            raise ValueError("simulation must name the starting workspace revision")
        if skill_ref(self.simulation.skill) not in self.coding.skill_versions:
            raise ValueError("development must bind the exact Skill used by simulation")
        return self


class DutDevelopmentResult(Contract):
    trace: TraceIdentifiers
    status: Literal["simulated_validated", "failed"]
    harness: CodingHarnessResult
    simulation: DutValidationEvidence | None = None
    failure: Failure | None = None
    physical_gate_satisfied: StrictBool = False

    @model_validator(mode="after")
    def completion_evidence(self) -> Self:
        if self.physical_gate_satisfied:
            raise ValueError("development and simulation cannot satisfy the physical gate")
        if self.status == "simulated_validated":
            if (
                self.harness.status != "validated"
                or self.simulation is None
                or self.simulation.status != "passed"
                or self.simulation.evidence_level != "simulated"
                or self.failure is not None
            ):
                raise ValueError("simulated validation requires Harness and simulator evidence")
        elif self.failure is None:
            raise ValueError("failed DUT development requires failure evidence")
        return self


class DutPhysicalValidationRequest(Contract):
    validation: DutValidationRequest


class DutChangeReview(Contract):
    implementation_digest: Sha256
    evidence: DutValidationEvidence
    reviewer: Symbol
    approval_ref: Text
    status: Literal["approved", "rejected"]

    @model_validator(mode="after")
    def physical_approval(self) -> Self:
        if self.status == "approved" and not (
            self.evidence.evidence_level == "production_like" and self.evidence.status == "passed"
        ):
            raise ValueError("approval requires passing production-like physical evidence")
        return self
