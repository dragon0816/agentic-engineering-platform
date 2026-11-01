"""Voice input boundary messages (docs/phases/VOICE_INPUT.md §3).

- `VoiceConfig`: the host's `voice` section; off by default, and an enabled
  host names a pinned local model (owner decisions d7, d8).
- `VoiceTranscribeRequest` / `VoiceTranscribeSuccess` / `VoiceTranscribeFailure`:
  Agent Web's `POST /api/voice/transcribe`.
- `TelegramVoice`: a `voice` or `audio` message, read before any download.
- `ERROR_CODES` and their Traditional Chinese `REPLIES` (§3.6).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, Self, get_args

from pydantic import Field, model_validator

from common.assets import reject_embedded_secrets
from common.base import Contract, Sha256, Symbol, Text

ErrorCode = Literal[
    "voice_disabled",
    "audio_too_long",
    "audio_too_large",
    "audio_unsupported_format",
    "audio_decode_failed",
    "download_failed",
    "transcript_empty",
    "stt_unavailable",
    "stt_busy",
    "stt_timeout",
    "stt_failed",
    "voice_not_confirmation",
]
ERROR_CODES: tuple[ErrorCode, ...] = get_args(ErrorCode)

#: What the person reads for each failure; nothing reaches the Agent.
REPLIES: dict[ErrorCode, str] = {
    "voice_disabled": "這台電腦沒有開啟語音輸入，請改用文字。",
    "audio_too_long": "語音超過 3 分鐘，請分段或改用文字。",
    "audio_too_large": "語音檔案太大（上限 10 MB），請分段或改用文字。",
    "audio_unsupported_format": "不支援這種音訊格式，請用 Telegram 語音訊息或網頁上的麥克風錄音。",
    "audio_decode_failed": "無法讀取這段音訊，請再錄一次。",
    "download_failed": "無法下載這段語音，請再傳一次。",
    "transcript_empty": "沒有聽到內容，請再說一次。",
    "stt_unavailable": "語音轉文字目前無法使用（模型未安裝），請改用文字。",
    "stt_busy": "語音處理忙碌中，請稍後再試。",
    "stt_timeout": "語音轉文字逾時，請再試一次或改用文字。",
    "stt_failed": "語音轉文字失敗，請再試一次或改用文字。",
    "voice_not_confirmation": "請按「確認執行」按鈕確認，語音不能代替確認。",
}

#: Accepted audio types on both channels (§3.3), by their base MIME type.
ACCEPTED_MIME_TYPES: dict[str, str] = {
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/mpeg": "mp3",
    "audio/mp4": "mp4",
    "audio/m4a": "mp4",
    "audio/x-m4a": "mp4",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}
#: The Bot API's `getFile` serves at most 20 MB.
BOT_API_DOWNLOAD_BYTES = 20 * 1024 * 1024


def base_mime(mime_type: str) -> str:
    return mime_type.split(";", 1)[0].strip().lower()


def accepted_mime(mime_type: str) -> bool:
    return base_mime(mime_type) in ACCEPTED_MIME_TYPES


class VoiceConfig(Contract):
    """`host.json` `voice`; a host without the section behaves as before."""

    enabled: bool = False
    provider: Literal["faster-whisper"] = "faster-whisper"
    # An owner-approved model package installed on this PC; the host never
    # downloads a model (owner decision d7).
    model_path: str | None = None
    model_sha256: Sha256 | None = None
    model: str = Field(default="whisper-small", min_length=1, max_length=80)
    compute: Literal["int8", "int8_float32", "float32"] = "int8"
    language: str | None = Field(default="zh", min_length=2, max_length=8)
    # Product terms that bias spelling (Whisper's initial prompt).
    hints: tuple[str, ...] = Field(default=(), max_length=200)
    max_seconds: int = Field(default=180, ge=1, le=600)
    max_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=BOT_API_DOWNLOAD_BYTES)
    timeout_seconds: int = Field(default=120, ge=1, le=900)
    idle_unload_seconds: int = Field(default=600, ge=0, le=86_400)
    # Waiting transcriptions beyond the one running; more answer `stt_busy`.
    queue: int = Field(default=2, ge=0, le=20)

    @model_validator(mode="after")
    def enabled_needs_a_pinned_model(self) -> Self:
        if self.enabled and (self.model_path is None or self.model_sha256 is None):
            raise ValueError("voice.enabled needs model_path and model_sha256")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


def declared_limit_error(
    duration_seconds: float | None,
    size_bytes: int | None,
    mime_type: str | None,
    config: VoiceConfig,
) -> ErrorCode | None:
    """The limits that can be checked from what a sender declared, before
    any download. Missing values are checked again after the download."""
    if duration_seconds is not None and duration_seconds > config.max_seconds:
        return "audio_too_long"
    if size_bytes is not None and size_bytes > config.max_bytes:
        return "audio_too_large"
    if mime_type and not accepted_mime(mime_type):
        return "audio_unsupported_format"
    return None


class TelegramVoice(Contract):
    """A Telegram `voice` note or `audio` file (owner decision d1); a
    `video_note` or video is not voice input."""

    kind: Literal["voice", "audio"]
    file_id: Text
    file_unique_id: str | None = None
    duration_seconds: int = Field(ge=0)
    mime_type: str | None = None
    file_size: int | None = Field(default=None, ge=0)
    file_name: str | None = None

    @classmethod
    def from_message(cls, message: Mapping[str, Any]) -> TelegramVoice | None:
        for kind in ("voice", "audio"):
            raw = message.get(kind)
            if not isinstance(raw, Mapping):
                continue
            file_id, duration = raw.get("file_id"), raw.get("duration")
            if not isinstance(file_id, str) or not file_id or not isinstance(duration, int):
                return None
            size = raw.get("file_size")
            return cls(
                kind=kind,
                file_id=file_id,
                file_unique_id=_text_or_none(raw.get("file_unique_id")),
                duration_seconds=max(duration, 0),
                mime_type=_text_or_none(raw.get("mime_type")),
                file_size=size if isinstance(size, int) and size >= 0 else None,
                file_name=_text_or_none(raw.get("file_name")),
            )
        return None


def _text_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


class VoiceTranscribeRequest(Contract):
    """`POST /api/voice/transcribe`: one recording, base64 in JSON like
    `/api/attachments`."""

    session_id: Symbol
    mime_type: str = Field(min_length=1, max_length=100)
    # Measured by the browser; advisory, the decoded length is what counts.
    duration_ms: int | None = Field(default=None, ge=0)
    data: str = Field(min_length=1)


class TranscriptView(Contract):
    """What Agent Web shows and puts into the message box."""

    id: Symbol
    text: Text
    language: str | None
    duration_seconds: float = Field(ge=0)
    engine: str
    model: str
    elapsed_seconds: float = Field(ge=0)


class VoiceTranscribeSuccess(Contract):
    ok: Literal[True] = True
    transcript: TranscriptView


class VoiceTranscribeFailure(Contract):
    ok: Literal[False] = False
    code: ErrorCode
    message: str

    @classmethod
    def for_code(cls, code: ErrorCode) -> VoiceTranscribeFailure:
        return cls(code=code, message=REPLIES[code])
