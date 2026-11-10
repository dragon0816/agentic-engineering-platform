"""Bounded metadata-only CLI handshakes; never send a user/inference message.

Codex uses app-server initialize/model/list. Claude uses the official Agent SDK
stream-json initialize control protocol. Only model identifiers leave this module.
"""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from host_runtime.acp_client import AcpLauncher, AcpProcess, launch

TIMEOUT_SECONDS = 25.0
MAX_OUTPUT = 262_144
MAX_MODELS = 500
MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+\[\]-]{0,199}\Z")


class CatalogError(Exception):
    pass


def valid_model(value: object) -> bool:
    return isinstance(value, str) and MODEL_ID.fullmatch(value) is not None


class MetadataChannel:
    def __init__(self, process: AcpProcess, timeout: float) -> None:
        self.process = process
        self.deadline = time.monotonic() + timeout
        self.messages: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=32)
        self.failed = threading.Event()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self) -> None:
        stream = self.process.stdout
        total = 0
        try:
            if stream is not None:
                while True:
                    line = stream.readline(MAX_OUTPUT + 1)
                    if not line:
                        break
                    total += len(line.encode("utf-8"))
                    if total > MAX_OUTPUT:
                        raise CatalogError("model_catalog_output_limit")
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise CatalogError("model_catalog_invalid")
                    self.messages.put_nowait(value)
            self.messages.put_nowait(None)
        except (ValueError, OSError, queue.Full, CatalogError):
            self.failed.set()

    def send(self, value: dict[str, Any]) -> None:
        if self.process.stdin is None:
            raise CatalogError("model_catalog_unavailable")
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()

    def receive(self) -> dict[str, Any]:
        while True:
            if self.failed.is_set():
                raise CatalogError("model_catalog_invalid")
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise CatalogError("model_catalog_timeout")
            try:
                value = self.messages.get(timeout=min(remaining, 0.1))
            except queue.Empty:
                continue
            if value is None:
                raise CatalogError("model_catalog_unavailable")
            return value

    def rpc(self, ident: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.send({"jsonrpc": "2.0", "id": ident, "method": method, "params": params})
        while True:
            value = self.receive()
            if "method" in value and "id" in value:
                raise CatalogError("model_catalog_invalid")
            if value.get("id") == ident:
                result = value.get("result")
                if "error" in value or not isinstance(result, dict):
                    raise CatalogError("model_catalog_unavailable")
                return result


def discover(
    backend: str,
    executable: str,
    cwd: Path,
    env: Mapping[str, str],
    *,
    launcher: AcpLauncher = launch,
    timeout: float = TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if backend == "codex":
        args = ["app-server", "--listen", "stdio://", "-c", "features.hooks=false"]
    elif backend == "claude_code":
        args = [
            "--safe-mode",
            "--restricted",
            "--print",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
            "--no-session-persistence",
            "--setting-sources",
            "",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--tools",
            "",
            "--disable-slash-commands",
            "--settings",
            '{"disableAllHooks":true}',
            "--permission-prompts",
            "none",
        ]
    else:
        return {"ok": False, "code": "model_catalog_unsupported", "models": []}
    process = None
    try:
        process = launcher([executable, *args], cwd, env)
        channel = MetadataChannel(process, timeout)
        names: list[str] = []
        if backend == "codex":
            channel.rpc(
                1,
                "initialize",
                {"clientInfo": {"name": "aep-model-catalog", "version": "1"}, "capabilities": {}},
            )
            channel.send({"jsonrpc": "2.0", "method": "initialized"})
            cursor = None
            seen: set[str] = set()
            for page in range(10):
                result = channel.rpc(
                    page + 2, "model/list", {"includeHidden": False, "limit": 100, "cursor": cursor}
                )
                rows = result.get("data")
                if not isinstance(rows, list):
                    raise CatalogError("model_catalog_invalid")
                for row in rows:
                    if not isinstance(row, dict):
                        raise CatalogError("model_catalog_invalid")
                    model = row.get("model")
                    if not isinstance(model, str) or not valid_model(model):
                        raise CatalogError("model_catalog_invalid")
                    names.append(model)
                cursor = result.get("nextCursor")
                if cursor is None:
                    break
                if not isinstance(cursor, str) or len(cursor) > 2000 or cursor in seen:
                    raise CatalogError("model_catalog_invalid")
                seen.add(cursor)
            else:
                raise CatalogError("model_catalog_output_limit")
        else:
            channel.send(
                {
                    "type": "control_request",
                    "request_id": "catalog",
                    "request": {"subtype": "initialize", "hooks": {}, "agents": {}},
                }
            )
            while True:
                value = channel.receive()
                if value.get("type") == "control_request":
                    raise CatalogError("model_catalog_invalid")
                response = value.get("response")
                if value.get("type") != "control_response" or not isinstance(response, dict):
                    continue
                if response.get("request_id") != "catalog":
                    continue
                metadata = response.get("response")
                if response.get("subtype") != "success" or not isinstance(metadata, dict):
                    raise CatalogError("model_catalog_unavailable")
                rows = metadata.get("models")
                if not isinstance(rows, list):
                    raise CatalogError("model_catalog_unavailable")
                for row in rows:
                    if not isinstance(row, dict) or not valid_model(row.get("value")):
                        raise CatalogError("model_catalog_invalid")
                    names.append(row["value"])
                break
        if not names or len(names) > MAX_MODELS:
            raise CatalogError("model_catalog_unavailable")
        return {"ok": True, "models": list(dict.fromkeys(names))}
    except CatalogError as error:
        return {"ok": False, "code": str(error), "models": []}
    except (OSError, ValueError):
        return {"ok": False, "code": "model_catalog_unavailable", "models": []}
    finally:
        if process is not None:
            try:
                if process.poll() is None:
                    # npm's Windows shim starts a child executable. Kill this
                    # discovery's process tree, never a shared app-server.
                    pid = getattr(process, "pid", None)
                    if os.name == "nt" and isinstance(pid, int):
                        taskkill = (
                            Path(os.environ.get("SystemRoot", r"C:\Windows"))
                            / "System32"
                            / "taskkill.exe"
                        )
                        subprocess.run(
                            [str(taskkill), "/PID", str(pid), "/T", "/F"],
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=2,
                            check=False,
                        )
                    else:
                        process.kill()
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
            finally:
                for stream in (process.stdin, process.stdout):
                    if stream is not None:
                        stream.close()
