"""The sandboxed Knowledge pipeline installed on a Host (K1.3, owner 2026-10-11)."""

import asyncio
from pathlib import Path
from typing import Any

from test_host_wiring import grant_record, membership_record, workspace
from test_knowledge_sandbox import _base, _snapshot

from capabilities.knowledge_pipeline.handlers import (
    CONVERT_SPEC,
    DROP_ADD_SPEC,
    INGEST_APPLY_SPEC,
    INGEST_PLAN_SPEC,
    LINT_SPEC,
    SANDBOX_CONTENTS_SPEC,
    SANDBOX_CREATE_SPEC,
    SANDBOX_DISCARD_SPEC,
    SANDBOX_LIST_SPEC,
)
from common.execution import TraceIdentifiers
from host_runtime.host import build_runtime

SPECS = (SANDBOX_CREATE_SPEC, SANDBOX_LIST_SPEC, CONVERT_SPEC, INGEST_PLAN_SPEC,
         INGEST_APPLY_SPEC, LINT_SPEC, DROP_ADD_SPEC, SANDBOX_CONTENTS_SPEC,
         SANDBOX_DISCARD_SPEC)


def _grants() -> list[dict[str, Any]]:
    return [*grant_record(), *({
        "actor": "engineer", "asset": spec.identity.model_dump(mode="json"),
        "permissions": ["knowledge-pipeline.use"], "policy_refs": ["knowledge-sandbox-policy"],
        "approval_ref": "knowledge-pipeline-approval",
    } for spec in SPECS)]


def _call(runtime: Any, spec: Any, arguments: dict[str, Any]) -> Any:
    from common.local_agent import LocalCapabilityRequest

    request = LocalCapabilityRequest(
        ingress="local", actor=runtime.actor, bridge_id=runtime.config.device.bridge_id,
        target=spec.identity, arguments=arguments,
        trace=TraceIdentifiers(trace_id="k1", request_id="k1", span_id="k1"))
    return asyncio.run(runtime.agent.execute_capability(request))


def test_a_configured_host_installs_and_runs_the_pipeline(tmp_path: Path) -> None:
    base = _base(tmp_path)
    before = _snapshot(base)
    config, _ = workspace(
        tmp_path, membership=membership_record(), grants=_grants(),
        config_changes={"knowledge_pipeline": {"vaults": [{"name": "k-test", "root": str(base)}]}})
    with build_runtime(config) as runtime:
        installed = runtime.agent.gateway.bridge.installed
        assert all(installed.get(spec.identity) is not None for spec in SPECS)
        created = _call(runtime, SANDBOX_CREATE_SPEC, {"base": "k-test", "label": "host trial"})
        assert created.capability.status == "succeeded", created
        sandbox = created.capability.data["sandbox_id"]
        added = _call(runtime, DROP_ADD_SPEC, {"sandbox_id": sandbox, "name": "a.txt",
                                               "data_base64": "aGVsbG8K"})
        assert added.capability.data["path"] == "drop/a.txt"
        converted = _call(runtime, CONVERT_SPEC, {"sandbox_id": sandbox, "mode": "apply"})
        assert converted.capability.status == "succeeded"
        assert converted.capability.data["items"][0]["status"] == "written"
        contents = _call(runtime, SANDBOX_CONTENTS_SPEC, {"sandbox_id": sandbox})
        assert contents.capability.data["drop"] == ["drop/a.txt"]
        # The base's note has no provenance and was never adopted, so only the
        # converted original is a Raw document the pipeline can ingest.
        assert contents.capability.data["raw"] == [converted.capability.data["items"][0]["raw_ref"]]
        listed = _call(runtime, SANDBOX_LIST_SPEC, {})
        assert [s["sandbox_id"] for s in listed.capability.data["sandboxes"]] == [sandbox]
        refused = _call(runtime, LINT_SPEC, {"sandbox_id": "../escape"})
        assert refused.capability.status == "failed"
        assert refused.capability.failure.code == "invalid_sandbox_id"
    assert _snapshot(base) == before


def test_without_the_section_nothing_is_installed(tmp_path: Path) -> None:
    config, _ = workspace(tmp_path, membership=membership_record(), grants=grant_record())
    with build_runtime(config) as runtime:
        assert runtime.agent.gateway.bridge.installed.get(CONVERT_SPEC.identity) is None
