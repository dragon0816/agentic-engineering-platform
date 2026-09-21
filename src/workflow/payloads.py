"""Content-addressed local storage for the payloads a checkpoint only references.

A `PayloadRef` in a checkpoint names validated, secret-free JSON that a future
recovery coordinator needs back: a run's arguments and each completed step's
result. This module stores exactly that, beside the checkpoint file, under the
host's own access controls.

The digest is the identity: a payload is written once under its own SHA-256 and
verified again on every read, so a corrupted or swapped file fails closed instead
of feeding recovery something the run never produced. The declared contract name
travels with it, and a read that expects a different contract is refused.

Nothing here resolves secrets, enforces policy, grants access or deletes data.
"""

import hashlib
import json
import os
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
# Payload evidence is small by design: references, identities and validated
# step data, never attachments, logs or binary content.
MAX_PAYLOAD_BYTES = 1_000_000


class PayloadStore(Protocol):
    """Trusted storage seam. `put` returns the reference a checkpoint records;
    `get` returns the payload only when the digest and contract still match."""

    def put(self, owner: CheckpointOwner, contract: Symbol, payload: JsonValue) -> PayloadRef: ...

    def get(self, owner: CheckpointOwner, ref: PayloadRef) -> JsonValue: ...


def _canonical(payload: JsonValue) -> bytes:
    """One byte string per value, so equal payloads share one digest and file."""
    return json.dumps(
        _JSON.validate_python(payload),
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    ).encode()


def digest_of(payload: JsonValue) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def ref_id_for(sha256: str) -> str:
    """The only identifier this store accepts, so a file name can never be a path."""
    return f"{REF_PREFIX}{sha256}"


class FilePayloadStore:
    """One directory per owner under `root`; one file per payload, named by digest.

    Writes are atomic (temporary file plus `os.replace`) and idempotent: the same
    payload lands on the same path with the same bytes. There is no deletion API,
    no TTL and no eviction — a checkpoint may reference a payload for as long as
    it is retained. Directory permissions are the host's responsibility; this
    store only keeps one owner's payloads out of another owner's directory.
    """

    def __init__(self, root: Path, *, max_bytes: int = MAX_PAYLOAD_BYTES) -> None:
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("max_bytes must be a positive integer")
        self._root = Path(root)
        self._max_bytes = max_bytes

    def _directory(self, owner: CheckpointOwner) -> Path:
        return self._root / owner.actor / owner.namespace

    def _path(self, owner: CheckpointOwner, sha256: str) -> Path:
        # Built from the validated hex digest alone, never from caller text.
        return self._directory(owner) / f"{ref_id_for(sha256)}.json"

    def put(self, owner: CheckpointOwner, contract: Symbol, payload: JsonValue) -> PayloadRef:
        checked_owner = validate_owner(owner)
        name = _SYMBOL.validate_python(contract)
        try:
            body = _canonical(payload)
        except (TypeError, ValueError):
            # Unserializable data is not evidence; never store a partial record.
            raise CheckpointStoreError("invalid_transition") from None
        if len(body) > self._max_bytes:
            raise CheckpointStoreError("capacity")
        sha256 = hashlib.sha256(body).hexdigest()
        ref = PayloadRef(ref_id=ref_id_for(sha256), sha256=sha256, contract=name)
        record = json.dumps({"contract": name, "payload": json.loads(body)}, separators=(",", ":"))
        path = self._path(checked_owner, sha256)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                self._write_atomically(path, record.encode())
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
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def get(self, owner: CheckpointOwner, ref: PayloadRef) -> JsonValue:
        checked_owner = validate_owner(owner)
        checked_ref = PayloadRef.model_validate(ref)
        if checked_ref.ref_id != ref_id_for(checked_ref.sha256):
            # A reference whose own parts disagree names nothing this store wrote.
            raise CheckpointStoreError("invalid_transition")
        path = self._path(checked_owner, checked_ref.sha256)
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            raise CheckpointStoreError("missing") from None
        except OSError:
            raise CheckpointStoreError("unavailable") from None
        try:
            record = json.loads(body)
            payload = _JSON.validate_python(record["payload"])
            stored_contract = _SYMBOL.validate_python(record["contract"])
        except (ValidationError, ValueError, TypeError, KeyError):
            raise CheckpointStoreError("unavailable") from None
        # The reference decides what is acceptable; the file never gets a vote.
        if digest_of(payload) != checked_ref.sha256:
            raise CheckpointStoreError("unavailable")
        if stored_contract != checked_ref.contract:
            raise CheckpointStoreError("invalid_transition")
        return payload
