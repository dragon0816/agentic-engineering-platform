"""Transcript records (`aep.voice.transcript/v1`, docs/phases/VOICE_INPUT.md §3.4).

One record per transcription, failed ones included, at
`<workspace>/voice/transcripts/<sha256(session)[:24]>/<id>.json`, readable
only for the person and session it belongs to and purged after the task
summaries' retention (default 30 days). Only the transcript is kept: the
`audio` block is metadata, and no audio is ever stored (owner, 2026-11-01).
"""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar, Final, Literal, Self

from pydantic import ConfigDict, Field, JsonValue, model_validator

from common.assets import reject_embedded_secrets
from common.base import Contract, Sha256
from host_runtime.workspace import write_atomically
from voice.contracts import ErrorCode
from voice.stt import Segment

SCHEMA: Final = "aep.voice.transcript/v1"
#: A Bot API file URL carries the bot token; it is never written down.
_BOT_URL = re.compile(r"/(?:file/)?bot[^/\s]*/", re.IGNORECASE)


class TranscriptAudio(Contract):
    sha256: Sha256 | None = None
    mime_type: str | None = None
    bytes: int | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)


class TranscriptStt(Contract):
    provider: str
    model: str
    model_revision: str
    compute: str
    language_requested: str | None
    language_detected: str | None
    settings: dict[str, JsonValue] = Field(default_factory=dict)
    elapsed_seconds: float = Field(ge=0)


class TranscriptUse(Contract):
    """The turn the transcript became, and whether the person edited it first."""

    turn: str = Field(min_length=1, max_length=200)
    edited: bool
    sent_text_sha256: Sha256


class TranscriptRecord(Contract):
    model_config = ConfigDict(**Contract.model_config, populate_by_name=True)

    schema_: Literal["aep.voice.transcript/v1"] = Field(default=SCHEMA, alias="schema")
    id: str = Field(pattern=r"^vt-[0-9]{14}-[0-9a-f]{8}$")
    channel: Literal["telegram", "web"]
    actor: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    created_at: datetime
    audio: TranscriptAudio = Field(default_factory=TranscriptAudio)
    stt: TranscriptStt | None = None
    text_raw: str | None = None
    text: str | None = None
    post_processing: tuple[str, ...] = ()
    segments: tuple[Segment, ...] = ()
    status: Literal["ok", "empty", "failed"]
    error_code: ErrorCode | None = None
    used_as: TranscriptUse | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.status == "ok":
            if not (self.text and self.text_raw) or self.error_code or self.stt is None:
                raise ValueError("an ok transcript has text, an engine and no error")
        else:
            if self.text is not None or self.text_raw is not None or self.segments:
                raise ValueError("a failed or empty transcript has no text")
            expected = "transcript_empty" if self.status == "empty" else None
            if self.error_code is None or (expected and self.error_code != expected):
                raise ValueError("a failed or empty transcript names its error code")
        dumped = self.dump()
        reject_embedded_secrets(dumped)
        if _BOT_URL.search(str(dumped)):
            raise ValueError("a transcript record never holds a Bot API URL")
        return self

    def dump(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True)

    @classmethod
    def failed(
        cls,
        *,
        id: str,
        channel: Literal["telegram", "web"],
        actor: str,
        session_id: str,
        created_at: datetime,
        code: ErrorCode,
        audio: TranscriptAudio | None = None,
        stt: TranscriptStt | None = None,
    ) -> TranscriptRecord:
        return cls(
            id=id,
            channel=channel,
            actor=actor,
            session_id=session_id,
            created_at=created_at,
            audio=audio or TranscriptAudio(),
            stt=stt,
            status="empty" if code == "transcript_empty" else "failed",
            error_code=code,
        )


class TranscriptStore:
    ID: ClassVar[re.Pattern[str]] = re.compile(r"vt-[0-9]{14}-[0-9a-f]{8}")

    def __init__(
        self, workspace_root: Path, *, clock: Callable[[], datetime] | None = None
    ) -> None:
        self.root = workspace_root / "voice" / "transcripts"
        self.clock = clock or (lambda: datetime.now(UTC))

    def _folder(self, session_id: str) -> Path:
        return self.root / hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:24]

    def new_id(self) -> str:
        return f"vt-{self.clock():%Y%m%d%H%M%S}-{secrets.token_hex(4)}"

    def save(self, record: TranscriptRecord) -> TranscriptRecord:
        path = self._folder(record.session_id) / f"{record.id}.json"
        write_atomically(path, record.model_dump_json(by_alias=True, indent=1).encode("utf-8"))
        return record

    def _read(self, path: Path) -> TranscriptRecord | None:
        try:
            return TranscriptRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def get(self, actor: str, session_id: str, transcript_id: str) -> TranscriptRecord | None:
        """The record, only for the person and session it belongs to."""
        if not self.ID.fullmatch(transcript_id):
            return None
        item = self._read(self._folder(session_id) / f"{transcript_id}.json")
        if item is None or item.actor != actor or item.session_id != session_id:
            return None
        return item

    def list(self, actor: str, session_id: str) -> list[TranscriptRecord]:
        folder = self._folder(session_id)
        found = [self._read(path) for path in sorted(folder.glob("vt-*.json"))]
        mine = [
            item
            for item in found
            if item is not None and item.actor == actor and item.session_id == session_id
        ]
        return sorted(mine, key=lambda item: item.created_at)

    def mark_used(
        self, actor: str, session_id: str, transcript_id: str, use: TranscriptUse
    ) -> TranscriptRecord | None:
        item = self.get(actor, session_id, transcript_id)
        if item is None:
            return None
        return self.save(item.model_copy(update={"used_as": use}))

    def purge(self, retention_days: int, now: datetime | None = None) -> int:
        """Delete every record older than the retention; no model is involved."""
        cutoff = (now or self.clock()) - timedelta(days=retention_days)
        removed = 0
        for path in self.root.glob("*/vt-*.json"):
            item = self._read(path)
            if item is not None and item.created_at >= cutoff:
                continue
            try:
                path.unlink()
                removed += 1
            except OSError:
                continue
        for folder in self.root.glob("*"):
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
        return removed
