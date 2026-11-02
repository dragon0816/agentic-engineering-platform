"""Fail when the vendored Atlas goldens differ from an Atlas checkout (BI K2, E1).

`tests/fixtures/atlas_dashboard_golden/*.json` and `atlas_embed_golden/*.json` are
Atlas's `web/tests/fixtures/<the same folder>/*.json`, byte for byte (see `SOURCE.md`
there). Like Atlas's `npm run check:aep-bi` for the feed goldens: the same file
names, the same bytes, or a contract change slipped through.

    python scripts/check_atlas_dashboard_golden.py --atlas <Atlas repo>
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VENDORED = REPO / "tests" / "fixtures" / "atlas_dashboard_golden"
UPSTREAM = Path("web") / "tests" / "fixtures" / "atlas_dashboard_golden"
EMBED_VENDORED = REPO / "tests" / "fixtures" / "atlas_embed_golden"
EMBED_UPSTREAM = Path("web") / "tests" / "fixtures" / "atlas_embed_golden"


class Drift(Exception):
    """The vendored copy differs from Atlas's."""


def check(
    atlas: Path, vendored: Path = VENDORED, folder: Path = UPSTREAM, label: str = "dashboard"
) -> int:
    """The number of matching files; raises `Drift` naming the first difference."""
    upstream = atlas / folder
    expected = sorted(p.name for p in upstream.glob("*.json"))
    actual = sorted(p.name for p in vendored.glob("*.json"))
    if not expected:
        raise Drift(f"no Atlas {label} goldens under {upstream}")
    if expected != actual:
        raise Drift(f"Atlas {label} golden file names differ: {expected} != {actual}")
    for name in expected:
        if (upstream / name).read_bytes() != (vendored / name).read_bytes():
            raise Drift(f"Atlas {label} golden differs: {name}")
    return len(expected)


def check_embed(atlas: Path, vendored: Path = EMBED_VENDORED) -> int:
    return check(atlas, vendored, EMBED_UPSTREAM, "embed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--atlas", required=True, type=Path, help="an Atlas checkout")
    args = parser.parse_args(argv)
    try:
        count = check(args.atlas)
        embed = check_embed(args.atlas)
    except Drift as drift:
        print(drift)
        return 1
    print(f"Atlas goldens match ({count} dashboard files, {embed} embed files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
