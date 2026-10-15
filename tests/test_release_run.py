"""Workflow 13's release run (owner 2026-10-08; push 2026-10-14).

Prepare, commit and push are separate approved runs. Commit takes only what
was prepared and reviewed; push takes only the commit that commit made. The
settings refuse any origin that is not a local repository in the marked
isolated root unless `remote_release` is on, and even then a URL carrying
credentials is refused. Every test here uses a local bare origin in a
temporary folder: no network, no real release repository.
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
    PUSH_SPEC,
    commit_workflow,
    prepare_workflow,
    push_workflow,
)
from capabilities.release_package.release_run import (
    LOCK_NAME,
    CommitHandler,
    CommitStepInput,
    PrepareHandler,
    PrepareStepInput,
    PushHandler,
    PushStepInput,
    ReleaseRunError,
    ReleaseRunRequest,
    ReleaseRunSettings,
    commit_release,
    prepare_release,
    project_path,
    push_release,
    quote_for_git,
)
from capabilities.release_package.versions import (
    lookup_published_version,
    newest_release,
    parse_simple_index,
)
from capabilities.runtime import CapabilityRefused
from common.assets import AssetIdentity, WorkflowManifest, WorkflowStep
from common.execution import RequestContext, TraceIdentifiers


def _capabilities(workflow: WorkflowManifest) -> list[AssetIdentity]:
    """The capability of every step; each release workflow step is a WorkflowStep."""
    steps = [step for step in workflow.steps if isinstance(step, WorkflowStep)]
    assert len(steps) == len(workflow.steps)
    return [step.capability for step in steps]


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture(autouse=True)
def identity(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in (
        ("GIT_AUTHOR_NAME", "AEP Test"),
        ("GIT_AUTHOR_EMAIL", "aep@example.test"),
        ("GIT_COMMITTER_NAME", "AEP Test"),
        ("GIT_COMMITTER_EMAIL", "aep@example.test"),
    ):
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
        release_repo_url=str(root / "rs-wmt-sw-release.git"),
        work_root=str(root / "work"),
        inbox_path=str(inbox),
        allowed_root=str(root),
    )


def request(**extra: Any) -> ReleaseRunRequest:
    return ReleaseRunRequest.model_validate(
        {
            "companyName": "Foxconn",
            "chipsetId": "kt326",
            "cmpKtOption": "KT161",
            "chipsetVersion": "2.0.17",
            "generalTestcaseVersion": "v3.0.17",
            "notes": 'fixed the "throughput" plan',
            "testPlans": ["plan.json"],
            **extra,
        }
    )


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
        "fixed the 'throughput' plan"
    )
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
    for url in (
        "https://code.rsint.net/rs-wmt-projects/releases/rs-wmt-sw-release.git",
        "git@code.rsint.net:rs-wmt-projects/releases/rs-wmt-sw-release.git",
    ):
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

    settings = isolated(tmp_path).model_copy(
        update={"artifactory_base_url": "https://index", "readiness_base_url": "https://ops"}
    )
    prepared = prepare_release(settings, request(chipsetVersion=""), fetch=fetch)
    assert (prepared.chipset_version, prepared.chipset_version_source) == (
        "2.0.8",
        "readiness table",
    )


def test_the_commit_message_keeps_the_source_quoting() -> None:
    assert quote_for_git('a "b" `c`\n d') == "a 'b' 'c' d"


def test_the_two_workflows_are_separate_approved_runs_that_never_push(tmp_path: Path) -> None:
    for spec in (PREPARE_SPEC, COMMIT_SPEC):
        assert spec.side_effect == "write" and spec.policy.approval_required
    assert _capabilities(prepare_workflow()) == [PREPARE_SPEC.identity]
    assert _capabilities(commit_workflow()) == [COMMIT_SPEC.identity]
    names = {p.name for p in prepare_workflow().parameters}
    assert "push" not in names and {"testPlans", "dryRun", "chipsetVersion"} <= names

    settings = isolated(tmp_path)
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor="owner",
        namespace="engineering",
        channel="local",
        message="x",
    )
    paths = settings.model_dump()
    prepared = asyncio.run(
        PrepareHandler()(
            context,
            PrepareStepInput.model_validate(
                {"request": request().model_dump(by_alias=True), **paths}
            ),
        )
    )
    committed = asyncio.run(
        CommitHandler()(
            context,
            CommitStepInput.model_validate(
                {
                    "branch": "Foxconn_kt326",
                    "fingerprint": prepared.fingerprint[:16],  # type: ignore[attr-defined]
                    **paths,
                }
            ),
        )
    )
    assert committed.committed  # type: ignore[attr-defined]
    with pytest.raises(CapabilityRefused):
        asyncio.run(
            CommitHandler()(
                context,
                CommitStepInput.model_validate(
                    {"branch": "Foxconn_kt326", "fingerprint": "f" * 16, **paths}
                ),
            )
        )


# -- push (owner 2026-10-14) ----------------------------------------------------

GITLAB = "https://code.example.test/rs-wmt-projects/releases/rs-wmt-sw-release.git"


def committed(tmp_path: Path) -> tuple[ReleaseRunSettings, str, Path]:
    settings = isolated(tmp_path)
    prepared = prepare_release(settings, request())
    done = commit_release(settings, prepared.branch, prepared.fingerprint[:16])
    return settings, done.commit, Path(prepared.repo_dir)


def remote_head(repo: Path, branch: str) -> str:
    return git("ls-remote", "--heads", "origin", branch, cwd=repo).split("\t", 1)[0]


def test_push_sends_exactly_the_reviewed_commit_to_origin(tmp_path: Path) -> None:
    settings, commit, repo = committed(tmp_path)
    with pytest.raises(ReleaseRunError) as stale:
        push_release(settings, "Foxconn_kt326", "0" * 12)
    assert stale.value.code == "stale_commit"
    with pytest.raises(ReleaseRunError) as other:
        push_release(settings, "Other_kt326", commit[:12])
    assert other.value.code == "stale_commit"

    pushed = push_release(settings, "Foxconn_kt326", commit[:12])
    assert pushed.pushed and pushed.commit == commit and pushed.project_path == ""
    assert remote_head(repo, "Foxconn_kt326") == commit
    upstream = git("rev-parse", "--abbrev-ref", "Foxconn_kt326@{upstream}", cwd=repo)
    assert upstream.strip() == "origin/Foxconn_kt326"  # -u, as the source pushes
    with pytest.raises(ReleaseRunError) as again:  # the record is used up
        push_release(settings, "Foxconn_kt326", commit[:12])
    assert again.value.code == "not_committed"


def test_push_refuses_before_a_commit_or_after_the_checkout_changed(tmp_path: Path) -> None:
    settings = isolated(tmp_path)
    prepare_release(settings, request())
    with pytest.raises(ReleaseRunError) as early:
        push_release(settings, "Foxconn_kt326", "a" * 12)
    assert early.value.code == "not_committed"

    (tmp_path / "second").mkdir()
    settings, commit, repo = committed(tmp_path / "second")
    (repo / "requirements.txt").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ReleaseRunError) as changed:
        push_release(settings, "Foxconn_kt326", commit[:12])
    assert changed.value.code == "checkout_changed"
    assert remote_head(repo, "Foxconn_kt326") == ""


def test_a_commit_already_on_origin_is_not_pushed_again(tmp_path: Path) -> None:
    settings, commit, repo = committed(tmp_path)
    git("push", "-q", "origin", "Foxconn_kt326", cwd=repo)
    result = push_release(settings, "Foxconn_kt326", commit[:12])
    assert not result.pushed and result.skipped == "already on origin"


def test_a_push_never_forces_over_a_branch_that_moved_on_origin(tmp_path: Path) -> None:
    settings, commit, repo = committed(tmp_path)
    other = tmp_path / "other"
    git("clone", "-q", settings.release_repo_url, str(other), cwd=tmp_path)
    git("checkout", "-q", "-b", "Foxconn_kt326", "origin/template", cwd=other)
    (other / "x.txt").write_text("someone else", encoding="utf-8")
    git("add", "-A", cwd=other)
    git("commit", "-q", "-m", "elsewhere", cwd=other)
    git("push", "-q", "origin", "Foxconn_kt326", cwd=other)
    moved = git("rev-parse", "HEAD", cwd=other).strip()
    with pytest.raises(ReleaseRunError) as refused:
        push_release(settings, "Foxconn_kt326", commit[:12])
    assert refused.value.code == "git_failed"
    assert remote_head(repo, "Foxconn_kt326") == moved


def test_the_real_repository_needs_remote_release_and_a_clean_url(tmp_path: Path) -> None:
    settings = isolated(tmp_path)
    off = settings.model_copy(update={"release_repo_url": GITLAB})
    with pytest.raises(ReleaseRunError) as refused:
        off.checked()
    assert refused.value.code == "remote_not_isolated"

    on = settings.model_copy(update={"release_repo_url": GITLAB, "remote_release": True})
    assert on.checked()[3] == GITLAB
    for url in (
        "git@code.example.test:rs-wmt-projects/releases/rs-wmt-sw-release.git",
        "ssh://git@code.example.test:2222/rs-wmt-projects/rs-wmt-sw-release.git",
    ):
        assert on.model_copy(update={"release_repo_url": url}).checked()[3] == url
    for url in (
        "http://code.example.test/group/repo.git",
        "https://someone@code.example.test/group/repo.git",
        "https://oauth2:not-a-real-value@code.example.test/group/repo.git",
        "file:///C:/repos/repo.git",
    ):
        with pytest.raises(ReleaseRunError) as bad:
            on.model_copy(update={"release_repo_url": url}).checked()
        assert bad.value.code == "remote_url_invalid"

    outside = on.model_copy(update={"work_root": str(tmp_path / "elsewhere")})
    with pytest.raises(ReleaseRunError) as escaped:
        outside.checked()
    assert escaped.value.code == "path_outside_isolated_root"


def test_with_remote_release_the_plan_names_the_push_and_a_foreign_origin_is_refused(
    tmp_path: Path,
) -> None:
    settings = isolated(tmp_path)
    prepare_release(settings, request(testPlans=[]))  # leaves a working copy
    remote = settings.model_copy(update={"release_repo_url": GITLAB, "remote_release": True})
    prepared = prepare_release(remote, request())  # fetches the existing copy: no network
    assert any(
        "push to rs-wmt-projects/releases/rs-wmt-sw-release" in line for line in prepared.plan
    )
    done = commit_release(remote, prepared.branch, prepared.fingerprint[:16])
    with pytest.raises(ReleaseRunError) as foreign:
        push_release(remote, prepared.branch, done.commit[:12])
    assert foreign.value.code == "origin_changed"


def test_project_path_matches_the_source_rule() -> None:
    assert project_path(GITLAB) == "rs-wmt-projects/releases/rs-wmt-sw-release"
    assert project_path("git@host:group/repo.git") == "group/repo"
    assert project_path("") == ""


def test_push_is_its_own_high_risk_approved_workflow(tmp_path: Path) -> None:
    assert PUSH_SPEC.side_effect == "external_side_effect"
    assert PUSH_SPEC.policy.approval_required and PUSH_SPEC.policy.risk == "high"
    assert _capabilities(push_workflow()) == [PUSH_SPEC.identity]
    static = {p.name: p for p in push_workflow().parameters if p.scope == "static"}
    assert static["remote_release"].default is False
    assert {p.name for p in prepare_workflow().parameters if p.scope == "static"} == set(static)

    settings, commit, _ = committed(tmp_path)
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor="owner",
        namespace="engineering",
        channel="local",
        message="x",
    )
    paths = settings.model_dump()
    with pytest.raises(CapabilityRefused):
        asyncio.run(
            PushHandler()(
                context,
                PushStepInput.model_validate(
                    {"branch": "Foxconn_kt326", "commit": "f" * 12, **paths}
                ),
            )
        )
    pushed = asyncio.run(
        PushHandler()(
            context,
            PushStepInput.model_validate(
                {"branch": "Foxconn_kt326", "commit": commit[:12], **paths}
            ),
        )
    )
    assert pushed.pushed  # type: ignore[attr-defined]


def test_the_release_capabilities_exist_once_this_install_has_release_settings(
    tmp_path: Path,
) -> None:
    """An unrelated host does not offer them; a host holding settings for a
    release Workflow does, so the Workflows can be installed from drafts."""
    from test_host_wiring import membership_record, workspace

    from capabilities.release_package.manifest import PREPARE
    from host_runtime.host import build_runtime
    from host_runtime.workflow_settings import SETTINGS_FILE, WorkflowSettingsStore

    config, layout = workspace(tmp_path, membership=membership_record(), assets=False)
    with build_runtime(config, layout=layout) as runtime:
        installed = runtime.agent.gateway.bridge.installed
        assert all(
            installed.get(spec.identity) is None for spec in (PREPARE_SPEC, COMMIT_SPEC, PUSH_SPEC)
        )

    WorkflowSettingsStore(layout.workspace_root / SETTINGS_FILE).save(
        PREPARE, {"work_root": str(tmp_path / "work")}
    )
    with build_runtime(config, layout=layout) as runtime:
        installed = runtime.agent.gateway.bridge.installed
        for spec in (PREPARE_SPEC, COMMIT_SPEC, PUSH_SPEC):
            assert installed.get(spec.identity) is not None
