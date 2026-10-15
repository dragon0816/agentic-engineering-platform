"""Published reference sets behind `ref:` choices (slice S6a)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_gateway import Handler, Probe, Report, capability_spec, request, workflow_manifest
from test_workflow_parameter_declaration import _manifest

from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from channels import telegram_flow as flow
from common.assets import ExecutionDependencies, WorkflowManifest
from host_runtime.reference_sets import (
    REFERENCE_SETS_FILE,
    ReferenceQuery,
    ReferenceSetStore,
    publish_values,
)
from host_runtime.web_page import PAGE
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

VERSIONS = [
    {"value": "2.0.18", "tags": {"chipset": "kt326"}},
    {"value": "2.0.19", "tags": {"chipset": "kt326"}},
    {"value": "1.4.0", "label": "1.4.0 (legacy)", "tags": {"chipset": "kt100"}},
]


def _store(tmp_path: Path) -> ReferenceSetStore:
    store = ReferenceSetStore(tmp_path / REFERENCE_SETS_FILE)
    publish_values(store, "chipsets", ["kt326", "kt100"], published_by="workflow-12")
    publish_values(store, "packageVersions", VERSIONS, published_by="workflow-12")
    return store


def test_sets_are_published_replaced_and_filtered_by_earlier_answers(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert [item.value for item in store.resolve("ref:chipsets", {}) or []] == ["kt326", "kt100"]
    query = "ref:packageVersions?chipset={chipset}"
    assert ReferenceQuery(query).needed() == ("chipset",)
    assert store.resolve(query, {}) is None  # waiting for the chipset
    assert [item.value for item in store.resolve(query, {"chipset": "kt326"}) or []] == [
        "2.0.18",
        "2.0.19",
    ]
    assert store.resolve("ref:unpublished", {}) is None
    publish_values(store, "chipsets", ["kt999"], published_by="workflow-12")
    assert [item.value for item in store.resolve("ref:chipsets", {}) or []] == ["kt999"]
    with pytest.raises((ValidationError, ValueError)):
        publish_values(store, "chipsets", ["password=hunter2"], published_by="x")


def _engine(handler: Handler, store: ReferenceSetStore | None) -> tuple[WorkflowEngine, Any]:
    installed = InstalledCapabilities()
    installed.register(
        capability_spec(), handler, Probe, Report, ExecutionDependencies(central_required=False)
    )
    bridge = BridgeExecutor(
        installed,
        LocalPolicy(
            (
                CapabilityGrant.model_validate(
                    {
                        "actor": "engineer",
                        "asset": capability_spec().identity,
                        "permissions": ["engineering.validate"],
                        "policy_refs": ["release-policy"],
                        "approval_ref": "release-approval",
                    }
                ),
            )
        ),
    )
    data = workflow_manifest().model_dump(mode="json")
    data["parameters"] = [
        {"name": "args", "label": "Chipset", "kind": "select", "choices_source": "ref:chipsets"},
    ]
    manifest = WorkflowManifest.model_validate(data)
    workflows = InstalledWorkflows()
    workflows.register(manifest)

    def choices(_manifest: Any, source: str, answers: Any) -> list[str] | None:
        found = None if store is None else store.resolve(source, answers)
        return None if found is None else [item.value for item in found]

    return WorkflowEngine(workflows, bridge, choices_provider=choices), manifest.metadata.identity


def test_engine_accepts_only_a_currently_published_choice(tmp_path: Path) -> None:
    handler = Handler()
    engine, identity = _engine(handler, None)
    missing = asyncio.run(engine.execute(request("run"), identity, {"args": "kt326"}))
    assert missing.run.failure is not None
    assert missing.run.failure.code == "reference_set_unavailable"
    engine, identity = _engine(handler, _store(tmp_path))
    stale = asyncio.run(engine.execute(request("run"), identity, {"args": "kt000"}))
    assert stale.run.failure is not None
    assert stale.run.failure.code == "workflow_choice_unavailable"
    assert handler.calls == 0
    ran = asyncio.run(engine.execute(request("run"), identity, {"args": "kt326"}))
    assert ran.run.status == "succeeded" and handler.calls == 1


def test_telegram_offers_published_choices_as_buttons(tmp_path: Path) -> None:
    store = _store(tmp_path)

    def choices(_manifest: Any, source: str, answers: Any) -> list[str] | None:
        found = store.resolve(source, answers)
        return None if found is None else [item.value for item in found]

    state = flow.start(
        _manifest(
            [
                {
                    "name": "chipset",
                    "label": "Chipset",
                    "kind": "select",
                    "required": True,
                    "order": 1,
                    "choices_source": "ref:chipsets",
                },
                {
                    "name": "version",
                    "label": "Version",
                    "kind": "select",
                    "required": True,
                    "order": 2,
                    "choices_source": "ref:packageVersions?chipset={chipset}",
                    "needs": ["chipset"],
                },
            ]
        ),
        "read",
        choices,
    )
    assert isinstance(state, flow.FlowState)
    first = flow.begin(state)
    assert first.prompt is not None
    assert first.prompt.buttons == [[("kt326", "kt326"), ("kt100", "kt100")]]
    refused = flow.answer(state, "kt555").prompt
    assert refused is not None
    assert "choose one" in (refused.text or "")
    second = flow.answer(state, "kt326")
    assert second.prompt is not None
    assert second.prompt.buttons == [[("2.0.18", "2.0.18"), ("2.0.19", "2.0.19")]]
    done = flow.answer(state, "2")  # by position
    assert done.kind == "ready" and done.arguments == {"chipset": "kt326", "version": "2.0.19"}


def test_agent_web_resolves_choices_for_the_form(tmp_path: Path) -> None:
    import threading

    from test_agent_web import base, fetch
    from test_conversation_turn_groups import _chat_config, _ChatGateway

    from capabilities.weekly_report.manifest import preview_workflow
    from host_runtime.host import build_runtime
    from host_runtime.web import AgentWeb, AgentWebServer

    data = preview_workflow().model_dump(mode="json")
    data["parameters"] = [
        {
            "name": "chipset",
            "label": "Chipset",
            "kind": "select",
            "order": 1,
            "choices_source": "ref:chipsets",
        },
        {
            "name": "version",
            "label": "Version",
            "kind": "select",
            "order": 2,
            "choices_source": "ref:packageVersions?chipset={chipset}",
        },
    ]
    manifest = WorkflowManifest.model_validate(data)
    identity = manifest.metadata.identity.model_dump(mode="json")
    config, layout = _chat_config(tmp_path)
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        (runtime.layout.workflows / "with-choices.json").write_text(
            manifest.model_dump_json(), encoding="utf-8"
        )
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = base(server) + "/api/workflow-options"
            body = {"workflow": identity, "field": "version", "answers": {}}
            unpublished = fetch(url, token=server.token, body={**body, "field": "chipset"})
            assert unpublished.json()["unavailable"] is True
            assert unpublished.json()["set"] == "chipsets"
            _store(runtime.layout.workspace_root)
            assert fetch(url, token=server.token, body=body).json()["waiting_for"] == ["chipset"]
            chosen = fetch(
                url,
                token=server.token,
                body={
                    **body,
                    "answers": {"chipset": "kt100"},
                },
            ).json()
            assert chosen["choices"] == [{"value": "1.4.0", "label": "1.4.0 (legacy)"}]
            assert fetch(url, body=body).status == 401
            assert fetch(url, token=server.token, body={**body, "field": "nope"}).status == 404
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def test_the_shared_renderer_loads_dynamic_choices() -> None:
    script = PAGE.split("<script>", 1)[1].split("</script>", 1)[0]
    section = script.split("// -- Parameter forms", 1)[1].split("// -- end Parameter forms", 1)[0]
    assert '"/api/workflow-options"' in section and "wireDynamicChoices(" in section
    for unsafe in ("innerHTML", "insertAdjacentHTML", "outerHTML"):
        assert unsafe not in section
