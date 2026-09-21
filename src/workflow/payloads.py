"""Content-addressed local storage for the payloads a checkpoint only references.

A `PayloadRef` in a checkpoint names validated, secret-free JSON that a future
recovery coordinator needs back: a run's arguments and each completed step's
result. This module stores exactly that, beside the checkpoint file, under the
host's own access controls.

What is stored is a record of owner, contract and payload, and the digest of that
whole record is the storage identity (`ref_id`); `PayloadRef.sha256` remains the
digest of the payload value itself. Both are checked on every read, and the
record's own owner decides who may read it, so case-insensitive filesystems,
tampering and swapped files all fail closed rather than returning something the
run never produced.

Nothing here resolves secrets, enforces policy, grants access or deletes data.
"""

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Protocol

from pydantic import JsonValue, TypeAdapter, ValidationError

from common.base import Symbol
from common.checkpoints import CheckpointOwner, PayloadRef
from workflow.checkpoints import CheckpointStoreError, validate_owner

_SYMBOL: TypeAdapter[str] = TypeAdapter(Symbol)
_JSON: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
# A digest may start with a digit, which a Symbol may not; the prefix also keeps
# the identifier recognisable as this store's, and the file name derives from it.
REF_PREFIX = "payload-"
_REF_ID = re.compile(f"^{REF_PREFIX}[a-f0-9]{{64}}$")
# Payload evidence is small by design: references, identities and validated
# step data, never attachments, logs or binary content.
MAX_PAYLOAD_BYTES = 1_000_000


class PayloadStore(Protocol):
    """Trusted storage seam. `put` returns the reference a checkpoint records;
    `get` returns the payload only when every recorded identity still matches."""

    def put(self, owner: CheckpointOwner, contract: Symbol, payload: JsonValue) -> PayloadRef: ...

    def get(self, owner: CheckpointOwner, ref: PayloadRef) -> JsonValue: ...


def _canonical(value: JsonValue) -> bytes:
    """One byte string per value, so equal records share one digest and file."""
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    ).encode()


def _reject_constant(literal: str) -> JsonValue:
    # NaN/Infinity are not JSON; a stored record containing them is not ours.
    raise ValueError(f"non-JSON constant: {literal}")


def digest_of(payload: JsonValue) -> str:
    return hashlib.sha256(_canonical(_JSON.validate_python(payload))).hexdigest()


def ref_id_for(record_sha256: str) -> str:
    """The only identifier this store accepts, so a file name can never be a path."""
    return f"{REF_PREFIX}{record_sha256}"


class FilePayloadStore:
    """One directory per owner under `root`; one file per stored record.

    Writes are atomic (temporary file plus `os.replace`) and idempotent: the same
    owner, contract and payload land on the same path with the same bytes. There
    is no deletion API, no TTL and no eviction — a checkpoint may reference a
    payload for as long as it is retained. Directory permissions are the host's
    responsibility; the owner recorded inside each file, not its location, is
    what this store checks.
    """

    def __init__(self, root: Path, *, max_bytes: int = MAX_PAYLOAD_BYTES) -> None:
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("max_bytes must be a positive integer")
        self._root = Path(root)
        self._max_bytes = max_bytes

    def _path(self, owner: CheckpointOwner, ref_id: str) -> Path:
        # Owner parts are validated Symbol/Slug and the file name is a validated
        # digest, so no component is free-form caller text.
        return self._root / owner.actor / owner.namespace / f"{ref_id}.json"

    @staticmethod
    def _record(owner: CheckpointOwner, contract: str, payload: JsonValue) -> bytes:
        return _canonical(
            {
                "owner": {"actor": owner.actor, "namespace": owner.namespace},
                "contract": contract,
                "payload": payload,
            }
        )

    def put(self, owner: CheckpointOwner, contract: Symbol, payload: JsonValue) -> PayloadRef:
        checked_owner = validate_owner(owner)
        name = _SYMBOL.validate_python(contract)
        try:
            value = _JSON.validate_python(payload)
            body = _canonical(value)
            record = self._record(checked_owner, name, value)
        except (ValidationError, TypeError, ValueError):
            # Unserializable data is not evidence; never store a partial record.
            raise CheckpointStoreError("invalid_transition") from None
        if len(body) > self._max_bytes:
            raise CheckpointStoreError("capacity")
        ref = PayloadRef(
            ref_id=ref_id_for(hashlib.sha256(record).hexdigest()),
            sha256=hashlib.sha256(body).hexdigest(),
            contract=name,
        )
        path = self._path(checked_owner, ref.ref_id)
        try:
            # An existing file is only trusted when it still hashes to this record;
            # a truncated or tampered one is rewritten rather than reported as fine.
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != (
                ref.ref_id.removeprefix(REF_PREFIX)
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                self._write_atomically(path, record)
        except OSError:
            raise CheckpointStoreError("unavailable") from None
        return ref

    @staticmethod
    def _write_atomically(path: Path, body: bytes) -> None:
        handle, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            _fsync_directory(path.parent)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def get(self, owner: CheckpointOwner, ref: PayloadRef) -> JsonValue:
        checked_owner = validate_owner(owner)
        checked_ref = PayloadRef.model_validate(ref)
        if not _REF_ID.match(checked_ref.ref_id):
            # Not an identifier this store issues: refuse before naming a path.
            raise CheckpointStoreError("invalid_transition")
        path = self._path(checked_owner, checked_ref.ref_id)
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            raise CheckpointStoreError("missing") from None
        except OSError:
            raise CheckpointStoreError("unavailable") from None
        # The reference decides what is acceptable; the file never gets a vote.
        if hashlib.sha256(body).hexdigest() != checked_ref.ref_id.removeprefix(REF_PREFIX):
            raise CheckpointStoreError("unavailable")
        try:
            record = json.loads(body, parse_constant=_reject_constant)
            payload = _JSON.validate_python(record["payload"])
            stored_owner = CheckpointOwner.model_validate(record["owner"])
            stored_contract = _SYMBOL.validate_python(record["contract"])
            payload_digest = digest_of(payload)
        except (ValidationError, ValueError, TypeError, KeyError, IndexError):
            raise CheckpointStoreError("unavailable") from None
        if stored_owner != checked_owner:
            # A filesystem that folds case must not fold ownership with it.
            raise CheckpointStoreError("missing")
        if payload_digest != checked_ref.sha256:
            raise CheckpointStoreError("unavailable")
        if stored_contract != checked_ref.contract:
            raise CheckpointStoreError("invalid_transition")
        return payload


def _fsync_directory(directory: Path) -> None:
    """Make the rename itself durable where the platform supports it."""
    try:
        handle = os.open(directory, os.O_RDONLY)
    except OSError:
        return  # Windows cannot open a directory; the replace is atomic there.
    try:
        os.fsync(handle)
    except OSError:
        pass
    finally:
        os.close(handle)
