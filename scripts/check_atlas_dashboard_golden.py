"""Fail when the vendored Atlas dashboard goldens differ from an Atlas checkout (BI K2).

`tests/fixtures/atlas_dashboard_golden/*.json` are Atlas's
`web/tests/fixtures/atlas_dashboard_golden/*.json`, byte for byte (see
`SOURCE.md` there). Like Atlas's `npm run check:aep-bi` for the feed goldens:
the same file names, the same bytes, or a contract change slipped through.

    python scripts/check_atlas_dashboard_golden.py --atlas <Atlas repo>
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VENDORED = REPO / "tests" / "fixtures" / "atlas_dashboard_golden"
UPSTREAM = Path("web") / "tests" / "fixtures" / "atlas_dashboard_golden"


class Drift(Exception):
    """The vendored copy differs from Atlas's."""


def check(atlas: Path, vendored: Path = VENDORED) -> int:
    """The number of matching files; raises `Drift` naming the first difference."""
    upstream = atlas / UPSTREAM
    expected = sorted(p.name for p in upstream.glob("*.json"))
    actual = sorted(p.name for p in vendored.glob("*.json"))
    if not expected:
        raise Drift(f"no Atlas dashboard goldens under {upstream}")
    if expected != actual:
        raise Drift(f"Atlas dashboard golden file names differ: {expected} != {actual}")
    for name in expected:
        if (upstream / name).read_bytes() != (vendored / name).read_bytes():
            raise Drift(f"Atlas dashboard golden differs: {name}")
    return len(expected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--atlas", required=True, type=Path, help="an Atlas checkout")
    args = parser.parse_args(argv)
    try:
        count = check(args.atlas)
    except Drift as drift:
        print(drift)
        return 1
    print(f"Atlas dashboard goldens match ({count} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
