"""Workflow 14 handlers: `prepare` reads, `render` writes the document."""

from __future__ import annotations

import asyncio
from pathlib import Path

from capabilities.ncc_plan.contracts import (
    NccPlan,
    NccPlanStepInput,
    NccRendered,
    NccRenderStepInput,
    OutputFile,
    Verdict,
)
from capabilities.ncc_plan.document import DocumentError, render
from capabilities.ncc_plan.planning import prepare_plan
from capabilities.ncc_plan.rules import JobError
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext

#: The source's operator messages, as stable codes: a message can quote the
#: station or the price list, and neither leaves the Bridge in a failure.
_REFUSALS = (
    ("no system was ticked", "ncc_nothing_ticked"),
    ("no unit price for", "ncc_price_missing"),
    ("priced per wattage", "ncc_power_unpriced"),
    ("has no service configured", "ncc_service_unconfigured"),
    ("priced per channel but no channel", "ncc_channels_missing"),
    ("no channels given", "ncc_channels_missing"),
    ("is not in the station table", "ncc_station_unknown"),
    ("params.station is empty", "ncc_station_unknown"),
    ("carries no `stations` list", "ncc_catalogue_empty"),
    ("not a JSON object", "ncc_catalogue_invalid"),
    ("template was not found", "ncc_template_missing"),
    ("output_dir is not a folder", "ncc_output_dir_missing"),
)


def refusal_code(error: JobError) -> str:
    message = str(error)
    return next((code for needle, code in _REFUSALS if needle in message), "ncc_plan_refused")


class NccPrepareHandler:
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        step = NccPlanStepInput.model_validate(inputs)
        try:
            return await asyncio.to_thread(prepare_plan, step.request)
        except JobError as error:
            raise CapabilityRefused(refusal_code(error)) from None
        except (OSError, ValueError):
            raise CapabilityRefused("ncc_catalogue_unreadable") from None


def render_plan(plan: NccPlan) -> NccRendered:
    if plan.dry_run:
        return NccRendered(written=False, verdict=plan.verdict, missing_photos=plan.missing_photos)
    output = Path(plan.output_path)
    if not output.parent.is_dir():
        raise DocumentError("ncc_output_dir_missing")
    try:
        warnings = render(Path(plan.template_file), plan.station, plan.document, output)
    except (OSError, ValueError, KeyError):
        raise DocumentError("template_unreadable") from None
    summary = f"{plan.station} {len(plan.services)} 項，總計 {plan.total:,} 元，已寫檔"
    return NccRendered(
        written=True,
        output=str(output),
        verdict=Verdict(ok=True, summary=summary),
        files=(OutputFile(name=output.name, path=str(output.resolve())),),
        missing_photos=plan.missing_photos,
        warnings=tuple(warnings),
    )


class NccRenderHandler:
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        step = NccRenderStepInput.model_validate(inputs)
        try:
            return await asyncio.to_thread(render_plan, step.plan)
        except DocumentError as error:
            raise CapabilityRefused(str(error)) from None
