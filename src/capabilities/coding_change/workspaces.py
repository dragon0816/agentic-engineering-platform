"""Where coding, browser downloads and Workflow scripts may work.

One containment rule for every place that checks a task workspace: the
run-python handler at run time, Workflow drafting before anything runs, and
what the Agent is told (owner 2026-10-08, after a Workflow fixed a folder
outside `coding.workspace_roots` and failed only at its approved run).
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


def workspace_note(roots: Sequence[str]) -> str:
    """What the Agent is told, so it never suggests a folder that will be refused."""
    if not roots:
        return ""
    listed = "; ".join(roots)
    return (
        "Task folders for coding/run-python, browser downloads and Workflow steps must be "
        f"folders under one of these roots: {listed}. When the person has not named one, "
        f"suggest a new folder under {roots[0]} named after the task (for example "
        f"{Path(roots[0]) / 'stock-price'}); never suggest a folder outside these roots."
    )
