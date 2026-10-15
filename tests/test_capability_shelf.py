"""Agent Web Capabilities: switch off, remove and "+ Add to this Agent".

Requirements (owner 2026-10-15): an installed Skill or Workflow can be
switched off (its kind's `disabled/` folder, as a superseded Skill already
is) and on again; "Remove from this Agent" never hard-deletes: the file moves
to `workspace/removed/<date>/`, a journal line says what moved where, and the
inventory row goes so the asset is no longer offered or reported. Manifests
AEP ships are refused, because `export-assets` writes them back. "+ Add to
this Agent" selects the exact version for this PC's Bridge in the Member
Portal as the member and runs the existing verified sync; assets-only mode
says that permissions stay with grants.json. Everything platform-side runs
against a real in-process shared platform.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_host_wiring import host_json, ready
from test_member_publish import _signed_in, workflow_manifest
from test_shared_platform_app import request
from test_shared_platform_settings import OLD_PLATFORM, _agent_login, _card, _host, _web

from agent.skills import SkillManifest
from common.assets import AssetIdentity, WorkflowManifest
from control_plane.app import SharedPlatformApplication
from host_runtime.asset_shelf import JOURNAL, shipped_keys
from host_runtime.assets import shipped
from host_runtime.contracts import CompanyHostConfiguration, HostLayout
from host_runtime.host import build_runtime
from host_runtime.shared_platform import LOGIN_VARIABLE, TOKEN_VARIABLE
from host_runtime.web import AgentWeb

IDENTITY = {"namespace": "lab", "name": "weekly-check", "version": "1.0.0"}
REFERENCE = "lab/weekly-check@1.0.0"


@pytest.fixture
def app(tmp_path: Path) -> Iterator[SharedPlatformApplication]:
    platform = SharedPlatformApplication.empty(
        administrators=("platform-admin",), registry_path=tmp_path / "registry.sqlite")
    with platform:
        yield platform


@pytest.fixture(autouse=True)
def _environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (TOKEN_VARIABLE, LOGIN_VARIABLE, "AEP_LOCAL_PLATFORM_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    from host_runtime import platform_publish

    monkeypatch.setattr(platform_publish, "_saved_user_variable", lambda name: None)


def _local_workflow(layout: HostLayout, name: str = "local-check") -> str:
    manifest = WorkflowManifest.model_validate(workflow_manifest(name, "1.0.0"))
    layout.workflows.mkdir(parents=True, exist_ok=True)
    (layout.workflows / f"lab__{name}__1.0.0.json").write_text(
        manifest.model_dump_json(), encoding="utf-8")
    return f"lab/{name}@1.0.0"


def _write(folder: Path, manifest: SkillManifest | WorkflowManifest) -> Path:
    identity = manifest.metadata.identity
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{identity.namespace}__{identity.name}__{identity.version}.json"
    path.write_text(manifest.model_dump_json(), encoding="utf-8")
    return path


def test_switching_a_workflow_off_and_on_moves_its_file_and_the_live_offer(
    tmp_path: Path,
) -> None:
    config, layout = ready(tmp_path)
    reference = _local_workflow(layout)
    identity = AssetIdentity(namespace="lab", name="local-check", version="1.0.0")
    with build_runtime(config) as runtime:
        web = AgentWeb(runtime)
        engine = runtime.agent.gateway.engine
        assert engine.workflows.get(identity) is not None
        listed = web.assets()
        [local] = [w for w in listed["workflows"] if w["name"] == "local-check"]
        assert local["shipped"] is False and listed["disabled"] == []

        off = web.switch_asset("workflow", reference, False)
        assert off["ok"] is True and "disabled" in off["message"], off
        assert not (layout.workflows / "lab__local-check__1.0.0.json").exists()
        assert (layout.workflows / "disabled" / "lab__local-check__1.0.0.json").is_file()
        assert engine.workflows.get(identity) is None  # no longer offered, no restart
        listed = web.assets()
        assert "local-check" not in [w["name"] for w in listed["workflows"]]
        assert [(d["kind"], d["name"]) for d in listed["disabled"]] == [
            ("workflow", "local-check")]
        assert web.switch_asset("workflow", reference, False)["code"] == "not_installed"

        on = web.switch_asset("workflow", reference, True)
        assert on["ok"] is True
        assert (layout.workflows / "lab__local-check__1.0.0.json").is_file()
        assert engine.workflows.get(identity) is not None
        assert web.assets()["disabled"] == []
        assert web.switch_asset("workflow", reference, True)["code"] == "not_disabled"
        assert web.switch_asset("knowledge", reference, False)["code"] == "kind_not_removable"
        assert web.switch_asset("workflow", "not a reference", False)["code"] == "bad_reference"


def test_a_skill_is_not_switched_on_beside_another_version_of_its_alias(
    tmp_path: Path,
) -> None:
    config, layout = ready(tmp_path)
    skill = next(item for item in shipped() if isinstance(item, SkillManifest))
    _write(layout.skills, skill)
    identity = skill.metadata.identity
    older = skill.model_copy(update={"metadata": skill.metadata.model_copy(update={
        "identity": identity.model_copy(update={"version": "0.0.1"})})})
    _write(layout.skills / "disabled", older)
    with build_runtime(config) as runtime:
        web = AgentWeb(runtime)
        reference = f"{identity.namespace}/{identity.name}@0.0.1"
        # A superseded version set aside in disabled/ is listed as switched off.
        [listed] = web.assets()["disabled"]
        assert (listed["kind"], listed["version"]) == ("skill", "0.0.1")
        refused = web.switch_asset("skill", reference, True)
        assert refused["code"] == "alias_in_use" and "one" in refused["message"]
        assert (layout.skills / "disabled" / f"{identity.namespace}__{identity.name}__0.0.1"
                ".json").is_file()

        current = f"{identity.namespace}/{identity.name}@{identity.version}"
        skills = runtime.agent.gateway.router.commands.skills
        assert skills.get(identity.namespace, skill.alias) is not None
        assert web.switch_asset("skill", current, False)["ok"] is True
        assert skills.get(identity.namespace, skill.alias) is None
        assert web.switch_asset("skill", reference, True)["ok"] is True


def test_removing_moves_the_file_to_a_dated_folder_and_refuses_shipped_assets(
    tmp_path: Path,
) -> None:
    config, layout = ready(tmp_path)
    reference = _local_workflow(layout)
    shipped_workflow = next(item for item in shipped() if isinstance(item, WorkflowManifest))
    shipped_path = _write(layout.workflows, shipped_workflow)
    shipped_identity = shipped_workflow.metadata.identity
    shipped_reference = (f"{shipped_identity.namespace}/{shipped_identity.name}"
                         f"@{shipped_identity.version}")
    assert ("workflow", *shipped_identity.key) in shipped_keys()
    with build_runtime(config) as runtime:
        web = AgentWeb(runtime)
        [flag] = [w["shipped"] for w in web.assets()["workflows"]
                  if w["name"] == shipped_identity.name]
        assert flag is True

        refused = web.remove_asset("workflow", shipped_reference)
        assert refused["ok"] is False and refused["code"] == "shipped_asset"
        assert "export-assets" in refused["message"] and "Switch it off" in refused["message"]
        assert shipped_path.is_file()
        # It can still be switched off, and stays refused while off.
        assert web.switch_asset("workflow", shipped_reference, False)["ok"] is True
        assert web.remove_asset("workflow", shipped_reference)["code"] == "shipped_asset"

        removed = web.remove_asset("workflow", reference)
        assert removed["ok"] is True, removed
        assert removed["still_selected"] is False and removed["inventory_forgotten"] is False
        assert not (layout.workflows / "lab__local-check__1.0.0.json").exists()
        [kept] = list((layout.workspace_root / "removed").glob("*/workflows/*.json"))
        assert kept.name == "lab__local-check__1.0.0.json"
        assert removed["kept_at"] in removed["message"].replace("workspace\\", "")
        WorkflowManifest.model_validate_json(kept.read_text(encoding="utf-8"))  # intact
        [line] = (layout.workspace_root / "removed" / JOURNAL).read_text(
            encoding="utf-8").splitlines()
        record = json.loads(line)
        assert record["asset"] == reference and record["actor"] == runtime.actor
        assert record["to"].endswith("lab__local-check__1.0.0.json")
        assert runtime.agent.gateway.engine.workflows.get(AssetIdentity(
            namespace="lab", name="local-check", version="1.0.0")) is None
        assert "local-check" not in [w["name"] for w in web.assets()["workflows"]]
        assert web.remove_asset("workflow", reference)["code"] == "not_installed"

        # The same version installed and removed again the same day keeps both.
        _local_workflow(layout)
        assert web.remove_asset("workflow", reference)["ok"] is True
        assert len(list((layout.workspace_root / "removed").glob("*/workflows/*.json"))) == 2


def _published(app: SharedPlatformApplication, visibility: str = "organization") -> None:
    portal = app.member_base_url + "/v1/member/"
    leo = _signed_in(app, "leo", "member")
    admin = _signed_in(app, "leo-admin", "platform_admin")
    status, submitted = request(portal + "assets/submit", authorization=leo, body={
        "kind": "workflow", "change": "minor", "visibility": visibility,
        "manifest": workflow_manifest()})
    assert status == 200, submitted
    assert request(portal + "admin/submissions/approve", authorization=admin, body={
        "submission_id": submitted["submission"]["submission_id"],
        "evidence": "read it"})[0] == 200


def test_add_to_this_agent_selects_as_the_member_syncs_and_removal_is_consistent(
    app: SharedPlatformApplication, tmp_path: Path,
) -> None:
    _published(app)
    path, layout = _host(tmp_path)
    grants = layout.grants.read_bytes()
    engineer = _signed_in(app, "engineer", "member")
    with build_runtime(CompanyHostConfiguration.model_validate_json(
            path.read_text("utf-8")), layout=layout) as runtime:
        web = _web(runtime, path, {})
        assert web.update_shared_platform(_card(app, _agent_login(app, engineer)))["ok"]
        [entry] = [i for i in web.platform()["catalog"] if i["name"] == "weekly-check"]
        assert entry["provenance"] and all(isinstance(p, str) for p in entry["provenance"])

        added = web.add_to_agent("workflow", REFERENCE)
        assert added["ok"] is True and added["installed"] is True, added
        assert added["assets_only"] is True and "grants.json" in added["message"]
        assert "now selected" in added["message"]
        assert added["sync"]["installed"] == [IDENTITY]
        installed = layout.workflows / "lab__weekly-check__1.0.0.json"
        assert installed.is_file() and layout.grants.read_bytes() == grants
        assert not layout.authorization.exists()
        assert [item.identity.name for item in runtime.state.installed()] == ["weekly-check"]
        # Pressing it again is not an error.
        again = web.add_to_agent("workflow", REFERENCE)
        assert again["ok"] is True and "already selected" in again["message"]

        # Removing a synced asset: recoverable, out of the inventory, and the
        # page is told it is still selected (a sync would install it again).
        removed = web.remove_asset("workflow", REFERENCE)
        assert removed["ok"] is True and removed["inventory_forgotten"] is True
        assert removed["still_selected"] is True and "Remove selection" in removed["message"]
        assert runtime.state.installed() == () and not installed.exists()
        [entry] = [i for i in web.platform()["catalog"] if i["name"] == "weekly-check"]
        assert entry["installed"] is False and entry["authorized"] is True

        dropped = web.remove_selection("workflow", REFERENCE)
        assert dropped["ok"] is True and dropped["selected"] is False, dropped
        [entry] = [i for i in web.platform()["catalog"] if i["name"] == "weekly-check"]
        assert entry["authorized"] is False
        assert web.remove_selection("workflow", REFERENCE)["code"] == "selection_missing"

        # Added again after removal, the verified sync installs the same bytes.
        assert web.add_to_agent("workflow", REFERENCE)["installed"] is True
        package = app.state.packages.get(AssetIdentity(**IDENTITY))
        assert package is not None and package.metadata.package is not None
        assert installed.read_bytes() == app.state.artifacts[
            package.metadata.package.artifact_ref]
        listed_tasks = json.dumps(web.task_list())
        assert "Add lab/weekly-check@1.0.0 to this Agent" in listed_tasks


def test_add_to_this_agent_explains_what_is_missing(
    app: SharedPlatformApplication, tmp_path: Path,
) -> None:
    _published(app)
    # No shared platform at all.
    config, layout = ready(tmp_path / "bare")
    with build_runtime(config) as runtime:
        refused = AgentWeb(runtime).add_to_agent("workflow", REFERENCE)
        assert refused["code"] == "platform_not_configured"
        assert "Settings > Shared platform" in refused["message"]
        assert AgentWeb(runtime).add_to_agent("workflow", "x")["code"] == "bad_reference"

    path, layout = _host(tmp_path)
    with build_runtime(CompanyHostConfiguration.model_validate_json(
            path.read_text("utf-8")), layout=layout) as runtime:
        web = _web(runtime, path, {})
        # The old platform, no publishing configured yet.
        assert web.add_to_agent("workflow", REFERENCE)["code"] == "publishing_not_configured"
        # Portal set, but no Personal Agent code on this PC.
        assert web.update_shared_platform(_card(app, enroll=False))["ok"]
        missing = web.add_to_agent("workflow", REFERENCE)
        assert missing["code"] == "login_missing" and "Personal Agent code" in missing["message"]
        # A code, but this PC is not enrolled for that member.
        engineer = _signed_in(app, "engineer", "member")
        assert web.update_shared_platform(
            _card(app, _agent_login(app, engineer), enroll=False))["ok"]
        assert runtime.platform is not None
        assert runtime.platform.binding.token_id == OLD_PLATFORM["token_id"]
        unenrolled = web.add_to_agent("workflow", REFERENCE)
        assert unenrolled["code"] == "actor_not_admitted"
        assert "Enroll this PC" in unenrolled["message"]
        # The portal stops answering (a dropped tunnel).
        assert web.update_shared_platform({**_card(app, enroll=False),
                                           "member_portal_url": "http://127.0.0.1:9"})["ok"]
        gone = web.add_to_agent("workflow", REFERENCE)
        assert gone["code"] == "platform_unreachable" and "Settings" in gone["message"]
        assert not (layout.workflows / "lab__weekly-check__1.0.0.json").exists()


def test_the_routes_need_the_token_and_a_named_asset(tmp_path: Path) -> None:
    import threading

    from test_agent_web import base, fetch

    from host_runtime.web import AgentWebServer

    config, layout = ready(tmp_path)
    reference = _local_workflow(layout)
    host_json(tmp_path, config)
    with build_runtime(config) as runtime:
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = base(server)
            for route in ("/api/assets/switch", "/api/assets/remove", "/api/platform/add",
                          "/api/platform/unselect"):
                assert fetch(url + route, body={}).status == 401
                assert fetch(url + route, token=server.token, body={"kind": "workflow"}
                             ).status == 400
            switched: Any = fetch(url + "/api/assets/switch", token=server.token, body={
                "kind": "workflow", "asset": reference, "enabled": False}).json()
            assert switched["ok"] is True
            removed: Any = fetch(url + "/api/assets/remove", token=server.token, body={
                "kind": "workflow", "asset": reference}).json()
            assert removed["ok"] is True and "removed" in removed["kept_at"]
            unconfigured: Any = fetch(url + "/api/platform/add", token=server.token, body={
                "kind": "workflow", "asset": reference}).json()
            assert unconfigured["code"] == "platform_not_configured"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
