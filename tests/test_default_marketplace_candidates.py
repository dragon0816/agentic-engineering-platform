"""Default candidates are portable drafts, not Registry publications."""

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from capabilities.weekly_report.handlers import PLAN_SPEC
from capabilities.weekly_report.manifest import PREVIEW_WORKFLOW, weekly_report_workflow
from common.assets import PackageMetadata, WorkflowManifest
from common.distribution import PublishedAssetPackage
from control_plane.distribution import InMemoryPackageRegistry
from host_runtime import default_candidates


def test_workflow11_preview_candidate_preserves_exact_read_only_route() -> None:
    candidate = default_candidates.workflow11_preview_candidate()
    manifest = WorkflowManifest.model_validate_json(candidate.content)

    assert manifest == candidate.manifest
    assert manifest.metadata.identity == PREVIEW_WORKFLOW
    assert manifest.metadata.lifecycle == "draft"
    assert manifest.metadata.visibility == "private"
    assert manifest.metadata.business_approval.status == "pending"
    assert manifest.metadata.technical_policy.status == "pending"
    assert manifest.metadata.technical_policy.approval_required
    assert manifest.metadata.technical_policy.required_permissions == (
        "weekly-report.plan",
        "github.read",
        "excel.read",
    )
    assert manifest.metadata.provenance[0].revision == ("896046e8fe2170d21f9213e56e5ce2f93c05ba43")
    assert manifest.run_alias == 11
    assert manifest.dependencies.local_capabilities == (
        "weekly_report.resolve_window",
        "github.search_project",
        "excel.read_scratch_sheet",
        "weekly_report.plan",
    )
    assert len(manifest.steps) == 4
    assert "weekly_report.apply" not in manifest.dependencies.local_capabilities
    assert "weekly_report.mail" not in manifest.dependencies.local_capabilities
    assert candidate.sha256 == hashlib.sha256(candidate.content).hexdigest()


def test_candidate_export_is_deterministic_and_not_registry_publishable(tmp_path: Path) -> None:
    registry = InMemoryPackageRegistry()
    first = default_candidates.export_default_candidates(tmp_path)
    first_bytes = first[0].read_bytes()
    second = default_candidates.export_default_candidates(tmp_path)

    assert first == second
    assert len(first) == 1
    assert first_bytes == second[0].read_bytes()
    assert first[0].parent.name == "candidates"
    assert WorkflowManifest.model_validate_json(first_bytes).metadata.lifecycle == "draft"
    assert registry.discover() == ()

    candidate = default_candidates.workflow11_preview_candidate()
    package = PackageMetadata(artifact_ref="candidate://preview", sha256=candidate.sha256)
    metadata = candidate.manifest.metadata.model_copy(update={"package": package})
    with pytest.raises(ValidationError, match="only published assets may be distributed"):
        PublishedAssetPackage(kind="workflow", metadata=metadata, description="Preview only")

    first[0].write_bytes(b"operator-edited candidate")
    with pytest.raises(ValueError, match="candidate file differs"):
        default_candidates.export_default_candidates(tmp_path)


def test_shipped_candidate_snapshot_matches_source_backed_export() -> None:
    root = Path(__file__).resolve().parents[1]
    path = (
        root / "examples/default-marketplace/candidates/"
        "engineering__jira-weekly-report-preview__1.0.0.json"
    )
    assert path.read_bytes() == default_candidates.workflow11_preview_candidate().content


def test_candidate_refuses_source_route_or_side_effect_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(default_candidates, "preview_workflow", weekly_report_workflow)
    with pytest.raises(ValueError, match="exact read-only preview"):
        default_candidates.workflow11_preview_candidate()

    monkeypatch.undo()
    write_classified_plan = PLAN_SPEC.model_copy(update={"side_effect": "write"})
    monkeypatch.setattr(
        default_candidates,
        "PREVIEW_SPECS",
        (*default_candidates.PREVIEW_SPECS[:3], write_classified_plan),
    )
    with pytest.raises(ValueError, match="exact read-only preview"):
        default_candidates.workflow11_preview_candidate()
