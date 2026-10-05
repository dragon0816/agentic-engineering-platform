"""Run one declared command on generated code under restricted Windows execution.

Coding on the Bridge (`docs/phases/CODING_ON_BRIDGE.md`) executes code a model
wrote, so the process gets no more than the run needs:

- a low-integrity token: it can read what the account reads, but can write
  only where the run folder was labelled low;
- a Job object with one active process, a memory cap and kill-on-close, so it
  cannot start another (unblocked) interpreter and dies with the run;
- an environment rebuilt from an allowlist, so no token or key reaches it;
- a wall-clock timeout that terminates the whole Job.

The outbound network block is a firewall rule on the runner interpreter; the
host checks that rule before a run (`harness.network_block`), because this
module cannot create it without administrator rights.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import Field

from common.base import Contract

#: Variables copied from the host environment; everything else is dropped.
ENVIRONMENT_ALLOWLIST = (
    "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
    "PATHEXT", "COMSPEC", "OS",
)
#: Output kept from a run; pytest's own summary fits easily.
MAX_OUTPUT_CHARS = 20_000
LOW_INTEGRITY_SID = "S-1-16-4096"


class RunnerError(Exception):
    """The run could not be started safely; nothing executed."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class RunnerLimits(Contract):
    timeout_seconds: int = Field(default=120, ge=5, le=1800, strict=True)
    memory_mb: int = Field(default=1024, ge=128, le=8192, strict=True)


@dataclass(frozen=True)
class RunResult:
    exit_code: int | None
    timed_out: bool
    output: str


def is_venv_launcher(python: Path) -> bool:
    """A venv's python.exe on Windows starts the base interpreter as a child;
    under a one-process Job that child is refused, and a firewall rule on the
    launcher would not cover it."""
    return (python.parent / "pyvenv.cfg").is_file() or (
        python.parent.parent / "pyvenv.cfg"
    ).is_file()


def label_low(folder: Path) -> None:
    """Let a low-integrity process write in `folder` and what it will hold."""
    result = subprocess.run(
        ["icacls", str(folder), "/setintegritylevel", "(OI)(CI)low", "/T", "/C", "/Q"],
        capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise RunnerError("run_folder_label_failed")


def restricted_environment(run_dir: Path, python: Path, extra: Mapping[str, str]) -> dict[str, str]:
    env = {name: os.environ[name] for name in ENVIRONMENT_ALLOWLIST if name in os.environ}
    temp = str(run_dir / "tmp")
    system_root = env.get("SYSTEMROOT", r"C:\Windows")
    env.update({
        "PATH": os.pathsep.join((str(python.parent), str(Path(system_root) / "System32"))),
        "TEMP": temp, "TMP": temp,
        "USERPROFILE": str(run_dir / "home"), "HOME": str(run_dir / "home"),
        "APPDATA": str(run_dir / "home"), "LOCALAPPDATA": str(run_dir / "home"),
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    env.update(extra)
    return env


class RestrictedRunner:
    """Runs `python <args>` in `cwd` under the limits above. Windows only."""

    def __init__(self, python: Path, limits: RunnerLimits | None = None) -> None:
        if sys.platform != "win32":
            raise RunnerError("restricted_runner_windows_only")
        if not python.is_file():
            raise RunnerError("runner_python_missing")
        if is_venv_launcher(python):
            raise RunnerError("runner_python_is_venv_launcher")
        self.python = python
        self.limits = limits if limits is not None else RunnerLimits()

    def run(
        self, args: Sequence[str], *, cwd: Path, run_dir: Path,
        extra_env: Mapping[str, str] | None = None,
    ) -> RunResult:
        import win32api
        import win32con
        import win32event
        import win32job
        import win32process
        import win32security

        for folder in (run_dir / "tmp", run_dir / "home"):
            folder.mkdir(parents=True, exist_ok=True)
        label_low(run_dir)
        output_path = run_dir / "output.txt"
        env = restricted_environment(run_dir, self.python, extra_env or {})
        command = subprocess.list2cmdline([str(self.python), *args])

        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(),
            win32con.TOKEN_DUPLICATE | win32con.TOKEN_QUERY | win32con.TOKEN_ADJUST_DEFAULT
            | win32con.TOKEN_ASSIGN_PRIMARY,
        )
        low = win32security.DuplicateTokenEx(
            token, win32security.SecurityImpersonation, win32con.MAXIMUM_ALLOWED,
            win32security.TokenPrimary, None,
        )
        win32security.SetTokenInformation(
            low, win32security.TokenIntegrityLevel,
            (win32security.ConvertStringSidToSid(LOW_INTEGRITY_SID),
             win32security.SE_GROUP_INTEGRITY),
        )
        job = win32job.CreateJobObject(None, "")
        limits = win32job.QueryInformationJobObject(
            job, win32job.JobObjectExtendedLimitInformation
        )
        limits["BasicLimitInformation"]["LimitFlags"] = (
            win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            | win32job.JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY
            | win32job.JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION
        )
        limits["BasicLimitInformation"]["ActiveProcessLimit"] = 1
        limits["ProcessMemoryLimit"] = self.limits.memory_mb * 1024 * 1024
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, limits)

        attributes = win32security.SECURITY_ATTRIBUTES()
        attributes.bInheritHandle = True
        # Opened here, at this process's integrity, and handed down: the
        # child writes through the handle without needing access to the file.
        handle = win32file_create(output_path, attributes)
        startup = win32process.STARTUPINFO()
        startup.dwFlags = win32process.STARTF_USESTDHANDLES
        startup.hStdOutput = handle
        startup.hStdError = handle
        startup.hStdInput = None
        try:
            process, thread, _, _ = win32process.CreateProcessAsUser(
                low, None, command, None, None, True,
                win32process.CREATE_SUSPENDED | win32process.CREATE_NO_WINDOW
                | win32process.CREATE_UNICODE_ENVIRONMENT,
                env, str(cwd), startup,
            )
        except Exception as error:  # noqa: BLE001 - a typed refusal, nothing ran
            handle.Close()
            job.Close()
            raise RunnerError("runner_start_failed") from error
        timed_out = False
        try:
            win32job.AssignProcessToJobObject(job, process)
            win32process.ResumeThread(thread)
            waited = win32event.WaitForSingleObject(process, self.limits.timeout_seconds * 1000)
            if waited == win32event.WAIT_TIMEOUT:
                timed_out = True
                win32job.TerminateJobObject(job, 1)
                win32event.WaitForSingleObject(process, 5000)
            exit_code = None if timed_out else win32process.GetExitCodeProcess(process)
        finally:
            for item in (thread, process, handle, job):
                item.Close()
        text = output_path.read_text(encoding="utf-8", errors="replace")
        return RunResult(exit_code=exit_code, timed_out=timed_out,
                         output=text[-MAX_OUTPUT_CHARS:])


def win32file_create(path: Path, attributes: Any) -> Any:
    import win32file

    return win32file.CreateFile(
        str(path), win32file.GENERIC_WRITE, win32file.FILE_SHARE_READ, attributes,
        win32file.CREATE_ALWAYS, win32file.FILE_ATTRIBUTE_NORMAL, None,
    )
