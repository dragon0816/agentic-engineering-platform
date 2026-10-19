"""What the Windows COM adapters share: asking whether an application is here,
and initialising COM on the thread that uses it (`apartment`).

Two adapters now drive Office through COM -- the workbook through Excel and
the weekly mail's draft through Outlook -- and both have to tell "this
installation is missing the bridge" apart from "this machine does not have
that application". The answer to the second is a registry read, and it is the
same read for either, so it lives here rather than in whichever adapter was
written first.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager


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


# ---------------------------------------------------------------------------
# COM on the calling thread
# ---------------------------------------------------------------------------
#
# COM must be initialised on every thread that uses it. Importing pythoncom
# initialises the importing thread only, so the first capability call that
# imported pywin32 on a worker thread worked and a later one, on another
# worker of `asyncio.to_thread`, failed with CO_E_NOTINITIALIZED (-2147221008;
# live test 2026-10-20: a second signature harvest after a restart). Every
# adapter now enters `apartment()` around each use and creates its Office
# object inside it, so no COM object crosses a thread or outlives the block.

#: CO_E_NOTINITIALIZED: COM was not initialised on the calling thread.
CO_E_NOTINITIALIZED = -2147221008
#: RPC_E_CHANGED_MODE: the thread is already initialised in another apartment.
RPC_E_CHANGED_MODE = -2147417850
_THREAD = threading.local()


def _co_initialize() -> bool:
    """Initialise COM (single-threaded apartment) on this thread. False when
    pywin32 is not installed: the adapter then refuses with its own
    `library_missing`, so there is nothing to initialise."""
    try:
        import pythoncom
    except ImportError:
        return False
    try:
        pythoncom.CoInitialize()
    except pythoncom.com_error as error:
        if getattr(error, "hresult", None) == RPC_E_CHANGED_MODE:
            # Already initialised on this thread as another apartment: usable,
            # and not ours to release.
            return False
        raise
    return True


def _co_uninitialize() -> None:
    import pythoncom

    pythoncom.CoUninitialize()


@contextmanager
def apartment() -> Iterator[None]:
    """COM initialised on the calling thread for the block, and released
    after it. Nested blocks on one thread initialise once.

    A caller creates its COM objects inside the block and lets them go before
    it ends: call a function that holds them as locals from inside the block,
    rather than keeping them on an object across calls."""
    depth: int = getattr(_THREAD, "depth", 0)
    if depth == 0:
        _THREAD.entered = _co_initialize()
    _THREAD.depth = depth + 1
    try:
        yield
    finally:
        _THREAD.depth -= 1
        if _THREAD.depth == 0 and _THREAD.entered:
            _THREAD.entered = False
            _co_uninitialize()
