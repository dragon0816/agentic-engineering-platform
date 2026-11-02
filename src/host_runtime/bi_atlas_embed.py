"""Atlas panels and dashboards framed in the general chat (BI E2-E4).

`docs/phases/BI_CHAT_EMBED_AND_PANEL_EDIT.md` §4; Atlas's contract is
`docs/AEP_EMBED_CONTRACT.md` in its repository. The host builds an embed's path
from a vault, a slug and parameters, or from a dashboard name, so the model never
supplies a URL; the page puts the person's Atlas address in front of it. Whether
Atlas can be framed is asked server-side (`HEAD /embed/panel` without Origin); an
iframe's load event cannot tell. AEP never writes to Atlas.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, urlencode

from capabilities.bi_cards.store import BiStoreError

#: The contract's reserved query keys: never an analysis parameter in a URL.
RESERVED = frozenset({"vault", "slug"})
PROBE_SECONDS = 2.0
#: A dashboard's panels drawn for the chart page shown when Atlas is not running.
FALLBACK_PANELS = 12
BI_DATASOURCE = "aep.bi.result"


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
    panels = document.get("panels") if isinstance(document, Mapping) else None
    found: list[tuple[float, float, str, str]] = []
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
        found.append((y, x, vault_id, slug))
    return list(dict.fromkeys((v, s) for _y, _x, v, s in sorted(found, key=lambda f: f[:2])))
