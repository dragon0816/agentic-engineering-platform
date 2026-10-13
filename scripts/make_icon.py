"""Make the AEP Agent shortcut icon from a square PNG (owner, 2026-10-13).

    .venv\Scripts\python.exe scripts\make_icon.py <icon.png>

Writes src/host_runtime/icons/aep-agent.ico with the sizes Windows uses for
desktop, Start menu and taskbar; the shortcut shows it after the next install,
update or `aep-host shortcut`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

TARGET = Path(__file__).resolve().parents[1] / "src" / "host_runtime" / "icons" / "aep-agent.ico"
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def make(source: Path, target: Path = TARGET) -> Path:
    image = Image.open(source).convert("RGBA")
    side = min(image.size)
    left, top = (image.width - side) // 2, (image.height - side) // 2
    square = image.crop((left, top, left + side, top + side))
    target.parent.mkdir(parents=True, exist_ok=True)
    square.save(target, format="ICO", sizes=SIZES)
    return target


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(make(Path(sys.argv[1])))
