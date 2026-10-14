"""Workflow forms v2 (owner 2026-10-15, `docs/phases/WORKFLOW_FORMS_V2.md`).

The contract and host parts every generated interface relies on: `allow_other`
("pick or type"), placeholders naming settings, the built-in folder listing,
the upload store and its engine confinement, and identity presets.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_gateway import Handler, Probe, Report, capability_spec, request, workflow_manifest
from test_workflow_parameter_declaration import _manifest

from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies, WorkflowManifest, parameter_value_problem
from common.workflow_forms import agent_tool_schema, form_fields
from common.workflow_parameters import WorkflowParameterError, validate_run_parameters
from host_runtime.choice_sources import ChoiceSources, folder_files
from host_runtime.identity_presets import PRESETS_FILE, IdentityPresets
from host_runtime.reference_sets import REFERENCE_SETS_FILE, ReferenceSetStore
from host_runtime.workflow_uploads import (
    MAX_UPLOAD_BYTES,
    WorkflowUploadError,
    WorkflowUploadStore,
)
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

COMBO = {"name": "chipset", "label": "Chipset", "kind": "select", "allow_other": True,
         "choices": [{"value": "kt326"}, {"value": "kt400"}]}


# -- A2 allow_other ------------------------------------------------------------


def test_allow_other_accepts_a_typed_value_and_keeps_old_manifests_unchanged() -> None:
    manifest = _manifest([COMBO])
    field = manifest.parameters[0]
    assert parameter_value_problem(field, "kt999") is None
    assert parameter_value_problem(field, "") == "must be nonempty text"
    closed = _manifest([{**COMBO, "allow_other": False}]).parameters[0]
    assert parameter_value_problem(closed, "kt999") == "must be a declared choice"
    # An unused field keeps the published bytes.
    assert "allow_other" not in closed.model_dump(mode="json")
    assert validate_run_parameters(manifest, {"chipset": "kt999"}) == {"chipset": "kt999"}
    schema = agent_tool_schema(manifest)["properties"]["chipset"]
    assert "enum" not in schema
    assert form_fields(manifest, "web")[0]["allow_other"] is True
    assert form_fields(_manifest([{**COMBO, "allow_other": False}]), "web")[0][
        "allow_other"] is False


@pytest.mark.parametrize("bad", [
    {"name": "x", "label": "X", "kind": "text", "allow_other": True},
    {**COMBO, "multiple": True},
])
def test_allow_other_is_for_single_selects_only(bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="allow other"):
        _manifest([bad])


# -- A4 placeholders naming settings, folder listing ------------------------------------


def _inbox(tmp_path: Path) -> Path:
    inbox = tmp_path / "inbox"
    (inbox / "nested").mkdir(parents=True)
    for name in ("b-plan.json", "A-plan.JSON", "config.yaml", ".hidden.json"):
        (inbox / name).write_text("{}", encoding="utf-8")
    (inbox / "nested" / "deep.json").write_text("{}", encoding="utf-8")
    return inbox


PICK = [
    {"name": "inbox_path", "label": "Inbox", "kind": "folder", "scope": "static"},
    {"name": "plans", "label": "Plans", "kind": "select", "multiple": True,
     "choices_source": "fn:folder_files?folder={inbox_path}&accept=.json"},
]


def test_a_placeholder_may_name_a_setting_declared_anywhere() -> None:
    # The setting comes after the field that uses it: settings are never asked.
    manifest = _manifest([PICK[1], PICK[0]])
    assert ChoiceSources.needed(PICK[1]["choices_source"], manifest) == ()
    assert ChoiceSources.needed(PICK[1]["choices_source"]) == ("inbox_path",)
    with pytest.raises(ValidationError, match="names no parameter"):
        _manifest([PICK[1]])


def test_folder_files_lists_only_plain_files_directly_in_the_folder(tmp_path: Path) -> None:
    inbox = _inbox(tmp_path)
    listed = folder_files({}, {"folder": str(inbox), "accept": ".json"})
    assert [item.value for item in listed] == ["A-plan.JSON", "b-plan.json"]
    every = [item.value for item in folder_files({}, {"folder": str(inbox)})]
    assert every == ["A-plan.JSON", "b-plan.json", "config.yaml"]
    assert [item.value for item in folder_files({}, {"folder": str(inbox),
                                                     "accept": "yaml,.yml"})] == ["config.yaml"]
    for folder in ("", "relative/inbox", str(tmp_path / "absent")):
        with pytest.raises(ValueError):
            folder_files({}, {"folder": folder})


def test_choice_sources_bind_settings_and_fail_soft(tmp_path: Path) -> None:
    inbox = _inbox(tmp_path)
    manifest = _manifest(PICK)
    settings: dict[str, Any] = {"inbox_path": str(inbox)}

    def broken(_settings: Any, _arguments: Any) -> list[Any]:
        raise RuntimeError("index down")

    sources = ChoiceSources(
        ReferenceSetStore(tmp_path / REFERENCE_SETS_FILE), lambda _m: settings,
        {"folder_files": folder_files, "broken": broken},
    )
    source = PICK[1]["choices_source"]
    # A run or form cannot point the listing elsewhere: the setting wins.
    assert sources.values(manifest, source, {"inbox_path": str(tmp_path)}) == [
        "A-plan.JSON", "b-plan.json"]
    assert sources.resolve(manifest, "fn:broken", {}) is None
    settings.clear()
    assert sources.resolve(manifest, source, {}) is None


# -- engine: allow_other skips the dynamic check, uploads must be in the store ---------


def _engine(
    tmp_path: Path, parameter: dict[str, Any], provider: Any = None,
    upload_root: Path | None = None,
) -> tuple[WorkflowEngine, Any, Handler]:
    handler = Handler()
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
    data["parameters"] = [parameter]
    manifest = WorkflowManifest.model_validate(data)
    workflows = InstalledWorkflows()
    workflows.register(manifest)
    engine = WorkflowEngine(workflows, bridge, choices_provider=provider,
                            upload_root=upload_root)
    return engine, manifest.metadata.identity, handler


def test_the_engine_never_consults_a_pick_or_type_source(tmp_path: Path) -> None:
    calls: list[str] = []

    def provider(_manifest: Any, source: str, _answers: Any) -> list[str] | None:
        calls.append(source)
        return None                                        # the index is down

    field = {"name": "args", "label": "Chipset", "kind": "select",
             "choices_source": "fn:release_package.chipsets", "allow_other": True}
    engine, identity, handler = _engine(tmp_path, field, provider)
    ran = asyncio.run(engine.execute(request("run"), identity, {"args": "kt999"}))
    assert ran.run.status == "succeeded" and handler.calls == 1 and calls == []
    closed = {**field, "allow_other": False}
    engine, identity, handler = _engine(tmp_path, closed, provider)
    refused = asyncio.run(engine.execute(request("run"), identity, {"args": "kt999"}))
    assert refused.run.failure is not None
    assert refused.run.failure.code == "choice_function_unavailable"


def test_the_engine_accepts_only_uploads_from_the_store(tmp_path: Path) -> None:
    store = WorkflowUploadStore(tmp_path / "workspace")
    field = {"name": "args", "label": "Plan", "kind": "upload", "accept": [".json"]}
    engine, identity, handler = _engine(tmp_path, field, upload_root=store.root)
    elsewhere = tmp_path / "secret.json"
    elsewhere.write_text("{}", encoding="utf-8")
    refused = asyncio.run(engine.execute(request("run"), identity, {"args": str(elsewhere)}))
    assert refused.run.failure is not None
    assert refused.run.failure.code == "workflow_upload_outside_store"
    traversal = str(store.root / ".." / "secret.json")
    refused = asyncio.run(engine.execute(request("run"), identity, {"args": traversal}))
    assert refused.run.failure is not None and handler.calls == 0
    manifest = WorkflowManifest.model_validate({
        **workflow_manifest().model_dump(mode="json"), "parameters": [field]})
    stored = store.add(store.new_set(), manifest.parameters[0], "plan.json", b"{}")
    ran = asyncio.run(engine.execute(request("run"), identity, {"args": str(stored)}))
    assert ran.run.status == "succeeded" and handler.calls == 1


# -- A5 upload store -------------------------------------------------------------------


def test_upload_store_checks_type_size_count_and_names(tmp_path: Path) -> None:
    store = WorkflowUploadStore(tmp_path)
    many = _manifest([{"name": "plans", "label": "Plans", "kind": "upload", "multiple": True,
                       "accept": [".json"]}]).parameters[0]
    one = _manifest([{"name": "plan", "label": "Plan", "kind": "upload"}]).parameters[0]
    upload_set = store.new_set()
    first = store.add(upload_set, many, r"..\..\evil\plan.json", b"{}")
    assert first.name == "plan.json"
    assert first.parent == (tmp_path / "workflow-uploads" / upload_set / "plans").resolve()
    again = store.add(upload_set, many, "plan.json", b"[]")
    assert again.name == "plan (2).json" and first.read_bytes() == b"{}"
    assert store.contains(first) and not store.contains(tmp_path / "other.json")
    for args, code in (
        ((upload_set, many, "plan.exe", b"x"), "upload_type_not_accepted"),
        ((upload_set, many, "big.json", b"x" * (MAX_UPLOAD_BYTES + 1)), "upload_too_large"),
        (("../up", many, "plan.json", b"{}"), "upload_set_invalid"),
    ):
        with pytest.raises(WorkflowUploadError) as caught:
            store.add(*args)
        assert caught.value.code == code
    text = _manifest([{"name": "plan", "label": "Plan", "kind": "text"}]).parameters[0]
    with pytest.raises(WorkflowUploadError):
        store.add(upload_set, text, "plan.json", b"{}")
    # A single-file field keeps only the latest upload.
    store.add(upload_set, one, "a.txt", b"a")
    latest = store.add(upload_set, one, "b.txt", b"b")
    assert [item.name for item in latest.parent.iterdir()] == ["b.txt"]


# -- A6 identity presets --------------------------------------------------------------


IDENTITY = [
    {"name": "company", "label": "Company", "kind": "text", "group": "identity"},
    {"name": "chipset", "label": "Chipset", "kind": "text", "group": "identity"},
    {"name": "notes", "label": "Notes", "kind": "text"},
]


def test_identity_presets_keep_only_identity_values_per_member(tmp_path: Path) -> None:
    presets = IdentityPresets(tmp_path)
    manifest = _manifest(IDENTITY)
    assert presets.last("alice", manifest) == {}
    presets.remember("alice", manifest, {"company": "Foxconn", "chipset": "kt326",
                                         "notes": "not identity"})
    presets.remember("bob", manifest, {"company": "Quanta"})
    assert presets.last("alice", manifest) == {"company": "Foxconn", "chipset": "kt326"}
    assert presets.last("bob", manifest) == {"company": "Quanta"}
    # A credential-looking value is never stored.
    presets.remember("alice", manifest, {"company": "password=" + "a" * 12})
    assert presets.last("alice", manifest)["company"] == "Foxconn"
    assert (tmp_path / PRESETS_FILE).is_file()
    # Unreadable file: no preset, no crash.
    (tmp_path / PRESETS_FILE).write_text("not json", encoding="utf-8")
    assert presets.last("alice", manifest) == {}


def test_validation_still_rejects_wrong_types_for_pick_or_type() -> None:
    with pytest.raises(WorkflowParameterError):
        validate_run_parameters(_manifest([COMBO]), {"chipset": 5})


# -- A7 the format external coding agents author from ------------------------------------


def test_the_catalog_format_examples_validate_and_cover_every_kind() -> None:
    from typing import get_args

    from common.assets import ParameterKind, WorkflowOutputCheck, WorkflowParameter
    from host_runtime.external_authoring import WORKFLOW_FORMAT, creator_text

    for check in WORKFLOW_FORMAT["checks"]:  # type: ignore[union-attr]
        WorkflowOutputCheck.model_validate(check)
    for example in WORKFLOW_FORMAT["parameter examples"]:  # type: ignore[union-attr]
        WorkflowParameter.model_validate(example)
    kinds = set(get_args(ParameterKind))
    assert set(WORKFLOW_FORMAT["parameter kinds"]) == kinds  # type: ignore[arg-type]
    described = WORKFLOW_FORMAT["parameter fields"]
    for name in ("help", "default", "examples", "choices", "choices_source", "allow_other",
                 "multiple", "accept", "pattern", "order", "group", "channels"):
        assert name in described  # type: ignore[operator]
    guide = creator_text("aep-workflow-creator")
    assert "## Parameters become the Agent Web and Telegram form" in guide
    for kind in kinds:
        assert f"`{kind}`" in guide
    assert "allow_other" in guide and "fn:folder_files" in guide
