"""Agent Web forms v2 (owner 2026-10-15): the upload and "last values" routes,
folder lists bound from settings, and the page's pick-or-type and upload
controls."""

from __future__ import annotations

import base64
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import base, fetch

from common.assets import WorkflowManifest
from host_runtime.identity_presets import IdentityPresets
from host_runtime.web_page import PAGE
from host_runtime.workflow_settings import SETTINGS_FILE, WorkflowSettingsStore

FIELDS: list[dict[str, Any]] = [
    {"name": "inbox_path", "label": "Inbox", "kind": "folder", "scope": "static"},
    {"name": "company", "label": "Company", "kind": "text", "group": "identity"},
    {"name": "plans", "label": "Plans", "kind": "select", "multiple": True,
     "choices_source": "fn:folder_files?folder={inbox_path}&accept=.json"},
    {"name": "package", "label": "Plan file", "kind": "upload", "accept": [".json"]},
]


@pytest.fixture
def served(tmp_path: Path) -> Iterator[tuple[Any, Any, WorkflowManifest, Path]]:
    from test_conversation_turn_groups import _chat_config, _ChatGateway

    from capabilities.weekly_report.manifest import preview_workflow
    from host_runtime.host import build_runtime
    from host_runtime.web import AgentWeb, AgentWebServer

    data = preview_workflow().model_dump(mode="json")
    data["metadata"]["identity"]["name"] = "forms-v2"
    data["parameters"] = FIELDS
    manifest = WorkflowManifest.model_validate(data)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "plan.json").write_text("{}", encoding="utf-8")
    (inbox / "readme.txt").write_text("x", encoding="utf-8")
    config, layout = _chat_config(tmp_path)
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        (runtime.layout.workflows / "forms-v2.json").write_text(
            manifest.model_dump_json(), encoding="utf-8")
        WorkflowSettingsStore(runtime.layout.workspace_root / SETTINGS_FILE).save(
            manifest.metadata.identity, {"inbox_path": str(inbox)})
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server, runtime, manifest, inbox
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def _upload(server: Any, manifest: WorkflowManifest, field: str, name: str,
            data: bytes, upload_set: str = "") -> Any:
    return fetch(base(server) + "/api/workflow-uploads", token=server.token, body={
        "workflow": manifest.metadata.identity.model_dump(mode="json"), "field": field,
        "upload_set": upload_set, "filename": name,
        "data": base64.b64encode(data).decode("ascii"),
    })


def test_uploads_are_stored_per_set_and_checked_against_the_field(served: Any) -> None:
    server, runtime, manifest, _ = served
    saved = _upload(server, manifest, "package", "plan.json", b"{}").json()
    assert saved["ok"] is True and saved["upload_set"].startswith("up-")
    stored = Path(saved["path"])
    assert stored.read_bytes() == b"{}"
    assert stored.is_relative_to((runtime.layout.workspace_root / "workflow-uploads").resolve())
    refused = _upload(server, manifest, "package", "tool.exe", b"MZ")
    assert refused.status == 400 and refused.json()["code"] == "upload_type_not_accepted"
    assert _upload(server, manifest, "company", "plan.json", b"{}").json()["code"] == (
        "workflow_field_unknown")
    assert _upload(server, manifest, "package", "plan.json", b"{}", "../../x").json()[
        "code"] == "upload_set_invalid"
    unauthenticated = fetch(base(server) + "/api/workflow-uploads", body={})
    assert unauthenticated.status == 401


def test_folder_choices_come_from_the_setting_and_never_wait_for_it(served: Any) -> None:
    server, _, manifest, _ = served
    listed = fetch(base(server) + "/api/workflow-options", token=server.token, body={
        "workflow": manifest.metadata.identity.model_dump(mode="json"), "field": "plans",
        "answers": {"inbox_path": "C:/elsewhere"},
    }).json()
    assert listed["choices"] == [{"value": "plan.json", "label": "plan.json"}]


def test_a_launched_run_remembers_the_identity_for_next_time(served: Any) -> None:
    server, runtime, manifest, _ = served
    identity = manifest.metadata.identity.model_dump(mode="json")
    url = base(server) + "/api/workflow-identity"
    assert fetch(url, token=server.token, body={"workflow": identity}).json() == {
        "ok": True, "values": {}}
    IdentityPresets(runtime.layout.workspace_root).remember(
        runtime.actor, manifest, {"company": "Foxconn"})
    assert fetch(url, token=server.token, body={"workflow": identity}).json()["values"] == {
        "company": "Foxconn"}
    unknown = {**identity, "name": "not-installed"}
    assert fetch(url, token=server.token, body={"workflow": unknown}).status == 404


def test_launch_records_presets_through_the_web_layer(served: Any) -> None:
    server, runtime, manifest, _ = served
    web = server.web
    from host_runtime.contracts import WorkflowLaunchRequest

    web.launch_workflow(WorkflowLaunchRequest(
        workflow=manifest.metadata.identity, arguments={"company": "Quanta"},
        idempotency_key="forms-v2-launch-1"))
    assert IdentityPresets(runtime.layout.workspace_root).last(runtime.actor, manifest) == {
        "company": "Quanta"}


def _script() -> str:
    return PAGE.split("<script>", 1)[1].split("</script>", 1)[0]


def test_the_page_draws_fn_lists_combo_boxes_uploads_and_last_values() -> None:
    script = _script()
    dynamic = script.split("function isDynamicChoice(field)", 1)[1].split("\n}\n", 1)[0]
    assert '"fn:"' in dynamic and '"ref:"' in dynamic
    combo = script.split("function comboControl(field, id)", 1)[1].split("\n}\n", 1)[0]
    assert 'createElement("datalist")' in combo and "Refresh list" in combo
    upload = script.split("function wireUpload(input, field, context)", 1)[1].split(
        "\n}\n", 1)[0]
    assert "/api/workflow-uploads" in upload
    assert "/api/workflow-identity" in script
    collect = script.split("function collectParameterValues(", 1)[1].split("\n}\n", 1)[0]
    assert "Wait for the upload to finish." in collect
    # The schedule form has nobody to upload: only the run form asks for files.
    contract = script.split("function showWorkflowContract()", 1)[1].split("\n}\n", 1)[0]
    schedule = script.split("function showScheduleTargetFields()", 1)[1].split("\n}\n", 1)[0]
    assert "uploads: true" in contract and "uploads: true" not in schedule
    section = script.split("// -- Parameter forms", 1)[1].split("// -- end Parameter forms", 1)[0]
    for unsafe in ("innerHTML", "insertAdjacentHTML", "outerHTML"):
        assert unsafe not in section
