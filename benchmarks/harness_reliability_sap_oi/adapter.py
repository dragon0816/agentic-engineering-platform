"""Benchmark-only governed exporter with mandatory independent acceptance."""

import json
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused, CapabilityTaskFailed
from common.base import Contract
from common.execution import RequestContext
from harness.thread_operations import run_tracked_thread

from .oracle import verify_records, verify_workbook
from .workbook import build_workbook, review_html, saved_cell_snapshot

HERE = Path(__file__).resolve().parent
SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "benchmark-oi", "name": "export", "version": "1.0.0"},
        "name": "benchmark_oi.export",
        "description": "Build the synthetic OI Excel PivotTable and independently verify it",
        "input_contract": "benchmark.oi.export.input.v1",
        "output_contract": "benchmark.oi.export.output.v1",
        "side_effect": "write",
        "policy": {
            "risk": "low",
            "approval_required": True,
            "required_permissions": ["benchmark.oi.write"],
            "policy_refs": ["synthetic-workspace-only"],
        },
    }
)


class ExportInput(Contract):
    normalized_path: str


class ExportResult(Contract):
    workbook: str
    verification: dict[str, JsonValue]


class ExportHandler:
    def __init__(self, workspace: Path, source_url: str) -> None:
        self.workspace = workspace.resolve()
        self.source_url = source_url
        self.attempts = 0

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = ExportInput.model_validate(inputs)
        candidate = Path(request.normalized_path).resolve()
        folder = self.workspace / "output"
        if folder not in candidate.parents or not candidate.is_file():
            raise CapabilityRefused("oi_input_outside_output")
        return await run_tracked_thread(self.workspace, lambda: self.export(candidate))

    def export(self, candidate: Path) -> ExportResult:
        self.attempts += 1
        output = self.workspace / "output" / "sales-oi-pivot.xlsx"
        evidence = self.workspace / "evidence"
        evidence.mkdir(exist_ok=True)
        try:
            records: list[dict[str, Any]] = json.loads(candidate.read_text(encoding="utf-8"))
            verify_records(records)
            build_workbook(output, records, self.source_url)
            verification = verify_workbook(output)
            saved_cell_snapshot(output)
            review_html(output)
            verification["authoring_backend"] = "openpyxl_after_native_artifact_export_failure"
            verification["formula_caches"] = "calculated_snapshot_not_desktop_recalculation"
        except (ValueError, KeyError, TypeError, OSError) as error:
            code = str(error) if isinstance(error, ValueError) else type(error).__name__
            verification = {"passed": False, "check": code}
            (evidence / f"verification-{self.attempts:02d}.json").write_text(
                json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            result = ExportResult(workbook=str(output), verification=verification)
            raise CapabilityTaskFailed("oi_verification_failed", result) from None
        (evidence / f"verification-{self.attempts:02d}.json").write_text(
            json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return ExportResult(workbook=str(output), verification=verification)
