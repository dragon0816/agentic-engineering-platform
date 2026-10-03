"""Apply a Workflow 13 dry run to one explicitly isolated local checkout.

No Git command, commit, push or network call occurs here. The caller must
provide a trusted allowed root; the Host has not registered this as a Bridge
capability yet, so production execution still needs its policy integration.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .planning import DEST_DIRS, ReleasePlan, ReleaseValidationError


@dataclass(frozen=True)
class DryRunReceipt:
    checkout: Path
    changed: tuple[str, ...]
    committed: bool = False
    pushed: bool = False


def _target(checkout: Path, relative: str) -> Path:
    target = checkout / relative
    nested = target
    while nested != checkout:
        if nested.is_symlink():
            raise ReleaseValidationError(f"destination {relative!r} crosses a symlink")
        nested = nested.parent
    if not target.resolve().is_relative_to(checkout):
        raise ReleaseValidationError(f"destination {relative!r} escapes the checkout")
    return target


def prepare_dry_run(
    plan: ReleasePlan,
    *,
    inbox: Path,
    checkout: Path,
    allowed_root: Path,
) -> DryRunReceipt:
    """Write the source's package files locally, leaving Git untouched.

    All sources and destinations are validated before the first write. The
    caller is responsible for preparing/serializing the correct branch, as in
    the original Bridge job's separate checkout step.
    """
    root = allowed_root.resolve()
    repo = checkout.resolve()
    if not repo.is_relative_to(root) or not (repo / ".git").exists():
        raise ReleaseValidationError("checkout must be a Git working copy inside allowed_root")
    inbox_root = inbox.resolve()
    payloads: list[tuple[Path, bytes]] = [
        (_target(repo, "requirements.txt"), ("\n".join(plan.requirements) + "\n").encode()),
        (_target(repo, "release.yaml"), plan.release_yaml.encode("utf-8")),
    ]
    for selected in plan.selected_files:
        if (
            selected.kind not in DEST_DIRS
            or not selected.name
            or "/" in selected.name
            or "\\" in selected.name
            or selected.name in {".", ".."}
            or selected.destination != f"{DEST_DIRS[selected.kind]}/{selected.name}"
        ):
            raise ReleaseValidationError("planned destination is not a release input folder")
        source = (inbox_root / selected.name).resolve()
        if not source.is_relative_to(inbox_root) or not source.is_file():
            raise ReleaseValidationError(f"inbox file {selected.name!r} is no longer available")
        content = source.read_bytes()
        if hashlib.sha256(content).hexdigest() != selected.sha256:
            raise ReleaseValidationError(f"inbox file {selected.name!r} changed after planning")
        payloads.append((_target(repo, selected.destination), content))

    changed = tuple(
        path.relative_to(repo).as_posix()
        for path, content in payloads
        if not path.is_file() or path.read_bytes() != content
    )
    if any(path.exists() and not path.is_file() for path, _ in payloads):
        raise ReleaseValidationError("a planned destination is not a regular file")
    for path, content in payloads:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return DryRunReceipt(checkout=repo, changed=changed)
