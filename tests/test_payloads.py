"""Payload storage: the digest is the identity, a reference decides what is
acceptable, and anything that does not match fails closed."""

import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import JsonValue, ValidationError
from test_checkpoints import failing

from common.checkpoints import CheckpointOwner, PayloadRef
from workflow.payloads import FilePayloadStore, PayloadStore, digest_of, ref_id_for


def owner(actor: str = "engineer", namespace: str = "sample") -> CheckpointOwner:
    return CheckpointOwner(actor=actor, namespace=namespace)


def store(tmp_path: Path, **changes: Any) -> PayloadStore:
    return FilePayloadStore(tmp_path / "payloads", **changes)


def test_round_trip_preserves_the_value_and_its_contract(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    payload: JsonValue = {"count": 1, "items": [None, True, 2.5, "x"], "nested": {"a": []}}
    ref = keeper.put(owner(), "count.input.v1", payload)
    assert ref.sha256 == digest_of(payload)
    assert ref.ref_id == ref_id_for(ref.sha256)
    assert ref.contract == "count.input.v1"
    assert keeper.get(owner(), ref) == payload
    # The reference is exactly what a checkpoint may record.
    assert PayloadRef.model_validate_json(ref.model_dump_json()) == ref


@pytest.mark.parametrize(
    "payload",
    [None, True, 0, -1.5, "", "text", [], {}, [{"a": [1, {"b": None}]}]],
)
def test_every_json_value_round_trips(tmp_path: Path, payload: JsonValue) -> None:
    keeper = store(tmp_path)
    assert keeper.get(owner(), keeper.put(owner(), "value.v1", payload)) == payload


def test_equal_payloads_share_one_file_and_writes_are_idempotent(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    first = keeper.put(owner(), "count.input.v1", {"a": 1, "b": 2})
    # Key order is not identity: the same value is the same payload.
    second = keeper.put(owner(), "count.input.v1", {"b": 2, "a": 1})
    assert first == second
    files = list((tmp_path / "payloads" / "engineer" / "sample").iterdir())
    assert len(files) == 1
    assert keeper.get(owner(), first) == {"a": 1, "b": 2}


def test_different_contracts_are_different_references(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    one = keeper.put(owner(), "count.input.v1", {"a": 1})
    other = keeper.put(owner(), "count.output.v1", {"a": 1})
    assert one.sha256 == other.sha256 and one.contract != other.contract
    # A reference that claims the wrong contract is refused, not silently read.
    failing(
        lambda: keeper.get(owner(), one.model_copy(update={"contract": "other.v1"})),
        "invalid_transition",
    )


def test_owners_cannot_read_each_others_payloads(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    mine = keeper.put(owner(), "count.input.v1", {"a": 1})
    theirs = keeper.put(owner(actor="other"), "count.input.v1", {"a": 1})
    assert mine == theirs  # the same value has the same digest
    failing(lambda: keeper.get(owner(namespace="other"), mine), "missing")
    assert keeper.get(owner(actor="other"), theirs) == {"a": 1}


def test_unknown_payload_is_missing(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    absent = PayloadRef(ref_id=ref_id_for("a" * 64), sha256="a" * 64, contract="count.input.v1")
    failing(lambda: keeper.get(owner(), absent), "missing")


def test_tampered_or_swapped_content_fails_closed(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    ref = keeper.put(owner(), "count.input.v1", {"a": 1})
    path = tmp_path / "payloads" / "engineer" / "sample" / f"{ref.ref_id}.json"
    path.write_text(json.dumps({"contract": "count.input.v1", "payload": {"a": 2}}))
    failing(lambda: keeper.get(owner(), ref), "unavailable")
    path.write_text("not json at all")
    failing(lambda: keeper.get(owner(), ref), "unavailable")
    path.write_text(json.dumps({"payload": {"a": 1}}))
    failing(lambda: keeper.get(owner(), ref), "unavailable")


def test_a_reference_whose_parts_disagree_is_refused(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    ref = keeper.put(owner(), "count.input.v1", {"a": 1})
    # ref_id and sha256 must agree: a reference this store never issued is refused.
    failing(
        lambda: keeper.get(owner(), ref.model_copy(update={"sha256": "b" * 64})),
        "invalid_transition",
    )
    absent = PayloadRef(ref_id=ref_id_for("b" * 64), sha256="b" * 64, contract="count.input.v1")
    failing(lambda: keeper.get(owner(), absent), "missing")
    other = keeper.put(owner(), "count.input.v1", {"a": 2})
    # A file that does not hash to the reference is refused even though it exists.
    swapped = PayloadRef(ref_id=other.ref_id, sha256=other.sha256, contract="count.input.v1")
    path = tmp_path / "payloads" / "engineer" / "sample" / f"{other.ref_id}.json"
    path.write_text(json.dumps({"contract": "count.input.v1", "payload": {"a": 1}}))
    failing(lambda: keeper.get(owner(), swapped), "unavailable")


def test_oversized_and_unserializable_payloads_are_refused(tmp_path: Path) -> None:
    keeper = store(tmp_path, max_bytes=64)
    failing(lambda: keeper.put(owner(), "big.v1", {"a": "x" * 200}), "capacity")
    failing(lambda: keeper.put(owner(), "bad.v1", float("nan")), "invalid_transition")
    # mypy is right that this is not JSON; the store must refuse it at runtime too.
    not_json = cast(JsonValue, {1: "int key"})
    failing(lambda: keeper.put(owner(), "bad.v1", not_json), "invalid_transition")
    assert not (tmp_path / "payloads" / "engineer").exists()
    with pytest.raises(ValueError):
        FilePayloadStore(tmp_path, max_bytes=0)


def test_invalid_owner_or_contract_is_rejected(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    with pytest.raises(ValidationError):
        keeper.put(CheckpointOwner.model_construct(actor="bad actor", namespace="x"), "v.1", {})
    with pytest.raises(ValidationError):
        keeper.put(owner(), "not a symbol!", {})


def test_a_failed_write_leaves_no_partial_file(tmp_path: Path) -> None:
    class Failing(FilePayloadStore):
        @staticmethod
        def _write_atomically(path: Path, body: bytes) -> None:
            raise OSError("disk full")

    keeper = Failing(tmp_path / "payloads")
    failing(lambda: keeper.put(owner(), "count.input.v1", {"a": 1}), "unavailable")
    assert list((tmp_path / "payloads" / "engineer" / "sample").iterdir()) == []


def test_payloads_survive_a_restart(tmp_path: Path) -> None:
    first = store(tmp_path)
    ref = first.put(owner(), "count.input.v1", {"a": 1})
    assert store(tmp_path).get(owner(), ref) == {"a": 1}
