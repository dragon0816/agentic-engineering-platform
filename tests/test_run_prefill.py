"""Run values read from a "run X" request (owner, 2026-10-25).

「幫我執行 43W SDE weekly report」 named the report week, and the question flow
asked it anyway. `common/run_prefill.py` reads such values from the Workflow's
declaration, only when unambiguous; Agent Web's run form and Telegram's
question flow both use it through `workflow_run_form.run_intent`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from test_workflow_parameter_declaration import _manifest

from common.assets import WorkflowManifest
from common.workflow_run_form import prefill_from_text, run_intent

#: The inputs of the owner's engineering/sde-weekly-report, all optional.
SDE_FIELDS: list[dict[str, Any]] = [
    {
        "name": "dry_run",
        "label": "Dry run: show the plan only",
        "kind": "boolean",
        "help": "Plan the week and show it; the workbook and the mail are not touched.",
        "order": 5,
    },
    {
        "name": "week",
        "label": "Report week",
        "kind": "text",
        "description": "Weekly sheet name, for example 2026_40W.",
        "order": 10,
    },
    {"name": "since", "label": "From date", "kind": "date", "order": 20},
    {"name": "until", "label": "Through date", "kind": "date", "order": 30},
    {"name": "max_issues", "label": "Maximum issues", "kind": "integer", "minimum": 1},
    {
        "name": "draft_mail",
        "label": "Save the weekly mail draft",
        "kind": "boolean",
        "default": True,
    },
]
TODAY = date(2026, 10, 25)


def _sde(fields: list[dict[str, Any]] | None = None) -> WorkflowManifest:
    manifest = _manifest(fields if fields is not None else SDE_FIELDS)
    data = manifest.model_dump(mode="json")
    data["metadata"]["identity"].update(namespace="engineering", name="sde-weekly-report")
    return WorkflowManifest.model_validate(data)


# -- reading values from the request ---------------------------------------------


def test_the_owners_request_gives_the_week_in_the_examples_format() -> None:
    intent = run_intent("幫我執行 43W SDE weekly report", [_sde()], today=TODAY)
    assert intent is not None and intent.prefill == {"week": "2026_43W"}
    for said in (
        "run sde weekly report W43",
        "執行 sde weekly report 第43週",
        "run sde-weekly-report 2026_43W",
    ):
        found = run_intent(said, [_sde()], today=TODAY)
        assert found is not None and found.prefill == {"week": "2026_43W"}, said
    # The year comes from the ISO calendar when omitted.
    early = run_intent("run sde weekly report 2W", [_sde()], today=date(2027, 1, 2))
    assert early is not None and early.prefill == {"week": "2026_02W"}


def test_dates_switches_and_choices_are_read_only_when_unambiguous() -> None:
    manifest = _sde()
    said = "run sde weekly report 43W dry run 2026-10-19 到 2026-10-25"
    assert prefill_from_text(manifest, said, today=TODAY) == {
        "week": "2026_43W",
        "dry_run": True,
        "since": "2026-10-19",
        "until": "2026-10-25",
    }
    assert prefill_from_text(manifest, "run sde weekly report 正式", today=TODAY) == {
        "dry_run": False
    }
    choices = _manifest(
        [
            {
                "name": "mode",
                "label": "Mode",
                "kind": "select",
                "choices": [{"value": "brief"}, {"value": "full"}],
            },
            {"name": "when", "label": "Day", "kind": "date"},
        ]
    )
    assert prefill_from_text(choices, "run inspect full 2026-10-19", today=TODAY) == {
        "mode": "full",
        "when": "2026-10-19",
    }


def test_ambiguous_text_prefills_nothing() -> None:
    manifest = _sde()
    for said in (
        "run sde weekly report 43W 44W",  # two weeks
        "run sde weekly report 2026-10-19",  # one date, two date fields
        "run sde weekly report dry run 正式",  # both ways
        "run sde weekly report",  # nothing at all
    ):
        assert "week" not in prefill_from_text(manifest, said, today=TODAY), said
        assert "since" not in prefill_from_text(manifest, said, today=TODAY), said
    assert "dry_run" not in prefill_from_text(manifest, "run sde dry run 正式", today=TODAY)
    choices = _manifest(
        [
            {
                "name": "a",
                "label": "A",
                "kind": "select",
                "choices": [{"value": "x1"}, {"value": "x2"}],
            },
        ]
    )
    assert prefill_from_text(choices, "run inspect x1 x2", today=TODAY) == {}
    # A field without an example of the week format is not guessed.
    plain = _sde([{"name": "week", "label": "Report week", "kind": "text"}])
    assert prefill_from_text(plain, "run sde weekly report 43W", today=TODAY) == {}


def test_an_invalid_prefill_is_dropped_and_asked() -> None:
    from channels import telegram_flow as flow

    strict = _sde(
        [
            {
                "name": "week",
                "label": "Report week",
                "kind": "text",
                "required": True,
                "description": "for example 2025_40W",
                "pattern": "^2025_",
            }
        ]
    )
    assert prefill_from_text(strict, "run sde weekly report 43W", today=TODAY) == {}
    state = flow.start(strict, "read", prefill={})
    assert isinstance(state, flow.FlowState)
    asked = flow.begin(state)
    assert asked.prompt is not None and "Report week *" in asked.prompt.text
