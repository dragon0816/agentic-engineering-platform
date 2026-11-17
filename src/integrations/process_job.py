"""Own a Windows command tree without token, network or process-count restrictions.

The small supervisor joins an unnamed kill-on-close Job BEFORE it launches the
requested executable; this avoids assigning an already exited process or guessing
PIDs. It exits with the real command status and its handle closes with the process.
https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
"""

WINDOWS_COMMAND_SUPERVISOR = r"""
import ctypes
from ctypes import wintypes as W
import json
from pathlib import Path
import subprocess
import sys

class Basic(ctypes.Structure):
    _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                ("flags", W.DWORD), ("min_ws", ctypes.c_size_t),
                ("max_ws", ctypes.c_size_t), ("active", W.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", W.DWORD), ("scheduling", W.DWORD)]
class IO(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]
class Extended(ctypes.Structure):
    _fields_ = [("basic", Basic), ("io", IO), ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                ("peak_job", ctypes.c_size_t)]

def fail(code):
    Path(sys.argv[1]).write_text(code, encoding="ascii")
    raise SystemExit(127)

kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.CreateJobObjectW.argtypes = (ctypes.c_void_p, W.LPCWSTR)
kernel.CreateJobObjectW.restype = W.HANDLE
kernel.GetCurrentProcess.argtypes = ()
kernel.GetCurrentProcess.restype = W.HANDLE
kernel.SetInformationJobObject.argtypes = (W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD)
kernel.SetInformationJobObject.restype = W.BOOL
kernel.AssignProcessToJobObject.argtypes = (W.HANDLE, W.HANDLE)
kernel.AssignProcessToJobObject.restype = W.BOOL
job = kernel.CreateJobObjectW(None, None)
limits = Extended()
limits.basic.flags = 0x2000
if not job or not kernel.SetInformationJobObject(
    job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
):
    fail("process_job_unavailable")
if not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()):
    fail("process_job_unavailable")
# The handle is not inherited and is intentionally kept until process exit.
try:
    result = subprocess.run(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")), check=False)
except PermissionError:
    fail("environment_denied")
except FileNotFoundError:
    fail("executable_not_found")
except OSError:
    fail("process_start_failed")
raise SystemExit(result.returncode)
"""
