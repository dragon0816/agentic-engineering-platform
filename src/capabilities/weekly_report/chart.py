"""The pie chart the weekly mail carries, drawn with the standard library.

The source drew a composite chart with matplotlib. Carrying matplotlib would mean carrying
numpy, Pillow, fonttools, kiwisolver and contourpy into an offline bundle that
is installed with `--no-index` on a company machine -- tens of megabytes of
wheels, and the bundle has already had one install fail because a wheel's path
was too long for Windows. A pie chart is arithmetic and a circle, so this
draws one and writes the PNG itself: `zlib` and `struct` are both stdlib, and
the bundle does not grow by a byte.

Nothing here draws text. The source's direct slice labels and stacked bars
remain a visible parity gap; the mail keeps the bar breakdown and all numeric
shares as HTML so blocked images still leave usable figures.
"""

from __future__ import annotations

import math
import struct
import zlib
from collections.abc import Mapping, Sequence

#: Source W2's seven-step blue ramp. A week with more named instruments folds
#: the tail into Other instead of cycling colours and implying false identity.
PALETTE: tuple[str, ...] = (
    "#12325b", "#18447b", "#1f579d", "#256bc0", "#377fd8", "#5a95df", "#7cabe6",
)
OTHER = "#c3c2b7"
UNASSIGNED = "#898781"
#: What sits behind the circle. White, because a mail body is white and a
#: transparent PNG in Outlook renders black often enough to matter.
BACKGROUND = "#fcfcfb"
#: The grey a slice is outlined in, so two similar colours still part.
EDGE = BACKGROUND


def colours_for(labels: Sequence[str]) -> dict[str, str]:
    """Which colour each label is drawn in, and the same mapping the HTML
    legend uses. Positional, so the same week always reads the same."""
    named = 0
    colours: dict[str, str] = {}
    for label in labels:
        if label == "Unassigned":
            colours[label] = UNASSIGNED
        elif label.startswith("Other ("):
            colours[label] = OTHER
        else:
            colours[label] = PALETTE[named % len(PALETTE)]
            named += 1
    return colours


def slices_for(
    totals: Mapping[str, int], *, min_share: float = 0.05
) -> tuple[tuple[str, int, str], ...]:
    """Source W2 chart grouping: seven named slices, then Other, then Unassigned.

    The source's default five-percent threshold is retained here. This one
    series drives the picture, member bars and totals table, so folding cannot
    make any one of them disagree with the others.
    """
    if not 0 <= min_share < 1:
        raise ValueError("min_share must be between zero and one")
    if any(count < 0 for count in totals.values()):
        raise ValueError("a slice cannot be a negative number of tickets")
    named = sorted(
        ((name, count) for name, count in totals.items() if name != "Unassigned" and count),
        key=lambda entry: (-entry[1], entry[0]),
    )
    unassigned = totals.get("Unassigned", 0)
    grand = sum(count for _, count in named) + unassigned
    kept: list[tuple[str, int]] = []
    folded: list[tuple[str, int]] = []
    for name, count in named:
        if len(kept) >= len(PALETTE) or (grand and count / grand < min_share):
            folded.append((name, count))
        else:
            kept.append((name, count))
    slices = [(name, count, PALETTE[index]) for index, (name, count) in enumerate(kept)]
    if folded:
        slices.append((f"Other ({len(folded)})", sum(count for _, count in folded), OTHER))
    if unassigned:
        slices.append(("Unassigned", unassigned, UNASSIGNED))
    return tuple(slices)


def _rgb(value: str) -> tuple[int, int, int]:
    text = value.lstrip("#")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def _png(width: int, height: int, rows: Sequence[bytearray]) -> bytes:
    """A PNG of 8-bit RGB. Written here rather than by a library, and written
    the simple way: filter 0 on every scanline, one IDAT."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def _fractions(counts: Sequence[int]) -> list[float]:
    """Where each slice ends, as a fraction of the circle."""
    total = sum(counts)
    edge = 0.0
    ends: list[float] = []
    for count in counts:
        edge += count / total
        ends.append(edge)
    # Floating point must not leave a hairline gap at twelve o'clock.
    ends[-1] = 1.0
    return ends


def _slice_at(turn: float, ends: Sequence[float]) -> int:
    for index, end in enumerate(ends):
        if turn <= end:
            return index
    return len(ends) - 1


def pie_png(
    labels: Sequence[str],
    counts: Sequence[int],
    *,
    size: int = 320,
    samples: int = 3,
) -> bytes | None:
    """A pie of `counts`, in the order given, starting at twelve o'clock and
    going clockwise -- the direction the source drew and the one a reader
    expects.

    None when there is nothing to draw, which is a week where nothing was
    worked on. The mail says that in words rather than showing an empty
    circle.

    `samples` is supersampling per axis: every pixel is decided by `samples`
    squared points inside it, which is what keeps a slice's edge from being a
    staircase without any drawing library.
    """
    if len(labels) != len(counts):
        raise ValueError("a pie needs one count per label")
    # Checked before the empty case: counts that sum to nothing because one
    # is negative is a miscount, not a quiet week, and the two must not
    # produce the same silence.
    if any(count < 0 for count in counts):
        raise ValueError("a slice cannot be a negative number of tickets")
    if not counts or sum(counts) <= 0:
        return None
    ends = _fractions(counts)
    palette = [_rgb(colour) for colour in colours_for(labels).values()]
    background = _rgb(BACKGROUND)
    edge = _rgb(EDGE)
    centre = (size - 1) / 2.0
    radius = size / 2.0 - 2.0
    # Where the outline sits: a thin ring, and the boundary between two slices
    # is drawn in the same colour, so neighbouring wedges never merge.
    inner = radius - 1.5
    step = 1.0 / samples
    offsets = [(index + 0.5) * step - 0.5 for index in range(samples)]
    per_pixel = samples * samples
    rows: list[bytearray] = []
    two_pi = 2.0 * math.pi
    for y in range(size):
        row = bytearray(size * 3)
        for x in range(size):
            red = green = blue = 0
            for dy in offsets:
                oy = y + dy - centre
                for dx in offsets:
                    ox = x + dx - centre
                    distance = math.hypot(ox, oy)
                    if distance > radius:
                        sample = background
                    elif distance > inner:
                        sample = edge
                    else:
                        # Clockwise from twelve o'clock: screen y grows
                        # downward, so the angle is measured from -y.
                        turn = (math.atan2(ox, -oy) % two_pi) / two_pi
                        sample = palette[_slice_at(turn, ends)]
                    red += sample[0]
                    green += sample[1]
                    blue += sample[2]
            at = x * 3
            row[at] = red // per_pixel
            row[at + 1] = green // per_pixel
            row[at + 2] = blue // per_pixel
        rows.append(row)
    return _png(size, size, rows)


def pie_for(totals: Mapping[str, int], **options: int) -> bytes | None:
    """The chart for a `totals` mapping, using the source's folded series."""
    slices = slices_for(totals)
    return pie_png(
        tuple(label for label, _, _ in slices),
        tuple(count for _, count, _ in slices),
        **options,
    )
