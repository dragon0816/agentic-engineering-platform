"""Generate the voice input test audio (docs/phases/VOICE_INPUT.md §4.1).

No recording of a real person: speech comes from Windows' built-in offline
text-to-speech voices (System.Speech; owner decision d6), the rest from the
standard library. The reference transcript of a speech fixture is the text
given to the voice. Output goes to `tests/fixtures/voice/` with a
`manifest.json` (text, generator, voice, format, duration, sha256).

    python scripts/voice_fixtures.py            # write the fixtures (Windows)
    python scripts/voice_fixtures.py --check    # verify files against the manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "voice"
MANIFEST = FIXTURES / "manifest.json"
RATE = 16_000

ZH_VOICE = "Microsoft Hanhan Desktop"
EN_VOICE = "Microsoft Zira Desktop"
#: (name, voice, text): one request per use, and the words a card must refuse.
SPEECH: tuple[tuple[str, str, str], ...] = (
    ("zh_ask", ZH_VOICE, "幫我查 CMX500 的 Wi-Fi 8 選項"),
    ("zh_workflow", ZH_VOICE, "執行週報 Workflow"),
    ("zh_coding", ZH_VOICE, "把 parser 的 CSV 欄位改成 UTF-8"),
    ("zh_confirm", ZH_VOICE, "好"),
    ("zh_cancel", ZH_VOICE, "取消"),
    ("en_ask", EN_VOICE, "What options does the CMX500 support for Wi-Fi 8?"),
)

_SPEAK = r"""
param([string]$Voice, [string]$TextFile, [string]$Out)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
  $s.SelectVoice($Voice)
  $format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, 16, 1)
  $s.SetOutputToWaveFile($Out, $format)
  $s.Speak([System.IO.File]::ReadAllText($TextFile, [System.Text.Encoding]::UTF8))
} finally { $s.Dispose() }
"""


def _write_wav(path: Path, samples: list[int]) -> None:
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def _duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        return round(audio.getnframes() / audio.getframerate(), 3)


def _speak(voice: str, text: str, out: Path) -> None:
    with tempfile.TemporaryDirectory() as folder:
        script = Path(folder) / "speak.ps1"
        script.write_text(_SPEAK, encoding="utf-8")
        text_file = Path(folder) / "text.txt"
        text_file.write_text(text, encoding="utf-8")
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-Voice",
                voice,
                "-TextFile",
                str(text_file),
                "-Out",
                str(out),
            ],
            check=True,
            capture_output=True,
        )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate() -> list[dict[str, object]]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []

    def add(name: str, file: str, kind: str, **extra: object) -> None:
        path = FIXTURES / file
        entry: dict[str, object] = {"name": name, "file": file, "kind": kind, **extra}
        if file.endswith(".wav") and kind != "invalid":
            entry["duration_seconds"] = _duration(path)
        entry["sha256"] = _sha256(path)
        entries.append(entry)

    for name, voice, text in SPEECH:
        _speak(voice, text, FIXTURES / f"{name}.wav")
        add(
            name,
            f"{name}.wav",
            "speech",
            text=text,
            language="en" if voice == EN_VOICE else "zh",
            generator="System.Speech (Windows, offline)",
            voice=voice,
            format="wav/pcm_s16le/16000/mono",
        )

    _write_wav(FIXTURES / "silence_2s.wav", [0] * (2 * RATE))
    add("silence_2s", "silence_2s.wav", "non_speech", generator="stdlib wave")
    tone = [int(8000 * math.sin(2 * math.pi * 1000 * i / RATE)) for i in range(RATE)]
    _write_wav(FIXTURES / "tone_1khz_1s.wav", tone)
    add("tone_1khz_1s", "tone_1khz_1s.wav", "non_speech", generator="stdlib wave")
    rng = random.Random(20261101)
    _write_wav(FIXTURES / "noise_1s.wav", [rng.randint(-3000, 3000) for _ in range(RATE)])
    add("noise_1s", "noise_1s.wav", "non_speech", generator="stdlib wave, seed 20261101")

    (FIXTURES / "empty.wav").write_bytes(b"")
    add("empty", "empty.wav", "invalid", generator="zero bytes")
    whole = (FIXTURES / "zh_ask.wav").read_bytes()
    (FIXTURES / "truncated.wav").write_bytes(whole[:60])
    add("truncated", "truncated.wav", "invalid", generator="first 60 bytes of zh_ask.wav")
    (FIXTURES / "not_audio.ogg").write_bytes(b"this is a text file, not audio\n")
    add("not_audio", "not_audio.ogg", "invalid", generator="text renamed .ogg")
    return entries


def check() -> list[str]:
    """Problems with the committed fixtures; empty when they match."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems = []
    for entry in manifest["fixtures"]:
        path = FIXTURES / entry["file"]
        if not path.is_file():
            problems.append(f"missing: {entry['file']}")
        elif _sha256(path) != entry["sha256"]:
            problems.append(f"changed: {entry['file']}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify against the manifest")
    args = parser.parse_args(argv)
    if args.check:
        problems = check()
        print("\n".join(problems) or "voice fixtures match the manifest")
        return 1 if problems else 0
    if sys.platform != "win32":
        print("speech fixtures need Windows' System.Speech", file=sys.stderr)
        return 2
    entries = generate()
    MANIFEST.write_text(
        json.dumps(
            {"schema": "aep.voice.fixtures/v1", "fixtures": entries}, ensure_ascii=False, indent=1
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(entries)} fixtures to {FIXTURES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
