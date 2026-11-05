"""Agent Web takes a whole page's requests even while it is too busy to accept them yet.

The page opens about 20 requests at once. On a loaded PC the accepting thread falls behind, and
with Python's default backlog of 5 Windows refuses the rest: `Failed to fetch` in the page, whose
Send button then stays shut, as `test_bi_many_sources_ui` and `test_bi_vault_steps_ui` saw.
Not accepting at all stands in for being that far behind, so the order is not luck.
"""

from __future__ import annotations

import socket
from pathlib import Path
from urllib.parse import urlsplit

from test_vault_asking_e2e import _bi_host

from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer

AT_ONCE = 40


def test_a_page_of_requests_is_not_refused_while_nothing_is_being_accepted(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path)
    with build_runtime(config, layout=layout) as runtime:
        server = AgentWebServer(AgentWeb(runtime))  # listening, and `serve_forever` never runs
        try:
            place = urlsplit(server.address)
            assert place.hostname is not None and place.port is not None
            opened: list[socket.socket] = []
            try:
                for _ in range(AT_ONCE):
                    opened.append(socket.create_connection((place.hostname, place.port), 5))
            finally:
                for each in opened:
                    each.close()
            assert len(opened) == AT_ONCE
        finally:
            server.server_close()
