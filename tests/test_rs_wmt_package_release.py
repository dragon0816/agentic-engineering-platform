"""`engineering/rs-wmt-package-release` (owner 2026-10-15, forms v2 item B).

One run from the form to the push: prepare -> commit -> push, with dry run on
and push off by default, files picked from the inbox or uploaded, and choice
lists that fail soft. Every run here uses a local bare origin in a temporary
marked root; the package index and readiness table are fakes.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from test_gateway import request as context_for
from test_release_run import git, identity, isolated, remote_head  # noqa: F401

from capabilities.release_package import choices
from capabilities.release_package.manifest import (
    COMMIT_SPEC,
    PREPARE_SPEC,
    PREVIEW,
    PUSH_SPEC,
    RELEASE,
    preview_skill,
    preview_workflow,
    release_workflow,
)
from capabilities.release_package.release_run import (
    CommitHandler,
    CommitResult,
    CommitStepInput,
    PreparedRelease,
    PrepareHandler,
    PrepareStepInput,
    PushHandler,
    PushResult,
    PushStepInput,
    ReleaseRunError,
    ReleaseRunRequest,
    ReleaseRunSettings,
    prepare_release,
)
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies, WorkflowManifest
from common.workflow_forms import agent_fields, form_fields
from common.workflow_parameters import validate_run_parameters
from host_runtime.choice_sources import ChoiceSources
from host_runtime.host import CHOICE_FUNCTIONS
from host_runtime.reference_sets import ReferenceSetStore
from host_runtime.workflow_uploads import WorkflowUploadStore
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

RUN = {
    "companyName": "Foxconn",
    "chipsetId": "kt326",
    "cmpKtOption": "KT161",
    "chipsetVersion": "2.0.17",
    "generalTestcaseVersion": "v3.0.17",
    "testPlans": ["plan.json"],
}


def test_the_workflow_is_named_not_numbered_and_asks_like_the_old_form() -> None:
    manifest = release_workflow()
    assert manifest.metadata.identity == RELEASE
    assert manifest.metadata.identity.name == "rs-wmt-package-release"
    assert manifest.run_alias is None and preview_workflow().run_alias is None
    assert [step.capability for step in manifest.steps] == [  # type: ignore[union-attr]
        PREPARE_SPEC.identity,
        COMMIT_SPEC.identity,
        PUSH_SPEC.identity,
    ]
    fields = {field["name"]: field for field in form_fields(manifest, "web")}
    assert [name for name in fields][:3] == ["companyName", "chipsetId", "info"]  # identity
    assert fields["chipsetId"]["allow_other"] and fields["chipsetId"]["group"] == "identity"
    assert fields["chipsetVersion"]["choices_source"] == (
        "fn:release_package.versions?package={chipsetId}"
    )
    assert fields["generalTestcaseVersion"]["choices_source"].endswith(
        "package=rs-wmt-general-testcase"
    )
    assert [choice["value"] for choice in fields["cmpKtOption"]["choices"]] == ["KT160", "KT161"]
    assert fields["testPlans"]["choices_source"] == (
        "fn:folder_files?folder={inbox_path}&accept=.json"
    )
    assert fields["configurationUploads"]["accept"] == [".yaml", ".yml"]
    assert fields["dryRun"]["default"] is True and fields["push"]["default"] is False
    # Pushing is a person's choice: confirmed, and never filled by a model.
    assert fields["push"]["confirm"] and "push" not in {f.name for f in agent_fields(manifest)}
    checked = validate_run_parameters(
        manifest,
        {
            "companyName": "Foxconn",
            "chipsetId": "kt999",
            "cmpKtOption": "KT160",
            "generalTestcaseVersion": "3.0.99",
        },
    )
    assert checked["dryRun"] is True and checked["push"] is False


def test_the_release_skill_starts_the_new_workflow_and_keeps_the_preview() -> None:
    skill = preview_skill()
    commands = {command.name: command.target for command in skill.commands}
    assert skill.default_command == "package"
    assert commands == {"package": RELEASE, "preview": PREVIEW}


# -- the chained run -------------------------------------------------------------------


def _engine(settings: ReleaseRunSettings, upload_root: Path) -> WorkflowEngine:
    installed = InstalledCapabilities()
    grants = []
    for spec, handler, step_input, output in (
        (PREPARE_SPEC, PrepareHandler(upload_root=upload_root), PrepareStepInput, PreparedRelease),
        (COMMIT_SPEC, CommitHandler(), CommitStepInput, CommitResult),
        (PUSH_SPEC, PushHandler(), PushStepInput, PushResult),
    ):
        installed.register(
            spec, handler, step_input, output, ExecutionDependencies(central_required=False)
        )
        grants.append(
            CapabilityGrant.model_validate(
                {
                    "actor": "engineer",
                    "asset": spec.identity,
                    "permissions": list(spec.policy.required_permissions),
                    "policy_refs": list(spec.policy.policy_refs),
                    "approval_ref": "owner-approval",
                }
            )
        )
    workflows = InstalledWorkflows()
    workflows.register(release_workflow())
    # Every setting the steps read is set, as on the owner's install; the
    # lookups never run because the tests name the chipset version.
    values = {
        **settings.model_dump(),
        "artifactory_base_url": "https://index.invalid/simple",
        "readiness_base_url": "https://ops.invalid",
    }
    # The inbox picks are checked against the folder listing, as on a host.
    sources = ChoiceSources(
        ReferenceSetStore(upload_root / "unused.sqlite"), lambda _manifest: values, CHOICE_FUNCTIONS
    )
    return WorkflowEngine(
        workflows,
        BridgeExecutor(installed, LocalPolicy(tuple(grants))),
        settings_provider=lambda _manifest: values,
        choices_provider=sources.values,
        upload_root=upload_root,
    )


def _run(engine: WorkflowEngine, arguments: dict[str, Any]) -> Any:
    checked = validate_run_parameters(release_workflow(), arguments)
    return asyncio.run(engine.execute(context_for("release"), RELEASE, checked))


def _outputs(snapshot: Any) -> list[Any]:
    return [result.data for result in snapshot.step_results]


def test_by_default_one_run_prepares_and_stops(tmp_path: Path) -> None:
    settings = isolated(tmp_path)
    engine = _engine(settings, tmp_path / "uploads")
    done = _run(engine, RUN)
    assert done.run.status == "succeeded", done.run.failure
    prepared, committed, pushed = _outputs(done)
    assert prepared["dry_run"] is True
    assert committed["committed"] is False and committed["skipped"].startswith("dry run")
    assert pushed == {
        "branch": "Foxconn_kt326",
        "commit": "",
        "pushed": False,
        "project_path": "",
        "skipped": "push not requested",
    }
    repo = Path(prepared["repo_dir"])
    assert git("log", "--oneline", cwd=repo).count("\n") == 1


def test_without_push_the_run_commits_locally_and_with_push_it_pushes_its_commit(
    tmp_path: Path,
) -> None:
    settings = isolated(tmp_path)
    engine = _engine(settings, tmp_path / "uploads")
    local = _run(engine, {**RUN, "dryRun": False})
    assert local.run.status == "succeeded", local.run.failure
    prepared, committed, pushed = _outputs(local)
    assert committed["committed"] and pushed["skipped"] == "push not requested"
    repo = Path(prepared["repo_dir"])
    assert remote_head(repo, "Foxconn_kt326") == ""

    released = _run(engine, {**RUN, "dryRun": False, "push": True, "releaseVersion": "0.0.2"})
    assert released.run.status == "succeeded", released.run.failure
    _, committed, pushed = _outputs(released)
    assert pushed["pushed"] is True and pushed["commit"] == committed["commit"]
    assert remote_head(repo, "Foxconn_kt326") == committed["commit"]


def test_push_ticked_on_a_dry_run_pushes_nothing(tmp_path: Path) -> None:
    settings = isolated(tmp_path)
    done = _run(_engine(settings, tmp_path / "uploads"), {**RUN, "push": True})
    assert done.run.status == "succeeded"
    assert _outputs(done)[2]["skipped"] == "nothing was committed in this run"


def test_uploaded_files_join_the_picked_ones_and_must_come_from_the_store(
    tmp_path: Path,
) -> None:
    settings = isolated(tmp_path)
    store = WorkflowUploadStore(tmp_path / "workspace")
    manifest = release_workflow()
    field = {item.name: item for item in manifest.parameters}
    upload_set = store.new_set()
    plan = store.add(upload_set, field["testPlanUploads"], "uploaded.json", b'{"n": 2}')
    config = store.add(upload_set, field["configurationUploads"], "cmx.yaml", b"a: 1\n")
    engine = _engine(settings, store.root)
    done = _run(
        engine, {**RUN, "testPlanUploads": [str(plan)], "configurationUploads": [str(config)]}
    )
    assert done.run.status == "succeeded", done.run.failure
    prepared = _outputs(done)[0]
    repo = Path(prepared["repo_dir"])
    assert (repo / "testplans" / "uploaded.json").read_bytes() == b'{"n": 2}'
    assert (repo / "testplans" / "plan.json").is_file()
    assert (repo / "configurations" / "cmx.yaml").read_bytes() == b"a: 1\n"
    assert {item["from"] for item in prepared["placed"]} == {"inbox", "upload"}

    stray = tmp_path / "elsewhere.json"
    stray.write_text("{}", encoding="utf-8")
    refused = _run(engine, {**RUN, "testPlanUploads": [str(stray)]})
    assert refused.run.failure is not None
    assert refused.run.failure.code == "workflow_upload_outside_store"
    # The step's own check holds even without the engine's.
    with pytest.raises(ReleaseRunError) as outside:
        prepare_release(
            settings,
            ReleaseRunRequest.model_validate({**RUN, "testPlanUploads": [str(stray)]}),
            upload_root=store.root,
        )
    assert outside.value.code == "upload_outside_store"
    with pytest.raises(ReleaseRunError) as no_store:
        prepare_release(
            settings, ReleaseRunRequest.model_validate({**RUN, "testPlanUploads": [str(plan)]})
        )
    assert no_store.value.code == "uploads_not_available"
    duplicate = store.add(upload_set, field["testPlanUploads"], "plan.json", b"{}")
    with pytest.raises(ReleaseRunError) as twice:
        prepare_release(
            settings,
            ReleaseRunRequest.model_validate({**RUN, "testPlanUploads": [str(duplicate)]}),
            upload_root=store.root,
        )
    assert twice.value.code == "invalid_release_input"


def test_a_wrong_type_upload_is_refused_by_the_plan(tmp_path: Path) -> None:
    settings = isolated(tmp_path)
    root = tmp_path / "workspace" / "workflow-uploads" / "up-20261015000000-0000abcd"
    root.mkdir(parents=True)
    script = root / "tool.exe"
    script.write_bytes(b"MZ")
    with pytest.raises(ReleaseRunError) as refused:
        prepare_release(
            settings,
            ReleaseRunRequest.model_validate({**RUN, "testPlanUploads": [str(script)]}),
            upload_root=tmp_path / "workspace" / "workflow-uploads",
        )
    assert refused.value.code == "invalid_release_input"


# -- choice lists ----------------------------------------------------------------------

INDEX_ROOT = """<a href="rs-wmt-kt326/">rs-wmt-kt326</a>
<a href="rs-wmt-general-testcase/">rs-wmt-general-testcase</a>
<a href="rs-wmt-kt400/">rs-wmt-kt400</a><a href="other/">other</a>"""
KT326 = """<a href="x">rs_wmt_kt326-2.0.9-py3-none-any.whl</a>
<a href="x">rs-wmt-kt326-2.0.11.tar.gz</a><a href="x">rs-wmt-kt326-2.1.0rc1.tar.gz</a>"""


def test_choice_lists_read_the_index_and_readiness_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTIFACTORY_TOKEN", "")
    asked: list[str] = []

    def fetch(url: str, headers: dict[str, str]) -> tuple[int, str]:
        asked.append(url)
        if "/api/chipsets" in url:
            return 200, (
                '{"data": {"chipsets": [{"name": "rs-wmt-kt326", "tag": "2.0.8"},'
                ' {"name": "kt500"}]}}'
            )
        if url.endswith("/rs-wmt-kt326/"):
            return 200, KT326
        if url == "https://index/simple/":
            return 200, INDEX_ROOT
        return 404, ""

    settings = {"artifactory_base_url": "https://index/simple", "readiness_base_url": "https://ops"}
    assert choices.chipset_choices(settings, {}, fetch) == [
        ("kt326", "kt326 (2.0.8)"),
        ("kt500", "kt500"),
    ]
    only_index = {"artifactory_base_url": "https://index/simple"}
    assert choices.chipset_choices(only_index, {}, fetch) == [
        ("kt326", "kt326"),
        ("kt400", "kt400"),
    ]
    assert choices.version_choices(settings, {"package": "kt326"}, fetch) == [
        ("2.0.11", "2.0.11"),
        ("2.0.9", "2.0.9"),
        ("2.1.0rc1", "2.1.0rc1 (dev)"),
    ]
    assert asked[-1] == "https://index/simple/rs-wmt-kt326/"
    with pytest.raises(ValueError):
        choices.version_choices(settings, {"package": "kt999"}, fetch)
    with pytest.raises(ValueError):
        choices.chipset_choices({}, {}, fetch)


def test_choice_lists_fail_soft_through_the_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """An index that is down yields no list, never an error in the form."""

    def down(url: str, headers: dict[str, str], timeout: float = 60) -> tuple[int, str]:
        raise TimeoutError("no answer within the timeout")

    monkeypatch.setattr(choices, "http_get", down)
    assert choices.CHOICE_TIMEOUT_SECONDS <= 5
    sources = ChoiceSources(
        ReferenceSetStore(Path("unused.sqlite")),
        lambda _manifest: {"artifactory_base_url": "https://index/simple"},
        CHOICE_FUNCTIONS,
    )
    manifest: WorkflowManifest = release_workflow()
    assert sources.resolve(manifest, "fn:release_package.chipsets", {}) is None
    assert (
        sources.resolve(
            manifest,
            "fn:release_package.versions?package={chipsetId}",
            {"chipsetId": "kt326"},
        )
        is None
    )


def test_telegram_asks_the_release_by_name_with_uploads_and_a_confirmation() -> None:
    from channels import telegram_flow as flow

    state = flow.start(release_workflow(), "external_side_effect", lambda *_: None, uploads=True)
    assert isinstance(state, flow.FlowState)
    names = [item.name for item in state.fields]
    assert names[:3] == ["companyName", "chipsetId", "info"]
    assert {"testPlanUploads", "configurationUploads", "overlayUploads", "push"} <= set(names)
    first = flow.begin(state)
    assert first.prompt is not None and "Which company" in first.prompt.text
    chipset = flow.answer(state, "Foxconn")
    # The index is down: the list is empty, but a typed id is taken.
    assert chipset.prompt is not None and "type the value" in chipset.prompt.text
    flow.answer(state, "kt326")
    assert state.answers["chipsetId"] == "kt326"


def test_the_release_capabilities_exist_once_the_new_workflow_has_settings(
    tmp_path: Path,
) -> None:
    from test_host_wiring import membership_record, workspace

    from host_runtime.host import build_runtime
    from host_runtime.workflow_settings import SETTINGS_FILE, WorkflowSettingsStore

    config, layout = workspace(tmp_path, membership=membership_record(), assets=False)
    WorkflowSettingsStore(layout.workspace_root / SETTINGS_FILE).save(
        RELEASE, {"work_root": str(tmp_path / "work")}
    )
    with build_runtime(config, layout=layout) as runtime:
        installed = runtime.agent.gateway.bridge.installed
        for spec in (PREPARE_SPEC, COMMIT_SPEC, PUSH_SPEC):
            assert installed.get(spec.identity) is not None
        prepare = installed.get(PREPARE_SPEC.identity)
        assert prepare is not None
        assert isinstance(prepare.handler, PrepareHandler)
        assert prepare.handler.upload_root == layout.workspace_root / "workflow-uploads"
        assert runtime.agent.gateway.engine.upload_root == (
            layout.workspace_root / "workflow-uploads"
        )
