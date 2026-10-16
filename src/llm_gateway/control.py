"""Start, stop, inspect and test the gateway; switch its autostart.

Used by `aep-host gateway ...` and (phase B) the Settings card. Standard
library only: this runs in AEP's environment, the gateway in its own.

Status `state`:
    serving   /health/liveliness answers on 127.0.0.1:<port>
    starting  the gateway process AEP started is alive, the port not yet
    stopped   neither
and `ours` says whether the serving process is the one in state.json (a
gateway someone else runs on the same port is reported, never stopped).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from llm_gateway import LOOPBACK, PINNED_LITELLM_VERSION, secrets_file, state
from llm_gateway.config import (
    TOKEN_VARIABLE,
    GatewayConfigError,
    GatewayPaths,
    GatewaySettings,
    load_settings,
    validate_config_text,
)

PYTHON_VARIABLE = "AEP_GATEWAY_PYTHON"
TASK_NAME = "AEP LLM Gateway"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "AEP LLM Gateway"
LOG_LIMIT_BYTES = 10 * 1024 * 1024
TEST_PROMPT = "Reply with exactly: OK"


class GatewayControlError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


# --- probing -------------------------------------------------------------------


def health(port: int, timeout: float = 2.0) -> bool:
    """Whether LiteLLM's liveness probe answers (no key needed)."""
    url = f"http://{LOOPBACK}:{port}/health/liveliness"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - loopback
            return bool(response.status == 200)
    except (urllib.error.URLError, OSError, ValueError):
        return False


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def gateway_python(settings: GatewaySettings, environ: Mapping[str, str]) -> Path:
    chosen = settings.python or environ.get(PYTHON_VARIABLE, "") or sys.executable
    return Path(chosen)


def windowless(python: Path) -> Path:
    """pythonw.exe beside python.exe, so autostart opens no console."""
    candidate = python.with_name("pythonw.exe")
    if python.name.lower() == "python.exe" and candidate.is_file():
        return candidate
    return python


def installed_litellm(python: Path) -> str | None:
    """LiteLLM's version in the gateway's environment, read from its files
    (LiteLLM is never imported into AEP's process)."""
    roots = [
        python.parent.parent / "Lib" / "site-packages",
        python.parent / "Lib" / "site-packages",
    ]
    roots += sorted((python.parent.parent / "lib").glob("python3*/site-packages"))
    for root in roots:
        for info in sorted(root.glob("litellm-*.dist-info")):
            return info.name[len("litellm-") : -len(".dist-info")]
    return None


# --- status --------------------------------------------------------------------


@dataclass
class GatewayStatus:
    state: str
    port: int
    ours: bool
    pid: int | None
    home: str
    config_problems: list[str]
    token: dict[str, object]
    key_present: bool
    last_refresh_at: str | None
    last_refresh_error: str | None
    last_test: object
    litellm_version: str | None
    autostart: dict[str, object] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        return {
            "state": self.state,
            "port": self.port,
            "address": f"http://{LOOPBACK}:{self.port}/v1",
            "ours": self.ours,
            "pid": self.pid,
            "home": self.home,
            "config_ok": not self.config_problems,
            "config_problems": self.config_problems,
            "token": self.token,
            "key_present": self.key_present,
            "last_refresh_at": self.last_refresh_at,
            "last_refresh_error": self.last_refresh_error,
            "last_test": self.last_test,
            "litellm_version": self.litellm_version,
            "litellm_pinned": PINNED_LITELLM_VERSION,
            "autostart": self.autostart,
        }


def status(
    paths: GatewayPaths,
    environ: Mapping[str, str] | None = None,
    *,
    probe: Callable[[int], bool] = health,
    alive: Callable[[int], bool] = process_alive,
    autostart_query: Callable[[], dict[str, object]] | None = None,
) -> GatewayStatus:
    env = os.environ if environ is None else environ
    problems: list[str] = []
    try:
        settings = load_settings(paths)
    except GatewayConfigError as error:
        settings = GatewaySettings()
        problems.append(str(error))
    try:
        problems += validate_config_text(paths.config.read_text(encoding="utf-8"))
    except FileNotFoundError:
        problems.append("no configuration; run `aep-host gateway init`")
    values = secrets_file.read(settings.secrets_path(paths))
    token = secrets_file.token_info(values.get(TOKEN_VARIABLE) or env.get(TOKEN_VARIABLE))
    facts = state.read(paths.state)
    raw_pid = facts.get("pid")
    pid = raw_pid if isinstance(raw_pid, int) and not isinstance(raw_pid, bool) else None
    running = pid is not None and alive(pid)
    serving = probe(settings.port)
    if serving:
        current = "serving"
    elif running:
        current = "starting"
    else:
        current = "stopped"
    refreshed = facts.get("last_refresh_at")
    refresh_error = facts.get("last_refresh_error")
    return GatewayStatus(
        state=current,
        port=settings.port,
        ours=running,
        pid=pid if running else None,
        home=str(paths.home),
        config_problems=problems,
        token=token.to_json(),
        key_present=bool(secrets_file.resolve_master_key(values, env)),
        last_refresh_at=refreshed if isinstance(refreshed, str) else None,
        last_refresh_error=refresh_error if isinstance(refresh_error, str) else None,
        last_test=facts.get("last_test"),
        litellm_version=installed_litellm(gateway_python(settings, env)),
        autostart=autostart_query() if autostart_query else {},
    )


# --- start / stop --------------------------------------------------------------


def launch_command(python: Path, paths: GatewayPaths, *, refresh_if_due: bool = False) -> list[str]:
    command = [str(python), "-m", "llm_gateway.launcher", "--home", str(paths.home)]
    if refresh_if_due:
        command.append("--refresh-if-due")
    return command


def rotate_log(log: Path, limit: int = LOG_LIMIT_BYTES) -> None:
    try:
        if log.stat().st_size > limit:
            os.replace(log, log.with_name(log.name + ".1"))
    except FileNotFoundError:
        return


Spawner = Callable[[Sequence[str], Path, Mapping[str, str]], int]


def spawn_detached(command: Sequence[str], log: Path, environ: Mapping[str, str]) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    rotate_log(log)
    flags = 0
    if sys.platform == "win32":
        flags = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
        )
    with log.open("ab") as output:
        output.write(f"=== gateway start {datetime.now(UTC).isoformat()} ===\n".encode())
        output.flush()
        process = subprocess.Popen(
            list(command),
            stdout=output,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=dict(environ),
            creationflags=flags,
            close_fds=True,
        )
    return process.pid


def start(
    paths: GatewayPaths,
    environ: Mapping[str, str] | None = None,
    *,
    wait_seconds: float = 0.0,
    probe: Callable[[int], bool] = health,
    alive: Callable[[int], bool] = process_alive,
    spawner: Spawner = spawn_detached,
    sleep: Callable[[float], None] = time.sleep,
) -> GatewayStatus:
    env = dict(os.environ if environ is None else environ)
    current = status(paths, env, probe=probe, alive=alive)
    if current.state in ("serving", "starting"):
        return current
    if current.config_problems:
        raise GatewayControlError("config", "; ".join(current.config_problems))
    settings = load_settings(paths)
    python = gateway_python(settings, env)
    pid = spawner(launch_command(windowless(python), paths), paths.log, env)
    state.update(paths.state, pid=pid, started_at=state.now_text(), port=settings.port)
    deadline = time.monotonic() + wait_seconds
    while wait_seconds > 0 and time.monotonic() < deadline:
        if probe(settings.port) or not alive(pid):
            break
        sleep(1.0)
    return status(paths, env, probe=probe, alive=alive)


def stop(
    paths: GatewayPaths,
    *,
    probe: Callable[[int], bool] = health,
    alive: Callable[[int], bool] = process_alive,
    killer: Callable[[int], None] | None = None,
) -> GatewayStatus:
    """Stop the gateway AEP started. One it did not start is left alone."""
    current = status(paths, {}, probe=probe, alive=alive)
    if current.pid is None:
        if current.state == "serving":
            raise GatewayControlError(
                "not_ours",
                f"127.0.0.1:{current.port} is served by a gateway AEP did not start; "
                "stop it where it was started.",
            )
        return current
    (killer or kill_tree)(current.pid)
    state.update(paths.state, pid=None)
    return status(paths, {}, probe=probe, alive=alive)


def kill_tree(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        os.kill(pid, 15)


# --- test ----------------------------------------------------------------------


@dataclass(frozen=True)
class ModelCheck:
    model: str
    ok: bool
    code: str
    detail: str = ""
    seconds: float = 0.0

    def to_json(self) -> dict[str, object]:
        return {
            "model": self.model,
            "ok": self.ok,
            "code": self.code,
            "detail": self.detail,
            "seconds": round(self.seconds, 1),
        }


#: What an HTTP status from the gateway most likely means (manual section).
HINTS = {
    401: ("unauthorized", "token expired or wrong local key: refresh the token, then restart"),
    404: ("unknown_model", "the model name is not in the gateway's list"),
    405: ("responses_api", "a model uses openai/ instead of hosted_vllm/ (Responses API)"),
    429: ("rate_limited", "the service is rate limiting; try again later"),
}


def _request(
    url: str, key: str, body: Mapping[str, object] | None, timeout: float
) -> tuple[int, object]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - loopback
        url,
        data=data,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return int(response.status), json.loads(response.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as error:
        text = error.read().decode("utf-8", "replace")[:2000]
        try:
            return int(error.code), json.loads(text)
        except ValueError:
            return int(error.code), text


def _summary(payload: object) -> str:
    """A short, value-free description of an error body."""
    if isinstance(payload, dict):
        error = payload.get("error", payload)
        if isinstance(error, dict):
            message = error.get("message", "")
            return str(message)[:300]
        return str(error)[:300]
    return str(payload)[:300]


def test(
    paths: GatewayPaths,
    environ: Mapping[str, str] | None = None,
    *,
    models: Sequence[str] | None = None,
    timeout: float = 120.0,
    clock: Callable[[], float] = time.monotonic,
) -> list[ModelCheck]:
    """List the gateway's models, then ask each requested one for `OK`."""
    env = os.environ if environ is None else environ
    settings = load_settings(paths)
    key = secrets_file.resolve_master_key(secrets_file.read(settings.secrets_path(paths)), env)
    base = f"http://{LOOPBACK}:{settings.port}/v1"
    results: list[ModelCheck] = []
    try:
        code, listing = _request(f"{base}/models", key, None, 20.0)
    except (urllib.error.URLError, OSError) as error:
        results.append(ModelCheck("(models)", False, "not_running", str(error)[:200]))
        _record(paths, results)
        return results
    if code != 200:
        name, hint = HINTS.get(code, ("http_error", f"HTTP {code}"))
        results.append(ModelCheck("(models)", False, name, f"{hint}: {_summary(listing)}"))
        _record(paths, results)
        return results
    available = []
    if isinstance(listing, dict) and isinstance(listing.get("data"), list):
        available = [
            item["id"]
            for item in listing["data"]
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
    results.append(ModelCheck("(models)", True, "ok", ", ".join(available)))
    for model in models or [settings.default_model]:
        started = clock()
        try:
            code, answer = _request(
                f"{base}/chat/completions",
                key,
                {"model": model, "messages": [{"role": "user", "content": TEST_PROMPT}]},
                timeout,
            )
        except (urllib.error.URLError, OSError) as error:
            results.append(
                ModelCheck(model, False, "no_answer", str(error)[:200], clock() - started)
            )
            continue
        elapsed = clock() - started
        if code == 200:
            text = ""
            if isinstance(answer, dict):
                choices = answer.get("choices")
                if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                    message = choices[0].get("message")
                    if isinstance(message, dict):
                        text = str(message.get("content") or "")[:80]
            results.append(ModelCheck(model, True, "ok", text, elapsed))
        else:
            name, hint = HINTS.get(code, ("http_error", f"HTTP {code}"))
            results.append(ModelCheck(model, False, name, f"{hint}: {_summary(answer)}", elapsed))
    _record(paths, results)
    return results


def _record(paths: GatewayPaths, results: Sequence[ModelCheck]) -> None:
    state.update(
        paths.state,
        last_test={
            "at": state.now_text(),
            "results": [{"model": r.model, "ok": r.ok, "code": r.code} for r in results],
        },
    )


# --- autostart -----------------------------------------------------------------


def task_script(command: Sequence[str]) -> str:
    """PowerShell that registers the logon task for the current user only,
    without elevation, never restarting a gateway that exited (a bad token
    would otherwise look like a restart loop)."""

    def quoted(text: str) -> str:
        return "'" + text.replace("'", "''") + "'"

    arguments = " ".join('"' + part + '"' if " " in part else part for part in command[1:])
    return "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            "$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name",
            f"$action = New-ScheduledTaskAction -Execute {quoted(command[0])} "
            f"-Argument {quoted(arguments)}",
            "$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user",
            "$principal = New-ScheduledTaskPrincipal -UserId $user "
            "-LogonType Interactive -RunLevel Limited",
            "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries "
            "-DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) "
            "-MultipleInstances IgnoreNew",
            f"Register-ScheduledTask -TaskName {quoted(TASK_NAME)} -Action $action "
            "-Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null",
        ]
    )


CommandRunner = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]


def run_command(arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(arguments),
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )


class RunKey:
    """HKCU\\...\\Run, the fallback when Task Scheduler refuses a logon task
    to a user without elevation. Injectable so tests never touch the registry."""

    def get(self) -> str | None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value, _kind = winreg.QueryValueEx(key, RUN_VALUE)
        except OSError:
            return None
        return value if isinstance(value, str) else None

    def set(self, command: str) -> None:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, command)

    def delete(self) -> None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, RUN_VALUE)
        except OSError:
            return


def command_line(command: Sequence[str]) -> str:
    return subprocess.list2cmdline(list(command))


def autostart_query(
    runner: CommandRunner = run_command, run_key: RunKey | None = None
) -> dict[str, object]:
    task = runner(["schtasks", "/Query", "/TN", TASK_NAME]).returncode == 0
    run = (run_key or RunKey()).get() is not None if sys.platform == "win32" else False
    return {"on": task or run, "task": task, "run_key": run}


def set_autostart(
    paths: GatewayPaths,
    on: bool,
    environ: Mapping[str, str] | None = None,
    *,
    runner: CommandRunner = run_command,
    run_key: RunKey | None = None,
) -> dict[str, object]:
    """Switch the logon start: a Task Scheduler task for the current user,
    or the user's Run key when the task is refused. Off removes both."""
    env = os.environ if environ is None else environ
    keys = run_key or RunKey()
    if not on:
        runner(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
        keys.delete()
        return {"on": False, "task": False, "run_key": False}
    settings = load_settings(paths)
    command = launch_command(windowless(gateway_python(settings, env)), paths, refresh_if_due=True)
    registered = runner(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", task_script(command)]
    )
    if registered.returncode == 0:
        keys.delete()
        return {"on": True, "task": True, "run_key": False}
    keys.set(command_line(command))
    return {
        "on": True,
        "task": False,
        "run_key": True,
        "note": "Task Scheduler refused the logon task; using the user's Run key instead.",
    }
