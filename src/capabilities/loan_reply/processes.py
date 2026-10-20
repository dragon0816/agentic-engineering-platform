"""Whether a process id is still running, without psutil (AEP port).

The source queue asked `psutil.pid_exists`; psutil is not an AEP dependency,
so the run lock's "is the holder still alive" check uses the operating
system directly. Only ever asked about a lock holder's pid, never used to
signal or stop anything.
"""

from __future__ import annotations

import os
import sys

#: PROCESS_QUERY_LIMITED_INFORMATION and STILL_ACTIVE (Windows).
_QUERY = 0x1000
_STILL_ACTIVE = 259


def pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        handle = kernel.OpenProcess(_QUERY, False, pid)
        if not handle:
            # Access denied still means the process is there.
            return ctypes.get_last_error() == 5
        try:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == _STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        # Signal 0 delivers nothing; it only asks whether the pid exists.
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
