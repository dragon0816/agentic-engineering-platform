"""Turn a pytest JUnit report into GitHub error annotations.

CI logs need repository admin rights to read, but check-run annotations do not,
so every failed or errored test is printed as one `::error` line that the
owner's tools can list. Only names and the first line of each message are
printed; tests do not put secrets in their messages.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_ANNOTATIONS = 50


def _escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def failure_lines(report: Path) -> list[str]:
    lines: list[str] = []
    for case in ET.parse(report).getroot().iter("testcase"):
        for kind in ("failure", "error"):
            found = case.find(kind)
            if found is None:
                continue
            name = f"{case.get('classname', '')}::{case.get('name', '')}"
            message = (found.get("message") or found.text or kind).strip().splitlines()
            first = message[0][:300] if message else kind
            lines.append(f"::error title={_escape(name)}::{_escape(f'{kind}: {first}')}")
    return lines


def main(argv: list[str]) -> int:
    report = Path(argv[1] if len(argv) > 1 else "pytest-results.xml")
    if not report.is_file():
        print(f"::warning::no pytest report at {report}")
        return 0
    found = failure_lines(report)
    for line in found[:MAX_ANNOTATIONS]:
        print(line)
    if len(found) > MAX_ANNOTATIONS:
        print(f"::warning::{len(found) - MAX_ANNOTATIONS} more failures not annotated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
