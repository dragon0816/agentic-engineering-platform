"""Read-only harness telemetry for Atlas (telemetry contract v0.2, owner 2026-10-08).

Served by Agent Web on the loopback address. The owner decided Atlas reads it
without the page token: these events are redacted metadata only. So these
routes skip the token, answer GET only, and allow cross-origin reads from
pages on this machine (127.0.0.1, localhost, [::1]) and nowhere else, so a web
site open in the same browser still cannot read them. The Host-header guard
of every Agent Web route still applies.

    GET /api/v1/telemetry/health
    GET /api/v1/telemetry/runs?limit=50&cursor=…&kind=…&status=…&since=…&until=…
                              &trace_id=…&parent_run_id=…
    GET /api/v1/telemetry/runs/{run_id}/events?after_sequence=N&limit=500
    GET /api/v1/telemetry/events?after_ingest_seq=N&limit=1000&since=…&until=…
    GET /api/v1/telemetry/stream?after_ingest_seq=N   (WebSocket; one event per message)
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import select
import socket
import struct
import time
from typing import Any
from urllib.parse import parse_qs, unquote

import telemetry.recorder as telemetry

PREFIX = "/api/v1/telemetry/"
_LOCAL_ORIGIN = re.compile(r"^https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$")
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
STREAM_POLL_SECONDS = 0.5
PING_SECONDS = 20.0


def _int(query: dict[str, list[str]], name: str, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(query.get(name, [str(default)])[0])))
    except ValueError:
        return default


def _cors(handler: Any) -> None:
    origin = handler.headers.get("Origin") or ""
    if _LOCAL_ORIGIN.match(origin):
        handler.send_header("Access-Control-Allow-Origin", origin)
        handler.send_header("Vary", "Origin")


def _reply(handler: Any, status: int, payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    _cors(handler)
    handler.end_headers()
    handler.wfile.write(body)


def handle(handler: Any, path: str, query_text: str) -> bool:
    """Answer a telemetry route; False when the path is not one."""
    if not path.startswith(PREFIX):
        return False
    origin = handler.headers.get("Origin")
    if origin and not _LOCAL_ORIGIN.match(origin):
        _reply(handler, 403, {"error": "telemetry is read only by pages on this machine"})
        return True
    active = telemetry.recorder()
    if active is None:
        _reply(handler, 503, {"error": "telemetry is not recording in this process"})
        return True
    store = active.store
    query = parse_qs(query_text)
    rest = path[len(PREFIX):]
    if rest == "health":
        _reply(handler, 200, {**active.health(), "last_ingest_seq": store.last_ingest_seq()})
    elif rest == "runs":
        limit = _int(query, "limit", 50, 1, 500)
        runs = store.runs(limit=limit, before=query.get("cursor", [None])[0],
                          kind=query.get("kind", [None])[0],
                          status=query.get("status", [None])[0],
                          since=query.get("since", [None])[0],
                          until=query.get("until", [None])[0],
                          trace_id=query.get("trace_id", [None])[0],
                          parent_run_id=query.get("parent_run_id", [None])[0])
        cursor = (f"{runs[-1]['started_at'] or ''}|{runs[-1]['run_id']}"
                  if len(runs) == limit else None)
        _reply(handler, 200, {"runs": runs, "next_cursor": cursor})
    elif (match := re.fullmatch(r"runs/([^/]+)/events", rest)) is not None:
        after = _int(query, "after_sequence", -1, -1, 2**62)
        limit = _int(query, "limit", 500, 1, 5000)
        events = store.run_events(unquote(match[1]), after_sequence=after, limit=limit)
        _reply(handler, 200, {"events": events, "next_sequence":
                              events[-1]["sequence"] if len(events) == limit else None})
    elif rest == "events":
        after = _int(query, "after_ingest_seq", 0, 0, 2**62)
        limit = _int(query, "limit", 1000, 1, 5000)
        events = store.events_after(after, limit=limit, since=query.get("since", [None])[0],
                                    until=query.get("until", [None])[0])
        _reply(handler, 200, {"events": events, "next_ingest_seq":
                              events[-1]["ingest_seq"] if events else after})
    elif rest == "stream":
        _stream(handler, store, _int(query, "after_ingest_seq", -1, -1, 2**62))
    else:
        _reply(handler, 404, {"error": "no such telemetry route"})
    return True


def _frame(payload: bytes, opcode: int = 0x1) -> bytes:
    head = bytes([0x80 | opcode])
    size = len(payload)
    if size < 126:
        return head + bytes([size]) + payload
    if size < 65536:
        return head + bytes([126]) + struct.pack(">H", size) + payload
    return head + bytes([127]) + struct.pack(">Q", size) + payload


def _client_closed(connection: socket.socket) -> bool:
    """Read what the client sent; a close frame or EOF ends the stream."""
    readable, _, _ = select.select([connection], [], [], 0)
    if not readable:
        return False
    try:
        data = connection.recv(4096)
    except OSError:
        return True
    return not data or (data[0] & 0x0F) == 0x8


def _stream(handler: Any, store: Any, after: int) -> None:
    """WebSocket: backfill from `after_ingest_seq`, then live events as they
    are stored. -1 starts at the newest event (live only)."""
    key = handler.headers.get("Sec-WebSocket-Key")
    if not key or "websocket" not in (handler.headers.get("Upgrade") or "").lower():
        _reply(handler, 426, {"error": "open this route as a WebSocket"})
        return
    accept = base64.b64encode(hashlib.sha1((key + _WS_GUID).encode()).digest()).decode()
    handler.send_response(101, "Switching Protocols")
    handler.send_header("Upgrade", "websocket")
    handler.send_header("Connection", "Upgrade")
    handler.send_header("Sec-WebSocket-Accept", accept)
    _cors(handler)
    handler.end_headers()
    handler.wfile.flush()
    handler.close_connection = True
    connection = handler.connection
    cursor = store.last_ingest_seq() if after < 0 else after
    last_ping = time.monotonic()
    try:
        while not _client_closed(connection):
            events = store.events_after(cursor, limit=500)
            for event in events:
                connection.sendall(_frame(json.dumps(event, ensure_ascii=False).encode()))
                cursor = event["ingest_seq"]
            if time.monotonic() - last_ping > PING_SECONDS:
                connection.sendall(_frame(b"", opcode=0x9))
                last_ping = time.monotonic()
            if not events:
                time.sleep(STREAM_POLL_SECONDS)
    except OSError:
        return
