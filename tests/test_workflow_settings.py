"""Per-install Workflow settings (slice S5): set once, merged into every run."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from test_gateway import Handler, Probe, Report, capability_spec, request, workflow_manifest
from test_workflow_parameter_declaration import _manifest

from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from common.assets import AssetIdentity, ExecutionDependencies, WorkflowManifest
from common.workflow_forms import form_fields, settings_fields
from common.workflow_parameters import WorkflowParameterError, validate_static_settings
from host_runtime.web_page import PAGE
from host_runtime.workflow_settings import (
    SETTINGS_FILE,
    WorkflowSettingsError,
    WorkflowSettingsStore,
)
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

SETTINGS = [
    {"name": "reference_dir", "label": "Reference folder", "kind": "folder",
     "scope": "static", "required": True, "order": 1},
    {"name": "region", "label": "Region", "kind": "select", "scope": "static",
     "options": ["tw", "cn"], "default": "tw", "order": 2},
    {"name": "project", "label": "Project", "kind": "text", "required": True},
]


def test_settings_are_never_run_fields_and_have_their_own_form() -> None:
    manifest = _manifest(SETTINGS)
    assert [field["name"] for field in form_fields(manifest, "web")] == ["project"]
    assert [field["name"] for field in settings_fields(manifest)] == ["reference_dir", "region"]


def test_static_settings_validation_applies_defaults_and_completeness() -> None:
    manifest = _manifest(SETTINGS)
    assert validate_static_settings(manifest, {}, complete=False) == {"region": "tw"}
    with pytest.raises(WorkflowParameterError, match="reference_dir is required"):
        validate_static_settings(manifest, {}, complete=True)
    assert validate_static_settings(
        manifest, {"reference_dir": "D:/ref"}, complete=True
    ) == {"reference_dir": "D:/ref", "region": "tw"}
    for bad in ({"project": "x"}, {"region": "eu"}, {"reference_dir": ""}):
        with pytest.raises(WorkflowParameterError):
            validate_static_settings(manifest, bad, complete=False)


def test_store_keys_by_workflow_name_and_refuses_credentials(tmp_path: Path) -> None:
    store = WorkflowSettingsStore(tmp_path / SETTINGS_FILE)
    v1 = AssetIdentity(namespace="engineering", name="release", version="1.0.0")
    v2 = v1.model_copy(update={"version": "2.0.0"})
    store.save(v1, {"reference_dir": "D:/ref"})
    assert store.values(v2) == {"reference_dir": "D:/ref"}   # kept across upgrades
    with pytest.raises(WorkflowSettingsError, match="credentials"):
        store.save(v1, {"password": "hunter2"})
    (tmp_path / SETTINGS_FILE).write_text("{broken", encoding="utf-8")
    with pytest.raises(WorkflowSettingsError):
        store.values(v1)


def _engine(handler: Handler, provider: Any) -> tuple[WorkflowEngine, WorkflowManifest]:
    installed = InstalledCapabilities()
    installed.register(
        capability_spec(), handler, Probe, Report, ExecutionDependencies(central_required=False)
    )
    bridge = BridgeExecutor(installed, LocalPolicy((CapabilityGrant.model_validate({
        "actor": "engineer", "asset": capability_spec().identity,
        "permissions": ["engineering.validate"], "policy_refs": ["release-policy"],
        "approval_ref": "release-approval",
    }),)))
    data = workflow_manifest().model_dump(mode="json")
    # The test step's input is `args`; here it is a per-install setting.
    data["parameters"] = [
        {"name": "args", "label": "Checkout folder", "kind": "text", "scope": "static",
         "required": True},
    ]
    manifest = WorkflowManifest.model_validate(data)
    workflows = InstalledWorkflows()
    workflows.register(manifest)
    return WorkflowEngine(workflows, bridge, settings_provider=provider), manifest


def test_engine_merges_settings_and_stops_a_run_without_them() -> None:
    handler = Handler()
    engine, manifest = _engine(handler, lambda _manifest: {})
    identity = manifest.metadata.identity
    missing = asyncio.run(engine.execute(request("run"), identity, {}))
    assert missing.run.status == "needs_input"
    assert missing.run.failure is not None
    assert missing.run.failure.code == "workflow_settings_incomplete"
    assert handler.calls == 0
    supplied = asyncio.run(engine.execute(request("run"), identity, {"args": "C:/repo"}))
    assert supplied.run.failure is not None
    assert supplied.run.failure.code == "workflow_setting_supplied_by_run"

    configured, _ = _engine(handler, lambda _manifest: {"args": "C:/repo"})
    ran = asyncio.run(configured.execute(request("run"), identity, {}))
    assert ran.run.status == "succeeded" and handler.calls == 1

    def unreadable(_manifest: WorkflowManifest) -> dict[str, Any]:
        raise WorkflowSettingsError("workflow settings file is unreadable")

    broken, _ = _engine(handler, unreadable)
    failed = asyncio.run(broken.execute(request("run"), identity, {}))
    assert failed.run.failure is not None
    assert failed.run.failure.code == "workflow_settings_unavailable"


def test_settings_are_shown_with_the_workflow_in_capabilities_and_are_safe() -> None:
    for expected in (
        'id="workflow-settings-list"', 'call("/api/settings/workflows")',
        '"/api/settings/workflows"', "renderParameterForm(form, fields, prefix)",
        "loadWorkflowSettings(item);",
    ):
        assert expected in PAGE, expected
    # Owner, 2026-10-06: they live with the Workflow, not on the Settings page.
    settings = PAGE.split('<section id="panel-settings">', 1)[1].split("</section>", 1)[0]
    installed = PAGE.split('<section id="panel-installed">', 1)[1].split("</section>", 1)[0]
    assert "workflow-settings" not in settings and 'id="workflow-settings"' in installed
    script = PAGE.split("<script>", 1)[1].split("</script>", 1)[0]
    section = script.split("// -- Workflow settings", 1)[1].split(
        "// -- end Workflow settings", 1
    )[0]
    for unsafe in ("innerHTML", "insertAdjacentHTML", "outerHTML"):
        assert unsafe not in section


def test_agent_web_lists_saves_and_refuses_settings(tmp_path: Path) -> None:
    import threading

    from test_agent_web import base, fetch
    from test_conversation_turn_groups import _chat_config, _ChatGateway

    from capabilities.weekly_report.manifest import preview_workflow
    from host_runtime.host import build_runtime
    from host_runtime.web import AgentWeb, AgentWebServer

    data = preview_workflow().model_dump(mode="json")
    data["parameters"] = [*data["parameters"], *SETTINGS[:2]]
    manifest = WorkflowManifest.model_validate(data)
    identity = manifest.metadata.identity.model_dump(mode="json")
    config, layout = _chat_config(tmp_path)
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        (runtime.layout.workflows / "with-settings.json").write_text(
            manifest.model_dump_json(), encoding="utf-8"
        )
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = base(server) + "/api/settings/workflows"
            listed = fetch(url, token=server.token).json()
            entry = next(item for item in listed["workflows"] if item["workflow"] == identity)
            assert [field["name"] for field in entry["fields"]] == ["reference_dir", "region"]
            assert entry["missing"] == ["reference_dir"]
            assert fetch(url, body={"workflow": identity, "values": {}}).status == 401
            refused = fetch(url, token=server.token, body={
                "workflow": identity, "values": {"region": "eu"},
            })
            assert refused.status == 400 and refused.json()["code"] == "workflow_settings_invalid"
            assert fetch(url, token=server.token, body={
                "workflow": identity, "values": {"reference_dir": "password=hunter2"},
            }).status == 400
            saved = fetch(url, token=server.token, body={
                "workflow": identity, "values": {"reference_dir": "D:/ref"},
            }).json()
            assert saved["ok"] is True and saved["workflow"]["missing"] == []
            # The engine reads the same file on the next run.
            engine = runtime.agent.gateway.engine
            assert engine.settings_provider is not None
            assert engine.settings_provider(manifest) == {"reference_dir": "D:/ref"}
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
