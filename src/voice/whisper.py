"""Local speech to text with faster-whisper (owner, 2026-11-01: §7.1 a2, d3, d7).

The model is an owner-approved package installed on this PC: `model_path` is
its folder and `model_sha256` the hash `model_package_sha256` gives for it.
The host never downloads a model (`local_files_only`); a missing folder, a
changed file or a host without the `voice` extra is `stt_unavailable`. The
model loads on the first transcription and `unload()` lets it go. Decoding
settings follow the prototype (draft PR #240), with voice activity filtering
on and a Traditional Chinese initial prompt carrying the product terms.
"""

from __future__ import annotations

import hashlib
import importlib
import sys
import threading
import time
from pathlib import Path
from typing import Any

from voice.contracts import VoiceConfig
from voice.service import VoiceService
from voice.stt import Pcm16k, Segment, SttError, SttResult
from voice.transcript import TranscriptStore

ENGINE = "faster-whisper"
#: Fixed decoding settings (prototype `provider.py`, plus the VAD filter).
DECODING: dict[str, Any] = {
    "beam_size": 5,
    "temperature": 0.0,
    "vad_filter": True,
    "condition_on_previous_text": False,
}
#: Steers Whisper toward Traditional characters (owner decision d3).
TRADITIONAL_PROMPT = "以下是繁體中文的語音內容，可能夾雜英文產品名稱。"
_MAX_PROMPT_CHARS = 400


def model_package_sha256(folder: Path) -> str:
    """One hash over every file's relative path and content, in name order."""
    digest = hashlib.sha256()
    for path in sorted(item for item in folder.rglob("*") if item.is_file()):
        content = hashlib.sha256(path.read_bytes()).hexdigest()
        digest.update(f"{path.relative_to(folder).as_posix()}\0{content}\n".encode())
    return digest.hexdigest()


def _whisper_model_class() -> Any:
    try:
        return importlib.import_module("faster_whisper").WhisperModel
    except ImportError:
        return None


def _audio_array(pcm: Pcm16k) -> Any:
    numpy = importlib.import_module("numpy")
    return numpy.frombuffer(pcm.samples, dtype=numpy.int16).astype(numpy.float32) / 32768.0


def initial_prompt(hints: tuple[str, ...]) -> str:
    if not hints:
        return TRADITIONAL_PROMPT
    return f"{TRADITIONAL_PROMPT}{'、'.join(hints)}"[:_MAX_PROMPT_CHARS]


class FasterWhisperProvider:
    def __init__(self, config: VoiceConfig) -> None:
        self.config = config
        self._model: Any = None
        self._lock = threading.Lock()

    def _load(self) -> Any:
        with self._lock:
            if self._model is not None:
                return self._model
            path, pinned = self.config.model_path, self.config.model_sha256
            if path is None or pinned is None or not Path(path).is_dir():
                raise SttError("stt_unavailable")
            if model_package_sha256(Path(path)) != pinned:
                raise SttError("stt_unavailable")
            whisper_model = _whisper_model_class()
            if whisper_model is None:
                raise SttError("stt_unavailable")
            try:
                self._model = whisper_model(
                    path,
                    device="cpu",
                    compute_type=self.config.compute,
                    local_files_only=True,
                )
            except Exception as error:
                raise SttError("stt_unavailable") from error
            return self._model

    def unload(self) -> None:
        with self._lock:
            self._model = None

    def transcribe(self, pcm: Pcm16k, *, language: str | None, hints: tuple[str, ...]) -> SttResult:
        model = self._load()
        started = time.perf_counter()
        segments, info = model.transcribe(
            _audio_array(pcm),
            language=language,
            initial_prompt=initial_prompt(hints),
            **DECODING,
        )
        found = tuple(
            Segment(float(item.start), float(item.end), str(item.text)) for item in segments
        )
        return SttResult(
            segments=found,
            language=getattr(info, "language", None),
            duration_seconds=float(getattr(info, "duration", pcm.duration_seconds)),
            elapsed_seconds=round(time.perf_counter() - started, 3),
            engine=ENGINE,
            model=self.config.model,
            model_revision=self.config.model_sha256 or "",
        )


def build_voice(config: VoiceConfig | None, workspace_root: Path) -> VoiceService | None:
    """The host's voice service: None (voice off) unless `voice.enabled`."""
    if config is None or not config.enabled:
        return None
    return VoiceService(config, FasterWhisperProvider(config), TranscriptStore(workspace_root))


def main(argv: list[str] | None = None) -> int:
    """`python -m voice.whisper <model folder>`: the `model_sha256` to pin in host.json."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not Path(args[0]).is_dir():
        print("usage: python -m voice.whisper <model folder>", file=sys.stderr)
        return 2
    print(model_package_sha256(Path(args[0])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
