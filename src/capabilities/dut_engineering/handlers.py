"""Capability specifications and handlers for the E2E-01 DUT boundary."""

import asyncio

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext
from dut.contracts import DutDevelopmentRequest, DutPhysicalValidationRequest
from dut.runtime import DutDevelopmentService, DutValidationRefused, PhysicalDutValidationService

DUT_DEVELOP_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "dut-engineering", "name": "develop", "version": "1.0.0"},
        "name": "dut_engineering.develop",
        "description": "Develop and simulate one bounded DUT controller change",
        "input_contract": "dut-engineering.develop.input.v1",
        "output_contract": "dut-engineering.develop.output.v1",
        "side_effect": "write",
        "policy": {
            "risk": "medium",
            "approval_required": True,
            "required_permissions": ["dut-engineering.develop"],
            "policy_refs": ["dut-workspace-policy"],
        },
    }
)

DUT_PHYSICAL_VALIDATE_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {
            "namespace": "dut-engineering",
            "name": "validate-physical",
            "version": "1.0.0",
        },
        "name": "dut_engineering.validate_physical",
        "description": "Execute approved DUT commands through a fixed local physical driver",
        "input_contract": "dut-engineering.validate-physical.input.v1",
        "output_contract": "dut-engineering.validate-physical.output.v1",
        "side_effect": "external_side_effect",
        "policy": {
            "risk": "high",
            "approval_required": True,
            "required_permissions": ["dut-engineering.validate-physical"],
            "policy_refs": ["dut-physical-execution-policy"],
        },
    }
)


class DutDevelopmentHandler:
    def __init__(self, service: DutDevelopmentService) -> None:
        self.service = service

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = DutDevelopmentRequest.model_validate(inputs)
        return await asyncio.to_thread(self.service.run, context.trace, request)


class PhysicalDutValidationHandler:
    def __init__(self, service: PhysicalDutValidationService) -> None:
        self.service = service

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = DutPhysicalValidationRequest.model_validate(inputs)
        try:
            return await asyncio.to_thread(self.service.run, context, request)
        except DutValidationRefused as refusal:
            raise CapabilityRefused(refusal.code) from refusal
