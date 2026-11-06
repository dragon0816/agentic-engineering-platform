"""Real attempts to get past the guard of BI tools and analyses (`analyses.GUARD`).

The guard catches mistakes and stray model output; a person approving the code is the real
control. Still, a script must not switch the guard off in one line, or reach a module the
guard denies because something loaded it first: before 2026-11-06 a tool could set
`__main__._ready = False`, reach the guard through a frame or the garbage collector, and,
with numpy installed (the release bundle carries it), use ctypes that openpyxl had pulled
in, writing process memory with no audit event. Every attempt here writes, or tries to
write, only a marker in a temp folder.
"""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

from capabilities.bi_cards import analyses, tool_runs
from capabilities.bi_cards.store import BiStoreError

NUMPY = importlib.util.find_spec("numpy") is not None
MARK = "outside-marker.txt"


def _attempts(outside: Path) -> dict[str, str]:
    escape = f"open({str(outside)!r}, 'w').write('escaped')\n"
    return {
        "import ctypes": "import ctypes\n",
        "ctypes from sys.modules": "import sys\nsys.modules['ctypes'].CDLL\n",
        "turn the guard off through __main__": (
            f"import __main__\n__main__._ready = False\n{escape}"
        ),
        "empty its list through __main__": (
            f"import __main__\n__main__.DENIED_EVENTS = ()\n__main__.WRITES = ()\n{escape}"
        ),
        "a builtin it calls": f"import builtins\nbuiltins.isinstance = lambda *a: False\n{escape}",
        "a function it calls": (
            f"import os\nos.path.realpath = lambda p: globals().get('OUTPUT', p)\n{escape}"
        ),
        "the frame that runs the script": (
            f"import sys\nsys._getframe(1).f_globals['_ready'] = False\n{escape}"
        ),
        "a traceback's frame": (
            "try:\n    raise ValueError\nexcept ValueError as e:\n"
            "    e.__traceback__.tb_frame.f_back.f_globals['_ready'] = False\n" + escape
        ),
        "the garbage collector": (
            "import gc\n[o for o in gc.get_objects() if getattr(o, '__name__', '') == '_guard']\n"
        ),
        "a trace function": "import sys\nsys.settrace(lambda *a: None)\n",
        "a child process through _winapi": (
            "import shutil\nshutil._winapi.CreateProcess(None, 'cmd /c exit 0', None, None, "
            "False, 0, None, None, None)\n"
        ),
        "a socket": "import socket\n",
    }


NUMPY_ATTEMPTS = {
    "ctypes through numpy": "import numpy\nnumpy.ctypeslib.ctypes\n",
    "ctypes memory write": (
        "import numpy\nc = numpy.ctypeslib.ctypes\n"
        "class U(c.Union):\n    _fields_ = [('a', c.c_void_p), ('p', c.POINTER(c.c_char))]\n"
    ),
}


def _tool(tmp_path: Path, code: str) -> None:
    source = tmp_path / "in.csv"
    source.write_text("a\n1\n", encoding="utf-8")
    done = code + "open(OUTPUT + '/out.csv', 'w').write('x\\n1\\n')\n"
    tool_runs.execute(done.encode("utf-8"), source, "in.csv", 60)


def _analysis(tmp_path: Path, code: str) -> None:
    db = tmp_path / "bi.sqlite"
    sqlite3.connect(db).close()
    analyses.run_python(db, code + "result = {'columns': ['x'], 'rows': [[1]]}\n", seconds=60)


RUNNERS = {"tool": _tool, "analysis": _analysis}


@pytest.mark.parametrize("runner", sorted(RUNNERS))
@pytest.mark.parametrize("name", sorted(_attempts(Path("x"))))
def test_an_attempt_is_refused_and_writes_nothing_outside(
    tmp_path: Path, runner: str, name: str
) -> None:
    outside = tmp_path / MARK
    with pytest.raises(BiStoreError):
        RUNNERS[runner](tmp_path, _attempts(outside)[name])
    assert not outside.exists(), name


@pytest.mark.skipif(not NUMPY, reason="numpy is not installed here (the release bundle has it)")
@pytest.mark.parametrize("runner", sorted(RUNNERS))
@pytest.mark.parametrize("name", sorted(NUMPY_ATTEMPTS))
def test_with_numpy_installed_ctypes_stays_out_of_reach(
    tmp_path: Path, runner: str, name: str
) -> None:
    with pytest.raises(BiStoreError):
        RUNNERS[runner](tmp_path, NUMPY_ATTEMPTS[name])


def test_a_denied_module_loaded_before_the_guard_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Whatever pulls one in tomorrow, the guard does not start with it in `sys.modules`.
    early = tool_runs.RUNNER.replace(
        '_install(OUTPUT, "a tool"', 'import ctypes\n_install(OUTPUT, "a tool"'
    )
    assert early != tool_runs.RUNNER
    monkeypatch.setattr(tool_runs, "RUNNER", early)
    with pytest.raises(BiStoreError) as failure:
        _tool(tmp_path, "")
    assert "loaded before the guard: _ctypes, ctypes" in failure.value.message


def test_openpyxl_still_works_in_a_tool(tmp_path: Path) -> None:
    pytest.importorskip("openpyxl")
    _tool(tmp_path, "import openpyxl\nopenpyxl.Workbook()\n")
