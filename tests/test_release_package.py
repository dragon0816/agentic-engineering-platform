"""Workflow 13 source-characterization cases, with no GitLab or Bridge writes."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from test_host_wiring import membership_record, workspace

from capabilities.release_package import release_yaml as ry
from capabilities.release_package.apply_isolated import (
    ISOLATED_MARKER,
    ISOLATED_MARKER_VALUE,
    IsolatedApplyError,
    apply_isolated,
)
from capabilities.release_package.contracts import (
    IsolatedApplyOutput,
    IsolatedApplySettings,
    ReleasePreview,
    ReleasePreviewRequest,
    ReleasePreviewSettings,
    ReleasePreviewStepInput,
)
from capabilities.release_package.local_dry_run import prepare_dry_run
from capabilities.release_package.manifest import (
    ISOLATED_APPLY_SPEC,
    PREVIEW_SPEC,
    isolated_apply_workflow,
    preview_skill,
    preview_workflow,
)
from capabilities.release_package.planning import (
    ReleasePlan,
    ReleaseRequest,
    ReleaseSettings,
    ReleaseValidationError,
    SelectedFile,
    branch_name,
    plan_release,
)
from capabilities.release_package.preview import (
    ReleasePreviewError,
    ReleasePreviewHandler,
    build_preview,
)
from capabilities.release_package.schema import PARAMS_SCHEMA
from capabilities.release_package.status import dry_run_plan, parse_status
from capabilities.runtime import CapabilityGrant, CapabilityRefused, LocalPolicy
from common.assets import WorkflowStep
from common.execution import RequestContext, TraceIdentifiers
from common.local_agent import LocalWorkflowRequest
from host_runtime.assets import export_assets
from host_runtime.host import build_runtime


@pytest.mark.parametrize(
    ("current", "expected"),
    [(None, "0.0.1"), ("0.0.15", "0.1.0"), ("0.15.15", "1.0.0")],
)
def test_source_version_radix(current: str | None, expected: str) -> None:
    assert ry.next_version(current) == expected


def test_source_version_overflow_is_refused() -> None:
    with pytest.raises(ry.ReleaseYamlError):
        ry.next_version("15.15.15")


def test_source_runtime_form_contract_is_data_and_does_not_grant_push() -> None:
    assert PARAMS_SCHEMA["required"] == [
        "companyName", "chipsetId", "generalTestcaseVersion", "cmpKtOption"
    ]
    fields = PARAMS_SCHEMA["properties"]
    assert fields["chipsetVersion"]["x-ui"]["options"] == (
        "ref:packageVersions:{chipsetId}"
    )
    assert fields["cmpKtOption"]["enum"] == ["KT160", "KT161"]
    assert "x-ui" not in fields["push"]


def test_source_branch_and_pinned_requirements() -> None:
    assert branch_name("Big Corp", "kt326", "demo") == "Big-Corp_kt326_demo"
    assert ry.requirements_lines("rs-wmt-kt326", "v2.0.18", "2.1.2") == [
        "rs-wmt-kt326==2.0.18",
        "rs-wmt-general-testcase==2.1.2",
    ]
    with pytest.raises(ReleaseValidationError):
        branch_name("Bad/Corp", "kt326")


def test_release_yaml_keeps_source_comments_and_manual_option() -> None:
    rendered = ry.render(
        chipset_id="rs-wmt-kt326",
        branch_name="Foxconn_kt326",
        customer_name="Foxconn",
        version="0.0.1",
        include=["rswmt/**/*", "overlay/**/*"],
        cmp_option="KT160",
    )
    assert "CMP_KT_OPTION: KT160" in rendered
    assert "KT_OPTION: kt326" in rendered
    assert "# Common parameters (both KT161 and KT160)" in rendered
    assert ry.parse_version(rendered) == "0.0.1"


def test_status_projection_preserves_source_grouping() -> None:
    assert parse_status(
        ["?? testplans/a.xml", "?? testplans/b.xml", " M release.yaml"]
    ) == [("test plans", 2), ("release.yaml", 1)]
    assert parse_status(["R  overlay/old.bin -> testplans/new.xml"]) == [
        ("test plans", 1)
    ]
    lines = dry_run_plan(
        company="WNC", chipset="sdx55", chipset_version="4.1.2",
        branch="WNC_sdx55", branch_state="created", template="template",
        release_version="0.0.1", previous_version="", testcase="2.8.1",
        changed=["?? testplans/a.xml"], project_path="test/release", will_push=False,
    )
    assert "Nothing has been committed and nothing has been pushed." in "\n".join(lines)
    assert "pushing is switched off" in "\n".join(lines)


def test_plan_is_pure_and_projects_source_destinations(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "a.json").write_text("{}", encoding="utf-8")
    repo = tmp_path / "repository"
    repo.mkdir()
    before = set(repo.iterdir())
    plan = plan_release(
        ReleaseRequest(
            company_name="Foxconn", chipset_id="kt326", cmp_kt_option="KT160",
            chipset_version="v2.0.18", general_testcase_version="2.1.2",
            test_plans=("a.json",),
        ),
        ReleaseSettings(inbox=inbox),
        previous_release_yaml="VERSION: 0.0.15\n",
    )
    assert plan.branch == "Foxconn_kt326"
    assert plan.release_version == "0.1.0"
    assert plan.requirements == (
        "rs-wmt-kt326==2.0.18", "rs-wmt-general-testcase==2.1.2"
    )
    assert plan.selected_files[0].destination == "testplans/a.json"
    assert "VERSION: 0.1.0" in plan.release_yaml
    assert set(repo.iterdir()) == before


@pytest.mark.parametrize("filename", ["../secret", "sub/file", "C:\\secret", "missing.json"])
def test_plan_refuses_unsafe_or_missing_inbox_name(tmp_path: Path, filename: str) -> None:
    with pytest.raises(ReleaseValidationError):
        plan_release(
            ReleaseRequest(
                company_name="Foxconn", chipset_id="kt326", cmp_kt_option="KT160",
                chipset_version="2.0.18", general_testcase_version="2.1.2",
                test_plans=(filename,),
            ),
            ReleaseSettings(inbox=tmp_path),
        )


def test_plan_refuses_upload_name_mixing_before_any_write(tmp_path: Path) -> None:
    with pytest.raises(ReleaseValidationError, match="both"):
        plan_release(
            ReleaseRequest(
                company_name="Foxconn", chipset_id="kt326", cmp_kt_option="KT160",
                chipset_version="2.0.18", general_testcase_version="2.1.2",
                upload_set_id="set-1", test_plans=("a.json",),
            ),
            ReleaseSettings(inbox=tmp_path),
        )


def test_plan_requires_explicit_published_version_until_lookup_is_integrated(
    tmp_path: Path,
) -> None:
    with pytest.raises(ReleaseValidationError, match="chipset_version"):
        plan_release(
            ReleaseRequest(
                company_name="Foxconn", chipset_id="kt326", cmp_kt_option="KT160",
                chipset_version="", general_testcase_version="2.1.2",
            ),
            ReleaseSettings(inbox=tmp_path),
        )


def test_dry_run_writes_only_isolated_checkout_without_commit_or_push(tmp_path: Path) -> None:
    git = shutil.which("git")
    if not git:
        pytest.skip("git is unavailable")
    repo = tmp_path / "release-repo"
    repo.mkdir()
    subprocess.run([git, "init", "-q", str(repo)], check=True)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "case.json").write_text("{}", encoding="utf-8")
    plan = plan_release(
        ReleaseRequest(
            company_name="Foxconn", chipset_id="kt326", cmp_kt_option="KT160",
            chipset_version="2.0.18", general_testcase_version="2.1.2",
            test_plans=("case.json",),
        ),
        ReleaseSettings(inbox=inbox),
    )
    head_before = subprocess.run(
        [git, "rev-parse", "--verify", "HEAD"], cwd=repo, capture_output=True
    ).returncode
    receipt = prepare_dry_run(plan, inbox=inbox, checkout=repo, allowed_root=tmp_path)
    assert receipt.changed == ("requirements.txt", "release.yaml", "testplans/case.json")
    assert not receipt.committed and not receipt.pushed
    assert (repo / "requirements.txt").read_text(encoding="utf-8") == (
        "rs-wmt-kt326==2.0.18\nrs-wmt-general-testcase==2.1.2\n"
    )
    assert (repo / "testplans" / "case.json").read_text(encoding="utf-8") == "{}"
    assert subprocess.run(
        [git, "rev-parse", "--verify", "HEAD"], cwd=repo, capture_output=True
    ).returncode == head_before
    status = subprocess.run(
        [git, "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout
    assert "requirements.txt" in status and "release.yaml" in status
    assert prepare_dry_run(plan, inbox=inbox, checkout=repo, allowed_root=tmp_path).changed == ()


def test_dry_run_refuses_checkout_outside_explicit_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    plan = plan_release(
        ReleaseRequest(
            company_name="Foxconn", chipset_id="kt326", cmp_kt_option="KT160",
            chipset_version="2.0.18", general_testcase_version="2.1.2",
        ),
        ReleaseSettings(inbox=tmp_path),
    )
    with pytest.raises(ReleaseValidationError, match="allowed_root"):
        prepare_dry_run(plan, inbox=tmp_path, checkout=repo, allowed_root=tmp_path / "elsewhere")
    assert list(repo.iterdir()) == [repo / ".git"]


def test_dry_run_refuses_forged_git_metadata_destination(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (tmp_path / "input.json").write_text("{}", encoding="utf-8")
    good = plan_release(
        ReleaseRequest(
            company_name="Foxconn", chipset_id="kt326", cmp_kt_option="KT160",
            chipset_version="2.0.18", general_testcase_version="2.1.2",
            test_plans=("input.json",),
        ),
        ReleaseSettings(inbox=tmp_path),
    )
    forged = replace(good, selected_files=(
        SelectedFile("testPlans", "input.json", ".git/config", good.selected_files[0].sha256),
    ))
    with pytest.raises(ReleaseValidationError, match="destination"):
        prepare_dry_run(forged, inbox=tmp_path, checkout=repo, allowed_root=tmp_path)
    assert not (repo / "requirements.txt").exists()


def test_dry_run_refuses_destination_parent_symlink_into_git_metadata(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / ".git" / "config").write_text("original", encoding="utf-8")
    (tmp_path / "config").write_text("payload", encoding="utf-8")
    try:
        (repo / "testplans").symlink_to(repo / ".git", target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable on this host")
    plan = plan_release(
        ReleaseRequest(
            company_name="Foxconn", chipset_id="kt326", cmp_kt_option="KT160",
            chipset_version="2.0.18", general_testcase_version="2.1.2",
            test_plans=("config",),
        ),
        ReleaseSettings(inbox=tmp_path),
    )
    with pytest.raises(ReleaseValidationError, match="symlink"):
        prepare_dry_run(plan, inbox=tmp_path, checkout=repo, allowed_root=tmp_path)
    assert (repo / ".git" / "config").read_text(encoding="utf-8") == "original"


def _preview_request() -> ReleasePreviewRequest:
    return ReleasePreviewRequest.model_validate({
        "companyName": "Foxconn",
        "chipsetId": "kt326",
        "cmpKtOption": "KT160",
        "chipsetVersion": "2.0.18",
        "generalTestcaseVersion": "2.1.2",
    })


def test_installed_w13_contract_is_exact_read_only_preview() -> None:
    workflow = preview_workflow()
    skill = preview_skill()
    assert workflow.run_alias == 13
    assert workflow.metadata.identity.name == "release-package-preview"
    assert PREVIEW_SPEC.side_effect == "read"
    assert isinstance(workflow.steps[0], WorkflowStep)
    assert workflow.steps[0].capability == PREVIEW_SPEC.identity
    assert workflow.steps[0].retry.max_attempts == 1
    assert skill.commands[0].name == "preview"
    assert skill.commands[0].target == workflow.metadata.identity
    params = {item.name: item for item in workflow.parameters}
    assert params["checkout_path"].scope == "static"
    assert params["inbox_path"].scope == "static"
    assert params["companyName"].required
    assert params["chipsetVersion"].required
    assert params["cmpKtOption"].options == ("KT160", "KT161")


def test_read_only_preview_uses_checked_out_version_and_keeps_files_unchanged(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "release"
    (checkout / ".git").mkdir(parents=True)
    (checkout / ".git" / "HEAD").write_text(
        "ref: refs/heads/Foxconn_kt326\n", encoding="utf-8"
    )
    (checkout / "release.yaml").write_text("VERSION: 0.0.15\n", encoding="utf-8")
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    before = {
        str(path.relative_to(checkout)): path.read_bytes()
        for path in checkout.rglob("*") if path.is_file()
    }
    settings = ReleasePreviewSettings(checkout_path=str(checkout), inbox_path=str(inbox))
    result = build_preview(settings, _preview_request())
    assert result.release_version == "0.1.0"
    assert result.previous_version == "0.0.15"
    assert result.branch == "Foxconn_kt326"
    assert result.changed_paths == ("requirements.txt", "release.yaml")
    assert result.committed is False and result.pushed is False
    assert "CMP_KT_OPTION: KT160" in result.release_yaml
    assert {
        str(path.relative_to(checkout)): path.read_bytes()
        for path in checkout.rglob("*") if path.is_file()
    } == before


def test_read_only_preview_refuses_wrong_branch_and_handler_maps_code(tmp_path: Path) -> None:
    checkout = tmp_path / "release"
    (checkout / ".git").mkdir(parents=True)
    (checkout / ".git" / "HEAD").write_text("ref: refs/heads/template\n", encoding="utf-8")
    settings = ReleasePreviewSettings(checkout_path=str(checkout), inbox_path=str(tmp_path))
    with pytest.raises(ReleasePreviewError, match="wrong_branch"):
        build_preview(settings, _preview_request())
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="w13", request_id="preview", span_id="test"),
        actor="engineer", namespace="engineering", message="preview", channel="local",
    )
    with pytest.raises(CapabilityRefused) as error:
        # The install's settings arrive with the run, not at construction.
        asyncio.run(ReleasePreviewHandler()(
            context, ReleasePreviewStepInput(
                request=_preview_request(), checkout_path=str(checkout),
                inbox_path=str(tmp_path),
            )
        ))
    assert error.value.code == "wrong_branch"
    with pytest.raises(CapabilityRefused) as invalid:
        asyncio.run(ReleasePreviewHandler()(
            context, ReleasePreviewStepInput(
                request=_preview_request(), checkout_path="relative/path",
                inbox_path=str(tmp_path),
            )
        ))
    assert invalid.value.code == "release_settings_invalid"


def test_installed_workflow_13_preview_respects_bridge_grant_and_never_writes_repo(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "release"
    (checkout / ".git").mkdir(parents=True)
    (checkout / ".git" / "HEAD").write_text(
        "ref: refs/heads/Foxconn_kt326\n", encoding="utf-8"
    )
    (checkout / "release.yaml").write_text("VERSION: 0.0.15\n", encoding="utf-8")
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "testplan.json").write_text("{}", encoding="utf-8")
    before = {
        str(path.relative_to(checkout)): path.read_bytes()
        for path in checkout.rglob("*") if path.is_file()
    }
    grant = {
        "actor": "engineer",
        "asset": PREVIEW_SPEC.identity.model_dump(mode="json"),
        "permissions": list(PREVIEW_SPEC.policy.required_permissions),
        "policy_refs": list(PREVIEW_SPEC.policy.policy_refs),
        "approval_ref": "release-preview-approval",
    }
    integration = {
        "integrations": {
            "release_package": {"checkout_path": str(checkout), "inbox_path": str(inbox)}
        }
    }
    arguments = {
        "companyName": "Foxconn", "chipsetId": "kt326", "cmpKtOption": "KT160",
        "chipsetVersion": "2.0.18", "generalTestcaseVersion": "2.1.2",
        "testPlans": ["testplan.json"],
    }
    for label, grants in (("authorized", [grant]), ("denied", [])):
        config, layout = workspace(
            tmp_path / label,
            membership=membership_record(),
            grants=grants,
            assets=False,
            config_changes=integration,
        )
        export_assets(layout.workspace_root / "assets")
        request = LocalWorkflowRequest(
            actor="engineer",
            bridge_id=config.device.bridge_id,
            workflow=preview_workflow().metadata.identity,
            arguments=arguments,
            idempotency_key=f"release-preview-{label}",
            trace=TraceIdentifiers(
                trace_id=f"w13-{label}", request_id="preview", span_id="test"
            ),
        )
        with build_runtime(config, layout=layout) as runtime:
            outcome = asyncio.run(runtime.agent.execute_workflow(request))
            assert outcome.refusal is None and outcome.workflow is not None
            if label == "authorized":
                assert outcome.workflow.run.status == "succeeded", outcome.workflow.run.failure
                preview = ReleasePreview.model_validate(outcome.workflow.step_results[-1].data)
                assert preview.release_version == "0.1.0"
                assert preview.committed is False and preview.pushed is False
            else:
                assert outcome.workflow.run.status == "failed"
                assert outcome.workflow.run.failure is not None
                assert outcome.workflow.run.failure.code == "permission_denied"
        assert {
            str(path.relative_to(checkout)): path.read_bytes()
            for path in checkout.rglob("*") if path.is_file()
        } == before


def test_workflow_13_runs_from_settings_page_values_without_host_integrations(
    tmp_path: Path,
) -> None:
    from host_runtime.workflow_settings import SETTINGS_FILE, WorkflowSettingsStore

    checkout = tmp_path / "release"
    (checkout / ".git").mkdir(parents=True)
    (checkout / ".git" / "HEAD").write_text("ref: refs/heads/Foxconn_kt326\n", encoding="utf-8")
    (checkout / "release.yaml").write_text("VERSION: 0.0.15\n", encoding="utf-8")
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "testplan.json").write_text("{}", encoding="utf-8")
    grant = {
        "actor": "engineer",
        "asset": PREVIEW_SPEC.identity.model_dump(mode="json"),
        "permissions": list(PREVIEW_SPEC.policy.required_permissions),
        "policy_refs": list(PREVIEW_SPEC.policy.policy_refs),
        "approval_ref": "release-preview-approval",
    }
    config, layout = workspace(
        tmp_path / "host", membership=membership_record(), grants=[grant], assets=False,
    )
    export_assets(layout.workspace_root / "assets")
    request = LocalWorkflowRequest(
        actor="engineer", bridge_id=config.device.bridge_id,
        workflow=preview_workflow().metadata.identity,
        arguments={
            "companyName": "Foxconn", "chipsetId": "kt326", "cmpKtOption": "KT160",
            "chipsetVersion": "2.0.18", "generalTestcaseVersion": "2.1.2",
        },
        idempotency_key="release-preview-settings",
        trace=TraceIdentifiers(trace_id="w13-settings", request_id="preview", span_id="test"),
    )
    with build_runtime(config, layout=layout) as runtime:
        unset = asyncio.run(runtime.agent.execute_workflow(request))
        assert unset.workflow is not None and unset.workflow.run.failure is not None
        assert unset.workflow.run.failure.code == "workflow_settings_incomplete"
        WorkflowSettingsStore(layout.workspace_root / SETTINGS_FILE).save(
            preview_workflow().metadata.identity,
            {"checkout_path": str(checkout), "inbox_path": str(inbox)},
        )
        ran = asyncio.run(runtime.agent.execute_workflow(
            request.model_copy(update={"idempotency_key": "release-preview-settings-2"})
        ))
        assert ran.workflow is not None
        assert ran.workflow.run.status == "succeeded", ran.workflow.run.failure


def test_settings_page_values_win_over_legacy_host_integrations(tmp_path: Path) -> None:
    from host_runtime.workflow_settings import SETTINGS_FILE, WorkflowSettingsStore

    legacy = {"checkout_path": str(tmp_path / "old"), "inbox_path": str(tmp_path / "in")}
    config, layout = workspace(
        tmp_path / "host", membership=membership_record(), assets=False,
        config_changes={"integrations": {"release_package": legacy}},
    )
    manifest = preview_workflow()
    with build_runtime(config, layout=layout) as runtime:
        provider = runtime.agent.gateway.engine.settings_provider
        assert provider is not None
        assert provider(manifest) == legacy
        WorkflowSettingsStore(layout.workspace_root / SETTINGS_FILE).save(
            manifest.metadata.identity, {"checkout_path": str(tmp_path / "new")}
        )
        assert provider(manifest) == {**legacy, "checkout_path": str(tmp_path / "new")}


def _isolated_checkout(tmp_path: Path) -> tuple[IsolatedApplySettings, Path, Path]:
    git = shutil.which("git")
    if not git:
        pytest.skip("git is unavailable")
    allowed = tmp_path / "isolated"
    allowed.mkdir()
    (allowed / ISOLATED_MARKER).write_text(ISOLATED_MARKER_VALUE, encoding="utf-8")
    repo = allowed / "checkout"
    repo.mkdir()
    subprocess.run([git, "init", "-q", str(repo)], check=True)
    subprocess.run(
        [git, "symbolic-ref", "HEAD", "refs/heads/Foxconn_kt326"],
        cwd=repo, check=True,
    )
    (repo / "release.yaml").write_text("VERSION: 0.0.15\n", encoding="utf-8")
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "case.json").write_text("{}", encoding="utf-8")
    return (
        IsolatedApplySettings(
            allowed_root=str(allowed), checkout_path=str(repo), inbox_path=str(inbox)
        ),
        repo,
        inbox,
    )


def _isolated_plan(repo: Path, inbox: Path) -> ReleasePlan:
    return plan_release(
        ReleaseRequest(
            company_name="Foxconn", chipset_id="kt326", cmp_kt_option="KT160",
            chipset_version="2.0.18", general_testcase_version="2.1.2",
            test_plans=("case.json",),
        ),
        ReleaseSettings(inbox=inbox),
        previous_release_yaml=(repo / "release.yaml").read_text(encoding="utf-8"),
    )


def test_isolated_apply_prepares_source_files_without_commit_push_or_network(
    tmp_path: Path,
) -> None:
    settings, repo, inbox = _isolated_checkout(tmp_path)
    plan = _isolated_plan(repo, inbox)
    git = shutil.which("git")
    assert git is not None
    head_before = subprocess.run(
        [git, "rev-parse", "--verify", "HEAD"], cwd=repo, capture_output=True
    ).returncode
    receipt = apply_isolated(plan, settings=settings)
    assert receipt.prepared and not receipt.committed and not receipt.pushed
    assert receipt.release_version == "0.1.0"
    assert receipt.changed_paths == (
        "requirements.txt", "release.yaml", "testplans/case.json"
    )
    assert (repo / "requirements.txt").read_text(encoding="utf-8") == (
        "rs-wmt-kt326==2.0.18\nrs-wmt-general-testcase==2.1.2\n"
    )
    assert "VERSION: 0.1.0" in (repo / "release.yaml").read_text(encoding="utf-8")
    assert (repo / "testplans" / "case.json").read_text(encoding="utf-8") == "{}"
    assert subprocess.run(
        [git, "rev-parse", "--verify", "HEAD"], cwd=repo, capture_output=True
    ).returncode == head_before
    assert not (repo / ".git" / "aep-w13-apply.lock").exists()
    with pytest.raises(IsolatedApplyError, match="stale_plan"):
        apply_isolated(plan, settings=settings)


def test_isolated_apply_refuses_stale_plan_before_any_write(tmp_path: Path) -> None:
    settings, repo, inbox = _isolated_checkout(tmp_path)
    plan = _isolated_plan(repo, inbox)
    (repo / "release.yaml").write_text("VERSION: 0.0.14\n", encoding="utf-8")
    with pytest.raises(IsolatedApplyError, match="stale_plan"):
        apply_isolated(plan, settings=settings)
    assert not (repo / "requirements.txt").exists()


def test_isolated_apply_refuses_unmarked_or_remote_checkout(tmp_path: Path) -> None:
    settings, repo, inbox = _isolated_checkout(tmp_path)
    plan = _isolated_plan(repo, inbox)
    Path(settings.allowed_root, ISOLATED_MARKER).unlink()
    with pytest.raises(IsolatedApplyError, match="isolated_root_unmarked"):
        apply_isolated(plan, settings=settings)
    Path(settings.allowed_root, ISOLATED_MARKER).write_text(
        ISOLATED_MARKER_VALUE, encoding="utf-8"
    )
    git = shutil.which("git")
    assert git is not None
    subprocess.run(
        [git, "remote", "add", "origin", "https://invalid.example/release.git"],
        cwd=repo, check=True,
    )
    with pytest.raises(IsolatedApplyError, match="remote_configured"):
        apply_isolated(plan, settings=settings)
    assert not (repo / "requirements.txt").exists()


def test_isolated_apply_serializes_checkout_and_requires_bridge_approval(tmp_path: Path) -> None:
    settings, repo, inbox = _isolated_checkout(tmp_path)
    plan = _isolated_plan(repo, inbox)
    lock = repo / ".git" / "aep-w13-apply.lock"
    lock.write_text("occupied", encoding="utf-8")
    with pytest.raises(IsolatedApplyError, match="checkout_busy"):
        apply_isolated(plan, settings=settings)
    assert not (repo / "requirements.txt").exists()
    assert ISOLATED_APPLY_SPEC.side_effect == "write"
    assert ISOLATED_APPLY_SPEC.policy.approval_required
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="w13", request_id="apply", span_id="test"),
        actor="engineer", namespace="engineering", message="apply", channel="local",
    )
    grant = CapabilityGrant(
        actor="engineer", asset=ISOLATED_APPLY_SPEC.identity,
        permissions=ISOLATED_APPLY_SPEC.policy.required_permissions,
        policy_refs=ISOLATED_APPLY_SPEC.policy.policy_refs,
    )
    assert not LocalPolicy((grant,)).authorize(context, ISOLATED_APPLY_SPEC).allowed


def test_installed_isolated_apply_requires_grant_and_approval_then_prepares_only_test_repo(
    tmp_path: Path,
) -> None:
    settings, repo, _ = _isolated_checkout(tmp_path)
    workflow = isolated_apply_workflow()
    assert workflow.run_alias is None
    step = workflow.steps[0]
    assert isinstance(step, WorkflowStep)
    assert step.capability == ISOLATED_APPLY_SPEC.identity
    before = {
        str(path.relative_to(repo)): path.read_bytes()
        for path in repo.rglob("*") if path.is_file()
    }
    grant = {
        "actor": "engineer",
        "asset": ISOLATED_APPLY_SPEC.identity.model_dump(mode="json"),
        "permissions": list(ISOLATED_APPLY_SPEC.policy.required_permissions),
        "policy_refs": list(ISOLATED_APPLY_SPEC.policy.policy_refs),
        "approval_ref": "isolated-release-write-approval",
    }
    arguments = {
        "companyName": "Foxconn", "chipsetId": "kt326", "cmpKtOption": "KT160",
        "chipsetVersion": "2.0.18", "generalTestcaseVersion": "2.1.2",
        "testPlans": ["case.json"],
    }
    for label, grants in (
        ("no-grant", []),
        ("no-approval", [{key: value for key, value in grant.items() if key != "approval_ref"}]),
        ("approved", [grant]),
    ):
        config, layout = workspace(
            tmp_path / label,
            membership=membership_record(),
            grants=grants,
            assets=False,
            config_changes={
                "integrations": {
                    "isolated_release_apply": settings.model_dump(mode="json")
                }
            },
        )
        export_assets(layout.workspace_root / "assets")
        request = LocalWorkflowRequest(
            actor="engineer",
            bridge_id=config.device.bridge_id,
            workflow=workflow.metadata.identity,
            arguments=arguments,
            idempotency_key=f"isolated-release-{label}",
            trace=TraceIdentifiers(
                trace_id=f"w13-{label}", request_id="apply", span_id="test"
            ),
        )
        with build_runtime(config, layout=layout) as runtime:
            outcome = asyncio.run(runtime.agent.execute_workflow(request))
            assert outcome.refusal is None and outcome.workflow is not None
            if label == "approved":
                assert outcome.workflow.run.status == "succeeded", outcome.workflow.run.failure
                applied = IsolatedApplyOutput.model_validate(
                    outcome.workflow.step_results[-1].data
                )
                assert applied.prepared and not applied.committed and not applied.pushed
                assert applied.release_version == "0.1.0"
            else:
                assert outcome.workflow.run.status == "failed"
                assert outcome.workflow.run.failure is not None
                assert outcome.workflow.run.failure.code == "permission_denied"
                assert {
                    str(path.relative_to(repo)): path.read_bytes()
                    for path in repo.rglob("*") if path.is_file()
                } == before
    assert (repo / "requirements.txt").read_text(encoding="utf-8") == (
        "rs-wmt-kt326==2.0.18\nrs-wmt-general-testcase==2.1.2\n"
    )
    assert "VERSION: 0.1.0" in (repo / "release.yaml").read_text(encoding="utf-8")
    assert (repo / "testplans" / "case.json").read_text(encoding="utf-8") == "{}"
