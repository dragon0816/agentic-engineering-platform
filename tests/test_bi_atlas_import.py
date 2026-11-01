"""The Dashboard order imported from an Atlas dashboard (BI K2).

`docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md` K2 and Atlas's
`docs/AEP_DASHBOARD_READ_CONTRACT.md`: the vendored goldens are Atlas's bytes;
the vault's panels are sorted by stored geometry, each analysis keeps its first
panel, duplicates and unmatched panels are listed, `hidden` is the vault's
other analyses; Agent Web reads Atlas server-side without an Origin, previews,
and stages `meta:dashboard` only with the preview's token. All data is fictional.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pytest
from test_bi_query_analyses import _joined
from test_bi_vault import _call, _ok, _refused

from capabilities.bi_cards import analyses, atlas_import, vault
from capabilities.bi_cards.store import BiStoreError
from scripts import bi_feed_fixtures as fixtures
from scripts import check_atlas_dashboard_golden as drift

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "atlas_dashboard_golden"
VAULT = fixtures.VAULT_ID  # feed-fixture, the vault the Atlas goldens name
SAVED = ["accounts-by-region", "node-coverage", "tech-updates", "draft-only"]


def _golden(name: str) -> Any:
    return json.loads((GOLDEN / name).read_bytes())


# -- the vendored goldens --------------------------------------------------------------------


def test_the_goldens_are_exact_response_bodies_and_say_where_they_came_from() -> None:
    for name in ("list.json", "dashboard-mixed.json", "dashboard-legacy.json"):
        assert not (GOLDEN / name).read_bytes().endswith(b"\n"), name
    assert _golden("list.json") == ["Legacy overview", "Mixed BI layout"]
    assert "49600737" in (GOLDEN / "SOURCE.md").read_text("utf-8")


def test_the_drift_check_finds_a_changed_missing_or_extra_file(tmp_path: Path) -> None:
    atlas = tmp_path / "atlas"
    upstream = atlas / drift.UPSTREAM
    shutil.copytree(GOLDEN, upstream)
    assert drift.check(atlas) == 3
    (upstream / "list.json").write_bytes(b'["Mixed BI layout"]')
    with pytest.raises(drift.Drift, match="differs: list.json"):
        drift.check(atlas)
    (upstream / "list.json").unlink()
    with pytest.raises(drift.Drift, match="names differ"):
        drift.check(atlas)
    with pytest.raises(drift.Drift, match="no Atlas dashboard goldens"):
        drift.check(tmp_path / "nowhere")
    assert drift.main(["--atlas", str(tmp_path / "nowhere")]) == 1


@pytest.mark.skipif(not os.environ.get("AEP_ATLAS_REPO"), reason="AEP_ATLAS_REPO not set")
def test_the_vendored_goldens_equal_the_atlas_checkout() -> None:
    assert drift.check(Path(os.environ["AEP_ATLAS_REPO"])) == 3


# -- the order (the contract's rules) --------------------------------------------------------


def test_the_mixed_dashboard_gives_the_documented_order() -> None:
    planned = atlas_import.plan(_golden("dashboard-mixed.json"), VAULT, SAVED, {})
    # Contract: sorted ids bi-tech, bi-coverage, bi-region, bi-coverage-copy (an (0, 6) tie
    # broken by id); array order and the misleading non-AEP panel do not count.
    assert planned["order"] == ["tech-updates", "node-coverage", "accounts-by-region"]
    assert planned["duplicates"] == ["bi-coverage-copy"]
    assert planned["hidden"] == ["draft-only"]
    status = {p["id"]: p["status"] for p in planned["panels"]}
    assert status == {
        "bi-tech": "kept",
        "bi-coverage": "kept",
        "bi-region": "kept",
        "bi-coverage-copy": "duplicate",
        "non-aep": "not_aep",
        "bi-other-vault": "other_vault",
    }
    assert {p["id"] for p in planned["unmatched"]} == {"non-aep", "bi-other-vault"}
    assert planned["dashboard"] == "Mixed BI layout" and len(planned["token"]) == 24


def test_a_panel_for_an_analysis_the_vault_lacks_is_listed_not_invented() -> None:
    planned = atlas_import.plan(_golden("dashboard-mixed.json"), VAULT, ["node-coverage"], {})
    assert planned["order"] == ["node-coverage"]
    status = {p["id"]: p["status"] for p in planned["panels"]}
    assert status["bi-tech"] == status["bi-region"] == "unknown_analysis"
    assert planned["hidden"] == []


def test_the_legacy_dashboard_has_no_order_and_bad_documents_are_refused() -> None:
    legacy = atlas_import.plan(_golden("dashboard-legacy.json"), VAULT, SAVED, {})
    assert legacy["order"] == [] and legacy["hidden"] == SAVED
    assert [p["status"] for p in legacy["panels"]] == ["not_aep"]
    bads: list[Any] = [[], {"schemaVersion": 1, "panels": []}, {"schemaVersion": 2}]
    for bad in bads:
        with pytest.raises(BiStoreError) as refused:
            atlas_import.plan(bad, VAULT, SAVED, {})
        assert refused.value.code == "atlas_invalid"
    another = atlas_import.plan(_golden("dashboard-mixed.json"), VAULT, SAVED[:3], {})
    first = atlas_import.plan(_golden("dashboard-mixed.json"), VAULT, SAVED, {})
    assert another["token"] != first["token"]  # the vault changed: a new preview


# -- through Agent Web's routes, against a stand-in Atlas ---------------------------------


class _Atlas(BaseHTTPRequestHandler):
    """Atlas's read routes answering with the golden bytes; records each request."""

    seen: list[dict[str, Any]] = []
    documents = {
        "Mixed BI layout": "dashboard-mixed.json",
        "Legacy overview": "dashboard-legacy.json",
    }

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - base signature
        return None

    def do_GET(self) -> None:  # noqa: N802 - the base class's spelling
        _Atlas.seen.append(
            {
                "path": self.path,
                "host": self.headers.get("Host"),
                "origin": self.headers.get("Origin"),
            }
        )
        if self.path == "/dashboards":
            body = (GOLDEN / "list.json").read_bytes()
        elif unquote(self.path[len("/dashboards/") :]) in self.documents:
            body = (GOLDEN / self.documents[unquote(self.path[len("/dashboards/") :])]).read_bytes()
        else:
            body, code = b'{"detail":{"message":"Dashboard not found"}}', 404
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def atlas() -> Iterator[int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Atlas)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _Atlas.seen = []
    try:
        yield int(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _layout(ws: Path) -> dict[str, list[str]]:
    return analyses.dashboard_layout(vault.Vault(ws, VAULT).repo.working_units())


def test_a_dry_run_then_the_confirmed_import_stages_only_the_order(
    tmp_path: Path, atlas: int
) -> None:
    ws = _joined(tmp_path)
    listed = _ok(_call(ws, "GET", f"/api/bi/vaults/{VAULT}/atlas-dashboards", port=str(atlas)))
    assert listed == {"port": atlas, "names": ["Legacy overview", "Mixed BI layout"]}
    units = dict(vault.Vault(ws, VAULT).repo.working_units())
    asked = {"name": "Mixed BI layout", "port": atlas}
    dry = _ok(_call(ws, "POST", f"/api/bi/vaults/{VAULT}/atlas-import", asked))
    assert dry["dry_run"] is True and dry["order"] == ["tech-updates", "node-coverage",
                                                        "accounts-by-region"]  # fmt: skip
    assert dry["duplicates"] == ["bi-coverage-copy"] and dry["hidden"] == ["draft-only"]
    assert dry["before"] == fixtures.LAYOUT
    assert dict(vault.Vault(ws, VAULT).repo.working_units()) == units  # nothing staged yet
    # Read server-side: loopback Host, no Origin, GET only.
    assert {s["origin"] for s in _Atlas.seen} == {None}
    assert {s["host"] for s in _Atlas.seen} == {f"127.0.0.1:{atlas}"}
    assert _Atlas.seen[-1]["path"] == "/dashboards/Mixed%20BI%20layout"

    _refused(_call(ws, "POST", f"/api/bi/vaults/{VAULT}/atlas-import",
                   {**asked, "apply": True, "token": "0" * 24}), 409, "preview_stale")  # fmt: skip
    done = _ok(_call(ws, "POST", f"/api/bi/vaults/{VAULT}/atlas-import",
                     {**asked, "apply": True, "token": dry["token"]}))  # fmt: skip
    assert done["staged"] == "meta:dashboard"
    assert _layout(ws) == {"order": ["tech-updates", "node-coverage", "accounts-by-region"],
                           "hidden": ["draft-only"]}  # fmt: skip
    after = dict(vault.Vault(ws, VAULT).repo.working_units())
    assert {k for k in after if after[k] != units.get(k)} == {"meta:dashboard"}


def test_nothing_to_import_and_atlas_failures_are_plain_errors(tmp_path: Path, atlas: int) -> None:
    ws = _joined(tmp_path)
    before = _layout(ws)
    legacy = {"name": "Legacy overview", "port": atlas}
    dry = _ok(_call(ws, "POST", f"/api/bi/vaults/{VAULT}/atlas-import", legacy))
    confirm = {**legacy, "apply": True, "token": dry["token"]}
    _refused(_call(ws, "POST", f"/api/bi/vaults/{VAULT}/atlas-import", confirm),
             400, "atlas_nothing")  # fmt: skip
    _refused(_call(ws, "POST", f"/api/bi/vaults/{VAULT}/atlas-import",
                   {"name": "Gone", "port": atlas}), 400, "atlas_not_found")  # fmt: skip
    _refused(_call(ws, "GET", f"/api/bi/vaults/{VAULT}/atlas-dashboards", port="0"),
             400, "atlas_port_invalid")  # fmt: skip
    closed = ThreadingHTTPServer(("127.0.0.1", 0), _Atlas)
    port = closed.server_address[1]
    closed.server_close()  # nothing listens there now
    _refused(_call(ws, "GET", f"/api/bi/vaults/{VAULT}/atlas-dashboards", port=str(port)),
             400, "atlas_unreachable")  # fmt: skip
    assert _layout(ws) == before
