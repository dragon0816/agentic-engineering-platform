"""Writing the shipped manifests where a workspace or a publisher reads them.

A host concern, beside the CLI: the manifests themselves are pure data in
the capability packages that ship them.
"""

import json
from pathlib import Path

from agent.skills import SkillManifest
from capabilities.chipset_report.manifest import preview_skill as chipset_preview_skill
from capabilities.chipset_report.manifest import preview_workflow as chipset_preview_workflow
from capabilities.chipset_report.manifest import report_workflow as chipset_report_workflow
from capabilities.company_agent.manifest import (
    knowledge_skill,
    market_alignment_skill,
    personal_proof_skill,
    personal_proof_workflow,
    workflow_author_skill,
)
from capabilities.ncc_plan.manifest import plan_skill as ncc_plan_skill
from capabilities.ncc_plan.manifest import plan_workflow as ncc_plan_workflow
from capabilities.release_package.manifest import (
    isolated_apply_workflow as release_isolated_apply_workflow,
)
from capabilities.release_package.manifest import preview_skill as release_preview_skill
from capabilities.release_package.manifest import preview_workflow as release_preview_workflow
from capabilities.team_tickets.manifest import preview_skill as team_tickets_preview_skill
from capabilities.team_tickets.manifest import preview_workflow as team_tickets_preview_workflow
from capabilities.weekly_report.manifest import (
    mail_workflow,
    preview_workflow,
    report_workflow,
    weekly_skill,
)
from common.assets import WorkflowManifest
from host_runtime.workspace import write_atomically


def shipped() -> tuple[SkillManifest | WorkflowManifest, ...]:
    """Every manifest this package ships, Skills and Workflows alike."""
    return (
        chipset_preview_skill(),
        chipset_preview_workflow(),
        chipset_report_workflow(),
        release_preview_skill(),
        release_preview_workflow(),
        release_isolated_apply_workflow(),
        ncc_plan_skill(),
        ncc_plan_workflow(),
        weekly_skill(),
        team_tickets_preview_skill(),
        workflow_author_skill(),
        knowledge_skill(),
        market_alignment_skill(),
        personal_proof_skill(),
        preview_workflow(),
        team_tickets_preview_workflow(),
        report_workflow(),
        mail_workflow(),
        personal_proof_workflow(),
    )


def export_assets(directory: Path) -> tuple[Path, ...]:
    """Write the shipped manifests as `skills/` and `workflows/` under
    `directory`, named as a sync would name them."""
    written: list[Path] = []
    for manifest in shipped():
        folder = "skills" if isinstance(manifest, SkillManifest) else "workflows"
        identity = manifest.metadata.identity
        path = (
            directory / folder / f"{identity.namespace}__{identity.name}__{identity.version}.json"
        )
        payload = json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False)
        write_atomically(path, payload.encode("utf-8") + b"\n")
        written.append(path)
    return tuple(written)
