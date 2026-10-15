"""Cut the owner's pixel-art character sheet into Agent Web avatar frames.

    .venv\\Scripts\\python scripts\\slice_avatars.py <sheet image> [--out src/host_runtime/avatars]

The sheet has one character per row: a name label on the left, then that
character's frames from left to right. Frame 1 is the idle picture and the
rest are the animation shown while the Agent works. Rows and frames are found
from the blank space between them, so frames of different widths (a long
punch, a wave) stay whole. White becomes transparent. Pillow is needed only
here; Agent Web reads the PNG files this writes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
NAMES = ("Luffy", "Zoro", "Nami", "Chopper", "Robin", "Sanji", "Usopp", "Franky", "Brook", "Jinbe")
LABEL_RIGHT = 165  # the name labels end left of this column
ROW_GAP = 12  # blank lines that still belong to one row
FRAME_GAP = 30  # blank columns that separate two frames
FINE_FRAME_GAP = 6  # for a row whose frames nearly touch (Jinbe's waves)
PAD = 2


def spans(marks: list[bool], start: int, gap: int) -> list[tuple[int, int]]:
    """Runs of True in `marks` from `start`, joining runs closer than `gap`."""
    found: list[tuple[int, int]] = []
    begin = None
    for index in range(start, len(marks) + 1):
        on = index < len(marks) and marks[index]
        if on and begin is None:
            begin = index
        if not on and begin is not None:
            if found and begin - found[-1][1] < gap:
                found[-1] = (found[-1][0], index)
            else:
                found.append((begin, index))
            begin = None
    return found


def slice_sheet(sheet: Path, out: Path) -> dict[str, object]:
    sheet_image = Image.open(sheet).convert("RGBA")
    gray = sheet_image.convert("L")
    width, height = gray.size
    pixels = gray.load()

    def ink(x: int, y: int) -> bool:
        return pixels[x, y] < 128

    rows = spans(
        [any(ink(x, y) for x in range(LABEL_RIGHT, width)) for y in range(height)], 0, ROW_GAP
    )
    if len(rows) != len(NAMES):
        raise SystemExit(f"expected {len(NAMES)} rows, found {len(rows)}")
    out.mkdir(parents=True, exist_ok=True)
    characters = []
    for name, (top, bottom) in zip(NAMES, rows, strict=True):
        columns = [any(ink(x, y) for y in range(top, bottom)) for x in range(width)]
        frames = spans(columns, LABEL_RIGHT, FRAME_GAP)
        if len(frames) < 6:
            frames = spans(columns, LABEL_RIGHT, FINE_FRAME_GAP)
        files = []
        for number, (left, right) in enumerate(frames, 1):
            box = (
                max(left - PAD, 0),
                max(top - PAD, 0),
                min(right + PAD, width),
                min(bottom + PAD, height),
            )
            # The art is black ink on white: keep it as black pixels whose
            # transparency is the ink, so each frame is a small two-tone PNG.
            ink_mask = gray.crop(box).point(lambda value: 255 if value < 160 else 0)
            frame = Image.new("LA", ink_mask.size, 0)
            frame.putalpha(ink_mask)
            file = f"{name.lower()}-{number}.png"
            frame.save(out / file, optimize=True)
            files.append({"file": file, "width": frame.width, "height": frame.height})
        characters.append(
            {"id": name.lower(), "name": name, "row_height": bottom - top, "frames": files}
        )
        print(f"{name}: {len(files)} frames")
    manifest = {"source": sheet.name, "idle_frame": 1, "characters": characters}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sheet", type=Path)
    parser.add_argument("--out", type=Path, default=REPO / "src" / "host_runtime" / "avatars")
    args = parser.parse_args()
    slice_sheet(args.sheet, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
