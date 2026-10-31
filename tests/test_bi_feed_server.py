"""The BI feed fixture server Atlas develops and tests against (BI feed F3).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §6.2: `scripts/bi_feed_server.py` serves
only the feed routes on the fixture vault, prints `ready <url>`, answers the
golden files, and a new script parameter answers `409` first and its result
after the queue delay. Run as Atlas runs it, a separate process.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections.abc import Iterator
from typing import Any

import pytest
from test_bi_feed_api import call

from scripts import bi_feed_fixtures as fixtures


@pytest.fixture
def server() -> Iterator[str]:
    process = subprocess.Popen(  # noqa: S603 - our interpreter and script, fixed arguments
        [sys.executable, "scripts/bi_feed_server.py", "--port", "0", "--queue-delay", "1"],
        cwd=fixtures.REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        line = process.stdout.readline().strip()
        assert line.startswith("ready http://127.0.0.1:") and line.endswith("/api/v1/bi"), (
            line,
            process.stderr.read() if process.poll() is not None and process.stderr else "",
        )
        yield line.split(" ", 1)[1]
    finally:
        process.terminate()
        process.wait(timeout=20)


def _golden(name: str) -> Any:
    return json.loads((fixtures.GOLDEN_DIR / name).read_text(encoding="utf-8"))


def test_the_fixture_server_answers_the_golden_files(server: str) -> None:
    origin = "http://localhost:5173"
    for name, path in (
        ("health.json", "/health"),
        ("vaults.json", "/vaults"),
        ("analyses.json", f"/vaults/{fixtures.VAULT_ID}/analyses"),
        ("result-tech-updates.json", f"/vaults/{fixtures.VAULT_ID}/analyses/tech-updates/result"),
    ):
        status, headers, body = call(server + path, origin=origin)
        assert status == 200 and json.loads(body) == _golden(name), name
        assert headers["Access-Control-Allow-Origin"] == origin
    waiting = f"{server}/vaults/{fixtures.VAULT_ID}/analyses/tech-updates/result?domain=wireless"
    status, _, body = call(waiting)
    assert (status, json.loads(body)) == (409, _golden("error-result_not_ready.json"))
    deadline = time.monotonic() + 60
    while status == 409 and time.monotonic() < deadline:
        time.sleep(0.3)
        status, _, body = call(waiting)
    assert json.loads(body) == _golden("result-tech-updates-domain-wireless.json")
    status, _, body = call(server + "/vaults", origin="https://example.com")
    assert (status, json.loads(body)) == (403, _golden("error-origin_refused.json"))
    root = server[: -len("/api/v1/bi")]
    for other in ("/", "/api/bi/vaults", "/api/v1/telemetry/health"):
        status, _, body = call(root + other)
        assert (status, json.loads(body)["code"]) == (404, "route_unknown"), other
