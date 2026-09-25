"""Bridge-installed Software issue capture and approved development."""

import asyncio

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext
from software.evolution import (
    SoftwareCatalog,
    SoftwareDevelopmentRequest,
    SoftwareFailureReport,
    capture_improvement,
)
from software.runtime import SoftwareDevelopmentRefused, SoftwareDevelopmentService

SOFTWARE_CAPTURE_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {
            "namespace": "software-evolution",
            "name": "capture-issue",
            "version": "1.0.0",
        },
        "name": "software_evolution.capture_issue",
        "description": "Route a user report to an exact published Software version",
        "input_contract": "software-evolution.report.input.v1",
        "output_contract": "software-evolution.improvement.output.v1",
        "side_effect": "read",
        "policy": {
            "approval_required": False,
            "required_permissions": ["software-evolution.capture-issue"],
            "policy_refs": ["software-issue-routing-policy"],
        },
    }
)

SOFTWARE_DEVELOP_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {
            "namespace": "software-evolution",
            "name": "prepare-change",
            "version": "1.0.0",
        },
        "name": "software_evolution.prepare_change",
        "description": "Reproduce and develop an approved Software change candidate",
        "input_contract": "software-evolution.development.input.v1",
        "output_contract": "software-evolution.development.output.v1",
        "side_effect": "write",
        "policy": {
            "risk": "medium",
            "approval_required": True,
            "required_permissions": ["software-evolution.prepare-change"],
            "policy_refs": ["software-workspace-policy"],
        },
    }
)


class SoftwareCaptureHandler:
    def __init__(self, catalog: SoftwareCatalog) -> None:
        self.catalog = catalog

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        report = SoftwareFailureReport.model_validate(inputs)
        try:
            return capture_improvement(
                self.catalog,
                report,
                request_id=f"software-{context.trace.request_id}",
            )
        except LookupError:
            raise CapabilityRefused("software_version_not_found") from None


class SoftwareDevelopHandler:
    def __init__(self, service: SoftwareDevelopmentService) -> None:
        self.service = service

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = SoftwareDevelopmentRequest.model_validate(inputs)
        try:
            return await asyncio.to_thread(self.service.run, context.trace, request)
        except SoftwareDevelopmentRefused as error:
            raise CapabilityRefused(error.code) from None
