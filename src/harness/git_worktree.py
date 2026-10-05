"""A detached git worktree per coding run: the change never touches the
repository's own checkout, is never committed, and stays for the owner to
review (`docs/phases/CODING_ON_BRIDGE.md`)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from harness.workspace import WorkspaceRefused


@dataclass(frozen=True)
class RunWorkspace:
    run_dir: Path
    worktree: Path
    head: str


def _git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=False,
    )
    if result.returncode != 0:
        raise WorkspaceRefused("git_failed")
    return result.stdout


def create(repository: Path, root: Path, run_id: str) -> RunWorkspace:
    """Check out the repository's HEAD, detached, under `root/run_id`."""
    if not (repository / ".git").exists():
        raise WorkspaceRefused("repository_not_git")
    run_dir = root / run_id
    if run_dir.exists():
        raise WorkspaceRefused("run_folder_exists")
    run_dir.mkdir(parents=True)
    worktree = run_dir / "worktree"
    head = _git("rev-parse", "HEAD", cwd=repository).strip()
    _git("worktree", "add", "--detach", str(worktree), head, cwd=repository)
    return RunWorkspace(run_dir=run_dir, worktree=worktree, head=head)


def diff(worktree: Path) -> str:
    """Everything changed against HEAD, new files included."""
    _git("add", "--all", "--intent-to-add", cwd=worktree)
    return _git("diff", "HEAD", cwd=worktree)


def remove(repository: Path, worktree: Path) -> None:
    _git("worktree", "remove", "--force", str(worktree), cwd=repository)
