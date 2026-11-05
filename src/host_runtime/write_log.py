"""One line per write request to Agent Web, so a change nobody owns can be traced to a client.

Time, method, path, status, `User-Agent`, `Referer`, the client's address and `X-AEP-Client`:
never a body, a query string, a cookie or a token, since a request here carries the team's own
words. `X-AEP-Client` is a label a client gives itself, not proof of who it is.

A request never waits on this: `note` puts the line on a queue and a thread writes it, so one
writer keeps lines whole, and a log that cannot be written costs a line, never a request.
"""

from __future__ import annotations

import json
import os
import queue
import threading
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

FILE_NAME = "agent-web-writes.log"
METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
#: The log and its rotated copies stay under about 20 MB.
MAX_BYTES = 5_000_000
KEEP = 3
#: Lines waiting for the writer; past this they are dropped and counted.
QUEUE_LINES = 2000
MAX_TEXT = 300
_STOP = None


def clean_path(target: str) -> str:
    """A request target without its query string, fragment, host or user."""
    text = target.split("?", 1)[0].split("#", 1)[0]
    if "://" in text:
        text = urlsplit(text).path
    return text[:MAX_TEXT]


def clean_referer(referer: str) -> str:
    """Where a request says it came from, without query string, fragment or user."""
    if not referer:
        return ""
    try:
        parts = urlsplit(referer)
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        return ""  # not an address: nothing here is known to be safe to keep
    if not parts.scheme or not host:
        return ""
    return f"{parts.scheme}://{host}{port}{parts.path}"[:MAX_TEXT]


def entry(
    *,
    method: str,
    target: str,
    status: int,
    user_agent: str,
    referer: str,
    client: str,
    label: str,
    at: str | None = None,
) -> dict[str, Any]:
    return {
        "at": at or datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "method": method,
        "path": clean_path(target),
        "status": status,
        "client": client,
        "label": label[:MAX_TEXT],
        "user_agent": user_agent[:MAX_TEXT],
        "referer": clean_referer(referer),
    }


class WriteLog:
    """The queue and its writer. The thread starts with the first line; `folder=None` is off."""

    def __init__(
        self,
        folder: Path | None,
        *,
        max_bytes: int = MAX_BYTES,
        keep: int = KEEP,
        queue_lines: int = QUEUE_LINES,
    ) -> None:
        self.folder = folder
        self.max_bytes = max_bytes
        self.keep = keep
        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=queue_lines)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.dropped = 0

    def note(self, record: Mapping[str, Any]) -> None:
        """Never raises and never blocks: a full queue drops the line and counts it."""
        if self.folder is None:
            return
        try:
            self._start()
            self._queue.put_nowait(dict(record))
        except queue.Full:
            self.dropped += 1
        except Exception:  # noqa: BLE001, S110 - no request ever fails for its log line
            self.dropped += 1

    def close(self, timeout: float = 2.0) -> None:
        """Write what is queued, for as long as `timeout`, and stop the thread."""
        thread = self._thread
        if thread is None:
            return
        try:
            self._queue.put(_STOP, timeout=timeout)
        except queue.Full:
            return
        thread.join(timeout)

    def _start(self) -> None:
        if self._thread is not None:
            return
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="write-log", daemon=True)
                self._thread.start()

    def _run(self) -> None:
        while True:
            first = self._queue.get()
            if first is _STOP:
                return
            batch = [first]
            stopping = False
            while len(batch) < 200:
                try:
                    more = self._queue.get_nowait()
                except queue.Empty:
                    break
                if more is _STOP:
                    stopping = True
                    break
                batch.append(more)
            try:
                self._write(batch)
            except Exception:  # noqa: BLE001, S110 - the log may be unwritable: lines are lost
                self.dropped += len(batch)
            if stopping:
                return

    def _write(self, batch: list[dict[str, Any]]) -> None:
        assert self.folder is not None
        records = list(batch)
        if self.dropped:
            lost, self.dropped = self.dropped, 0
            records.append({"dropped": lost})
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / FILE_NAME
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        held = bytearray()
        for record in records:
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            data = line.encode("utf-8", "replace")
            if (held or size) and size + len(held) + len(data) > self.max_bytes:
                size = self._flush(path, held, size)
            held += data
        self._flush(path, held, size, rotate=False)

    def _flush(self, path: Path, data: bytearray, size: int, *, rotate: bool = True) -> int:
        """Append `data`; with `rotate` the file is full, so the next line starts a new one."""
        with path.open("ab") as out:
            out.write(data)
        size += len(data)
        data.clear()
        if not rotate:
            return size
        try:
            self._rotate(path)
        except OSError:
            return size  # a reader holds it: it runs a little over, and rotates next time
        return 0

    def _rotate(self, path: Path) -> None:
        for number in range(self.keep, 0, -1):
            older = path.with_name(f"{path.name}.{number}")
            if number == self.keep:
                older.unlink(missing_ok=True)
            else:
                newer = path.with_name(f"{path.name}.{number + 1}")
                if older.exists():
                    os.replace(older, newer)
        os.replace(path, path.with_name(f"{path.name}.1"))
