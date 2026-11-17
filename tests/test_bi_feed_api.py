"""The BI analysis feed served by Agent Web: the contract test (BI feed F2).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §5, §6.1. The live routes on the
fixture vault answer exactly the golden files Atlas vendors, replayed in the
order of `golden/requests.json` over real HTTP; GET only, no token, local page
origins only, and every other Agent Web route keeps its token. All data is
fictional.
"""

from __future__ import annotations

import json
import shutil
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aep_bi.cards import feed
from host_runtime.web import AgentWebServer
from scripts import bi_feed_fixtures as fixtures

Reply = tuple[int, dict[str, str], bytes]


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, Path]]:
    """Agent Web's own handler on a PC that joined a copy of the fixture vault."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    copy = tmp_path / "shared" / "vault"
    shutil.copytree(fixtures.VAULT_DIR, copy)
    fixtures.join(workspace, copy)
    monkeypatch.setattr(feed, "clock", lambda: fixtures.COMPUTED_AT)
    feed.drain()
    web = SimpleNamespace(runtime=SimpleNamespace(layout=SimpleNamespace(workspace_root=workspace)))
    server = AgentWebServer(web)  # type: ignore[arg-type]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", workspace
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        feed.drain()


def call(url: str, *, origin: str | None = None, method: str = "GET", **headers: str) -> Reply:
    request = urllib.request.Request(url, method=method, data=b"{}" if method == "POST" else None)
    if origin:
        request.add_header("Origin", origin)
    for name, value in headers.items():
        request.add_header(name.replace("_", "-"), value)
    try:
        with urllib.request.urlopen(request, timeout=60) as answer:
            return answer.status, dict(answer.headers), answer.read()
    except urllib.error.HTTPError as refused:
        return refused.code, dict(refused.headers), refused.read()


def _golden(name: str) -> Any:
    return json.loads((fixtures.GOLDEN_DIR / name).read_text(encoding="utf-8"))


def test_the_live_routes_answer_exactly_the_golden_files(served: tuple[str, Path]) -> None:
    url, workspace = served
    feed.compute_defaults(workspace, fixtures.VAULT_ID)  # as on publish
    for listed in _golden("requests.json")["requests"]:
        status, headers, body = call(url + listed["url"], origin=listed["origin"])
        deadline = time.monotonic() + 60
        while listed["after_queue"] and status == 409 and time.monotonic() < deadline:
            time.sleep(0.2)  # the worker computes what the earlier request queued
            status, headers, body = call(url + listed["url"], origin=listed["origin"])
        assert status == listed["status"], (listed["file"], body)
        assert json.loads(body) == _golden(listed["file"]), listed["file"]
        assert headers["Content-Type"] == "application/json; charset=utf-8"
        assert headers["Cache-Control"] == "no-store" and len(body) <= feed.MAX_BYTES


def test_only_local_pages_read_it_without_a_token(served: tuple[str, Path]) -> None:
    url, _ = served
    health = url + "/api/v1/bi/health"
    for origin in ("http://127.0.0.1:5173", "http://localhost:3000", "http://[::1]:8080"):
        status, headers, _ = call(health, origin=origin)
        assert status == 200 and headers["Access-Control-Allow-Origin"] == origin
    status, headers, _ = call(health)
    assert status == 200 and "Access-Control-Allow-Origin" not in headers
    for origin in ("https://example.com", "http://127.0.0.1.example.com", "null"):
        status, headers, body = call(health, origin=origin)
        assert (status, json.loads(body)["code"]) == (403, "origin_refused"), origin
        assert "Access-Control-Allow-Origin" not in headers
    status, _, body = call(health, method="POST")
    assert (status, json.loads(body)["code"]) == (405, "method_not_allowed")
    status, _, _ = call(health, Host="aep.example.com")
    assert status == 403  # the loopback Host guard of every route
    status, _, _ = call(url + "/api/bi/vaults")
    assert status == 401  # every other route keeps its token
    status, _, _ = call(url + "/api/v1/bi/vaults/feed-fixture/analyses/x/result/more")
    assert status == 404


def test_a_publish_queues_the_default_results(
    served: tuple[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from aep_bi.host import bi_feed_api

    url, workspace = served
    monkeypatch.setattr(feed, "on_queued", None)  # this test drains the queue itself
    assert feed.enqueue_defaults(workspace, fixtures.VAULT_ID) == 3
    feed.drain()
    assert feed.enqueue_defaults(workspace, fixtures.VAULT_ID) == 0  # all cached now
    bi_feed_api.refresh(workspace, "no-such-vault")  # never raises
    status, _, body = call(url + "/api/v1/bi/vaults/feed-fixture/analyses/tech-updates/result")
    assert status == 200 and json.loads(body) == _golden("result-tech-updates.json")
