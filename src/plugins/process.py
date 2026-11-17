"""One plugin worker process with a bounded JSON-lines exchange.

The wire messages are the existing Bridge Extension ones
(`extensions.runtime.ExtensionRequest/ExtensionResponse`,
`aep-extension-jsonl/v1`). Unlike the legacy session, a reply line is read
with a byte limit, so a worker cannot make the core buffer unbounded output.
Requests to one worker are serialized. A timeout, a closed stream, an
oversized or malformed reply ends the process (its whole tree on Windows);
nothing is retried here, so a write is never sent twice.

The worker runs with the AEP interpreter itself, isolated (`-I`), unbuffered
(`-u`) and without writing bytecode (`-B`, the staged folder stays exactly as
installed). A fixed bootstrap puts the staged `worker/` folder first on
`sys.path` and runs the declared module. It inherits the ordinary
environment plus the staged package file and the plugin's data folder.
"""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path
from threading import Lock
from typing import IO
from uuid import uuid4

from pydantic import JsonValue, ValidationError

import common.plugins as contract
from common.assets import AssetIdentity
from common.plugins import PluginErrorCode, PluginManifest
from extensions.runtime import ExtensionRequest, ExtensionResponse

PACKAGE_ENV = "AEP_PLUGIN_PACKAGE_FILE"
DATA_ENV = "AEP_PLUGIN_DATA_ROOT"
#: Platform-owned context key (Plugin API 1.1, H1): the Host's existing `bi/`
#: folder, set only for a manifest declaring `data.reads = ("bi",)`.
READ_BI_ENV = "AEP_PLUGIN_READ_BI"
#: Room for the reply envelope around a response at the contract's limit.
LINE_OVERHEAD = 16 * 1024

BOOTSTRAP = (
    "import runpy, sys\n"
    "root, module = sys.argv[1], sys.argv[2]\n"
    "sys.argv = [module]\n"
    "sys.path.insert(0, root)\n"
    "runpy.run_module(module, run_name='__main__', alter_sys=True)\n"
)


class WorkerFailure(Exception):
    """The worker did not give a valid answer; the process is gone."""

    def __init__(self, code: PluginErrorCode) -> None:
        self.code: PluginErrorCode = code
        super().__init__(code)


class WorkerRefusal(Exception):
    """The worker answered `refused`/`failed` with its own code; it still runs."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def line_limit() -> int:
    return contract.MAX_RESPONSE_BYTES + LINE_OVERHEAD


def _kill_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError):
            pass
    if process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


class WorkerSession:
    """A started worker; `exchange` is serialized and bounded."""

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        if process.stdin is None or process.stdout is None:
            raise ValueError("plugin worker requires standard input and output")
        self._process = process
        self._stdin: IO[bytes] = process.stdin
        self._stdout: IO[bytes] = process.stdout
        self._lock = Lock()
        self._reader = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aep-plugin")
        self.closed = False

    @property
    def alive(self) -> bool:
        return not self.closed and self._process.poll() is None

    def exchange(self, request: ExtensionRequest, timeout_seconds: float) -> ExtensionResponse:
        with self._lock:
            if not self.alive:
                raise WorkerFailure("plugin_worker_failed")
            try:
                self._stdin.write(request.model_dump_json().encode("utf-8") + b"\n")
                self._stdin.flush()
            except (OSError, ValueError):
                self.close()
                raise WorkerFailure("plugin_worker_failed") from None
            limit = line_limit()
            future = self._reader.submit(self._stdout.readline, limit + 1)
            try:
                line = future.result(timeout=timeout_seconds)
            except FutureTimeout:
                self.close()
                raise WorkerFailure("plugin_timeout") from None
            except (OSError, ValueError):
                self.close()
                raise WorkerFailure("plugin_worker_failed") from None
            if not line:
                self.close()
                raise WorkerFailure("plugin_worker_failed")
            if len(line) > limit or not line.endswith(b"\n"):
                self.close()
                raise WorkerFailure("plugin_response_too_large")
            try:
                response = ExtensionResponse.model_validate_json(line)
            except (ValidationError, ValueError):
                self.close()
                raise WorkerFailure("plugin_worker_failed") from None
            if response.request_id != request.request_id:
                self.close()
                raise WorkerFailure("plugin_worker_failed")
            return response

    def close(self) -> None:
        self.closed = True
        _kill_tree(self._process)
        for stream in (self._stdin, self._stdout):
            try:
                stream.close()
            except (OSError, ValueError):
                pass
        self._reader.shutdown(wait=False, cancel_futures=True)


def start_worker(
    manifest: PluginManifest,
    staged: Path,
    data_root: Path,
    *,
    interpreter: str,
    bi_root: Path | None = None,
) -> WorkerSession:
    """Start the declared module and require an exact health declaration.

    `READ_BI_ENV` is never inherited from this process: it is removed, then set
    to `bi_root` only when the manifest declares `data.reads = ("bi",)`. A
    declaring manifest without `bi_root` does not start
    (`plugin_environment_failed`); `bi_root` given for one that declares nothing
    is ignored. This is declared context, not an access grant."""
    runtime = manifest.runtime
    if runtime is None:
        raise ValueError("plugin declares no worker")
    # The ordinary execution environment (PATH, OS/service identity) is kept:
    # a worker is a separate process, not a sandbox, and claims no secret
    # isolation. `-I` already keeps PYTHONPATH/PYTHON* out of module loading.
    environment = dict(os.environ)
    environment.pop(READ_BI_ENV, None)
    if "bi" in manifest.data.reads:
        if bi_root is None:
            raise WorkerFailure("plugin_environment_failed")
        environment[READ_BI_ENV] = str(bi_root)
    environment[PACKAGE_ENV] = str(staged / "package.json")
    environment[DATA_ENV] = str(data_root)
    try:
        process = subprocess.Popen(
            [
                interpreter,
                "-I",
                "-u",
                "-B",
                "-c",
                BOOTSTRAP,
                str(staged / "worker"),
                runtime.module,
            ],
            cwd=staged,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        raise WorkerFailure("plugin_environment_failed") from None
    session = WorkerSession(process)
    try:
        response = session.exchange(
            ExtensionRequest(request_id=f"health-{uuid4().hex[:12]}", operation="health"),
            runtime.health.startup_timeout_seconds,
        )
    except WorkerFailure:
        session.close()
        raise WorkerFailure("plugin_health_failed") from None
    expected = tuple(item.spec.identity for item in manifest.capabilities)
    if response.status != "healthy" or response.capabilities != expected:
        session.close()
        raise WorkerFailure("plugin_health_failed")
    return session


def invoke(
    session: WorkerSession,
    capability: AssetIdentity,
    arguments: dict[str, JsonValue],
    timeout_seconds: float,
) -> JsonValue:
    """The worker's data for one call, or its refusal, or a failure."""
    if contract.json_size(arguments) > contract.MAX_REQUEST_BYTES:
        raise WorkerFailure("plugin_request_too_large")
    response = session.exchange(
        ExtensionRequest(
            request_id=f"call-{uuid4().hex[:16]}",
            operation="invoke",
            capability=capability,
            arguments=arguments,
        ),
        timeout_seconds,
    )
    if response.status == "succeeded":
        return response.data
    if response.status == "healthy" or response.code is None:
        session.close()
        raise WorkerFailure("plugin_worker_failed")
    raise WorkerRefusal(response.code)
