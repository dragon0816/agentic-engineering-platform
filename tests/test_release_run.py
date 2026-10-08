"""Workflow 13's release run up to the commit (owner 2026-10-08).

Prepare and commit are separate approved runs. Commit takes only what was
prepared and reviewed. Push does not exist yet, and the settings refuse any
origin that is not a local repository in the marked isolated root.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

import pytest

from capabilities.release_package.apply_isolated import ISOLATED_MARKER, ISOLATED_MARKER_VALUE
from capabilities.release_package.manifest import (
    COMMIT_SPEC,
    PREPARE_SPEC,
    commit_workflow,
    prepare_workflow,
)
from capabilities.release_package.release_run import (
    LOCK_NAME,
    CommitHandler,
    PrepareHandler,
    ReleaseRunError,
    ReleaseRunRequest,
    ReleaseRunSettings,
    commit_release,
    prepare_release,
    quote_for_git,
)
from capabilities.release_package.versions import (
    lookup_published_version,
    newest_release,
    parse_simple_index,
)
from capabilities.runtime import CapabilityRefused
from common.execution import RequestContext, TraceIdentifiers


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout


@pytest.fixture(autouse=True)
def identity(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in (("GIT_AUTHOR_NAME", "AEP Test"), ("GIT_AUTHOR_EMAIL", "aep@example.test"),
                       ("GIT_COMMITTER_NAME", "AEP Test"),
                       ("GIT_COMMITTER_EMAIL", "aep@example.test")):
        monkeypatch.setenv(key, value)


def isolated(tmp_path: Path, *, existing_version: str | None = None) -> ReleaseRunSettings:
    """A marked root with a bare `origin` holding `template` (and maybe the branch)."""
    root = tmp_path / "iso"
    root.mkdir()
    (root / ISOLATED_MARKER).write_text(ISOLATED_MARKER_VALUE, encoding="utf-8")
    seed = root / "seed"
    seed.mkdir()
    git("init", "-q", "-b", "template", cwd=seed)
    (seed / "rswmt").mkdir()
    (seed / "rswmt" / "base.py").write_text("print('base')\n", encoding="utf-8")
    git("add", "-A", cwd=seed)
    git("commit", "-q", "-m", "template", cwd=seed)
    if existing_version is not None:
        git("checkout", "-q", "-b", "Foxconn_kt326", cwd=seed)
        (seed / "release.yaml").write_text(f"VERSION: {existing_version}\n", encoding="utf-8")
        git("add", "-A", cwd=seed)
        git("commit", "-q", "-m", "first release", cwd=seed)
    git("clone", "-q", "--bare", str(seed), str(root / "rs-wmt-sw-release.git"), cwd=root)
    inbox = root / "inbox"
    inbox.mkdir()
    (inbox / "plan.json").write_text('{"tests": [1]}', encoding="utf-8")
    return ReleaseRunSettings(
        release_repo_url=str(root / "rs-wmt-sw-release.git"), work_root=str(root / "work"),
        inbox_path=str(inbox), allowed_root=str(root))


def request(**extra: Any) -> ReleaseRunRequest:
    return ReleaseRunRequest.model_validate({
        "companyName": "Foxconn", "chipsetId": "kt326", "cmpKtOption": "KT161",
        "chipsetVersion": "2.0.17", "generalTestcaseVersion": "v3.0.17",
        "notes": 'fixed the "throughput" plan', "testPlans": ["plan.json"], **extra})


def test_a_new_branch_is_created_from_the_template_prepared_and_committed_locally(
    tmp_path: Path,
) -> None:
    settings = isolated(tmp_path)
    prepared = prepare_release(settings, request())
    repo = Path(prepared.repo_dir)
    assert prepared.branch == "Foxconn_kt326" and prepared.branch_state == "created"
    assert prepared.release_version == "0.0.1" and prepared.previous_version is None
    assert prepared.requirements == ("rs-wmt-kt326==2.0.17", "rs-wmt-general-testcase==3.0.17")
    assert (repo / "testplans" / "plan.json").read_text() == '{"tests": [1]}'
    assert dict(prepared.changes) == {"release.yaml": 1, "requirements.txt": 1, "test plans": 1}
    assert any("create the branch Foxconn_kt326 from template" in line for line in prepared.plan)
    assert git("log", "--oneline", cwd=repo).count("\n") == 1  # nothing committed yet

    done = commit_release(settings, "Foxconn_kt326", prepared.fingerprint[:16])
    assert done.committed and done.files == 3 and not done.pushed
    message = git("log", "-1", "--format=%B", cwd=repo)
    assert message.startswith(
        "Release Foxconn kt326 2.0.17 v0.0.1 (general-testcase v3.0.17)\n\n"
        "fixed the 'throughput' plan")
    assert git("ls-remote", "--heads", "origin", "Foxconn_kt326", cwd=repo) == ""  # not pushed


def test_an_existing_branch_continues_its_version(tmp_path: Path) -> None:
    settings = isolated(tmp_path, existing_version="0.0.15")
    prepared = prepare_release(settings, request(testPlans=[]))
    assert prepared.branch_state == "existing"
    assert (prepared.previous_version, prepared.release_version) == ("0.0.15", "0.1.0")


def test_a_dry_run_or_a_changed_checkout_is_never_committed(tmp_path: Path) -> None:
    settings = isolated(tmp_path)
    dry = prepare_release(settings, request(dryRun=True))
    skipped = commit_release(settings, dry.branch, dry.fingerprint[:16])
    assert not skipped.committed and skipped.skipped.startswith("dry run")
    prepared = prepare_release(settings, request())
    (Path(prepared.repo_dir) / "requirements.txt").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ReleaseRunError) as changed:
        commit_release(settings, prepared.branch, prepared.fingerprint[:16])
    assert changed.value.code == "checkout_changed"
    with pytest.raises(ReleaseRunError) as wrong:
        commit_release(settings, prepared.branch, "0" * 16)
    assert wrong.value.code == "stale_prepare"


def test_only_a_local_origin_inside_a_marked_root_is_accepted(tmp_path: Path) -> None:
    settings = isolated(tmp_path)
    for url in ("https://code.rsint.net/rs-wmt-projects/releases/rs-wmt-sw-release.git",
                "git@code.rsint.net:rs-wmt-projects/releases/rs-wmt-sw-release.git"):
        with pytest.raises(ReleaseRunError) as remote:
            prepare_release(settings.model_copy(update={"release_repo_url": url}), request())
        assert remote.value.code == "remote_not_isolated"
    (Path(settings.allowed_root) / ISOLATED_MARKER).unlink()
    with pytest.raises(ReleaseRunError) as unmarked:
        prepare_release(settings, request())
    assert unmarked.value.code == "isolated_root_unmarked"


def test_one_run_per_working_copy_and_no_upload_sets(tmp_path: Path) -> None:
    settings = isolated(tmp_path)
    prepared = prepare_release(settings, request())
    lock = Path(prepared.repo_dir) / ".git" / LOCK_NAME
    lock.write_text("", encoding="utf-8")
    with pytest.raises(ReleaseRunError) as busy:
        prepare_release(settings, request())
    assert busy.value.code == "checkout_busy"
    lock.unlink()
    with pytest.raises(ReleaseRunError) as upload:
        prepare_release(settings, request(uploadSetId="set-1", testPlans=[]))
    assert upload.value.code == "upload_sets_not_supported"


INDEX = """<html><body>
<a href="../rs_wmt_kt326-2.0.9-py3-none-any.whl#sha256=1">rs_wmt_kt326-2.0.9-py3-none-any.whl</a>
<a href="x">rs-wmt-kt326-2.0.11.tar.gz</a>
<a href="x">rs-wmt-kt326-2.1.0rc1.tar.gz</a>
<a href="x">rs-wmt-kt326-extras-9.0.tar.gz</a>
</body></html>"""


def test_the_newest_published_release_is_pinned_and_dev_builds_are_not(tmp_path: Path) -> None:
    versions = parse_simple_index(INDEX, "rs-wmt-kt326")
    assert [v.version for v in versions] == ["2.0.11", "2.0.9", "2.1.0rc1"]
    assert newest_release(versions) == "2.0.11"
    asked: list[str] = []

    def fetch(url: str, headers: dict[str, str]) -> tuple[int, str]:
        asked.append(url)
        return 200, INDEX

    assert lookup_published_version("kt326", "https://index/simple", "", print, fetch) == "2.0.11"
    assert asked == ["https://index/simple/rs-wmt-kt326/"]
    settings = isolated(tmp_path).model_copy(update={"artifactory_base_url": "https://index"})
    prepared = prepare_release(settings, request(chipsetVersion=""), fetch=fetch)
    assert prepared.chipset_version == "2.0.11"
    assert prepared.chipset_version_source == "published index"


def test_an_unreachable_index_falls_back_to_the_readiness_table(tmp_path: Path) -> None:
    def fetch(url: str, headers: dict[str, str]) -> tuple[int, str]:
        if "/api/chipsets" in url:
            return 200, '{"data": {"chipsets": [{"name": "rs-wmt-kt326", "tag": "2.0.8"}]}}'
        raise OSError("down")

    settings = isolated(tmp_path).model_copy(update={
        "artifactory_base_url": "https://index", "readiness_base_url": "https://ops"})
    prepared = prepare_release(settings, request(chipsetVersion=""), fetch=fetch)
    assert (prepared.chipset_version, prepared.chipset_version_source) == (
        "2.0.8", "readiness table")


def test_the_commit_message_keeps_the_source_quoting() -> None:
    assert quote_for_git('a "b" `c`\n d') == "a 'b' 'c' d"


def test_the_two_workflows_are_separate_approved_runs_that_never_push(tmp_path: Path) -> None:
    for spec in (PREPARE_SPEC, COMMIT_SPEC):
        assert spec.side_effect == "write" and spec.policy.approval_required
    assert [s.capability for s in prepare_workflow().steps] == [PREPARE_SPEC.identity]
    assert [s.capability for s in commit_workflow().steps] == [COMMIT_SPEC.identity]
    names = {p.name for p in prepare_workflow().parameters}
    assert "push" not in names and {"testPlans", "dryRun", "chipsetVersion"} <= names

    settings = isolated(tmp_path)
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"), actor="owner",
        namespace="engineering", channel="local", message="x")
    paths = settings.model_dump()
    prepared = asyncio.run(PrepareHandler()(context, {
        "request": request().model_dump(by_alias=True), **paths}))
    committed = asyncio.run(CommitHandler()(context, {
        "branch": "Foxconn_kt326", "fingerprint": prepared.fingerprint[:16],  # type: ignore[attr-defined]
        **paths}))
    assert committed.committed  # type: ignore[attr-defined]
    with pytest.raises(CapabilityRefused):
        asyncio.run(CommitHandler()(context, {"branch": "Foxconn_kt326",
                                              "fingerprint": "f" * 16, **paths}))
