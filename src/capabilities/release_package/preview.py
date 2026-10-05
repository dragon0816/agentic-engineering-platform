"""Read-only Workflow 13 preview over a branch already checked out locally."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from capabilities.release_package.contracts import (
    ReleasePreview,
    ReleasePreviewRequest,
    ReleasePreviewSettings,
    ReleasePreviewStepInput,
    ReleaseSelectedFile,
)
from capabilities.release_package.planning import (
    ReleaseSettings,
    ReleaseValidationError,
    branch_name,
    plan_release,
)
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext


class ReleasePreviewError(Exception):
    """Stable refusal code; paths and customer material never enter the run trace."""


def _checked_out_branch(checkout: Path) -> str:
    git_dir = checkout / ".git"
    head = git_dir / "HEAD"
    if not git_dir.is_dir() or git_dir.is_symlink() or not head.is_file():
        raise ReleasePreviewError("checkout_missing")
    if not head.resolve().is_relative_to(checkout):
        raise ReleasePreviewError("checkout_unreadable")
    try:
        value = head.read_text(encoding="utf-8").strip()
    except OSError:
        raise ReleasePreviewError("checkout_unreadable") from None
    prefix = "ref: refs/heads/"
    if not value.startswith(prefix):
        raise ReleasePreviewError("detached_checkout")
    return value[len(prefix):]


def _changed(checkout: Path, relative: str, content: bytes) -> bool:
    path = checkout / relative
    if path.is_symlink() or not path.resolve().is_relative_to(checkout):
        raise ReleasePreviewError("checkout_unreadable")
    try:
        return not path.is_file() or path.read_bytes() != content
    except OSError:
        raise ReleasePreviewError("checkout_unreadable") from None


def build_preview(
    settings: ReleasePreviewSettings,
    request: ReleasePreviewRequest,
) -> ReleasePreview:
    """Project package contents from the checked-out branch without writing."""
    settings = ReleasePreviewSettings.model_validate(settings)
    request = ReleasePreviewRequest.model_validate(request)
    checkout = Path(settings.checkout_path).resolve()
    if not checkout.is_dir():
        raise ReleasePreviewError("checkout_missing")
    try:
        wanted_branch = branch_name(request.company_name, request.chipset_id, request.info)
    except ReleaseValidationError:
        raise ReleasePreviewError("invalid_release_input") from None
    if _checked_out_branch(checkout) != wanted_branch:
        raise ReleasePreviewError("wrong_branch")
    current = checkout / "release.yaml"
    if current.is_symlink() or not current.resolve().is_relative_to(checkout):
        raise ReleasePreviewError("checkout_unreadable")
    try:
        current_yaml = current.read_text(encoding="utf-8-sig") if current.exists() else None
    except (OSError, UnicodeError):
        raise ReleasePreviewError("checkout_unreadable") from None
    try:
        plan = plan_release(
            request.to_release_request(),
            ReleaseSettings(inbox=Path(settings.inbox_path)),
            previous_release_yaml=current_yaml,
        )
        intended = {
            "requirements.txt": ("\n".join(plan.requirements) + "\n").encode("utf-8"),
            "release.yaml": plan.release_yaml.encode("utf-8"),
        }
        for selected in plan.selected_files:
            source_path = Path(settings.inbox_path) / selected.name
            content = source_path.read_bytes()
            if hashlib.sha256(content).hexdigest() != selected.sha256:
                raise ReleasePreviewError("inbox_changed")
            intended[selected.destination] = content
    except (ReleaseValidationError, OSError):
        raise ReleasePreviewError("invalid_release_input") from None
    changed = tuple(
        relative for relative, content in intended.items() if _changed(checkout, relative, content)
    )
    return ReleasePreview(
        branch=plan.branch,
        previous_version=plan.previous_version,
        release_version=plan.release_version,
        requirements=plan.requirements,
        release_yaml=plan.release_yaml,
        selected_files=tuple(
            ReleaseSelectedFile(
                kind=item.kind,
                name=item.name,
                destination=item.destination,
                sha256=item.sha256,
            )
            for item in plan.selected_files
        ),
        changed_paths=changed,
        source_revision=plan.source_revision,
    )


class ReleasePreviewHandler:
    """Settings arrive with each run from this install's Workflow settings."""

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        step = ReleasePreviewStepInput.model_validate(inputs)
        try:
            settings = step.settings()
        except ValueError:
            raise CapabilityRefused("release_settings_invalid") from None
        try:
            return await asyncio.to_thread(build_preview, settings, step.request)
        except ReleasePreviewError as error:
            raise CapabilityRefused(str(error)) from None
