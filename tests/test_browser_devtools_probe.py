"""A browser that answers its DevTools port with a broken reply is not answering.

CI 2026-10-19: a browser shutting down answered `/json/version` with a broken
status line; `http.client.BadStatusLine` is not an OSError, so it escaped the
probes and failed a real-browser test.
"""

import socket
import threading
from collections.abc import Iterator

import pytest

from integrations.browser import Browser


@pytest.fixture
def garbage_port() -> Iterator[int]:
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(4)
    stop = threading.Event()

    def serve() -> None:
        server.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = server.accept()
            except OSError:
                continue
            with conn:
                conn.recv(1024)
                conn.sendall(b"not an http status line\r\n\r\n")

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield server.getsockname()[1]
    stop.set()
    thread.join(2)
    server.close()


def test_a_broken_reply_means_the_browser_is_not_answering(garbage_port: int) -> None:
    probe = Browser.__new__(Browser)
    assert probe._still_answering(garbage_port) is False
    assert probe._ask_it_to_close(garbage_port) is False
