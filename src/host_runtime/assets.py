"""Writing the shipped manifests where a workspace or a publisher reads them.

A host concern, beside the CLI: the manifests themselves are pure data in
the capability packages that ship them.
"""

import json
from pathlib import Path

from agent.skills import SkillManifest
from capabilities.weekly_report.manifest import (
    preview_workflow,
    report_workflow,
    weekly_skill,
)
from common.assets import WorkflowManifest
from host_runtime.workspace import write_atomically


def shipped() -> tuple[SkillManifest | WorkflowManifest, ...]:
    """Every manifest this package ships, Skills and Workflows alike."""
    return (weekly_skill(), preview_workflow(), report_workflow())


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
