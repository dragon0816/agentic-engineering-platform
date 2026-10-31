"""Serve only the BI analysis feed, on the fixture vault (BI feed F3).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §6.2. For Atlas development and its
end-to-end test: a temporary workspace joins a copy of
`tests/fixtures/bi_feed/vault/`, the default results are computed, and the
feed routes (`/api/v1/bi/*`, Agent Web's own `bi_feed_api`) are served on the
loopback address with the fixture's fixed `computed_at`, so every answer equals
its golden file. No model, no token, no other route.

    python scripts/bi_feed_server.py --port 53611 [--queue-delay 2]

Prints `ready <url>` (the feed's base, `http://127.0.0.1:<port>/api/v1/bi`)
when listening. A script result asked for with new parameters answers
`409 result_not_ready` and is computed `--queue-delay` seconds later; each
start begins with an empty cache. Stop it with Ctrl+C.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src"):  # run as a script: neither is importable then
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from capabilities.bi_cards import feed  # noqa: E402
from host_runtime import bi_feed_api  # noqa: E402
from scripts import bi_feed_fixtures as fixtures  # noqa: E402


class _Handler(BaseHTTPRequestHandler):
    server: _FeedServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - base signature
        return None

    def _loopback(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return host in ("127.0.0.1", "localhost", "::1")

    def _answer(self, method: str) -> None:
        parsed = urlparse(self.path)
        if method != "GET":
            length = int(self.headers.get("Content-Length") or "0")
            if 0 < length <= 1_000_000:
                self.rfile.read(length)
        if not self._loopback():
            bi_feed_api._reply(self, 403, {"ok": False, "code": "host_refused",
                                           "message": "loopback only"})  # fmt: skip
            return
        path = parsed.path if bi_feed_api.is_feed(parsed.path) else feed.PREFIX + "-"
        bi_feed_api.handle(self, method, path, parsed.query, self.server.workspace)

    def do_GET(self) -> None:  # noqa: N802 - the base class's spelling
        self._answer("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._answer("POST")


class _FeedServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, port: int, workspace: Path) -> None:
        self.workspace = workspace
        super().__init__(("127.0.0.1", port), _Handler)


def prepare(root: Path) -> Path:
    """A workspace that joined a copy of the fixture vault, defaults computed."""
    workspace = root / "workspace"
    workspace.mkdir()
    copy = root / "shared" / "vault"
    shutil.copytree(fixtures.VAULT_DIR, copy)
    fixtures.join(workspace, copy)
    feed.clock = lambda: fixtures.COMPUTED_AT
    feed.compute_defaults(workspace, fixtures.VAULT_ID)
    return workspace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=53611, help="0 picks a free port")
    parser.add_argument(
        "--queue-delay", type=float, default=2.0, help="seconds before a queued result is computed"
    )
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(
        prefix="aep-bi-feed-server-", ignore_cleanup_errors=True
    ) as scratch:
        workspace = prepare(Path(scratch))
        bi_feed_api.QUEUE_DELAY = max(0.0, args.queue_delay)
        bi_feed_api.ensure_worker()
        server = _FeedServer(args.port, workspace)
        print(f"ready http://127.0.0.1:{server.server_address[1]}/api/v1/bi", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
