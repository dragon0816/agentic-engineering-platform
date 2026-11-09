from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_workflow_parameter_declaration import _manifest

from common.assets import WorkflowManifest
from host_runtime.authoring_task import (
    AuthoringQuestion,
    AuthoringTask,
    ProcedureAssertion,
    Requirement,
    TaskStore,
    coverage_problems,
)


def test_task_requirements_survive_restart_and_cannot_silently_disappear(tmp_path: Path) -> None:
    store = TaskStore(tmp_path)
    task = store.plan(
        "owner",
        "session",
        "Read every page",
        [
            Requirement(
                requirement_id="all_rows", description="Read every page", check_ids=("rows",)
            )
        ],
    )
    assert TaskStore(tmp_path).load("owner", "session") == task
    assert store.load("other", "session") is None
    with pytest.raises(ValueError, match="requirement_removed"):
        store.plan("owner", "session", "Read one page", [])


def test_procedure_evidence_can_be_rebound_and_requires_fresh_trial(tmp_path: Path) -> None:
    store = TaskStore(tmp_path)
    original = Requirement(
        requirement_id="orders",
        description="Read Sales Orders",
        check_ids=("rows",),
        assertions=(
            ProcedureAssertion(
                path=("steps", 0, "inputs", "actions", "value"),
                operator="contains",
                expected="Sales Orders",
            ),
        ),
    )
    task = store.plan("owner", "session", "Read Sales Orders", [original])
    store.save(
        "owner",
        "session",
        task.model_copy(update={"verified_digest": "verified", "active_trial_token": "old-trial"}),
    )
    unchanged = store.plan("owner", "session", "Read Sales Orders", [original])
    assert unchanged.verified_digest == "verified"
    assert unchanged.active_trial_token == "old-trial"

    rebound = original.model_copy(
        update={
            "assertions": (
                ProcedureAssertion(
                    path=("steps", 1, "inputs", "actions", "value", "*", "target", "name"),
                    operator="equals",
                    expected="Sales Orders",
                ),
            )
        }
    )
    updated = store.plan("owner", "session", "Read Sales Orders", [rebound])
    assert updated.requirements == (rebound,)
    assert updated.verified_digest is None
    assert updated.active_trial_token is None
    assert TaskStore(tmp_path).load("owner", "session") == updated


@pytest.mark.parametrize(
    "change",
    [
        {"assertions": ()},
        {"description": "Read one visible order"},
        {"check_ids": ()},
    ],
)
def test_rebinding_cannot_clear_evidence_or_remove_business_coverage(
    tmp_path: Path, change: dict[str, Any]
) -> None:
    store = TaskStore(tmp_path)
    original = Requirement(
        requirement_id="orders",
        description="Read every order",
        check_ids=("rows",),
        assertions=(ProcedureAssertion(path=("steps",)),),
    )
    task = store.plan("owner", "session", "Read every order", [original])
    with pytest.raises(ValueError, match="requirement_weakened"):
        store.plan("owner", "session", "Read every order", [original.model_copy(update=change)])
    assert store.load("owner", "session") == task


def test_requirement_coverage_checks_real_procedure_not_only_capability_names() -> None:
    # Constructed manifest is enough to test a missing procedure field.
    raw_manifest = {
        "metadata": {
            "identity": {"namespace": "lab", "name": "test", "version": "1.0.0"},
            "owner": {"type": "user", "id": "owner"},
            "visibility": "private",
            "lifecycle": "draft",
        },
        "description": "test",
        "execution": {"mode": "local"},
        "dependencies": {"central_required": False},
        "input_contract": "x",
        "output_contract": "y",
        "steps": [
            {
                "capability": {"namespace": "browser", "name": "operate", "version": "1.0.0"},
                "inputs": {
                    "actions": {
                        "source": "fixed",
                        "value": [{"do": "read_text", "save_as": "body"}],
                    }
                },
            }
        ],
        "checks": [{"check_id": "rows", "step_index": 0, "kind": "data_nonempty"}],
    }
    manifest = WorkflowManifest.model_validate(raw_manifest)
    task = AuthoringTask(
        objective="Read every page",
        requirements=(
            Requirement(
                requirement_id="all_rows",
                description="Read every page",
                check_ids=("rows",),
                assertions=(
                    {
                        "path": ["steps", "*", "inputs", "actions", "value", "*", "pagination"],
                        "operator": "present",
                    },
                ),
            ),
        ),
    )
    assert "all_rows" in ";".join(coverage_problems(task, manifest))


@pytest.mark.parametrize("expected", [0, -1, True, 1.5, "2", 100001])
def test_min_count_requires_a_nonzero_bounded_whole_number(expected: Any) -> None:
    with pytest.raises(ValidationError, match="positive bounded integer"):
        ProcedureAssertion(path=("steps",), operator="min_count", expected=expected)


@pytest.mark.parametrize(
    ("tail", "expected", "passed"),
    [
        (("rows",), 3, True),
        (("rows",), 4, False),
        (("mapping",), 2, True),
        (("mapping",), 3, False),
        (("text",), 3, True),
        (("text",), 4, False),
        (("rows", "*", "id"), 3, True),
        (("rows", "*", "id"), 4, False),
        (("scalar",), 1, True),
        (("scalar",), 2, False),
        (("missing",), 1, False),
    ],
)
def test_min_count_counts_selected_collections_or_wildcard_matches(
    tail: tuple[str, ...], expected: int, passed: bool
) -> None:
    manifest = _manifest(
        [],
        steps=[
            {
                "capability": {"namespace": "lab", "name": "inspect", "version": "1.0.0"},
                "inputs": {
                    "payload": {
                        "source": "fixed",
                        "value": {
                            "rows": [{"id": 1}, {"id": 2}, {"id": 3}],
                            "mapping": {"a": 1, "b": 2},
                            "text": "abc",
                            "scalar": 42,
                        },
                    }
                },
            }
        ],
        checks=[{"check_id": "rows", "step_index": 0, "kind": "data_nonempty"}],
    )
    task = AuthoringTask(
        objective="Count the selected data",
        requirements=(
            Requirement(
                requirement_id="rows",
                description="Count the selected data",
                check_ids=("rows",),
                assertions=(
                    ProcedureAssertion(
                        path=("steps", 0, "inputs", "payload", "value", *tail),
                        operator="min_count",
                        expected=expected,
                    ),
                ),
            ),
        ),
    )
    assert (coverage_problems(task, manifest) == []) is passed


def test_new_user_input_clears_question_while_preserving_plan_and_trial_proof(
    tmp_path: Path,
) -> None:
    store = TaskStore(tmp_path)
    question = AuthoringQuestion(reason="missing_resource", question="Which workbook?")
    task = AuthoringTask(
        objective="Read the report",
        question=question,
        verified_digest="verified",
        last_trial_digest="verified",
        last_status="succeeded",
        last_run_id="trial-1",
        requirements=(Requirement(requirement_id="rows", description="Read all rows"),),
    )
    store.save("owner", "session", task)
    store.observe("owner", "session", "Use the attached workbook")
    assert store.load("owner", "session") == task.model_copy(update={"question": None})
    # Re-reading identical evidence must not clear a newly raised question.
    store.save("owner", "session", task)
    store.observe("owner", "session", "Use the attached workbook")
    assert store.load("owner", "session") == task
    assert len(store.messages("owner", "session")) == 1
    store.observe("owner", "session", "Use the attached workbook", ({"path": "C:/new.xlsx"},))
    assert store.load("owner", "session") == task.model_copy(update={"question": None})
    assert len(store.messages("owner", "session")) == 2
