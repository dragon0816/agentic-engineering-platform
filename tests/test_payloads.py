"""Payload storage: the stored record decides what is acceptable, and anything
that does not match the reference fails closed."""

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import JsonValue, ValidationError
from test_checkpoints import failing

from common.checkpoints import CheckpointOwner, PayloadRef
from workflow.payloads import REF_PREFIX, FilePayloadStore, PayloadStore, digest_of, ref_id_for


def owner(actor: str = "engineer", namespace: str = "sample") -> CheckpointOwner:
    return CheckpointOwner(actor=actor, namespace=namespace)


def store(tmp_path: Path, **changes: Any) -> PayloadStore:
    return FilePayloadStore(tmp_path / "payloads", **changes)


def file_of(tmp_path: Path, ref: PayloadRef, actor: str = "engineer") -> Path:
    return tmp_path / "payloads" / actor / "sample" / f"{ref.ref_id}.json"


def test_round_trip_preserves_the_value_and_its_contract(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    payload: JsonValue = {"count": 1, "items": [None, True, 2.5, "x"], "nested": {"a": []}}
    ref = keeper.put(owner(), "count.input.v1", payload)
    assert ref.sha256 == digest_of(payload)
    assert ref.ref_id.startswith(REF_PREFIX) and ref.contract == "count.input.v1"
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


def test_equal_records_share_one_file_and_writes_are_idempotent(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    first = keeper.put(owner(), "count.input.v1", {"a": 1, "b": 2})
    # Key order is not identity: the same value is the same payload.
    second = keeper.put(owner(), "count.input.v1", {"b": 2, "a": 1})
    assert first == second
    assert len(list(file_of(tmp_path, first).parent.iterdir())) == 1
    assert keeper.get(owner(), first) == {"a": 1, "b": 2}


def test_the_same_value_under_two_contracts_stays_readable(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    one = keeper.put(owner(), "count.input.v1", {"a": 1})
    other = keeper.put(owner(), "count.output.v1", {"a": 1})
    # Same payload digest, different stored records, both retrievable.
    assert one.sha256 == other.sha256
    assert one.ref_id != other.ref_id
    assert keeper.get(owner(), one) == {"a": 1}
    assert keeper.get(owner(), other) == {"a": 1}
    # A reference that claims the wrong contract is refused, not silently read.
    failing(
        lambda: keeper.get(owner(), one.model_copy(update={"contract": "count.output.v1"})),
        "invalid_transition",
    )


def test_owners_cannot_read_each_others_payloads(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    mine = keeper.put(owner(), "count.input.v1", {"a": 1})
    theirs = keeper.put(owner(actor="other"), "count.input.v1", {"a": 1})
    # The owner is part of the stored record, so the references differ.
    assert mine.ref_id != theirs.ref_id and mine.sha256 == theirs.sha256
    failing(lambda: keeper.get(owner(namespace="other"), mine), "missing")
    failing(lambda: keeper.get(owner(actor="other"), mine), "missing")
    assert keeper.get(owner(actor="other"), theirs) == {"a": 1}


def test_a_case_folding_filesystem_cannot_fold_ownership(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    ref = keeper.put(owner(actor="alice"), "count.input.v1", {"a": 1})
    # On Windows/macOS these name the same directory; the record still decides.
    for impostor in ("Alice", "ALICE", "alice."):
        failing(lambda who=impostor: keeper.get(owner(actor=who), ref), "missing")
    assert keeper.get(owner(actor="alice"), ref) == {"a": 1}


def test_unknown_or_malformed_references(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    absent = PayloadRef(ref_id=ref_id_for("a" * 64), sha256="a" * 64, contract="count.input.v1")
    failing(lambda: keeper.get(owner(), absent), "missing")
    # An identifier this store never issues is refused before naming a path.
    for bad in ("payload-short", "elsewhere-" + "a" * 64, "payload-" + "A" * 64):
        wrong = PayloadRef(ref_id=bad, sha256="a" * 64, contract="count.input.v1")
        failing(lambda item=wrong: keeper.get(owner(), item), "invalid_transition")


def test_tampered_or_swapped_content_fails_closed(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    ref = keeper.put(owner(), "count.input.v1", {"a": 1})
    path = file_of(tmp_path, ref)
    original = path.read_bytes()
    for corruption in (
        json.dumps({"contract": "count.input.v1", "payload": {"a": 2}}).encode(),
        b"not json at all",
        b'{"owner": {"actor": "engineer", "namespace": "sample"}, "payload": {"a": 1}}',
        b'{"owner": {"actor": "engineer", "namespace": "sample"},'
        b' "contract": "count.input.v1", "payload": NaN}',
        original[:-3],
        b"",
    ):
        path.write_bytes(corruption)
        failing(lambda: keeper.get(owner(), ref), "unavailable")
    path.write_bytes(original)
    assert keeper.get(owner(), ref) == {"a": 1}


def test_put_rewrites_a_corrupt_file_instead_of_reporting_success(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    ref = keeper.put(owner(), "count.input.v1", {"a": 1})
    file_of(tmp_path, ref).write_bytes(b"truncated")
    failing(lambda: keeper.get(owner(), ref), "unavailable")
    assert keeper.put(owner(), "count.input.v1", {"a": 1}) == ref
    assert keeper.get(owner(), ref) == {"a": 1}


def test_a_reference_claiming_the_wrong_payload_digest_is_refused(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    ref = keeper.put(owner(), "count.input.v1", {"a": 1})
    failing(lambda: keeper.get(owner(), ref.model_copy(update={"sha256": "b" * 64})), "unavailable")


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


def test_the_stored_record_is_exactly_what_the_reference_names(tmp_path: Path) -> None:
    keeper = store(tmp_path)
    ref = keeper.put(owner(), "count.input.v1", {"a": 1})
    body = file_of(tmp_path, ref).read_bytes()
    assert hashlib.sha256(body).hexdigest() == ref.ref_id.removeprefix(REF_PREFIX)
    record = json.loads(body)
    assert record == {
        "contract": "count.input.v1",
        "owner": {"actor": "engineer", "namespace": "sample"},
        "payload": {"a": 1},
    }
    assert digest_of(record["payload"]) == ref.sha256
