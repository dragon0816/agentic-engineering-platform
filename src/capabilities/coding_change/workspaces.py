"""Where coding, browser downloads and Workflow scripts may work.

One containment rule for every place that checks a task workspace: the
run-python handler at run time, Workflow drafting before anything runs, and
what the Agent is told (owner 2026-10-08, after a Workflow fixed a folder
outside `coding.workspace_roots` and failed only at its approved run).

A task folder under a root that does not exist yet is created (owner
2026-10-20): the Agent used to hand `coding_workspace_missing` to the person
and ask them to make the folder by hand. Outside the roots, or by a path with
`..`, nothing is created and the request is refused as before.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


def containing_root(raw: str, roots: Sequence[str]) -> Path | None:
    """The resolved workspace when it is an absolute path inside one of the
    roots (a root itself counts), otherwise None."""
    path = Path(raw.strip())
    if not path.is_absolute():
        return None
    resolved = path.resolve()
    for root in roots:
        if resolved.is_relative_to(Path(root).resolve()):
            return resolved
    return None


def has_traversal(raw: str) -> bool:
    """Whether a workspace path climbs with `..`: refused outright, even when
    it would resolve inside a root, so a folder is never made by a path that
    reads as somewhere else."""
    return ".." in Path(raw.strip()).parts


def create_workspace(resolved: Path) -> None:
    """Make a missing task folder, with input/ and output/ as every task
    folder has (the same layout `prepare_workspaces` gives a Workflow's fixed
    folder). The caller has already checked it lies under a root."""
    for part in ("input", "output"):
        (resolved / part).mkdir(parents=True, exist_ok=True)


def workspace_note(roots: Sequence[str]) -> str:
    """What the Agent is told, so it never suggests a folder that will be refused."""
    if not roots:
        return ""
    listed = "; ".join(roots)
    return (
        f"Suggested task folders: {listed}. These are defaults, not permission boundaries. "
        f"When no folder is supplied, choose a task-named folder under {roots[0]} "
        f"(for example {Path(roots[0]) / 'stock-price'}). Any absolute IT-accessible path "
        "is valid. Create missing input/output folders without asking the person to do it."
    )
