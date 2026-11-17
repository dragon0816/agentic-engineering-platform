"""Atlas panels and dashboards framed in the general chat (BI E2-E4).

`docs/phases/BI_CHAT_EMBED_AND_PANEL_EDIT.md` §4; Atlas's contract is
`docs/AEP_EMBED_CONTRACT.md` in its repository. The host builds an embed's path
from a vault, a slug and parameters, or from a dashboard name, so the model never
supplies a URL; the page puts the person's Atlas address in front of it. Whether
Atlas can be framed is asked server-side (`HEAD /embed/panel` without Origin); an
iframe's load event cannot tell. AEP never writes to Atlas.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from aep_bi.cards.store import BiStoreError
from host_runtime.workspace import write_atomically

#: The contract's reserved query keys: never an analysis parameter in a URL.
RESERVED = frozenset({"vault", "slug"})
PROBE_SECONDS = 2.0
#: A dashboard's panels drawn for the chart page shown when Atlas is not running.
FALLBACK_PANELS = 12
BI_DATASOURCE = "aep.bi.result"
#: Per PC, under the workspace: which AEP panels each dashboard had when last read,
#: so a stopped Atlas still has charts to show. Only references, never Atlas's layout.
BOARDS_FILE = "bi-atlas-dashboards.json"
MAX_BOARDS = 50


def _text(value: Any) -> str:
    """A parameter's value as the contract writes it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def panel_path(vault_id: str, slug: str, params: Mapping[str, Any] | None = None) -> str:
    given = dict(params or {})
    reserved = sorted(RESERVED & set(given))
    if reserved:
        raise BiStoreError("param_invalid", f"Atlas 的網址不能設定這些參數：{', '.join(reserved)}")
    query = [("vault", vault_id), ("slug", slug)]
    query += [(name, _text(given[name])) for name in sorted(given)]
    return "/embed/panel?" + urlencode(query)


def dashboard_path(name: str) -> str:
    return "/embed/dashboard/" + quote(name, safe="")


def framable(port: int) -> bool:
    """200 means framable; a refused connection or a 503 (no frontend built) does not."""
    request = urllib.request.Request(f"http://127.0.0.1:{port}/embed/panel", method="HEAD")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # loopback only
    try:
        with opener.open(request, timeout=PROBE_SECONDS) as reply:
            return bool(reply.status == 200)
    except (urllib.error.URLError, OSError):
        return False


def panels_of(document: Any) -> list[tuple[str, str]]:
    """The (vault, slug) of a dashboard's AEP panels, top to bottom, each once."""
    return list(dict.fromkeys((r["vault"], r["slug"]) for r in panel_refs(document)))


def _panel_params(query: Mapping[str, Any]) -> dict[str, Any]:
    """A panel's plain parameters; an Atlas variable (`${...}`) means nothing here,
    so the analysis's default stands for it."""
    given = query.get("params")
    if not isinstance(given, Mapping):
        return {}
    return {
        str(name): value
        for name, value in given.items()
        if isinstance(value, (str, int, float, bool)) and "${" not in str(value)
    }


def panel_refs(document: Any) -> list[dict[str, Any]]:
    """A dashboard's AEP panels top to bottom: vault, slug and parameters, each
    such combination once."""
    panels = document.get("panels") if isinstance(document, Mapping) else None
    found: list[tuple[float, float, dict[str, Any]]] = []
    for panel in panels if isinstance(panels, list) else []:
        if not isinstance(panel, Mapping):
            continue
        source, query = panel.get("datasource"), panel.get("query")
        if not isinstance(source, Mapping) or source.get("id") != BI_DATASOURCE:
            continue
        if not isinstance(query, Mapping):
            continue
        vault_id, slug = query.get("vault"), query.get("slug")
        if not isinstance(vault_id, str) or not isinstance(slug, str) or not vault_id or not slug:
            continue
        layout = panel.get("layout") if isinstance(panel.get("layout"), Mapping) else {}
        where = [layout.get(key) for key in ("y", "x")]  # type: ignore[union-attr]
        y, x = (float(v) if isinstance(v, (int, float)) else float("inf") for v in where)
        found.append((y, x, {"vault": vault_id, "slug": slug, "params": _panel_params(query)}))
    unique: dict[str, dict[str, Any]] = {}
    for _y, _x, ref in sorted(found, key=lambda f: f[:2]):
        unique.setdefault(json.dumps(ref, sort_keys=True, ensure_ascii=False), ref)
    return list(unique.values())


def _boards(workspace: Path) -> dict[str, Any]:
    try:
        found = json.loads((workspace / BOARDS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def remember_board(workspace: Path, name: str, document: Any, now: datetime) -> None:
    """Keep which AEP panels this dashboard has, the newest `MAX_BOARDS` boards."""
    boards = _boards(workspace)
    boards.pop(name, None)
    boards[name] = {
        "read_at": now.strftime("%Y-%m-%d %H:%M"),
        "panels": panel_refs(document)[:FALLBACK_PANELS],
    }
    kept = dict(list(boards.items())[-MAX_BOARDS:])
    text = json.dumps(kept, ensure_ascii=False, indent=2)
    write_atomically(workspace / BOARDS_FILE, text.encode("utf-8"))


def board_copy(workspace: Path, name: str) -> dict[str, Any] | None:
    found = _boards(workspace).get(name)
    return found if isinstance(found, dict) and isinstance(found.get("panels"), list) else None


def board_copies(workspace: Path) -> dict[str, str]:
    """The dashboards with a copy here, and when each was read."""
    return {
        name: str(item.get("read_at") or "")
        for name, item in _boards(workspace).items()
        if isinstance(item, dict)
    }
