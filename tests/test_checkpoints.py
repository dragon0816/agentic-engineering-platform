"""Contract/reference-store checks, not a filesystem durability claim."""

from typing import Any

import pytest
from pydantic import ValidationError
from test_dispatch import spec
from test_engine import context, manifest

from common.assets import RunInput, WorkflowStep
from common.checkpoints import CheckpointOwner, PayloadRef, RunCheckpoint, StepCheckpoint
from workflow.checkpoints import (
    CheckpointStore,
    CheckpointStoreError,
    MemoryCheckpointStore,
    StoreErrorCode,
)


def record(**changes: Any) -> RunCheckpoint:
    return RunCheckpoint.model_validate(
        {
            "run_id": "run-1",
            "owner": {"actor": context().actor, "namespace": context().namespace},
            "trace": context().trace.model_dump(),
            "manifest": manifest([spec().identity] * 2).model_dump(),
            "runtime_contract": "workflow.v1",
            "intent_sha256": "a" * 64,
            "arguments": payload().model_dump(),
            "steps": [{"step_index": 0}, {"step_index": 1}],
            **changes,
        }
    )


def payload() -> PayloadRef:
    return PayloadRef(ref_id="payload-1", sha256="b" * 64, contract="count.input.v1")


def changed(item: RunCheckpoint, **changes: Any) -> RunCheckpoint:
    return RunCheckpoint.model_validate({**item.model_dump(), **changes})


def started(item: RunCheckpoint) -> RunCheckpoint:
    return changed(item, steps=[{"step_index": 0, "state": "started"}, {"step_index": 1}])


def completed(item: RunCheckpoint) -> RunCheckpoint:
    return changed(
        item,
        steps=[
            {"step_index": 0, "state": "completed", "result": payload()},
            {"step_index": 1},
        ],
    )


def test_round_trip_and_recovery_are_metadata_only() -> None:
    item = started(record())
    restored = RunCheckpoint.model_validate_json(item.model_dump_json())
    plan = restored.recovery_plan()
    assert [step.state for step in plan.steps] == ["uncertain", "never_started"]
    assert plan.status == "needs_input"
    assert plan.next_step == 0
    assert "payload-1" not in plan.model_dump_json()
    assert "arguments" not in plan.model_dump_json()
    assert restored == item


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": "2"},
        {"revision": True},
        {"revision": -1},
        {"arguments": {"value": "secret-value"}},
        {"authorization": {"allowed": True}},
        {"status": "succeeded"},
        {"steps": [{"step_index": 1}, {"step_index": 0}]},
        {"steps": [{"step_index": 0}]},
        {"steps": [{"step_index": 0}, {"step_index": 1, "state": "started"}]},
        {"resumed_from": "run-1"},
        {"continued_by": "run-1"},
        {"continued_by": "run-2"},
    ],
)
def test_invalid_records_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        record(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"state": "completed"},
        {"state": "never_started", "result": payload()},
        {"state": "started", "result": payload()},
        {"state": "completed", "result": payload(), "code": "failure"},
        {"state": "never_started", "code": "failure"},
    ],
)
def test_invalid_step_evidence(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        StepCheckpoint.model_validate({"step_index": 0, **changes})


def test_key_binding_is_scoped_atomic_and_retained_at_capacity() -> None:
    store: CheckpointStore = MemoryCheckpointStore(capacity=1)
    item = store.create(record(idempotency_key="event-1"))
    assert store.create(record(run_id="run-2", idempotency_key="event-1")) == item
    with pytest.raises(CheckpointStoreError, match="key_conflict"):
        store.create(record(idempotency_key="event-1", intent_sha256="c" * 64))
    with pytest.raises(CheckpointStoreError, match="capacity"):
        store.create(record(run_id="run-2", idempotency_key="event-2"))
    assert store.find_key(item.owner, "event-2") is None
    assert store.find_key(item.owner, "event-1") == item
    assert store.get(CheckpointOwner(actor="other", namespace="sample"), item.run_id) is None
    assert store.get(CheckpointOwner(actor="engineer", namespace="other"), item.run_id) is None


def test_same_key_other_owner_is_independent() -> None:
    store = MemoryCheckpointStore()
    one = store.create(record(idempotency_key="event-1"))
    two = store.create(
        record(
            run_id="run-2",
            idempotency_key="event-1",
            owner={"actor": "other", "namespace": "sample"},
        )
    )
    assert store.find_key(one.owner, "event-1") == one
    assert store.find_key(two.owner, "event-1") == two


def test_cas_success_is_immutable_and_inputs_are_isolated() -> None:
    store = MemoryCheckpointStore()
    item = store.create(record())
    active = store.replace(started(item), expected_revision=0)
    assert active.revision == 1
    with pytest.raises(CheckpointStoreError, match="conflict"):
        store.replace(started(item), expected_revision=0)
    done = store.replace(completed(active), expected_revision=1)
    with pytest.raises(CheckpointStoreError, match="invalid_transition"):
        store.replace(started(done), expected_revision=2)
    with pytest.raises(CheckpointStoreError, match="invalid_transition"):
        store.replace(changed(done, intent_sha256="c" * 64), expected_revision=2)


def test_deep_copies_protect_nested_manifests() -> None:
    source = record()
    step = WorkflowStep(capability=spec().identity, inputs={})
    source = changed(source, manifest={**source.manifest.model_dump(), "steps": [step, step]})
    store = MemoryCheckpointStore()
    saved = store.create(source)
    assert isinstance(source.manifest.steps[0], WorkflowStep)
    source.manifest.steps[0].inputs["unexpected"] = RunInput(source="run")
    assert store.get(saved.owner, saved.run_id) == saved


def test_cannot_skip_write_ahead_or_create_precompleted_run() -> None:
    store = MemoryCheckpointStore()
    item = store.create(record())
    with pytest.raises(CheckpointStoreError, match="invalid_transition"):
        store.replace(completed(item), expected_revision=0)
    with pytest.raises(CheckpointStoreError, match="invalid_transition"):
        store.create(completed(record(run_id="run-2")))


def test_continuation_is_atomic_preserves_prefix_and_original_key() -> None:
    store = MemoryCheckpointStore()
    parent = store.create(record(idempotency_key="event-1"))
    parent = store.replace(started(parent), expected_revision=0)
    parent = store.replace(completed(parent), expected_revision=1)
    parent = store.replace(changed(parent, status="suspended"), expected_revision=2)
    child = changed(
        parent,
        run_id="run-2",
        revision=0,
        status="running",
        resumed_from=parent.run_id,
        idempotency_key=None,
    )
    created = store.continue_run(child, expected_parent_revision=3)
    assert created.steps[0] == parent.steps[0]
    linked = store.get(parent.owner, parent.run_id)
    assert linked is not None and linked.continued_by == child.run_id
    assert linked.revision == 4
    assert store.find_key(parent.owner, "event-1") == linked
    with pytest.raises(CheckpointStoreError, match="already_continued"):
        store.continue_run(changed(child, run_id="run-3"), expected_parent_revision=4)
    assert store.get(parent.owner, "run-3") is None


def test_failed_continuation_leaves_no_half_link() -> None:
    store = MemoryCheckpointStore(capacity=1)
    parent = store.create(record())
    parent = store.replace(changed(parent, status="suspended"), expected_revision=0)
    child = changed(
        parent, run_id="run-2", revision=0, status="running", resumed_from=parent.run_id
    )
    with pytest.raises(CheckpointStoreError, match="capacity"):
        store.continue_run(child, expected_parent_revision=1)
    assert store.get(parent.owner, parent.run_id) == parent
    assert store.get(parent.owner, child.run_id) is None


class FaultStore(MemoryCheckpointStore):
    """Inject a write failure into the documented coordinator ordering example."""

    fail_revision: int = -1
    failure: StoreErrorCode = "unavailable"

    def replace(self, checkpoint: RunCheckpoint, *, expected_revision: int) -> RunCheckpoint:
        if expected_revision == self.fail_revision and self.failure == "unavailable":
            raise CheckpointStoreError(self.failure)
        saved = super().replace(checkpoint, expected_revision=expected_revision)
        if expected_revision == self.fail_revision:
            raise CheckpointStoreError(self.failure)
        return saved


@pytest.mark.parametrize(
    ("revision", "failure", "expected_effects", "expected_state"),
    [
        (0, "unavailable", 0, "never_started"),
        (0, "commit_unknown", 0, "uncertain"),
        (1, "unavailable", 1, "uncertain"),
        (1, "commit_unknown", 1, "completed"),
    ],
)
def test_fault_windows_never_claim_effect_was_not_invoked(
    revision: int, failure: StoreErrorCode, expected_effects: int, expected_state: str
) -> None:
    store = FaultStore()
    store.fail_revision = revision
    store.failure = failure
    item = store.create(record())
    effects: list[str] = []
    # Minimal future-coordinator example: an acknowledgment gates each next action.
    with pytest.raises(CheckpointStoreError, match=failure):
        active = store.replace(started(item), expected_revision=0)
        effects.append("inert-effect")
        store.replace(completed(active), expected_revision=1)
    restored = store.get(item.owner, item.run_id)
    assert restored is not None
    assert restored.recovery_plan().steps[0].state == expected_state
    assert len(effects) == expected_effects


def test_terminal_success_cannot_be_reopened() -> None:
    store = MemoryCheckpointStore()
    item = store.create(record())
    item = store.replace(started(item), expected_revision=0)
    item = store.replace(completed(item), expected_revision=1)
    steps = [item.steps[0], StepCheckpoint(step_index=1, state="started")]
    item = store.replace(changed(item, steps=steps), expected_revision=2)
    steps[1] = StepCheckpoint(step_index=1, state="completed", result=payload())
    item = store.replace(changed(item, steps=steps, status="succeeded"), expected_revision=3)
    assert item.recovery_plan().next_step is None
    assert item.recovery_plan().status == "succeeded"
    with pytest.raises(CheckpointStoreError, match="invalid_transition"):
        store.replace(item, expected_revision=4)


@pytest.mark.parametrize("field", ["manifest", "arguments", "runtime_contract", "owner", "trace"])
def test_execution_intent_is_immutable(field: str) -> None:
    store = MemoryCheckpointStore()
    item = store.create(record())
    alternatives: dict[str, Any] = {
        "manifest": manifest([spec().identity] * 2, description="changed"),
        "arguments": PayloadRef(ref_id="different", sha256="c" * 64, contract="input.v2"),
        "runtime_contract": "workflow.v2",
        "owner": CheckpointOwner(actor="other", namespace="sample"),
        "trace": context().trace.model_copy(update={"trace_id": "trace-2"}),
    }
    with pytest.raises(CheckpointStoreError, match="missing|invalid_transition"):
        store.replace(changed(item, **{field: alternatives[field]}), expected_revision=0)
    assert store.get(item.owner, item.run_id) == item


@pytest.mark.parametrize("revision", [True, -1, 1])
def test_invalid_revision_never_writes(revision: int) -> None:
    store = MemoryCheckpointStore()
    item = store.create(record())
    with pytest.raises(CheckpointStoreError, match="conflict"):
        store.replace(started(item), expected_revision=revision)
    assert store.get(item.owner, item.run_id) == item


def test_continuation_rejects_changed_prefix_and_stale_writer() -> None:
    store = MemoryCheckpointStore()
    parent = store.create(record())
    parent = store.replace(started(parent), expected_revision=0)
    parent = store.replace(completed(parent), expected_revision=1)
    parent = store.replace(changed(parent, status="suspended"), expected_revision=2)
    child = changed(
        parent, run_id="run-2", revision=0, status="running", resumed_from=parent.run_id
    )
    with pytest.raises(CheckpointStoreError, match="conflict"):
        store.continue_run(child, expected_parent_revision=2)
    with pytest.raises(CheckpointStoreError, match="invalid_transition"):
        store.continue_run(changed(child, steps=record().steps), expected_parent_revision=3)
    assert store.get(parent.owner, parent.run_id) == parent
    assert store.get(parent.owner, child.run_id) is None


def test_lost_creation_acknowledgments_do_not_duplicate_relations() -> None:
    store = MemoryCheckpointStore()
    original = record(idempotency_key="event-1")
    with pytest.raises(CheckpointStoreError, match="commit_unknown"):
        store.create(original)
        raise CheckpointStoreError("commit_unknown")
    parent = store.create(changed(original, run_id="run-2"))
    assert parent.run_id == original.run_id
    parent = store.replace(changed(parent, status="suspended"), expected_revision=0)
    child = changed(
        parent,
        run_id="run-2",
        revision=0,
        status="running",
        resumed_from=parent.run_id,
        idempotency_key=None,
    )
    with pytest.raises(CheckpointStoreError, match="commit_unknown"):
        store.continue_run(child, expected_parent_revision=1)
        raise CheckpointStoreError("commit_unknown")
    with pytest.raises(CheckpointStoreError, match="already_continued"):
        store.continue_run(child, expected_parent_revision=1)
    restored = store.get(parent.owner, parent.run_id)
    assert restored is not None and restored.continued_by == child.run_id
    assert store.get(child.owner, child.run_id) == child
