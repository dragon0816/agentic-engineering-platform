"""The host's one transcription service (docs/phases/VOICE_INPUT.md §2.2).

`VoiceService(config, provider, store)` is the injection seam:
Agent Web and the Telegram ingress take `voice: VoiceService | None`, and None
means voice is off on this host. The provider loads its model on first use;
after `idle_unload_seconds` without work (0: never) the service calls the
provider's `unload()`, when it has one. One transcription at a time with at most
`queue` waiting (more answer `stt_busy`); a `timeout_seconds` cap
(`stt_timeout`; the engine's thread finishes on its own). The blocking work
runs on the service's own thread, so neither the Telegram poll loop nor the
web server waits on it. Every call leaves a transcript record, failed ones
included; the audio itself is only ever in memory (owner, 2026-11-01).
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import logging
import shutil
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime
from pathlib import Path
from typing import Literal

from voice import audio
from voice.contracts import ErrorCode, VoiceConfig, declared_limit_error
from voice.stt import Pcm16k, SttError, SttProvider, SttResult
from voice.transcript import TranscriptAudio, TranscriptRecord, TranscriptStore, TranscriptStt

_LOG = logging.getLogger(__name__)

Channel = Literal["telegram", "web"]
Decoder = Callable[[bytes, str | None, VoiceConfig], Pcm16k]


def _opencc() -> Callable[[str], str] | None:
    """Simplified to Taiwan Traditional with phrases (owner decision d3),
    when the optional `voice` extra is installed."""
    try:
        import opencc
    except ImportError:
        return None
    converter = opencc.OpenCC("s2twp")
    return lambda text: str(converter.convert(text))


def sweep_temporary_audio(workspace_root: Path) -> None:
    """Remove `voice/tmp/` left by a crash; audio is never kept."""
    shutil.rmtree(workspace_root / "voice" / "tmp", ignore_errors=True)


class VoiceService:
    def __init__(
        self,
        config: VoiceConfig,
        provider: SttProvider,
        store: TranscriptStore,
        *,
        clock: Callable[[], datetime] | None = None,
        to_traditional: Callable[[str], str] | None = None,
        decoder: Decoder = audio.decode,
    ) -> None:
        self.config = config
        self.clock = clock or store.clock
        self.store = store
        self.provider = provider
        self._decoder = decoder
        self._to_traditional = to_traditional if to_traditional is not None else _opencc()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aep-voice")
        self._lock = threading.Lock()
        self._pending = 0
        self._loaded = False
        self._last_used: datetime | None = None
        sweep_temporary_audio(store.workspace_root)

    # -- model lifetime ----------------------------------------------------------

    def unload_if_idle(self) -> bool:
        """Unload the model after the idle period; True when it was unloaded."""
        idle = self.config.idle_unload_seconds
        unload = getattr(self.provider, "unload", None)
        with self._lock:
            if not self._loaded or self._pending or idle == 0 or self._last_used is None:
                return False
            if (self.clock() - self._last_used).total_seconds() < idle:
                return False
            if callable(unload):
                unload()
            self._loaded = False
            return True

    def _schedule_unload(self) -> None:
        if self.config.idle_unload_seconds:
            timer = threading.Timer(self.config.idle_unload_seconds + 1, self.unload_if_idle)
            timer.daemon = True
            timer.start()

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    # -- transcription -----------------------------------------------------------

    def _work(self, data: bytes, mime_type: str | None) -> tuple[Pcm16k, SttResult]:
        pcm = self._decoder(data, mime_type, self.config)
        result = self.provider.transcribe(
            pcm, language=self.config.language, hints=self.config.hints
        )
        self._loaded = True
        self._last_used = self.clock()
        return pcm, result

    def _done(self, _future: object) -> None:
        with self._lock:
            self._pending -= 1
        self._schedule_unload()

    def transcribe(
        self,
        data: bytes,
        mime_type: str | None,
        *,
        channel: Channel,
        actor: str,
        session_id: str,
        declared_seconds: float | None = None,
    ) -> TranscriptRecord:
        """A saved transcript record; `status` says whether there is text."""
        record_id, created_at = self.store.new_id(), self.clock()
        meta = TranscriptAudio(
            sha256=hashlib.sha256(data).hexdigest() if data else None,
            mime_type=(mime_type or None) and mime_type[:100],
            bytes=len(data),
            duration_seconds=declared_seconds,
        )

        def failed(code: ErrorCode, stt: TranscriptStt | None = None) -> TranscriptRecord:
            return self.store.save(
                TranscriptRecord.failed(
                    id=record_id,
                    channel=channel,
                    actor=actor,
                    session_id=session_id,
                    created_at=created_at,
                    code=code,
                    audio=meta,
                    stt=stt,
                )
            )

        declared = declared_limit_error(declared_seconds, len(data), mime_type, self.config)
        if declared is not None:
            return failed(declared)
        with self._lock:
            if self._pending > self.config.queue:
                return failed("stt_busy")
            self._pending += 1
        future = self._executor.submit(self._work, data, mime_type)
        future.add_done_callback(self._done)
        try:
            pcm, result = future.result(timeout=self.config.timeout_seconds)
        except FutureTimeout:
            return failed("stt_timeout")
        except SttError as error:
            return failed(error.code)
        except Exception as error:
            _LOG.warning("voice: transcription failed (%s)", type(error).__name__)
            return failed("stt_failed")
        meta = meta.model_copy(update={"duration_seconds": round(pcm.duration_seconds, 3)})
        stt = TranscriptStt(
            provider=result.engine,
            model=result.model,
            model_revision=result.model_revision,
            compute=f"cpu-{self.config.compute}",
            language_requested=self.config.language,
            language_detected=result.language,
            settings={"hints": len(self.config.hints)},
            elapsed_seconds=result.elapsed_seconds,
        )
        raw = result.text
        steps: list[str] = []
        text = raw
        if self._to_traditional is not None:
            text = self._to_traditional(text)
            steps.append("opencc:s2twp")
        text = text.strip()
        steps.append("strip")
        if not any(character.isalnum() for character in text):
            return failed("transcript_empty", stt)
        return self.store.save(
            TranscriptRecord(
                id=record_id,
                channel=channel,
                actor=actor,
                session_id=session_id,
                created_at=created_at,
                audio=meta,
                stt=stt,
                text_raw=raw,
                text=text,
                post_processing=tuple(steps),
                segments=result.segments,
                status="ok",
            )
        )

    async def transcribe_async(
        self,
        data: bytes,
        mime_type: str | None,
        *,
        channel: Channel,
        actor: str,
        session_id: str,
        declared_seconds: float | None = None,
    ) -> TranscriptRecord:
        call = functools.partial(
            self.transcribe,
            data,
            mime_type,
            channel=channel,
            actor=actor,
            session_id=session_id,
            declared_seconds=declared_seconds,
        )
        return await asyncio.get_running_loop().run_in_executor(None, call)
