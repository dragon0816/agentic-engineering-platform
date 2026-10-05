"""`fn:` choice sources: read-only host functions over a Workflow's own settings.

Workflow 14's station menu is a property of the install (the catalogue file its
settings name), not something a run published, so it comes from a function
that reads those settings. The engine, Telegram and Agent Web resolve it the
same way they resolve `ref:` sets.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from test_gateway import Handler, Probe, Report, capability_spec, request, workflow_manifest
from test_workflow_parameter_declaration import _manifest

from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from channels import telegram_flow as flow
from common.assets import ExecutionDependencies, WorkflowManifest
from host_runtime import host as host_module
from host_runtime.choice_sources import ChoiceSources, FunctionQuery
from host_runtime.reference_sets import REFERENCE_SETS_FILE, ReferenceItem, ReferenceSetStore
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

SOURCE = "fn:test.stations?region={region}"


def _stations(settings: Mapping[str, Any], arguments: Mapping[str, str]) -> list[ReferenceItem]:
    catalogue = Path(str(settings["catalogue"]))
    rows = [line.split(",") for line in catalogue.read_text(encoding="utf-8").splitlines()]
    return [
        ReferenceItem(value=name, label=f"{name} ({region})")
        for name, region in rows if region == arguments["region"]
    ]


def _catalogue(tmp_path: Path) -> Path:
    path = tmp_path / "stations.csv"
    path.write_text("公館站,east\n四條溝站,north\n東清站,east\n", encoding="utf-8")
    return path


def _sources(tmp_path: Path, settings: dict[str, Any]) -> ChoiceSources:
    return ChoiceSources(
        ReferenceSetStore(tmp_path / REFERENCE_SETS_FILE),
        lambda _manifest: settings,
        {"test.stations": _stations},
    )


def _with_station_field() -> WorkflowManifest:
    return _manifest([
        {"name": "region", "label": "Region", "kind": "text", "required": True, "order": 1},
        {"name": "station", "label": "Station", "kind": "select", "required": True,
         "order": 2, "choices_source": SOURCE, "needs": ["region"]},
    ])


def test_a_function_reads_the_settings_and_the_bound_arguments(tmp_path: Path) -> None:
    manifest = _with_station_field()
    sources = _sources(tmp_path, {"catalogue": str(_catalogue(tmp_path))})
    assert FunctionQuery(SOURCE).needed() == ("region",)
    assert ChoiceSources.needed(SOURCE) == ("region",)
    assert sources.resolve(manifest, SOURCE, {}) is None              # waiting for region
    assert sources.values(manifest, SOURCE, {"region": "east"}) == ["公館站", "東清站"]
    assert sources.resolve(manifest, "fn:unknown.function", {}) is None
    # A function that cannot read its settings is "unavailable", not a crash.
    missing = _sources(tmp_path, {"catalogue": str(tmp_path / "absent.csv")})
    assert missing.resolve(manifest, SOURCE, {"region": "east"}) is None
    unset = _sources(tmp_path, {})
    assert unset.resolve(manifest, SOURCE, {"region": "east"}) is None


def _engine(tmp_path: Path, handler: Handler, functions: dict[str, Any]) -> tuple[
    WorkflowEngine, Any
]:
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
    data["parameters"] = [
        {"name": "args", "label": "Station", "kind": "select",
         "choices_source": "fn:test.stations?region=east"},
    ]
    manifest = WorkflowManifest.model_validate(data)
    workflows = InstalledWorkflows()
    workflows.register(manifest)
    sources = ChoiceSources(
        ReferenceSetStore(tmp_path / REFERENCE_SETS_FILE),
        lambda _manifest: {"catalogue": str(_catalogue(tmp_path))},
        functions,
    )
    return (
        WorkflowEngine(workflows, bridge, choices_provider=sources.values),
        manifest.metadata.identity,
    )


def test_the_engine_accepts_only_a_value_the_function_offers(tmp_path: Path) -> None:
    handler = Handler()
    engine, identity = _engine(tmp_path, handler, {})
    unknown = asyncio.run(engine.execute(request("run"), identity, {"args": "公館站"}))
    assert unknown.run.failure is not None
    assert unknown.run.failure.code == "choice_function_unavailable"
    engine, identity = _engine(tmp_path, handler, {"test.stations": _stations})
    outside = asyncio.run(engine.execute(request("run"), identity, {"args": "四條溝站"}))
    assert outside.run.failure is not None
    assert outside.run.failure.code == "workflow_choice_unavailable"
    assert handler.calls == 0
    ran = asyncio.run(engine.execute(request("run"), identity, {"args": "東清站"}))
    assert ran.run.status == "succeeded" and handler.calls == 1


def test_telegram_offers_function_choices_as_buttons(tmp_path: Path) -> None:
    sources = _sources(tmp_path, {"catalogue": str(_catalogue(tmp_path))})
    state = flow.start(_with_station_field(), "read", sources.values)
    assert isinstance(state, flow.FlowState)
    flow.begin(state)
    station = flow.answer(state, "east")
    assert station.prompt is not None
    assert station.prompt.buttons == [[("公館站", "公館站"), ("東清站", "東清站")]]
    done = flow.answer(state, "東清站")
    assert done.kind == "ready" and done.arguments == {"region": "east", "station": "東清站"}


def test_agent_web_resolves_function_choices_for_the_form(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_agent_web import base, fetch
    from test_conversation_turn_groups import _chat_config, _ChatGateway

    from capabilities.weekly_report.manifest import preview_workflow
    from host_runtime.host import build_runtime
    from host_runtime.web import AgentWeb, AgentWebServer
    from host_runtime.workflow_settings import SETTINGS_FILE, WorkflowSettingsStore

    monkeypatch.setitem(host_module.CHOICE_FUNCTIONS, "test.stations", _stations)
    data = preview_workflow().model_dump(mode="json")
    data["parameters"] = [
        {"name": "catalogue", "label": "Catalogue", "kind": "file", "scope": "static"},
        {"name": "region", "label": "Region", "kind": "text", "order": 1},
        {"name": "station", "label": "Station", "kind": "select", "order": 2,
         "choices_source": SOURCE},
    ]
    manifest = WorkflowManifest.model_validate(data)
    identity = manifest.metadata.identity.model_dump(mode="json")
    config, layout = _chat_config(tmp_path)
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        (runtime.layout.workflows / "with-function.json").write_text(
            manifest.model_dump_json(), encoding="utf-8"
        )
        WorkflowSettingsStore(runtime.layout.workspace_root / SETTINGS_FILE).save(
            manifest.metadata.identity, {"catalogue": str(_catalogue(tmp_path))}
        )
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = base(server) + "/api/workflow-options"
            body = {"workflow": identity, "field": "station", "answers": {}}
            assert fetch(url, token=server.token, body=body).json()["waiting_for"] == ["region"]
            chosen = fetch(url, token=server.token, body={
                **body, "answers": {"region": "north"},
            }).json()
            assert chosen["choices"] == [{"value": "四條溝站", "label": "四條溝站 (north)"}]
            monkeypatch.delitem(host_module.CHOICE_FUNCTIONS, "test.stations")
            gone = fetch(url, token=server.token, body={
                **body, "answers": {"region": "north"},
            }).json()
            assert gone["unavailable"] is True and gone["set"] == "test.stations"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
