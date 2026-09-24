"""What the Windows COM adapters share: asking whether an application is here.

Two adapters now drive Office through COM -- the workbook through Excel and
the weekly mail's draft through Outlook -- and both have to tell "this
installation is missing the bridge" apart from "this machine does not have
that application". The answer to the second is a registry read, and it is the
same read for either, so it lives here rather than in whichever adapter was
written first.
"""

from __future__ import annotations

import sys


def progid_is_registered(prog_id: str) -> bool:
    """Whether a ProgID names something this machine could start.

    Reads the registry and starts nothing, which is what a doctor is allowed
    to do, and reads exactly what resolving the ProgID would read. It does
    not go through the COM bridge to ask: that bridge's module is a shim over
    a DLL, and on a host where the shim is unhappy every question asked
    through it fails alike, which would make "Excel is not installed" the
    answer to a question about something else entirely. That is what happened
    on 2026-09-24.
    """
    if sys.platform != "win32":
        # No registry, and no Office either, so the answer is the same. The
        # platform test is also what lets a type checker read the import
        # below, which is Windows-only in the standard library.
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id + r"\CLSID"):
            return True
    except OSError:
        return False
