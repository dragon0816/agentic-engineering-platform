"""One Workflow parameter declaration for every generated interface (slice S1).

Source design: rs_workflow_system `PARAMS_SCHEMA` + `x-ui` (docs/BRIDGE_API.md
§6.1-6.6). New fields are optional so existing manifests stay valid.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from test_contracts import task_data

from common.assets import WorkflowManifest
from common.workflow_parameters import WorkflowParameterError, validate_run_parameters


def _manifest(parameters: list[dict[str, Any]], **extra: Any) -> WorkflowManifest:
    data = task_data()
    data.pop("capability")
    data["steps"] = [{"namespace": "sample", "name": "inspect", "version": "1.0.0"}]
    data["parameters"] = parameters
    data.update(extra)
    return WorkflowManifest.model_validate(data)


RICH = [
    {"name": "project", "label": "Project", "kind": "text", "group": "identity", "order": 10,
     "help": "GitLab project path", "examples": ["rs/cmx"], "pattern": r"^[a-z0-9/_-]+$",
     "min_length": 2},
    {"name": "chipset", "label": "Chipset", "kind": "select", "order": 20,
     "choices_source": "ref:chipsets", "needs": ["project"]},
    {"name": "branch", "label": "Branch", "kind": "select", "order": 30,
     "choices_source": "fn:branches?project={project}", "needs": ["project"]},
    {"name": "mode", "label": "Mode", "kind": "select", "order": 40, "default": "brief",
     "choices": [{"value": "brief", "label": "Brief"}, {"value": "full", "label": "Full"}]},
    {"name": "ratio", "label": "Ratio", "kind": "number", "minimum": 0, "maximum": 1,
     "default": 0.5},
    {"name": "reporters", "label": "Reporters", "kind": "text_list", "default": []},
    {"name": "cc", "label": "CC", "kind": "emails"},
    {"name": "requirements", "label": "Requirements", "kind": "upload", "multiple": True,
     "accept": [".txt", ".yaml"]},
    {"name": "output", "label": "Output folder", "kind": "folder", "channels": ["web"]},
    {"name": "send", "label": "Send mail", "kind": "boolean", "default": False,
     "confirm": True},
    {"name": "trace_level", "label": "Trace", "kind": "integer", "channels": []},
]


def test_rich_declaration_round_trips_with_steps_and_machine_occupancy() -> None:
    manifest = _manifest(
        RICH,
        progress_steps=[
            {"id": "prepare", "title": "Prepare"},
            {"id": "upload", "title": "Upload artifacts", "optional": True},
        ],
        occupies_machine=True,
    )
    assert WorkflowManifest.model_validate_json(manifest.model_dump_json()) == manifest
    fields = {item.name: item for item in manifest.parameters}
    assert fields["mode"].choice_values == ("brief", "full")
    assert fields["chipset"].choices_source == "ref:chipsets"
    assert fields["output"].channels == ("web",)
    assert fields["trace_level"].channels == ()
    assert fields["project"].channels == ("web", "telegram", "schedule", "agent")
    assert manifest.occupies_machine is True
    assert manifest.progress_steps[1].optional is True


def test_legacy_options_remain_shorthand_for_choices() -> None:
    manifest = _manifest([
        {"name": "mode", "label": "Mode", "kind": "select", "options": ["brief", "full"]},
    ])
    assert manifest.parameters[0].choice_values == ("brief", "full")
    assert manifest.occupies_machine is False and manifest.progress_steps == ()


@pytest.mark.parametrize(
    "field",
    [
        {"name": "n", "label": "N", "kind": "integer", "default": "ten"},
        {"name": "b", "label": "B", "kind": "boolean", "default": "yes"},
        {"name": "m", "label": "M", "kind": "select", "options": ["a"], "default": "z"},
        {"name": "m", "label": "M", "kind": "select", "options": ["a"],
         "choices": [{"value": "a"}]},
        {"name": "t", "label": "T", "kind": "text", "choices": [{"value": "a"}]},
        {"name": "t", "label": "T", "kind": "text", "pattern": "("},
        {"name": "i", "label": "I", "kind": "integer", "pattern": "^1$"},
        {"name": "b", "label": "B", "kind": "boolean", "min_length": 1},
        {"name": "t", "label": "T", "kind": "text", "accept": [".txt"]},
        {"name": "t", "label": "T", "kind": "text", "multiple": True},
        {"name": "t", "label": "T", "kind": "text", "choices_source": "web:list"},
        {"name": "t", "label": "T", "kind": "text", "channels": ["web", "web"]},
        {"name": "r", "label": "R", "kind": "number", "minimum": 2, "maximum": 1},
        {"name": "c", "label": "C", "kind": "emails", "default": ["not-an-email"]},
    ],
)
def test_inconsistent_field_declarations_are_refused(field: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _manifest([field])


def test_dependencies_must_exist_and_come_first() -> None:
    project = {"name": "project", "label": "Project", "kind": "text", "order": 10}
    with pytest.raises(ValidationError, match="needs"):
        _manifest([project, {"name": "x", "label": "X", "kind": "select",
                             "choices_source": "ref:sets", "needs": ["missing"]}])
    with pytest.raises(ValidationError, match="before"):
        _manifest([{**project, "order": 50}, {"name": "x", "label": "X", "kind": "select",
                                              "order": 20, "choices_source": "ref:sets",
                                              "needs": ["project"]}])
    with pytest.raises(ValidationError, match="placeholder"):
        _manifest([project, {"name": "x", "label": "X", "kind": "select", "order": 20,
                             "choices_source": "fn:list?p={other}"}])
    with pytest.raises(ValidationError):
        _manifest([project], progress_steps=[{"id": "a", "title": "A"}, {"id": "a", "title": "B"}])


def test_runtime_values_follow_the_richer_kinds_and_defaults() -> None:
    manifest = _manifest(RICH)
    checked = validate_run_parameters(manifest, {
        "project": "rs/cmx", "ratio": 0.25, "reporters": ["amy", "bo"],
        "cc": ["a@example.com"], "requirements": ["req.txt"], "mode": "full",
    })
    # Declared defaults fill absent fields; supplied values are kept.
    assert checked["mode"] == "full" and checked["send"] is False
    assert checked["reporters"] == ["amy", "bo"]
    for invalid in (
        {"project": "R"},                      # min_length and pattern
        {"project": "Rs/CMX"},                 # pattern
        {"ratio": 2},                          # above maximum
        {"ratio": True},                       # bool is not a number
        {"reporters": ["amy", ""]},
        {"cc": ["not-an-email"]},
        {"mode": "other"},
        {"requirements": "req.txt"},           # multiple upload expects a list
    ):
        with pytest.raises(WorkflowParameterError):
            validate_run_parameters(manifest, invalid)


def test_unused_later_fields_keep_published_manifest_bytes() -> None:
    legacy = _manifest([{"name": "week", "label": "Week", "kind": "text"}])
    dumped = legacy.model_dump(mode="json")
    assert "progress_steps" not in dumped and "occupies_machine" not in dumped
    assert set(dumped["parameters"][0]) == {
        "name", "label", "kind", "scope", "description", "required", "options",
        "minimum", "maximum",
    }
    used = _manifest(
        [{"name": "week", "label": "Week", "kind": "text", "order": 1, "channels": ["web"]}],
        occupies_machine=True,
    ).model_dump(mode="json")
    assert used["occupies_machine"] is True
    assert used["parameters"][0]["order"] == 1 and used["parameters"][0]["channels"] == ["web"]
