"""Writing the shipped manifests where a workspace or a publisher reads them.

A host concern, beside the CLI: the manifests themselves are pure data in
the capability packages that ship them.

Two sets (owner 2026-10-16, docs/DECISIONS.md "The weekly report is
personal, not bundled"):

- `shipped()`: what every installation gets. The Windows bundle installs
  these (`aep-host assets install-bundled`) and `export-assets` writes them;
- `personal()`: the owner's own Workflows (the SDE weekly report). They stay
  in the package so the owner's install and upgrade keep working, but they
  are written or installed only when asked for, with `--include-personal`
  or `AEP_INCLUDE_PERSONAL_ASSETS=1`. A machine that received them from an
  earlier bundle keeps what it has: nothing here removes them, and nothing
  adds them again.
"""

import json
import os
from collections.abc import Mapping
from pathlib import Path

from agent.skills import SkillManifest
from capabilities.chipset_report.manifest import preview_skill as chipset_preview_skill
from capabilities.chipset_report.manifest import preview_workflow as chipset_preview_workflow
from capabilities.chipset_report.manifest import report_workflow as chipset_report_workflow
from capabilities.coding_change.manifest import (
    coding_skill,
    coding_workflow,
    run_python_workflow,
)
from capabilities.company_agent.manifest import (
    knowledge_skill,
    market_alignment_skill,
    personal_proof_skill,
    personal_proof_workflow,
    workflow_author_skill,
)
from capabilities.ncc_plan.manifest import plan_skill as ncc_plan_skill
from capabilities.ncc_plan.manifest import plan_workflow as ncc_plan_workflow
from capabilities.release_package.manifest import commit_workflow as release_commit_workflow
from capabilities.release_package.manifest import (
    isolated_apply_workflow as release_isolated_apply_workflow,
)
from capabilities.release_package.manifest import prepare_workflow as release_prepare_workflow
from capabilities.release_package.manifest import preview_skill as release_preview_skill
from capabilities.release_package.manifest import preview_workflow as release_preview_workflow
from capabilities.release_package.manifest import push_workflow as release_push_workflow
from capabilities.release_package.manifest import release_workflow as release_run_workflow
from capabilities.team_tickets.manifest import preview_skill as team_tickets_preview_skill
from capabilities.team_tickets.manifest import preview_workflow as team_tickets_preview_workflow
from capabilities.weekly_report.manifest import weekly_report_workflow, weekly_skill
from common.assets import WorkflowManifest
from host_runtime.workspace import write_atomically


def shipped() -> tuple[SkillManifest | WorkflowManifest, ...]:
    """Every manifest every installation gets, Skills and Workflows alike.

    The owner's personal Workflows are not among them (`personal()`)."""
    return (
        chipset_preview_skill(),
        chipset_preview_workflow(),
        chipset_report_workflow(),
        release_preview_skill(),
        release_preview_workflow(),
        release_isolated_apply_workflow(),
        release_prepare_workflow(),
        release_commit_workflow(),
        release_push_workflow(),
        release_run_workflow(),
        ncc_plan_skill(),
        ncc_plan_workflow(),
        team_tickets_preview_skill(),
        workflow_author_skill(),
        knowledge_skill(),
        market_alignment_skill(),
        personal_proof_skill(),
        team_tickets_preview_workflow(),
        personal_proof_workflow(),
        coding_skill(),
        coding_workflow(),
        run_python_workflow(),
    )


#: Set to 1 on the owner's own computer so install and upgrade bring his
#: personal Workflows too.
INCLUDE_PERSONAL_VARIABLE = "AEP_INCLUDE_PERSONAL_ASSETS"


def personal() -> tuple[SkillManifest | WorkflowManifest, ...]:
    """The owner's personal Skill and Workflow: never bundled or shared."""
    return (weekly_skill(), weekly_report_workflow())


def include_personal_requested(environment: Mapping[str, str] | None = None) -> bool:
    """Whether this computer asks for the personal set (`INCLUDE_PERSONAL_VARIABLE`)."""
    value = (os.environ if environment is None else environment).get(INCLUDE_PERSONAL_VARIABLE, "")
    return value.strip().lower() in ("1", "true", "yes", "on")


def manifests(*, include_personal: bool = False) -> tuple[SkillManifest | WorkflowManifest, ...]:
    """`shipped()`, plus `personal()` when asked for."""
    return shipped() + (personal() if include_personal else ())


def export_assets(directory: Path, *, include_personal: bool = False) -> tuple[Path, ...]:
    """Write the shipped manifests (and, when asked, the personal ones) as
    `skills/` and `workflows/` under `directory`, named as a sync would
    name them."""
    written: list[Path] = []
    for manifest in manifests(include_personal=include_personal):
        folder = "skills" if isinstance(manifest, SkillManifest) else "workflows"
        identity = manifest.metadata.identity
        path = (
            directory / folder / f"{identity.namespace}__{identity.name}__{identity.version}.json"
        )
        payload = json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False)
        write_atomically(path, payload.encode("utf-8") + b"\n")
        written.append(path)
    return tuple(written)
