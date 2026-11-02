"""Read Atlas's dashboards and import one's order into a vault (BI K2).

`docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md` K2; Atlas's contract is
`docs/AEP_DASHBOARD_READ_CONTRACT.md` in its repository (goldens vendored in
`tests/fixtures/atlas_dashboard_golden/`). Agent Web reads Atlas's loopback API
server-side, GET only: `GET /dashboards` (names) and `GET /dashboards/{name}`
(a schemaVersion 2 document), on `127.0.0.1:<port>` (default 8127), without an
Origin header, within a short timeout and Atlas's 2,000,000-byte bound. It
never writes to Atlas. The import is a dry run first (the preview of
`capabilities.bi_cards.atlas_import.plan`, with a token); confirming with that
token stages `meta:dashboard` in the vault's working copy, nothing else. A file
the person chooses (owner 2026-11-02) takes the same path with no Atlas running:
its text is parsed as strict JSON within the same bound, then only `plan` reads
it. It is never run or stored; a confirm sends the text again.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote

from capabilities.bi_cards import analyses, atlas_import, vault
from capabilities.bi_cards.store import BiStoreError

DEFAULT_PORT = 8127
TIMEOUT_SECONDS = 5.0
MAX_BYTES = 2_000_000
#: Atlas's read errors (contract "Reads and access") as what the person is told.
STATUS = {
    400: ("atlas_invalid", "Atlas 不接受這個 Dashboard 名稱"),
    403: ("atlas_refused", "Atlas 拒絕了這個讀取（只接受本機）"),
    404: ("atlas_not_found", "Atlas 沒有這個 Dashboard"),
    413: ("atlas_too_large", "這個 Atlas Dashboard 太大"),
    422: ("atlas_invalid", "Atlas 存的這個 Dashboard 格式不正確"),
}


def port_of(given: Any) -> int:
    """The Atlas port asked for; the default when none."""
    if given in (None, ""):
        return DEFAULT_PORT
    text = str(given).strip()
    if not text.isdigit() or not 1 <= int(text) <= 65535:
        raise BiStoreError("atlas_port_invalid", "Atlas 的 port 必須是 1 到 65535 的數字")
    return int(text)


def _get(port: int, path: str) -> Any:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        method="GET",
        headers={"Accept": "application/json"},  # no Origin: a server-side read
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as reply:  # noqa: S310 - loopback only
            body = reply.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        code, message = STATUS.get(error.code, ("atlas_failed", f"Atlas 回應 {error.code}"))
        raise BiStoreError(code, message) from None
    except (urllib.error.URLError, OSError):
        raise BiStoreError(
            "atlas_unreachable", f"Atlas 沒有在這台電腦的 port {port} 執行"
        ) from None
    if len(body) > MAX_BYTES:
        raise BiStoreError("atlas_too_large", "這個 Atlas Dashboard 太大")
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise BiStoreError("atlas_invalid", "Atlas 的回應不是 JSON") from None


def names(port: int) -> list[str]:
    found = _get(port, "/dashboards")
    if not isinstance(found, list) or not all(isinstance(n, str) for n in found):
        raise BiStoreError("atlas_invalid", "Atlas 的 Dashboard 清單格式不正確")
    return found


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    found = dict(pairs)
    if len(found) != len(pairs):
        raise ValueError("a repeated key")
    return found


def _no_constant(name: str) -> Any:
    raise ValueError(f"{name} is not JSON")


def document_from_file(text: Any) -> Any:
    """A chosen file's text as a document: strict JSON (no repeated key, no
    `NaN`), within Atlas's bound."""
    if not isinstance(text, str):
        raise BiStoreError("atlas_invalid", "這個檔案不是文字")
    if len(text.encode("utf-8", "surrogatepass")) > MAX_BYTES:
        raise BiStoreError("atlas_too_large", "這個 Dashboard 檔案太大")
    try:
        return json.loads(
            text.removeprefix("\ufeff"),
            object_pairs_hook=_unique_keys,
            parse_constant=_no_constant,
        )
    except (ValueError, RecursionError):
        raise BiStoreError("atlas_invalid", "這個檔案不是有效的 JSON") from None


def preview(workspace: Path, vault_id: str, name: Any, port: int) -> dict[str, Any]:
    if not isinstance(name, str) or not name:
        raise BiStoreError("atlas_name_missing", "請選一個 Atlas Dashboard")
    vault.Vault(workspace, vault_id)._require_folder()
    document = _get(port, "/dashboards/" + quote(name, safe=""))
    return _planned(workspace, vault_id, document)


def _planned(workspace: Path, vault_id: str, document: Any) -> dict[str, Any]:
    units = vault.Vault(workspace, vault_id).repo.working_units()
    saved = [item["slug"] for item in analyses.saved(units)]
    return atlas_import.plan(document, vault_id, saved, analyses.dashboard_layout(units))


def import_order(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """The dry run (no `apply`), or the import (`apply` with its token)."""
    if "file" in given:
        if given.get("name"):
            raise BiStoreError("atlas_source_ambiguous", "只能選 Atlas 的 Dashboard 或檔案其中一個")
        vault.Vault(workspace, vault_id)._require_folder()
        planned = _planned(workspace, vault_id, document_from_file(given["file"]))
    else:
        planned = preview(workspace, vault_id, given.get("name"), port_of(given.get("port")))
    if given.get("apply") is not True:
        return {"dry_run": True, **planned}
    if given.get("token") != planned["token"]:
        raise BiStoreError("preview_stale", "Atlas 或知識庫在預覽後有變動，請重新預覽")
    if not planned["order"]:
        raise BiStoreError(
            "atlas_nothing", "這個 Atlas Dashboard 沒有這個知識庫的分析，沒有可匯入的順序"
        )
    listed = analyses.set_dashboard(
        workspace, vault_id, {"order": planned["order"], "hidden": planned["hidden"]}
    )
    return {
        "dry_run": False,
        **planned,
        "staged": analyses.DASHBOARD_UNIT,
        "analyses": listed["analyses"],
    }
