"""Pure, source-derived preparation contract for Workflow 13.

This slice plans a release from explicit versions and local inbox names. Git,
published-version lookup, upload transfer, commit and push belong to separate
Bridge capabilities and are deliberately absent here.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import release_yaml as ry

DEST_DIRS = {
    "testPlans": "testplans",
    "configurations": "configurations",
    "overlays": "overlay",
}
SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
#: Extensions an uploaded file of each kind may have (None: any).
UPLOAD_SUFFIXES: dict[str, frozenset[str] | None] = {
    "testPlans": frozenset({".json"}),
    "configurations": frozenset({".yaml", ".yml"}),
    "overlays": None,
}
DEFAULT_INCLUDE = (
    "rswmt/**/*",
    "overlay/**/*",
    "testplans/**/*",
    "configurations/**/*",
)


class ReleaseValidationError(ValueError):
    """A release cannot be planned without guessing or crossing the inbox boundary."""


@dataclass(frozen=True)
class ReleaseRequest:
    company_name: str
    chipset_id: str
    cmp_kt_option: str
    chipset_version: str
    general_testcase_version: str
    info: str = ""
    release_version: str = ""
    suffix: str = ""
    notes: str = ""
    test_plans: tuple[str, ...] = ()
    configurations: tuple[str, ...] = ()
    overlays: tuple[str, ...] = ()
    upload_set_id: str = ""
    # Files uploaded for this run (forms v2): (kind, absolute path), already
    # confined to the host's upload store by the caller.
    uploaded: tuple[tuple[str, Path], ...] = field(default=())


@dataclass(frozen=True)
class ReleaseSettings:
    inbox: Path
    include: tuple[str, ...] = DEFAULT_INCLUDE
    os_name: str = "win"
    py: str = "3.13"
    arch: str = "64"
    docs: bool = False


@dataclass(frozen=True)
class SelectedFile:
    kind: str
    name: str
    destination: str
    sha256: str
    # Where an uploaded file is read from; empty for an inbox file.
    source: str = ""


@dataclass(frozen=True)
class ReleasePlan:
    branch: str
    previous_version: str | None
    source_release_present: bool
    source_release_sha256: str
    release_version: str
    requirements: tuple[str, str]
    release_yaml: str
    selected_files: tuple[SelectedFile, ...]
    source_revision: str = "rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43"


def branch_name(company: str, chipset: str, info: str = "") -> str:
    """Preserve the source's `[company]_[chipset]_[info]` spelling and guard."""
    parts = [company.strip(), chipset.strip()]
    if info.strip():
        parts.append(info.strip())
    cleaned = []
    for part in parts:
        part = re.sub(r"\s+", "-", part)
        if not SAFE_SEGMENT.fullmatch(part):
            raise ReleaseValidationError(
                f"{part!r} cannot be part of a branch name. Use letters, digits, "
                "dot, dash or underscore, starting with a letter or digit."
            )
        cleaned.append(part)
    return "_".join(cleaned)


def _selected_file(inbox: Path, kind: str, name: str) -> SelectedFile:
    # The source admits names in a configured inbox, never arbitrary paths.
    # Check Windows separators explicitly so this behaves the same on CI/Linux.
    if not name or name in {".", ".."} or "/" in name or "\\" in name or ":" in name:
        raise ReleaseValidationError(f"{name!r} is not a bare inbox file name")
    root = inbox.resolve()
    file_path = (root / name).resolve()
    if not file_path.is_relative_to(root) or not file_path.is_file():
        raise ReleaseValidationError(f"{name!r} is not a file in the configured inbox")
    digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
    return SelectedFile(kind, name, f"{DEST_DIRS[kind]}/{name}", digest)


def _uploaded_file(kind: str, path: Path) -> SelectedFile:
    name = path.name
    if not name or name in {".", ".."} or not path.is_file():
        raise ReleaseValidationError(f"{name!r} is not an uploaded file")
    allowed = UPLOAD_SUFFIXES[kind]
    if allowed is not None and path.suffix.lower() not in allowed:
        raise ReleaseValidationError(f"{name!r} is not a {', '.join(sorted(allowed))} file")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return SelectedFile(kind, name, f"{DEST_DIRS[kind]}/{name}", digest, str(path))


def plan_release(
    request: ReleaseRequest,
    settings: ReleaseSettings,
    *,
    previous_release_yaml: str | None = None,
) -> ReleasePlan:
    """Validate inputs and project source-compatible files without writing them.

    `chipset_version` must be supplied until the published-index/readiness lookup
    is wired through a read capability. Upload sets likewise need the governed
    transfer capability; this planner never fetches or deletes one.
    """
    for label, value in (
        ("company_name", request.company_name),
        ("chipset_id", request.chipset_id),
        ("cmp_kt_option", request.cmp_kt_option),
        ("general_testcase_version", request.general_testcase_version),
        ("chipset_version", request.chipset_version),
    ):
        if not value.strip():
            raise ReleaseValidationError(f"{label} is required")

    named = {
        "testPlans": request.test_plans,
        "configurations": request.configurations,
        "overlays": request.overlays,
    }
    if request.upload_set_id and any(named.values()):
        raise ReleaseValidationError("both uploadSetId and file names were given")
    if request.upload_set_id:
        raise ReleaseValidationError("uploadSetId needs the governed upload transfer capability")

    branch = branch_name(request.company_name, request.chipset_id, request.info)
    previous = ry.parse_version(previous_release_yaml or "")
    try:
        version = request.release_version.strip() or ry.next_version(previous)
        requirements = tuple(ry.requirements_lines(
            request.chipset_id,
            request.chipset_version,
            request.general_testcase_version,
        ))
        release_yaml = ry.render(
            chipset_id=request.chipset_id,
            branch_name=branch,
            customer_name=request.company_name,
            version=version,
            include=settings.include,
            cmp_option=request.cmp_kt_option,
            suffix=request.suffix,
            notes=request.notes,
            os_name=settings.os_name,
            py=settings.py,
            arch=settings.arch,
            docs=settings.docs,
        )
    except ry.ReleaseYamlError as exc:
        raise ReleaseValidationError(str(exc)) from exc
    selected = tuple(
        _selected_file(settings.inbox, kind, name)
        for kind, names in named.items()
        for name in names
    ) + tuple(_uploaded_file(kind, path) for kind, path in request.uploaded)
    destinations = [item.destination for item in selected]
    for destination in destinations:
        if destinations.count(destination) > 1:
            raise ReleaseValidationError(
                f"two chosen files would both be written to {destination}")
    return ReleasePlan(
        branch=branch,
        previous_version=previous,
        source_release_present=previous_release_yaml is not None,
        source_release_sha256=hashlib.sha256(
            (previous_release_yaml or "").encode("utf-8")
        ).hexdigest(),
        release_version=version,
        requirements=(requirements[0], requirements[1]),
        release_yaml=release_yaml,
        selected_files=selected,
    )
