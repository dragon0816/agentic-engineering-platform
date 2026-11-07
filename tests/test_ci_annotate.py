"""Windows check annotations preserve non-ASCII failures under a legacy console."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_windows_legacy_console_emits_utf8_annotations(tmp_path: Path) -> None:
    report = tmp_path / "results.xml"
    report.write_text(
        '<testsuite><testcase classname="test_fake" name="case">'
        '<failure message="虛構錯誤" /></testcase></testsuite>',
        encoding="utf-8",
    )
    environment = dict(os.environ, PYTHONIOENCODING="cp1252")
    result = subprocess.run(
        [sys.executable, "scripts/ci_annotate.py", str(report)],
        env=environment,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "::error title=test_fake::case::failure: 虛構錯誤" in result.stdout.decode("utf-8")
