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

Starting takes 10-30 seconds, and a click that shows nothing for that long
looks broken (owner 2026-10-16). So when `open` has to start the server it
first opens a static page from the workspace, `agent-web-starting.html`
(no server behind it): a spinner and the elapsed time. The page loads
`agent-web-starting.js`, which this launcher rewrites as the start goes
(`starting`, `ready`, `failed`, `opened`), every second with a `<script>`
tag (a page opened from a file may not `fetch` another file). Only `ready`
carries the address, the same one `agent-web.json` already holds and the
browser was given before; the page then goes there. After `HANDOFF_SECONDS`
the launcher rewrites the status without it, so the address is left in no
other file. The page itself never holds the address.
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
from typing import Literal

from host_runtime.workspace import write_atomically

ADDRESS_FILE = "agent-web.json"
DEFAULT_PORT = 53583
START_WAIT_SECONDS = 180.0
STARTING_PAGE = "agent-web-starting.html"
STARTING_STATUS = "agent-web-starting.js"
#: How long the status keeps the address for the starting page to pick up.
HANDOFF_SECONDS = 15.0
#: After this long the starting page says it is taking too long, and where the log is.
SLOW_START_SECONDS = 120
StartState = Literal["starting", "ready", "failed", "opened"]
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


STARTING_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>AEP Agent is starting</title>
<style>
:root { --bg: #f6f7f9; --card: #ffffff; --text: #1d2330; --muted: #5d6675;
  --accent: #2f6fde; --ring: #dfe3ea; --warn-bg: #fff6e0; --warn: #7a5200;
  --bad-bg: #fde8e8; --bad: #9b1c1c; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #14171c; --card: #1d2128; --text: #e7eaf0; --muted: #a0a8b6;
    --accent: #6ea0ff; --ring: #343a45; --warn-bg: #3a2f12; --warn: #f3d27a;
    --bad-bg: #3d1a1a; --bad: #ffb4b4; }
}
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; display: flex; align-items: center;
  justify-content: center; background: var(--bg); color: var(--text);
  font: 16px/1.5 "Segoe UI", system-ui, -apple-system, sans-serif; padding: 16px; }
main { background: var(--card); border-radius: 12px; padding: 32px 28px;
  width: 100%; max-width: 480px; text-align: center;
  box-shadow: 0 2px 12px rgba(0, 0, 0, .12); }
h1 { font-size: 1.35rem; margin: 16px 0 4px; }
p { margin: 6px 0; color: var(--muted); }
#spinner { width: 48px; height: 48px; margin: 0 auto; border-radius: 50%;
  border: 5px solid var(--ring); border-top-color: var(--accent);
  animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { #spinner { animation-duration: 3s; } }
#elapsed { font-variant-numeric: tabular-nums; color: var(--text); font-weight: 600; }
.box { display: none; margin-top: 16px; padding: 12px 14px; border-radius: 8px;
  text-align: left; font-size: .95rem; }
.box.shown { display: block; }
#slow { background: var(--warn-bg); color: var(--warn); }
#failed { background: var(--bad-bg); color: var(--bad); }
code { font-family: Consolas, ui-monospace, monospace; word-break: break-all; }
</style>
</head>
<body>
<main>
  <div id="spinner" role="progressbar" aria-label="Starting"></div>
  <h1 id="title">AEP Agent is starting…</h1>
  <p lang="zh-TW">AEP Agent 啟動中，請稍候</p>
  <p id="note">This usually takes 10–30 seconds. Agent Web opens here by itself.</p>
  <p>Elapsed <span id="elapsed">0:00</span></p>
  <div id="slow" class="box" role="status">
    <strong>This is taking longer than usual.</strong>
    It may still start. If it does not, send the newest
    <code>agent-web-*.err.log</code> in <code class="logs"></code> to whoever supports AEP.
  </div>
  <div id="failed" class="box" role="alert">
    <strong>AEP Agent did not start.</strong> <span id="reason"></span>
    See the newest <code>agent-web-*.err.log</code> in <code class="logs"></code>.
  </div>
</main>
<script>
(function () {
  "use strict";
  var SLOW = __SLOW__ * 1000;
  var loaded = Date.now();
  var status = null;
  var done = false;
  var timer = null;
  var LOOPBACK = /^http:[/][/](127[.]0[.]0[.]1|localhost):[0-9]+[/]/;
  function el(id) { return document.getElementById(id); }
  function since() {
    var from = status && status.started_ms ? status.started_ms : loaded;
    return Math.max(0, Date.now() - from);
  }
  function clock(ms) {
    var s = Math.floor(ms / 1000);
    var r = s % 60;
    return Math.floor(s / 60) + ":" + (r < 10 ? "0" : "") + r;
  }
  function logs() {
    var where = (status && status.logs) || "the workspace logs folder";
    var items = document.querySelectorAll(".logs");
    for (var i = 0; i < items.length; i++) { items[i].textContent = where; }
  }
  function stop(title) {
    done = true;
    if (timer) { clearInterval(timer); }
    el("spinner").style.display = "none";
    el("title").textContent = title;
  }
  function render() {
    if (done) { return; }
    el("elapsed").textContent = clock(since());
    if (!status) { return; }
    if (status.state === "ready" && LOOPBACK.test(status.address || "")) {
      stop("Opening Agent Web…");
      window.location.replace(status.address);
      return;
    }
    if (status.state === "failed") {
      logs();
      el("reason").textContent = status.message || "";
      el("failed").className = "box shown";
      el("slow").className = "box";
      el("note").textContent = "";
      stop("AEP Agent did not start");
      return;
    }
    if (status.state === "opened") {
      el("note").textContent =
        "Agent Web is running. Click the AEP Agent shortcut again to open it.";
      stop("AEP Agent is running");
      return;
    }
    if (since() > SLOW) { logs(); el("slow").className = "box shown"; }
  }
  window.aepStarting = function (value) {
    if (value && typeof value === "object") { status = value; }
    render();
  };
  function poll() {
    if (done) { return; }
    var tag = document.createElement("script");
    tag.src = "__STATUS__?t=" + Date.now();
    tag.onload = tag.onerror = function () {
      if (tag.parentNode) { tag.parentNode.removeChild(tag); }
    };
    document.body.appendChild(tag);
    render();
  }
  timer = setInterval(poll, 1000);
  poll();
})();
</script>
</body>
</html>
""".replace("__SLOW__", str(SLOW_START_SECONDS)).replace("__STATUS__", STARTING_STATUS)


def starting_page(workspace_root: Path) -> Path:
    return workspace_root / STARTING_PAGE


def write_starting_page(workspace_root: Path) -> Path:
    """The static page `open` shows while Agent Web starts; it holds no address."""
    path = starting_page(workspace_root)
    write_atomically(path, STARTING_HTML.encode("utf-8"))
    return path


def write_start_status(
    workspace_root: Path,
    state: StartState,
    *,
    started_ms: int,
    message: str = "",
    address: str = "",
) -> None:
    """What the starting page reads. Only `ready` carries the address."""
    status: dict[str, object] = {
        "state": state,
        "started_ms": started_ms,
        "logs": str(workspace_root / "logs"),
        "message": message,
    }
    if state == "ready":
        status["address"] = address
    script = f"window.aepStarting && window.aepStarting({json.dumps(status)});\n"
    write_atomically(workspace_root / STARTING_STATUS, script.encode("utf-8"))


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


def start_server(
    config_path: Path, port: int, logs: Path, schedules: bool = True
) -> subprocess.Popen[bytes]:
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
        return subprocess.Popen(
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
    start: Callable[[], object] | None = None,
    opener: Callable[[str], object] = webbrowser.open,
    wait_seconds: float = START_WAIT_SECONDS,
    poll: float = 1.0,
    handoff_seconds: float = HANDOFF_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Open the running Agent Web, starting it first when nothing answers.

    While it starts, the browser shows the starting page, which goes on to
    Agent Web when the status says `ready`. When the browser could not be
    asked to show the page, Agent Web is opened directly, as before."""
    record = read_record(workspace_root)
    if record is not None and answers(str(record["address"])):
        opener(str(record["address"]))
        return "opened"
    if record is not None:
        record_path(workspace_root).unlink(missing_ok=True)  # left by a server that died
    started_ms = int(time.time() * 1000)
    write_start_status(workspace_root, "starting", started_ms=started_ms)
    shown = opener(write_starting_page(workspace_root).as_uri()) is not False
    launch = start or (lambda: start_server(config_path, port, workspace_root / "logs", schedules))
    process = launch()
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        record = read_record(workspace_root)
        if record is not None and answers(str(record["address"])):
            address = str(record["address"])
            if not shown:
                opener(address)
                return "started"
            write_start_status(workspace_root, "ready", started_ms=started_ms, address=address)
            sleep(handoff_seconds)
            write_start_status(workspace_root, "opened", started_ms=started_ms)
            return "started"
        exited = getattr(process, "poll", None)
        code = exited() if callable(exited) else None
        if code is not None:
            message = f"Agent Web stopped while starting (exit code {code})."
            write_start_status(workspace_root, "failed", started_ms=started_ms, message=message)
            raise LauncherError(
                "agent_web_exited",
                f"{message} See the newest agent-web-*.err.log in {workspace_root / 'logs'}",
            )
        sleep(poll)
    message = f"Agent Web did not answer within {wait_seconds:g} seconds."
    write_start_status(workspace_root, "failed", started_ms=started_ms, message=message)
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
