"""The pie the weekly mail carries, checked by decoding it back.

Nothing here trusts that the bytes are a PNG because a library said so:
there is no library. The header is read back, and the picture is sampled at
points whose colour is known in advance -- twelve o'clock is the first slice,
outside the circle is the page.
"""

from __future__ import annotations

import struct
import zlib

import pytest

from capabilities.weekly_report import chart


def decoded(png: bytes) -> tuple[int, int, list[list[tuple[int, int, int]]]]:
    """Width, height and pixels, read with the standard library only."""
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    at = 8
    width = height = 0
    data = b""
    while at < len(png):
        (length,) = struct.unpack(">I", png[at : at + 4])
        kind = png[at + 4 : at + 8]
        payload = png[at + 8 : at + 8 + length]
        (stated,) = struct.unpack(">I", png[at + 8 + length : at + 12 + length])
        assert stated == zlib.crc32(kind + payload) & 0xFFFFFFFF, f"{kind!r} is corrupt"
        if kind == b"IHDR":
            width, height, depth, colour = struct.unpack(">IIBB", payload[:10])
            assert (depth, colour) == (8, 2), "8-bit RGB is what the header must say"
        elif kind == b"IDAT":
            data += payload
        at += 12 + length
    raw = zlib.decompress(data)
    stride = width * 3
    rows = []
    for y in range(height):
        start = y * (stride + 1)
        assert raw[start] == 0, "every scanline is written unfiltered"
        line = raw[start + 1 : start + 1 + stride]
        rows.append([(line[x * 3], line[x * 3 + 1], line[x * 3 + 2]) for x in range(width)])
    return width, height, rows


def at(png: bytes, x: float, y: float) -> tuple[int, int, int]:
    """The pixel at a fraction of the way across and down."""
    width, height, rows = decoded(png)
    return rows[int(height * y)][int(width * x)]


def rgb(colour: str) -> tuple[int, int, int]:
    text = colour.lstrip("#")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def test_the_bytes_are_a_png_this_machine_can_read_back() -> None:
    png = chart.pie_png(("CMP180", "CMW100"), (3, 1), size=64)
    assert png is not None
    width, height, rows = decoded(png)
    assert (width, height) == (64, 64)
    assert len(rows) == 64 and len(rows[0]) == 64


def test_twelve_oclock_is_the_first_slice_and_it_goes_clockwise() -> None:
    """The direction the source drew, and the one a reader assumes. Drawn the
    other way every number would still be right and every reading wrong."""
    png = chart.pie_png(("first", "second"), (1, 1), size=200)
    assert png is not None
    first, second = (rgb(colour) for colour in chart.colours_for(("first", "second")).values())
    assert at(png, 0.5, 0.2) == first, "twelve o'clock"
    assert at(png, 0.75, 0.5) == first, "three o'clock, half a circle clockwise"
    assert at(png, 0.25, 0.5) == second, "nine o'clock"


def test_a_slice_is_as_big_as_its_share() -> None:
    """A quarter is a quarter: the top right is the first slice and nothing
    else is."""
    png = chart.pie_png(("quarter", "rest"), (1, 3), size=200)
    assert png is not None
    quarter, rest = (rgb(colour) for colour in chart.colours_for(("quarter", "rest")).values())
    assert at(png, 0.6, 0.35) == quarter, "inside the first quarter"
    assert at(png, 0.6, 0.65) == rest, "just past it, clockwise"
    assert at(png, 0.4, 0.35) == rest


def test_outside_the_circle_is_the_page_behind_it() -> None:
    """A transparent corner renders black in Outlook often enough to matter,
    so the corner is white on purpose."""
    png = chart.pie_png(("only",), (1,), size=100)
    assert png is not None
    assert at(png, 0.02, 0.02) == rgb(chart.BACKGROUND)
    assert at(png, 0.98, 0.98) == rgb(chart.BACKGROUND)


def test_one_instrument_fills_the_circle() -> None:
    png = chart.pie_png(("CMP180",), (9,), size=100)
    assert png is not None
    only = rgb(chart.colours_for(("CMP180",))["CMP180"])
    for x, y in ((0.5, 0.2), (0.8, 0.5), (0.5, 0.8), (0.2, 0.5)):
        assert at(png, x, y) == only


def test_a_week_with_nothing_in_it_draws_nothing() -> None:
    """An empty circle is a picture of a lie; the mail says it in words."""
    assert chart.pie_for({}) is None
    assert chart.pie_for({"CMP180": 0}) is None


def test_a_miscounted_series_is_refused_rather_than_drawn() -> None:
    with pytest.raises(ValueError, match="one count per label"):
        chart.pie_png(("a", "b"), (1,))
    with pytest.raises(ValueError, match="negative"):
        chart.pie_png(("a",), (-1,))


def test_the_same_week_draws_the_same_bytes() -> None:
    """A mail somebody compares with last week's must not differ because it
    was drawn twice."""
    week = {"CMP180": 7, "CMW100": 4, "Unassigned": 5}
    assert chart.pie_for(week) == chart.pie_for(dict(week))


def test_every_slice_gets_a_colour_even_past_the_palette() -> None:
    """A week naming more instruments than the palette has must still draw."""
    many = tuple(f"instrument-{index}" for index in range(len(chart.PALETTE) + 3))
    colours = chart.colours_for(many)
    assert len(colours) == len(many)
    assert all(value in chart.PALETTE for value in colours.values())
    png = chart.pie_png(many, tuple(1 for _ in many), size=60)
    assert png is not None


def test_the_legend_is_keyed_to_the_picture() -> None:
    """The colour a row shows is the colour its slice is drawn in. Two
    mappings that drifted apart would mislabel the chart silently."""
    labels = ("CMP180", "CMW100", "Unassigned")
    colours = chart.colours_for(labels)
    png = chart.pie_png(labels, (1, 1, 1), size=200)
    assert png is not None
    assert at(png, 0.5, 0.2) == rgb(colours["CMP180"]), "the first row is the slice at the top"
