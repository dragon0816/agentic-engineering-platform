"""Guarded Workflow 13 file preparation for an isolated checkout only.

This covers the source job's deterministic write step. It cannot clone, fetch,
commit or push; the corresponding production Bridge/Git steps are not wired.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from capabilities.release_package.contracts import (
    IsolatedApplyOutput,
    IsolatedApplySettings,
    IsolatedApplyStepInput,
    ReleasePreviewRequest,
    ReleaseSelectedFile,
)
from capabilities.release_package.local_dry_run import prepare_dry_run
from capabilities.release_package.planning import (
    ReleasePlan,
    ReleaseSettings,
    ReleaseValidationError,
    plan_release,
)
from capabilities.release_package.preview import ReleasePreviewError, _checked_out_branch
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext

ISOLATED_MARKER = ".aep-isolated-release-root"
ISOLATED_MARKER_VALUE = "AEP_ISOLATED_RELEASE_ROOT_V1\n"
_REMOTE_SECTION = re.compile(r'^\s*\[remote\s+"', re.IGNORECASE | re.MULTILINE)


class IsolatedApplyError(Exception):
    """Stable refusal code with no input path or customer content."""


def _guard_checkout(settings: IsolatedApplySettings) -> tuple[Path, Path, Path]:
    root = Path(settings.allowed_root).resolve()
    marker = root / ISOLATED_MARKER
    try:
        if marker.is_symlink() or marker.read_text(encoding="utf-8") != ISOLATED_MARKER_VALUE:
            raise IsolatedApplyError("isolated_root_unmarked")
    except OSError:
        raise IsolatedApplyError("isolated_root_unmarked") from None
    repo = Path(settings.checkout_path).resolve()
    git_dir = repo / ".git"
    if (
        repo == root
        or not repo.is_relative_to(root)
        or not git_dir.is_dir()
        or git_dir.is_symlink()
    ):
        raise IsolatedApplyError("checkout_not_isolated")
    config = git_dir / "config"
    try:
        if config.is_symlink() or _REMOTE_SECTION.search(config.read_text(encoding="utf-8")):
            raise IsolatedApplyError("remote_configured")
    except OSError:
        raise IsolatedApplyError("checkout_unreadable") from None
    return root, repo, git_dir


@contextmanager
def _checkout_lock(git_dir: Path) -> Iterator[None]:
    lock = git_dir / "aep-w13-apply.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise IsolatedApplyError("checkout_busy") from None
    except OSError:
        raise IsolatedApplyError("checkout_lock_unavailable") from None
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def _current_release(repo: Path) -> str | None:
    path = repo / "release.yaml"
    if path.is_symlink() or not path.resolve().is_relative_to(repo):
        raise IsolatedApplyError("checkout_unreadable")
    try:
        return path.read_text(encoding="utf-8-sig") if path.exists() else None
    except (OSError, UnicodeError):
        raise IsolatedApplyError("checkout_unreadable") from None


def apply_isolated(
    plan: ReleasePlan,
    *,
    settings: IsolatedApplySettings,
) -> IsolatedApplyOutput:
    """Apply a previously reviewed plan without Git, commit, push or network.

    The marker and absence of a configured remote keep this function confined
    to an intentionally isolated test checkout. A stale plan is refused before
    any release file is written.
    """
    settings = IsolatedApplySettings.model_validate(settings)
    root, repo, git_dir = _guard_checkout(settings)
    with _checkout_lock(git_dir):
        try:
            if _checked_out_branch(repo) != plan.branch:
                raise IsolatedApplyError("wrong_branch")
        except ReleasePreviewError as error:
            raise IsolatedApplyError(str(error)) from None
        current = _current_release(repo)
        current_digest = hashlib.sha256((current or "").encode("utf-8")).hexdigest()
        if (current is not None) != plan.source_release_present or (
            current_digest != plan.source_release_sha256
        ):
            raise IsolatedApplyError("stale_plan")
        try:
            receipt = prepare_dry_run(
                plan,
                inbox=Path(settings.inbox_path),
                checkout=repo,
                allowed_root=root,
            )
        except (OSError, ReleaseValidationError):
            raise IsolatedApplyError("apply_refused") from None
    return IsolatedApplyOutput(
        branch=plan.branch,
        previous_version=plan.previous_version,
        release_version=plan.release_version,
        requirements=plan.requirements,
        changed_paths=receipt.changed,
        selected_files=tuple(
            ReleaseSelectedFile(
                kind=item.kind, name=item.name,
                destination=item.destination, sha256=item.sha256,
            )
            for item in plan.selected_files
        ),
        source_revision=plan.source_revision,
    )


def apply_request_isolated(
    settings: IsolatedApplySettings,
    request: ReleasePreviewRequest,
) -> IsolatedApplyOutput:
    """Plan from the branch as it exists now and apply under the same guard."""
    settings = IsolatedApplySettings.model_validate(settings)
    request = ReleasePreviewRequest.model_validate(request)
    _, repo, _ = _guard_checkout(settings)
    try:
        plan = plan_release(
            request.to_release_request(),
            ReleaseSettings(inbox=Path(settings.inbox_path)),
            previous_release_yaml=_current_release(repo),
        )
    except (OSError, ReleaseValidationError):
        raise IsolatedApplyError("invalid_release_input") from None
    return apply_isolated(plan, settings=settings)


class IsolatedApplyHandler:
    """Settings arrive with each run from this install's Workflow settings."""

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        step = IsolatedApplyStepInput.model_validate(inputs)
        try:
            settings = step.isolated_settings()
        except ValueError:
            raise CapabilityRefused("release_settings_invalid") from None
        try:
            return await asyncio.to_thread(apply_request_isolated, settings, step.request)
        except IsolatedApplyError as error:
            raise CapabilityRefused(str(error)) from None
