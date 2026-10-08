"""Workflow 13's release run up to the commit (owner 2026-10-08).

Ported from `host-bridge/jobs/release_package.py` at rs_workflow_system@896046e8,
PRESERVE + ADAPT. The source does resolve, checkout, write, commit, push in one
job. Here the work is split into two capabilities, each a separate approved run:

- `prepare` resolves the chipset version, clones or fetches the release
  repository, checks out the branch (or creates it from the template), writes
  requirements.txt, the selected inputs and release.yaml, and reports what a
  commit would contain, with the source's plain-language dry-run plan. It never
  commits. It records what it prepared in the checkout's `.git`.
- `commit` commits exactly what `prepare` left. If the branch, HEAD or any changed
  file differs from that record, it refuses.

Push is deliberately absent in this round. The settings accept only a release
repository that is a local path inside an explicitly marked isolated root, so
neither capability can reach the real GitLab yet.

Git runs as a fixed argument list with no shell, inside the configured work
root, and never prompts. The source ran it through the Bridge's PowerShell
terminal. The commit message keeps the source's quoting rule (`_quote_for_git`)
so both produce the same text.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Self

from pydantic import Field, StrictBool, model_validator

from capabilities.release_package.apply_isolated import ISOLATED_MARKER, ISOLATED_MARKER_VALUE
from capabilities.release_package.contracts import ReleasePreviewRequest
from capabilities.release_package.planning import (
    DEFAULT_INCLUDE,
    ReleaseRequest,
    ReleaseSettings,
    ReleaseValidationError,
    branch_name,
    plan_release,
)
from capabilities.release_package.status import dry_run_plan, parse_status
from capabilities.release_package.versions import (
    VersionLookupError,
    lookup_published_version,
    lookup_readiness_version,
)
from capabilities.runtime import CapabilityRefused
from common.assets import reject_embedded_secrets
from common.base import Contract, Text
from common.execution import RequestContext

PREPARED_RECORD = "aep-w13-prepared.json"
LOCK_NAME = "aep-w13.lock"
GIT_TIMEOUT_SECONDS = 600
SOURCE_REVISION = "rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43"

LogFn = Callable[[str], None]


class ReleaseRunError(Exception):
    """A refusal; the message is safe to show (no secrets, no file content)."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


# -- settings ----------------------------------------------------------------


class ReleaseRunSettings(Contract):
    """This install's paths. Until push is approved, everything must live in
    an isolated root that carries the AEP marker, origin included."""

    release_repo_url: Text
    template_branch: Text = "template"
    work_root: Text
    inbox_path: Text
    allowed_root: Text
    artifactory_base_url: str = ""
    readiness_base_url: str = ""

    @model_validator(mode="after")
    def no_secrets(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self

    def checked(self) -> tuple[Path, Path, Path, Path]:
        """Root, work root, inbox and the local origin, or a refusal."""
        root = Path(self.allowed_root)
        if not root.is_absolute():
            raise ReleaseRunError("settings_invalid", "allowed_root must be absolute")
        root = root.resolve()
        marker = root / ISOLATED_MARKER
        try:
            if marker.is_symlink() or marker.read_text(encoding="utf-8") != ISOLATED_MARKER_VALUE:
                raise ReleaseRunError("isolated_root_unmarked")
        except OSError:
            raise ReleaseRunError("isolated_root_unmarked") from None
        if re.match(r"^[a-z][a-z0-9+.-]*://", self.release_repo_url, re.IGNORECASE) or (
                "@" in self.release_repo_url and ":" in self.release_repo_url.split("@", 1)[1]):
            raise ReleaseRunError(
                "remote_not_isolated",
                "this release run only uses a local repository inside the isolated root; "
                "a GitLab remote comes with the push step")
        origin = Path(self.release_repo_url)
        work = Path(self.work_root)
        inbox = Path(self.inbox_path)
        for path in (origin, work, inbox):
            if not path.is_absolute() or not path.resolve().is_relative_to(root):
                raise ReleaseRunError("path_outside_isolated_root")
        return root, work.resolve(), inbox.resolve(), origin.resolve()


# -- git -----------------------------------------------------------------------


class Git:
    """`git` with an argument list, inside the work root, never prompting."""

    def __init__(self, root: Path, timeout: float = GIT_TIMEOUT_SECONDS) -> None:
        self.root = root
        self.timeout = timeout

    def __call__(self, *args: str, cwd: Path, check: bool = True) -> str:
        if not cwd.resolve().is_relative_to(self.root):
            raise ReleaseRunError("git_outside_work_root")
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
        try:
            done = subprocess.run(
                ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=self.timeout, env=env, stdin=subprocess.DEVNULL)
        except FileNotFoundError:
            raise ReleaseRunError("git_unavailable") from None
        except subprocess.TimeoutExpired:
            raise ReleaseRunError("git_timeout", f"git {args[0]} timed out") from None
        if check and done.returncode != 0:
            detail = (done.stderr or done.stdout or "").strip()[:300]
            raise ReleaseRunError("git_failed",
                                  f"git {args[0]} failed (exit {done.returncode}): {detail}")
        return done.stdout


def _repo_dir(work_root: Path, repo_url: str) -> Path:
    """Where the source clones a repository: its last path part, without .git."""
    name = repo_url.rstrip("/\\").replace("\\", "/").rsplit("/", 1)[-1]
    return work_root / name.removesuffix(".git")


def ensure_working_copy(git: Git, work_root: Path, repo_url: str, log: LogFn) -> Path:
    repo_dir = _repo_dir(work_root, repo_url)
    if (repo_dir / ".git").is_dir():
        log(f"working copy exists: {repo_dir}")
        git("fetch", "--prune", "origin", cwd=repo_dir)
        return repo_dir
    work_root.mkdir(parents=True, exist_ok=True)
    log(f"cloning {repo_url} into {repo_dir}")
    git("clone", repo_url, repo_dir.name, cwd=work_root)
    return repo_dir


def checkout_branch(git: Git, repo_dir: Path, branch: str, template: str, log: LogFn) -> str:
    if git("ls-remote", "--heads", "origin", branch, cwd=repo_dir).strip():
        log(f"branch {branch} exists; updating it")
        git("checkout", branch, cwd=repo_dir)
        git("reset", "--hard", f"origin/{branch}", cwd=repo_dir)
        return "existing"
    if not git("ls-remote", "--heads", "origin", template, cwd=repo_dir).strip():
        raise ReleaseRunError(
            "template_missing",
            f"neither {branch} nor the template branch {template} exists on origin. "
            "Check the template branch in this Workflow's settings.")
    log(f"branch {branch} does not exist; creating it from {template}")
    git("checkout", "-B", branch, f"origin/{template}", cwd=repo_dir)
    return "created"


@contextmanager
def checkout_lock(repo_dir: Path) -> Iterator[None]:
    """One release run per working copy at a time, as the source's Bridge
    serialized jobs. A lock left by a crashed run is removed by hand after
    looking at the checkout: never retried automatically."""
    lock = repo_dir / ".git" / LOCK_NAME
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ReleaseRunError("checkout_busy",
                              "another release run is using this working copy") from None
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def quote_for_git(text: str) -> str:
    """The source's `_quote_for_git`, kept so both commit messages agree."""
    cleaned = (text or "").replace("`", "'").replace('"', "'")
    return " ".join(cleaned.split())[:500]


def _changed(git: Git, repo_dir: Path) -> list[str]:
    status = git("status", "--porcelain", cwd=repo_dir)
    return [line for line in status.splitlines() if line.strip()]


def fingerprint(git: Git, repo_dir: Path, branch: str) -> str:
    """The branch, HEAD and every changed file's bytes: what a commit would take."""
    digest = hashlib.sha256()
    head = git("rev-parse", "HEAD", cwd=repo_dir).strip()
    digest.update(f"{branch}\n{head}\n".encode())
    listed = git("status", "--porcelain", "-uall", "-z", cwd=repo_dir)
    for entry in sorted(item for item in listed.split("\0") if item):
        digest.update(entry.encode("utf-8"))
        path = repo_dir / entry[3:]
        if path.is_file() and not path.is_symlink():
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _current_branch(git: Git, repo_dir: Path) -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_dir).strip()


# -- contracts -----------------------------------------------------------------


class ReleaseRunRequest(ReleasePreviewRequest):
    """The source's run values; chipsetVersion may be empty (looked up)."""

    chipset_version: str = Field(default="", alias="chipsetVersion")
    upload_set_id: str = Field(default="", alias="uploadSetId")
    dry_run: StrictBool = Field(default=False, alias="dryRun")


class PrepareStepInput(Contract):
    request: ReleaseRunRequest
    release_repo_url: Text
    template_branch: Text = "template"
    work_root: Text
    inbox_path: Text
    allowed_root: Text
    artifactory_base_url: str = ""
    readiness_base_url: str = ""

    def settings(self) -> ReleaseRunSettings:
        return ReleaseRunSettings.model_validate(
            self.model_dump(exclude={"request"}))


class PreparedRelease(Contract):
    branch: Text
    branch_state: Text
    repo_dir: Text
    chipset_version: Text
    chipset_version_source: Text
    previous_version: str | None
    release_version: Text
    requirements: tuple[Text, Text]
    placed: tuple[dict[str, str], ...]
    changed_files: int
    changes: tuple[tuple[str, int], ...]
    plan: tuple[str, ...]
    subject: Text
    notes: str
    fingerprint: Text
    dry_run: StrictBool
    committed: StrictBool = False
    pushed: StrictBool = False
    source_revision: Text = SOURCE_REVISION


class CommitStepInput(Contract):
    """What the person reviewed: the branch and the fingerprint `prepare` showed."""

    branch: Text
    fingerprint: Text = Field(min_length=12)
    release_repo_url: Text
    template_branch: Text = "template"
    work_root: Text
    inbox_path: Text
    allowed_root: Text
    artifactory_base_url: str = ""
    readiness_base_url: str = ""

    def settings(self) -> ReleaseRunSettings:
        return ReleaseRunSettings.model_validate(
            self.model_dump(exclude={"branch", "fingerprint"}))


class CommitResult(Contract):
    branch: Text
    committed: StrictBool
    commit: str = ""
    skipped: str = ""
    files: int = 0
    pushed: StrictBool = False


# -- the two steps ---------------------------------------------------------------


def _resolve(request: ReleaseRunRequest, settings: ReleaseRunSettings,
             log: LogFn, fetch: Callable[..., tuple[int, str]] | None) -> tuple[str, str]:
    given = request.chipset_version.strip()
    if given:
        return given, "given"
    extra = {} if fetch is None else {"fetch": fetch}
    found = lookup_published_version(request.chipset_id, settings.artifactory_base_url,
                                     os.environ.get("ARTIFACTORY_TOKEN", ""), log, **extra)
    if found:
        return found, "published index"
    try:
        return (lookup_readiness_version(request.chipset_id, settings.readiness_base_url,
                                         os.environ.get("OPS_TOKEN", ""), log, **extra),
                "readiness table")
    except VersionLookupError as error:
        raise ReleaseRunError("chipset_version_unknown", str(error)) from None


def prepare_release(
    settings: ReleaseRunSettings, request: ReleaseRunRequest, *, log: LogFn = lambda _: None,
    fetch: Callable[..., tuple[int, str]] | None = None,
) -> PreparedRelease:
    root, work_root, inbox, origin = settings.checked()
    if request.upload_set_id:
        # The source fetched upload sets from its own ops dashboard; on AEP the
        # files arrive as attachments. Until that is wired, name inbox files.
        raise ReleaseRunError("upload_sets_not_supported",
                              "name files in the inbox; upload sets are not wired on AEP yet")
    try:
        branch = branch_name(request.company_name, request.chipset_id, request.info)
    except ReleaseValidationError as error:
        raise ReleaseRunError("invalid_release_input", str(error)) from None
    chipset_version, source = _resolve(request, settings, log, fetch)
    git = Git(root)
    repo_dir = ensure_working_copy(git, work_root, str(origin), log)
    with checkout_lock(repo_dir):
        branch_state = checkout_branch(git, repo_dir, branch, settings.template_branch, log)
        release_path = repo_dir / "release.yaml"
        previous_text = (release_path.read_text(encoding="utf-8-sig")
                         if release_path.exists() else None)
        try:
            plan = plan_release(
                ReleaseRequest(**{**request.to_release_request().__dict__,
                                  "chipset_version": chipset_version}),
                ReleaseSettings(inbox=inbox, include=DEFAULT_INCLUDE),
                previous_release_yaml=previous_text,
            )
        except ReleaseValidationError as error:
            raise ReleaseRunError("invalid_release_input", str(error)) from None
        # Written as the source writes them: text mode for the two generated
        # files (so line endings match on the same machine), copy2 for inputs.
        (repo_dir / "requirements.txt").write_text(
            "\n".join(plan.requirements) + "\n", encoding="utf-8")
        placed = []
        for item in plan.selected_files:
            target = repo_dir / item.destination
            if not target.resolve().is_relative_to(repo_dir.resolve()):
                raise ReleaseRunError("invalid_release_input")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(inbox / item.name, target)
            placed.append({"kind": item.kind, "file": item.name,
                           "dest": item.destination.split("/", 1)[0]})
            log(item.destination)
        release_path.write_text(plan.release_yaml, encoding="utf-8")
        changed = _changed(git, repo_dir)
        lines = dry_run_plan(
            company=request.company_name, chipset=request.chipset_id,
            chipset_version=chipset_version, branch=branch, branch_state=branch_state,
            template=settings.template_branch, release_version=plan.release_version,
            previous_version=plan.previous_version or "",
            testcase=request.general_testcase_version, changed=changed,
            project_path="", will_push=False)
        subject = (f"Release {request.company_name} {request.chipset_id} {chipset_version} "
                   f"v{plan.release_version} (general-testcase "
                   f"{request.general_testcase_version})")
        prepared = PreparedRelease(
            branch=branch, branch_state=branch_state, repo_dir=str(repo_dir),
            chipset_version=chipset_version, chipset_version_source=source,
            previous_version=plan.previous_version, release_version=plan.release_version,
            requirements=plan.requirements, placed=tuple(placed), changed_files=len(changed),
            changes=tuple(parse_status(changed)), plan=tuple(lines), subject=subject,
            notes=request.notes.strip(), fingerprint=fingerprint(git, repo_dir, branch),
            dry_run=request.dry_run,
        )
        (repo_dir / ".git" / PREPARED_RECORD).write_text(
            prepared.model_dump_json(indent=2), encoding="utf-8")
    return prepared


def commit_release(
    settings: ReleaseRunSettings, branch: str, fingerprint_shown: str, *,
    log: LogFn = lambda _: None,
) -> CommitResult:
    """Commit what `prepare` left, if it is still exactly what was reviewed."""
    root, work_root, _, origin = settings.checked()
    repo_dir = _repo_dir(work_root, str(origin))
    prepared = recorded_prepare(repo_dir)
    if prepared is None:
        raise ReleaseRunError("not_prepared", "prepare this release first")
    if prepared.branch != branch or not prepared.fingerprint.startswith(
            fingerprint_shown.strip().lower()):
        raise ReleaseRunError("stale_prepare",
                              "this is not the release that was last prepared; prepare and "
                              "review it again")
    if prepared.dry_run:
        return CommitResult(branch=prepared.branch, committed=False,
                            skipped=f"dry run; {prepared.changed_files} file(s) would be "
                                    "committed")
    if prepared.changed_files == 0:
        return CommitResult(branch=prepared.branch, committed=False, skipped="nothing changed")
    git = Git(root)
    with checkout_lock(repo_dir):
        record = repo_dir / ".git" / PREPARED_RECORD
        if _current_branch(git, repo_dir) != prepared.branch or fingerprint(
                git, repo_dir, prepared.branch) != prepared.fingerprint:
            raise ReleaseRunError("checkout_changed",
                                  "the working copy changed after it was prepared; prepare again")
        files = len(_changed(git, repo_dir))
        git("add", "-A", cwd=repo_dir)
        args = ["commit", "-m", quote_for_git(prepared.subject)]
        if prepared.notes:
            args += ["-m", quote_for_git(prepared.notes)]
        git(*args, cwd=repo_dir)
        commit = git("rev-parse", "HEAD", cwd=repo_dir).strip()
        record.unlink(missing_ok=True)
        log(f"committed: {prepared.subject}")
    return CommitResult(branch=prepared.branch, committed=True, commit=commit, files=files)


# -- Bridge handlers --------------------------------------------------------------


def _refused(error: ReleaseRunError) -> CapabilityRefused:
    return CapabilityRefused(error.code)


class PrepareHandler:
    def __init__(self, fetch: Callable[..., tuple[int, str]] | None = None) -> None:
        self.fetch = fetch

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        step = PrepareStepInput.model_validate(inputs)
        try:
            settings = step.settings()
        except ValueError:
            raise CapabilityRefused("release_settings_invalid") from None
        try:
            return await asyncio.to_thread(prepare_release, settings, step.request,
                                           fetch=self.fetch)
        except ReleaseRunError as error:
            raise _refused(error) from None


class CommitHandler:
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        step = CommitStepInput.model_validate(inputs)
        try:
            settings = step.settings()
        except ValueError:
            raise CapabilityRefused("release_settings_invalid") from None
        try:
            return await asyncio.to_thread(commit_release, settings, step.branch,
                                           step.fingerprint)
        except ReleaseRunError as error:
            raise _refused(error) from None


def recorded_prepare(repo_dir: Path) -> PreparedRelease | None:
    try:
        return PreparedRelease.model_validate_json(
            (repo_dir / ".git" / PREPARED_RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

