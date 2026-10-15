"""Open Agent Web with one click (owner 2026-10-08).

The token still changes on every start (`web.py`'s guard). Instead of the
person copying the address, the running server keeps it in a file in the
workspace, which is under the Windows user's own profile:

- `aep-host web` writes `agent-web.json` (address, port, process) once it
  listens, and removes it when it stops;
- `aep-host open` opens that address in the browser. When nothing answers,
  it first starts `aep-host web` in the background, with the user's current
  environment variables re-read so credentials set since logon are seen;
- `aep-host shortcut` puts an "AEP Agent" shortcut on the desktop and in the
  Start menu that runs `open` without a console window.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from host_runtime.workspace import write_atomically

ADDRESS_FILE = "agent-web.json"
DEFAULT_PORT = 53583
START_WAIT_SECONDS = 180.0
# Environment the server needs that may have been set after this logon.
REFRESHED_PREFIXES = ("AEP_", "LITELLM_", "ARTIFACTORY_", "OPS_")


class LauncherError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def record_path(workspace_root: Path) -> Path:
    return workspace_root / ADDRESS_FILE


def write_record(workspace_root: Path, address: str, port: int) -> None:
    record = {
        "address": address,
        "port": port,
        "pid": os.getpid(),
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    write_atomically(record_path(workspace_root), json.dumps(record).encode("utf-8"))


def clear_record(workspace_root: Path) -> None:
    """Remove the address, only if it is this process's own."""
    path = record_path(workspace_root)
    try:
        if json.loads(path.read_text(encoding="utf-8")).get("pid") == os.getpid():
            path.unlink(missing_ok=True)
    except (OSError, ValueError):
        return


def read_record(workspace_root: Path) -> dict[str, object] | None:
    try:
        record = json.loads(record_path(workspace_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) and isinstance(record.get("address"), str) else None


def answers(address: str, timeout: float = 3.0) -> bool:
    """Whether the server behind this address is up and takes its token."""
    try:
        with urllib.request.urlopen(address, timeout=timeout) as response:  # noqa: S310 - loopback
            return bool(response.status == 200)
    except (urllib.error.URLError, OSError, ValueError):
        return False


def refreshed_environment(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """This process's environment with the user's and machine's current
    AEP-related variables read again from the registry (Windows)."""
    env = dict(os.environ if base is None else base)
    if sys.platform != "win32":
        return env
    import winreg

    places = (
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
        (winreg.HKEY_CURRENT_USER, "Environment"),
    )
    for hive, key_path in places:
        try:
            key = winreg.OpenKey(hive, key_path)
        except OSError:
            continue
        with key:
            index = 0
            while True:
                try:
                    name, value, kind = winreg.EnumValue(key, index)
                except OSError:
                    break
                index += 1
                if not name.upper().startswith(REFRESHED_PREFIXES) or not isinstance(value, str):
                    continue
                env[name] = os.path.expandvars(value) if kind == winreg.REG_EXPAND_SZ else value
    return env


def console_python(executable: str = sys.executable) -> str:
    """python.exe beside pythonw.exe: the server's output goes to log files."""
    path = Path(executable)
    if path.name.lower() == "pythonw.exe" and (path.parent / "python.exe").is_file():
        return str(path.parent / "python.exe")
    return executable


def start_server(config_path: Path, port: int, logs: Path, schedules: bool = True) -> None:
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    args = [
        console_python(),
        "-u",
        "-m",
        "host_runtime.cli",
        "web",
        "--config",
        str(config_path.resolve()),
        "--port",
        str(port),
    ]
    if schedules:
        args.append("--schedules")
    flags = 0
    if sys.platform == "win32":
        flags = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
        )
    with (
        (logs / f"agent-web-{stamp}.out.log").open("wb") as out,
        (logs / f"agent-web-{stamp}.err.log").open("wb") as err,
    ):
        subprocess.Popen(
            args,
            stdout=out,
            stderr=err,
            stdin=subprocess.DEVNULL,
            env=refreshed_environment(),
            creationflags=flags,
            close_fds=True,
        )


def open_agent(
    workspace_root: Path,
    config_path: Path,
    *,
    port: int = DEFAULT_PORT,
    schedules: bool = True,
    start: Callable[[], None] | None = None,
    opener: Callable[[str], object] = webbrowser.open,
    wait_seconds: float = START_WAIT_SECONDS,
    poll: float = 1.0,
) -> str:
    """Open the running Agent Web, starting it first when nothing answers."""
    record = read_record(workspace_root)
    if record is not None and answers(str(record["address"])):
        opener(str(record["address"]))
        return "opened"
    if record is not None:
        record_path(workspace_root).unlink(missing_ok=True)  # left by a server that died
    launch = start or (lambda: start_server(config_path, port, workspace_root / "logs", schedules))
    launch()
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        record = read_record(workspace_root)
        if record is not None and answers(str(record["address"])):
            opener(str(record["address"]))
            return "started"
        time.sleep(poll)
    raise LauncherError(
        "agent_web_not_started",
        f"Agent Web did not answer within {wait_seconds:g} seconds; see the newest "
        f"agent-web-*.err.log in {workspace_root / 'logs'}",
    )


#: The AEP Agent icon the shortcuts show; scripts/make_icon.py makes it from a PNG.
SHORTCUT_ICON = Path(__file__).parent / "icons" / "aep-agent.ico"


def create_shortcuts(config_path: Path, port: int = DEFAULT_PORT) -> list[Path]:
    """Desktop and Start menu shortcuts running `aep-host open` without a window."""
    if sys.platform != "win32":
        raise LauncherError("shortcut_windows_only", "shortcuts are made on Windows only")
    python = Path(sys.executable)
    windowless = python.parent / "pythonw.exe"
    target = windowless if windowless.is_file() else python
    arguments = f'-m host_runtime.cli open --config "{config_path.resolve()}" --port {port}'
    places = [
        Path(os.environ.get("USERPROFILE", "~")).expanduser() / "Desktop",
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    made: list[Path] = []
    for place in places:
        if not place.is_dir():
            continue
        link = place / "AEP Agent.lnk"
        script = (
            "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:AEP_LINK); "
            "$s.TargetPath = $env:AEP_TARGET; $s.Arguments = $env:AEP_ARGS; "
            "$s.WorkingDirectory = $env:AEP_DIR; $s.Description = 'Open AEP Agent Web'; "
            "if ($env:AEP_ICON) { $s.IconLocation = $env:AEP_ICON + ',0' }; "
            "$s.Save()"
        )
        # Values travel in the environment, so no path is ever parsed as script.
        env = {
            **os.environ,
            "AEP_LINK": str(link),
            "AEP_TARGET": str(target),
            "AEP_ARGS": arguments,
            "AEP_DIR": str(config_path.resolve().parent),
            "AEP_ICON": str(SHORTCUT_ICON) if SHORTCUT_ICON.is_file() else "",
        }
        done = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if done.returncode != 0:
            raise LauncherError("shortcut_failed", f"could not create {link}")
        made.append(link)
    return made
