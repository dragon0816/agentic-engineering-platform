"""Laya decision acceleration from the Settings page (owner 2026-10-13).

The card edits `host.json` `laya`; the Agent's `decision_accelerator` is derived
from it, always pointing at a loopback port that an SSH tunnel forwards to the
Laya host. Agent Web can keep that tunnel open itself (`auto_tunnel`): it runs
`ssh -N` in batch mode, so a key that is not accepted fails visibly instead of
asking for a password, and it reopens a dropped tunnel with a growing pause.
Nothing here sends a message to Laya; the Gateway does that through the
existing egress approval.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agent.decisions import AcceleratorEgressApproval, DecisionAcceleratorConfig
from common.assets import SecretRef
from host_runtime.contracts import CompanyHostConfiguration, LayaSettings

ENDPOINT = "http://127.0.0.1:{port}/v1/systemone"
DEFAULT_CREDENTIAL = "jev_api_key"
DEFAULT_MODEL = "laya-rl-agent"
DEFAULT_MAX_TOOLS = 3
#: Pauses between attempts to reopen a dropped tunnel.
BACKOFF_SECONDS = (5, 10, 20, 40, 60)


class LayaError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def ssh_config_host(path: Path, alias: str = "laya") -> dict[str, Any]:
    """Host, port, user and forward of one `Host` block in an OpenSSH config,
    to prefill the card the first time; identity files are never read."""
    found: dict[str, Any] = {}
    if not path.is_file():
        return found
    inside = False
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        words = line.strip().split()
        if not words or words[0].startswith("#"):
            continue
        key = words[0].casefold()
        if key == "host":
            inside = alias in words[1:]
            continue
        if not inside or len(words) < 2:
            continue
        if key == "hostname":
            found["ssh_host"] = words[1]
        elif key == "port" and words[1].isdigit():
            found["ssh_port"] = int(words[1])
        elif key == "user":
            found["ssh_user"] = words[1]
        elif key == "localforward" and len(words) >= 3:
            local, remote = words[1].rsplit(":", 1)[-1], words[2].rsplit(":", 1)[-1]
            if local.isdigit() and remote.isdigit():
                found["local_port"], found["remote_port"] = int(local), int(remote)
    return found


def current_settings(config: CompanyHostConfiguration, ssh_config: Path | None = None
                     ) -> LayaSettings:
    """The card's values: the saved ones, or what host.json and the person's
    SSH config already say."""
    if config.laya is not None:
        return config.laya
    accelerator = config.decision_accelerator
    values: dict[str, Any] = {}
    if ssh_config is not None:
        values.update(ssh_config_host(ssh_config))
    if accelerator.provider == "JEV":
        port = urlparse(accelerator.endpoint or "").port
        if port is not None and port >= 1024:
            values["local_port"] = port
        values.update(mode=accelerator.mode, timeout_ms=max(100, accelerator.timeout_ms),
                      confidence_threshold=accelerator.confidence_threshold)
        if accelerator.egress_approval is not None:
            values["approval_ref"] = accelerator.egress_approval.approval_ref
    try:
        return LayaSettings.model_validate(values)
    except ValueError:
        return LayaSettings()


def accelerator_for(settings: LayaSettings, previous: DecisionAcceleratorConfig,
                    credentials: dict[str, str]) -> DecisionAcceleratorConfig:
    """The `decision_accelerator` the card's values mean. Settings the card
    does not show (credential name, model, decision types, list length) are
    kept from the previous configuration."""
    if settings.mode == "off":
        return DecisionAcceleratorConfig()
    if settings.approval_ref is None:
        raise LayaError("egress_approval_missing")
    jev = previous if previous.provider == "JEV" else None
    credential = jev.credential if jev is not None and jev.credential else SecretRef(
        name=DEFAULT_CREDENTIAL)
    if credential.name not in credentials:
        raise LayaError("credential_unmapped")
    return DecisionAcceleratorConfig(
        provider="JEV", endpoint=ENDPOINT.format(port=settings.local_port),
        credential=credential,
        model_profile=jev.model_profile if jev is not None else DEFAULT_MODEL,
        timeout_ms=settings.timeout_ms, confidence_threshold=settings.confidence_threshold,
        enabled_decision_types=jev.enabled_decision_types if jev is not None
        else ("skill_selection",),
        mode=settings.mode,
        skill_max_tools=jev.skill_max_tools if jev is not None else DEFAULT_MAX_TOOLS,
        egress_approval=AcceleratorEgressApproval(approval_ref=settings.approval_ref))


def tunnel_command(settings: LayaSettings, ssh: str = "ssh") -> list[str]:
    """One argument per item, never a shell line; host and user are validated
    names, so neither can become an ssh option."""
    return [
        ssh, "-N", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
        "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
        "-p", str(settings.ssh_port),
        "-L", f"127.0.0.1:{settings.local_port}:127.0.0.1:{settings.remote_port}",
        "-l", settings.ssh_user, "--", settings.ssh_host,
    ]


def probe(local_port: int, timeout: float = 2.0) -> dict[str, Any]:
    """Whether Laya answers through the local port, and how fast."""
    started = time.monotonic()
    try:
        with urllib.request.urlopen(  # noqa: S310 - a fixed loopback URL
                f"http://127.0.0.1:{local_port}/health", timeout=timeout) as reply:
            ok = reply.status == 200
    except (urllib.error.URLError, OSError, ValueError) as error:
        return {"reachable": False, "ms": None, "error": type(error).__name__}
    return {"reachable": ok, "ms": round((time.monotonic() - started) * 1000, 1),
            "error": None if ok else "unexpected_status"}


def last_decision(log: Path) -> dict[str, Any] | None:
    """The newest shadow decision: when, its outcome and how long Laya took."""
    if not log.is_file():
        return None
    with log.open("rb") as handle:
        handle.seek(0, 2)
        handle.seek(max(0, handle.tell() - 65536))
        tail = handle.read().decode("utf-8", errors="ignore").splitlines()
    for line in reversed(tail):
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get("kind") == "shadow":
            return {key: record.get(key) for key in ("at", "outcome", "latency_ms")}
    return None


Popen = Callable[..., Any]


def bind_to_this_process(pid: int) -> Any:
    """A Windows job that ends the child when Agent Web ends, even when it is
    killed rather than stopped, so no ssh is left holding the local port.
    Best effort: None where jobs are unavailable."""
    try:
        import win32api
        import win32con
        import win32job
    except ImportError:
        return None
    try:
        job = win32job.CreateJobObject(None, "")
        limits = win32job.QueryInformationJobObject(
            job, win32job.JobObjectExtendedLimitInformation)
        limits["BasicLimitInformation"]["LimitFlags"] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, limits)
        handle = win32api.OpenProcess(
            win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE, False, pid)
        win32job.AssignProcessToJobObject(job, handle)
        return job
    except Exception:  # noqa: BLE001 - the tunnel works without it
        return None


class SshTunnel:
    """`ssh -N` kept open while Agent Web runs."""

    def __init__(self, settings: LayaSettings, *, popen: Popen = subprocess.Popen,
                 ssh: str | None = None, sleep: Callable[[float], None] = time.sleep,
                 bind: Callable[[int], Any] = bind_to_this_process) -> None:
        self.settings = settings
        self._popen = popen
        self._ssh = ssh or shutil.which("ssh") or "ssh"
        self._sleep = sleep
        self._bind = bind
        self._job: Any = None
        self._stop = threading.Event()
        self._process: Any = None
        self._thread: threading.Thread | None = None
        self.state = "stopped"
        self.error: str | None = None
        self.restarts = 0
        self.since: str | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="laya-tunnel", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
        self.state = "stopped"

    def status(self) -> dict[str, Any]:
        return {"state": self.state, "error": self.error, "restarts": self.restarts,
                "since": self.since}

    def _run(self) -> None:
        attempt = 0
        while not self._stop.is_set():
            self.state, self.since = "starting", datetime.now(UTC).isoformat(timespec="seconds")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                self._process = self._popen(
                    tunnel_command(self.settings, self._ssh), stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=flags)
            except OSError as error:
                self.state, self.error = "failed", f"ssh_not_started:{type(error).__name__}"
                return
            self._job = self._bind(self._process.pid)
            self.state, opened = "running", time.monotonic()
            last = ""
            for raw in iter(self._process.stderr.readline, b""):
                text = raw.decode("utf-8", errors="ignore").strip()
                if text:
                    last = re.sub(r"\s+", " ", text)[:200]
            self._process.wait()
            if self._stop.is_set():
                break
            self.state, self.error = "down", last or f"exit {self._process.returncode}"
            self.restarts += 1
            if time.monotonic() - opened > 60:
                attempt = 0  # it was up for a while: start the pauses over
            self._sleep(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])
            attempt += 1
        self.state = "stopped"
