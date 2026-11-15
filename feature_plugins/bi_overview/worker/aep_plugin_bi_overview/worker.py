"""BI overview feature plugin worker (stdlib only).

Speaks the existing `aep-extension-jsonl/v1` request/reply protocol on standard
input/output: one JSON request per line, one JSON reply per line. It serves one
read-only page service, `bi-overview.read_overview`, by wrapping
`reader.read_overview` on the Host's existing `bi/` folder named by
AEP_PLUGIN_READ_BI (Plugin API 1.1 `data.reads`). Without that binding it
refuses; it never derives a workspace from another path.

It writes, creates, rebuilds and syncs nothing, imports no AEP code and calls no
model. The answer is display data fitted to the manifest's declared outputs:
every table cell is a string, and an unknown value is shown as a dash, never as
zero. A complete card total is given only when every dataset was read and
nothing was cut; otherwise only the partial count of readable local copies is.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, BinaryIO

from aep_plugin_bi_overview.reader import MAX_ROWS, read_overview

PROTOCOL = "aep-extension-jsonl/v1"
PACKAGE_ENV = "AEP_PLUGIN_PACKAGE_FILE"
READ_BI_ENV = "AEP_PLUGIN_READ_BI"
#: The page service's local capability name.
SERVICE = "read_overview"
#: `common.plugins.MAX_REQUEST_BYTES` plus room for the request envelope.
MAX_REQUEST_LINE = 64 * 1024 + 4 * 1024
#: `common.plugins.MAX_RESPONSE_BYTES`: the whole reply line stays within it.
MAX_RESPONSE_BYTES = 256 * 1024
MAX_CELL = 160
DASH = "—"
_SYMBOL = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.-]{0,127}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_ORIGIN = {
    "local": "本機資料庫",
    "vault": "本機 vault 工作投影（非已發佈問答來源）",
    "subscribed": "本機訂閱副本",
}


# -- the overview as display data --------------------------------------------------------


def _text(value: object) -> str:
    """One display-safe cell: plain text, no control characters, bounded."""
    if value is None or value == "":
        return DASH
    text = _CONTROL.sub(" ", str(value))
    return text if len(text) <= MAX_CELL else text[: MAX_CELL - 1] + "…"


def _flag(value: object) -> str:
    if value is None:
        return DASH
    return "是" if value else "否"


def _row(entry: dict[str, Any]) -> dict[str, str]:
    kind = str(entry.get("kind"))
    cards = entry.get("cards")
    return {
        "name": _text(entry.get("name")),
        "kind": _text(kind),
        "status": _text(entry.get("status")),
        "reason": _text(entry.get("reason")),
        "origin": _ORIGIN.get(kind, DASH),
        "cards": str(cards) if isinstance(cards, int) and not isinstance(cards, bool) else DASH,
        "updated": _text(entry.get("updated")),
        "schema_ref": _text(entry.get("schema")),
        "dashboard": _flag(entry.get("dashboard")),
        "read_only": _flag(entry.get("read_only")),
        "version": _text(entry.get("version")),
    }


def _coverage(status: str, unavailable: int, shown: int, total: int, invalid: int) -> str:
    if status == "missing":
        return "這台電腦還沒有 BI 資料夾（未讀到資料集）"
    if status != "ready":
        return "BI 資料夾無法讀取，未讀到資料集"
    parts = []
    if unavailable:
        parts.append(f"{unavailable} 個資料集無法讀取")
    if shown < total:
        parts.append(f"只列出 {shown} / {total} 個資料集")
    if invalid:
        parts.append(f"{invalid} 筆 vault 登錄無法使用")
    return "不完整：" + "；".join(parts) if parts else "完整"


def summary(bi_root: Path) -> dict[str, Any]:
    """The page service's answer for the `bi/` folder `bi_root`."""
    overview = read_overview(bi_root, limit=MAX_ROWS)
    status = str(overview["status"])
    entries = list(overview["datasets"])
    ready = [item for item in entries if item.get("status") == "ready"]
    total = int(overview["total"])
    invalid = int(overview.get("invalid_registrations") or 0)
    rows = [_row(item) for item in entries]
    data: dict[str, Any] = {
        "bi_status": status if status != "unsupported" else f"unsupported:{overview.get('reason')}",
        "coverage": "",
        "datasets_found": total,
        "datasets_unavailable": len(entries) - len(ready),
        "cards_known": sum(int(item["cards"]) for item in ready),
        "cards_total": DASH,
        "truncated": bool(overview["truncated"]),
        "invalid_registrations": invalid,
        "datasets": rows,
    }
    # The whole reply line stays within the response bound: drop rows from the end.
    while rows and _reply_size(data) > MAX_RESPONSE_BYTES:
        rows.pop()
        data["truncated"] = True
    complete = (
        status == "ready"
        and not data["truncated"]
        and data["datasets_unavailable"] == 0
        and invalid == 0
        and len(rows) == total
    )
    if complete:
        data["cards_total"] = str(data["cards_known"])
    data["coverage"] = _coverage(status, data["datasets_unavailable"], len(rows), total, invalid)
    return data


def _reply_size(data: dict[str, Any]) -> int:
    reply = {"protocol": PROTOCOL, "request_id": "x" * 128, "status": "succeeded", "data": data}
    return len(_line(reply))


# -- the protocol -----------------------------------------------------------------------


def _line(reply: dict[str, Any]) -> bytes:
    return (json.dumps(reply, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _reply(request_id: str, status: str, **fields: Any) -> dict[str, Any]:
    return {"protocol": PROTOCOL, "request_id": request_id, "status": status, **fields}


def _manifest() -> dict[str, Any] | None:
    try:
        envelope = json.loads(Path(os.environ[PACKAGE_ENV]).read_text(encoding="utf-8"))
        manifest = envelope["manifest"]
        return manifest if isinstance(manifest, dict) else None
    except (KeyError, OSError, ValueError, TypeError):
        return None


def _service_identity(manifest: dict[str, Any]) -> dict[str, Any] | None:
    namespace = manifest["identity"]["namespace"]
    for item in manifest.get("capabilities", ()):
        if item["spec"]["name"] == f"{namespace}.{SERVICE}":
            return dict(item["spec"]["identity"])
    return None


def respond(raw: bytes, manifest: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
    """The reply to one request line, and whether the worker stops after it."""
    try:
        request = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return _reply("unknown", "refused", code="request_malformed"), False
    if not isinstance(request, dict):
        return _reply("unknown", "refused", code="request_malformed"), False
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not _SYMBOL.match(request_id):
        return _reply("unknown", "refused", code="request_malformed"), False
    if request.get("protocol") != PROTOCOL:
        return _reply(request_id, "refused", code="protocol_unsupported"), False
    operation = request.get("operation")
    if operation == "shutdown":
        return _reply(request_id, "succeeded"), True
    if manifest is None:
        return _reply(request_id, "failed", code="package_unreadable"), False
    if operation == "health":
        identities = [dict(item["spec"]["identity"]) for item in manifest["capabilities"]]
        return _reply(request_id, "healthy", capabilities=identities), False
    if operation != "invoke":
        return _reply(request_id, "refused", code="operation_unknown"), False
    if request.get("capability") != _service_identity(manifest):
        return _reply(request_id, "refused", code="capability_unknown"), False
    if request.get("arguments") not in ({}, None):
        return _reply(request_id, "refused", code="arguments_unexpected"), False
    bound = os.environ.get(READ_BI_ENV, "")
    if not bound:
        return _reply(request_id, "refused", code="bi_context_missing"), False
    root = Path(bound)
    if not root.is_absolute():
        return _reply(request_id, "refused", code="bi_context_invalid"), False
    try:
        data = summary(root)
    except (OSError, ValueError):
        return _reply(request_id, "failed", code="bi_read_failed"), False
    return _reply(request_id, "succeeded", data=data), False


def serve(source: BinaryIO, sink: BinaryIO) -> None:
    manifest = _manifest()
    while True:
        raw = source.readline(MAX_REQUEST_LINE + 1)
        if not raw:
            return
        if len(raw) > MAX_REQUEST_LINE:
            while raw and not raw.endswith(b"\n"):  # skip the rest of the line
                raw = source.readline(MAX_REQUEST_LINE + 1)
            reply, stop = _reply("unknown", "refused", code="request_too_large"), False
        elif not raw.strip():
            continue
        else:
            reply, stop = respond(raw, manifest)
        sink.write(_line(reply))
        sink.flush()
        if stop:
            return


if __name__ == "__main__":
    serve(sys.stdin.buffer, sys.stdout.buffer)
