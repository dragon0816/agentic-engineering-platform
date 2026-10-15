"""Portable, inert Marketplace candidates derived from shipped Host manifests.

Candidates live outside the installed ``workflows/`` directory and retain a
draft lifecycle. Publishing and installation remain separate review actions.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from capabilities.contracts import CapabilitySpec
from capabilities.weekly_report.handlers import (
    PLAN_SPEC,
    PROJECT_SEARCH_SPEC,
    READ_SCRATCH_SHEET_SPEC,
    RESOLVE_WINDOW_SPEC,
)
from capabilities.weekly_report.manifest import PREVIEW_WORKFLOW, preview_workflow
from common.assets import WorkflowManifest, WorkflowStep
from host_runtime.workspace import write_atomically

SOURCE_REVISION = "896046e8fe2170d21f9213e56e5ce2f93c05ba43"
PREVIEW_SPECS: tuple[CapabilitySpec, ...] = (
    RESOLVE_WINDOW_SPEC,
    PROJECT_SEARCH_SPEC,
    READ_SCRATCH_SHEET_SPEC,
    PLAN_SPEC,
)


@dataclass(frozen=True)
class DefaultCandidate:
    manifest: WorkflowManifest
    content: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


def _require_exact_read_only_preview(
    manifest: WorkflowManifest, specs: tuple[CapabilitySpec, ...]
) -> None:
    step_identities = tuple(
        step.capability if isinstance(step, WorkflowStep) else step for step in manifest.steps
    )
    if (
        manifest.metadata.identity != PREVIEW_WORKFLOW
        or manifest.execution.mode != "local"
        or manifest.dependencies.central_required
        or manifest.dependencies.local_capabilities != tuple(spec.name for spec in specs)
        or step_identities != tuple(spec.identity for spec in specs)
        or any(spec.side_effect != "read" for spec in specs)
    ):
        raise ValueError("default candidate requires the exact read-only preview")


def workflow11_preview_candidate() -> DefaultCandidate:
    """Stage the source-pinned preview for review without making it installable."""
    source = preview_workflow()
    _require_exact_read_only_preview(source, PREVIEW_SPECS)
    permissions = tuple(
        dict.fromkeys(
            permission for spec in PREVIEW_SPECS for permission in spec.policy.required_permissions
        )
    )
    policy_refs = tuple(
        dict.fromkeys(ref for spec in PREVIEW_SPECS for ref in spec.policy.policy_refs)
    )
    payload = source.model_dump(mode="json")
    metadata = payload["metadata"]
    metadata.update(
        {
            "visibility": "private",
            "lifecycle": "draft",
            "categories": ["engineering", "reporting"],
            "provenance": [
                {
                    "source": "dragon0816/rs_workflow_system:workflows/11_jira_weekly_report.json",
                    "revision": SOURCE_REVISION,
                },
                {
                    "source": (
                        "agentic-engineering-platform:"
                        "capabilities.weekly_report.manifest.preview_workflow"
                    )
                },
            ],
            "compatibility": {"contract_version": "1", "platforms": ["windows"]},
            "business_approval": {"status": "pending"},
            "technical_policy": {
                "status": "pending",
                "risk": "low",
                "approval_required": True,
                "required_permissions": permissions,
                "policy_refs": policy_refs,
                "assessment": "manual",
            },
            "package": None,
        }
    )
    manifest = WorkflowManifest.model_validate(payload)
    content = manifest.model_dump_json(indent=2).encode("utf-8") + b"\n"
    return DefaultCandidate(manifest=manifest, content=content)


def export_default_candidates(directory: Path) -> tuple[Path, ...]:
    """Write draft JSON under ``candidates/``; never register or install it."""
    candidate = workflow11_preview_candidate()
    identity = candidate.manifest.metadata.identity
    target = (
        directory / "candidates" / f"{identity.namespace}__{identity.name}__{identity.version}.json"
    )
    if target.exists():
        if target.read_bytes() != candidate.content:
            raise ValueError("candidate file differs from the source-pinned draft")
    else:
        write_atomically(target, candidate.content)
    return (target,)
