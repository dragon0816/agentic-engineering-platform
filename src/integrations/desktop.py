"""The Windows UI Automation helper behind `desktop/operate` (lab gap L2).

`desktop_uia.cs` beside this module is a small C# 5 program on the UI
Automation client built into .NET Framework (System.Windows.Automation), so no
third-party package is involved. It is compiled on first use with the .NET
Framework compiler every Windows machine has, into a cache folder the caller
owns, and rebuilt when the source is newer than the executable.

One helper process serves one call: it reads a JSON request on stdin, operates
the windows of one process id and writes one JSON result on stdout. A hung UI
is bounded by the process timeout, not by anything inside the helper.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

SOURCE = Path(__file__).with_name("desktop_uia.cs")
EXE_NAME = "desktop_uia.exe"


class DesktopToolError(Exception):
    """The helper could not be built or run; `code` says why."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code)


def _framework() -> Path:
    windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
    for bits in ("Framework64", "Framework"):
        folder = windows / "Microsoft.NET" / bits / "v4.0.30319"
        if (folder / "csc.exe").is_file():
            return folder
    raise DesktopToolError("desktop_tool_unavailable", "no .NET Framework 4 compiler")


def ensure_helper(cache_dir: Path, source: Path = SOURCE) -> Path:
    """Return the compiled helper, building it when missing or older than `source`."""
    if sys.platform != "win32":
        raise DesktopToolError("desktop_tool_unavailable", "Windows UI Automation needs Windows")
    exe = cache_dir / EXE_NAME
    if exe.is_file() and exe.stat().st_mtime >= source.stat().st_mtime:
        return exe
    framework = _framework()
    cache_dir.mkdir(parents=True, exist_ok=True)
    partial = cache_dir / (EXE_NAME + ".building")
    command = [
        str(framework / "csc.exe"), "/nologo", "/codepage:65001", "/target:exe", "/optimize+",
        f"/out:{partial}",
        f"/reference:{framework / 'WPF' / 'UIAutomationClient.dll'}",
        f"/reference:{framework / 'WPF' / 'UIAutomationTypes.dll'}",
        f"/reference:{framework / 'WPF' / 'WindowsBase.dll'}",
        f"/reference:{framework / 'System.Web.Extensions.dll'}",
        str(source),
    ]
    try:
        run = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise DesktopToolError("desktop_tool_build_failed", str(error)) from None
    if run.returncode != 0 or not partial.is_file():
        partial.unlink(missing_ok=True)
        raise DesktopToolError("desktop_tool_build_failed", (run.stdout + run.stderr)[-2000:])
    os.replace(partial, exe)
    return exe


def run_actions(exe: Path, request: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    """Run one request through a fresh helper process and return its JSON result."""
    try:
        run = subprocess.run(
            [str(exe)], input=json.dumps(request, ensure_ascii=False).encode("utf-8"),
            capture_output=True, timeout=timeout_s,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        raise DesktopToolError("desktop_tool_timed_out") from None
    except OSError as error:
        raise DesktopToolError("desktop_tool_failed", str(error)) from None
    try:
        result = json.loads(run.stdout.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        detail = run.stderr.decode("utf-8", "replace")[-2000:]
        raise DesktopToolError("desktop_tool_failed", detail) from None
    if not isinstance(result, dict):
        raise DesktopToolError("desktop_tool_failed", "the helper did not answer an object")
    return result
