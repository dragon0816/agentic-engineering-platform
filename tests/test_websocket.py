"""The WebSocket client, against a server built here out of sockets.

Nothing is stubbed. The frames this writes are read back by something that
knows RFC 6455, and the frames it reads are written by hand -- fragmented,
interleaved with pings, and at every length the protocol encodes differently.
That is the only way to find out whether a client written from the
specification actually speaks it.
"""

from __future__ import annotations

import json
import socket
import struct
import threading
from collections.abc import Callable, Iterator

import pytest

from integrations.websocket import (
    CLOSE,
    PING,
    TEXT,
    Devtools,
    DevtoolsRefused,
    WebSocket,
    WebSocketError,
    accept_for,
    frame,
)


def server_frame(opcode: int, payload: bytes, *, final: bool = True) -> bytes:
    """A frame as a server sends one: never masked."""
    header = bytearray([(0x80 if final else 0) | opcode])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 1 << 16:
        header.append(126)
        header += struct.pack(">H", length)
    else:
        header.append(127)
        header += struct.pack(">Q", length)
    return bytes(header) + payload


def read_frame(connection: socket.socket) -> tuple[int, bytes]:
    """One frame from a client, unmasked. Raises if it was not masked, which
    is the rule a client must follow."""

    def take(count: int) -> bytes:
        held = b""
        while len(held) < count:
            chunk = connection.recv(count - len(held))
            if not chunk:
                raise AssertionError("the client closed mid-frame")
            held += chunk
        return held

    first, second = take(2)
    assert second & 0x80, "a client must mask every frame it sends"
    length = second & 0x7F
    if length == 126:
        (length,) = struct.unpack(">H", take(2))
    elif length == 127:
        (length,) = struct.unpack(">Q", take(8))
    mask = take(4)
    payload = take(length)
    return first & 0x0F, bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


class Server:
    """A loopback WebSocket server driven by a script."""

    def __init__(self, behave: Callable[[socket.socket], None], *, upgrade: bool = True) -> None:
        self.behave = behave
        self.upgrade = upgrade
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.failure: BaseException | None = None
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/devtools/page/ABC"

    def _serve(self) -> None:
        try:
            connection, _address = self.listener.accept()
            with connection:
                request = b""
                while b"\r\n\r\n" not in request:
                    chunk = connection.recv(4096)
                    if not chunk:
                        return
                    request += chunk
                if not self.upgrade:
                    connection.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                    return
                key = next(
                    line.split(":", 1)[1].strip()
                    for line in request.decode("latin-1").split("\r\n")
                    if line.lower().startswith("sec-websocket-key:")
                )
                connection.sendall(
                    (
                        "HTTP/1.1 101 Switching Protocols\r\n"
                        "Upgrade: websocket\r\n"
                        "Connection: Upgrade\r\n"
                        f"Sec-WebSocket-Accept: {accept_for(key)}\r\n\r\n"
                    ).encode()
                )
                self.behave(connection)
        except BaseException as failure:  # noqa: BLE001 - reported to the test
            self.failure = failure

    def close(self) -> None:
        self.listener.close()


@pytest.fixture
def served() -> Iterator[list[Server]]:
    made: list[Server] = []
    yield made
    for server in made:
        server.close()


def start(made: list[Server], behave: Callable[[socket.socket], None], **options: object) -> Server:
    server = Server(behave, **options)  # type: ignore[arg-type]
    made.append(server)
    return server


# -- what it refuses ------------------------------------------------------


def test_it_speaks_to_this_machine_and_nowhere_else() -> None:
    """A browser this machine started listens on loopback. Anything else is
    somebody else's browser, and this has no business reaching it."""
    for elsewhere in (
        "ws://example.com/devtools",
        "ws://10.0.0.5:9222/devtools",
        "wss://127.0.0.1:9222/devtools",
    ):
        with pytest.raises(WebSocketError) as refused:
            WebSocket(elsewhere)
        assert refused.value.code == "not_loopback"


def test_nothing_listening_is_its_own_answer() -> None:
    spare = socket.socket()
    spare.bind(("127.0.0.1", 0))
    port = spare.getsockname()[1]
    spare.close()
    with pytest.raises(WebSocketError) as refused:
        WebSocket(f"ws://127.0.0.1:{port}/x", timeout_s=2)
    assert refused.value.code == "connect_failed"


def test_something_that_is_not_a_websocket_server_is_told_apart(
    served: list[Server],
) -> None:
    server = start(served, lambda _c: None, upgrade=False)
    with pytest.raises(WebSocketError) as refused:
        WebSocket(server.url, timeout_s=5)
    assert refused.value.code == "handshake_refused"


def test_a_wrong_accept_is_refused(served: list[Server]) -> None:
    """Proof the server actually spoke WebSocket rather than echoing."""

    def lie(connection: socket.socket) -> None:
        pass

    class Lying(Server):
        def _serve(self) -> None:
            connection, _address = self.listener.accept()
            with connection:
                while b"\r\n\r\n" not in connection.recv(4096):
                    pass
                connection.sendall(
                    b"HTTP/1.1 101 Switching Protocols\r\n"
                    b"Upgrade: websocket\r\n"
                    b"Sec-WebSocket-Accept: not-the-right-answer\r\n\r\n"
                )

    server = Lying(lie)
    served.append(server)
    with pytest.raises(WebSocketError) as refused:
        WebSocket(server.url, timeout_s=5)
    assert refused.value.code == "handshake_wrong"


def test_a_masked_server_frame_is_a_protocol_error(served: list[Server]) -> None:
    def misbehave(connection: socket.socket) -> None:
        connection.sendall(frame(TEXT, b"hello"))  # masked, which a server may not do

    server = start(served, misbehave)
    with WebSocket(server.url, timeout_s=5) as ws:
        with pytest.raises(WebSocketError) as refused:
            ws.receive()
    assert refused.value.code == "protocol_error"


# -- what it does ---------------------------------------------------------


def test_what_it_sends_is_masked_and_readable(served: list[Server]) -> None:
    seen: list[tuple[int, bytes]] = []

    def listen(connection: socket.socket) -> None:
        seen.append(read_frame(connection))
        connection.sendall(server_frame(TEXT, b"heard"))

    server = start(served, listen)
    with WebSocket(server.url, timeout_s=5) as ws:
        ws.send("a message with 中文 in it")
        assert ws.receive() == "heard"
    assert server.failure is None
    assert seen[0][0] == TEXT
    assert seen[0][1].decode("utf-8") == "a message with 中文 in it"


@pytest.mark.parametrize("size", [0, 5, 125, 126, 200, 65535, 65536, 70000])
def test_every_length_the_protocol_encodes_differently(served: list[Server], size: int) -> None:
    """7-bit, 16-bit and 64-bit lengths, and the boundaries between them."""
    body = ("x" * size).encode()

    def echo(connection: socket.socket) -> None:
        read_frame(connection)
        connection.sendall(server_frame(TEXT, body))

    server = start(served, echo)
    with WebSocket(server.url, timeout_s=10) as ws:
        ws.send("x" * size)
        assert ws.receive() == "x" * size
    assert server.failure is None, server.failure


def test_a_fragmented_message_arrives_whole(served: list[Server]) -> None:
    """A screenshot is base64 in one message and Chromium does fragment."""

    def in_pieces(connection: socket.socket) -> None:
        connection.sendall(server_frame(TEXT, b"one ", final=False))
        connection.sendall(server_frame(0, b"two ", final=False))
        connection.sendall(server_frame(0, b"three", final=True))

    server = start(served, in_pieces)
    with WebSocket(server.url, timeout_s=5) as ws:
        assert ws.receive() == "one two three"


def test_a_ping_is_answered_and_is_not_the_message(served: list[Server]) -> None:
    answered: list[tuple[int, bytes]] = []

    def ping_then_speak(connection: socket.socket) -> None:
        connection.sendall(server_frame(PING, b"still there?"))
        answered.append(read_frame(connection))
        connection.sendall(server_frame(TEXT, b"the actual message"))

    server = start(served, ping_then_speak)
    with WebSocket(server.url, timeout_s=5) as ws:
        assert ws.receive() == "the actual message"
    assert answered[0][0] == 0xA, "a pong"
    assert answered[0][1] == b"still there?"


def test_a_ping_between_fragments_does_not_break_the_message(
    served: list[Server],
) -> None:
    def interleave(connection: socket.socket) -> None:
        connection.sendall(server_frame(TEXT, b"first ", final=False))
        connection.sendall(server_frame(PING, b""))
        read_frame(connection)
        connection.sendall(server_frame(0, b"second", final=True))

    server = start(served, interleave)
    with WebSocket(server.url, timeout_s=5) as ws:
        assert ws.receive() == "first second"


def test_a_close_is_reported_rather_than_hung(served: list[Server]) -> None:
    def leave(connection: socket.socket) -> None:
        connection.sendall(server_frame(CLOSE, b""))

    server = start(served, leave)
    with WebSocket(server.url, timeout_s=5) as ws:
        with pytest.raises(WebSocketError) as refused:
            ws.receive()
    assert refused.value.code == "closed"


# -- the protocol on top --------------------------------------------------


def devtools_server(
    served: list[Server],
    answers: list[dict[str, object]],
    events: list[dict[str, object]] | None = None,
) -> Server:
    def behave(connection: socket.socket) -> None:
        for event in events or ():
            connection.sendall(server_frame(TEXT, json.dumps(event).encode()))
        for answer in answers:
            _opcode, asked = read_frame(connection)
            reply = dict(answer)
            reply.setdefault("id", json.loads(asked)["id"])
            connection.sendall(server_frame(TEXT, json.dumps(reply).encode()))

    return start(served, behave)


def test_a_command_gets_its_own_answer(served: list[Server]) -> None:
    server = devtools_server(served, [{"result": {"value": 42}}])
    with Devtools(server.url, timeout_s=5) as page:
        assert page.call("Runtime.evaluate", expression="6*7") == {"value": 42}


def test_events_arriving_first_are_kept_not_mistaken_for_the_answer(
    served: list[Server],
) -> None:
    """`Page.loadEventFired` is how a navigation is known to have finished,
    so an event is worth keeping rather than dropping."""
    server = devtools_server(
        served,
        [{"result": {"frameId": "1"}}],
        [{"method": "Page.loadEventFired", "params": {"timestamp": 1}}],
    )
    with Devtools(server.url, timeout_s=5) as page:
        assert page.call("Page.navigate", url="about:blank") == {"frameId": "1"}
        assert page.drain("Page.loadEventFired") is True
        assert page.drain("Page.somethingElse") is False


def test_a_refused_command_names_the_method(served: list[Server]) -> None:
    server = devtools_server(served, [{"error": {"code": -32000, "message": "Cannot navigate"}}])
    with Devtools(server.url, timeout_s=5) as page:
        with pytest.raises(DevtoolsRefused) as refused:
            page.call("Page.navigate", url="about:blank")
    assert refused.value.method == "Page.navigate"
    assert "Cannot navigate" in refused.value.detail


def test_answers_that_are_not_json_are_a_protocol_error(served: list[Server]) -> None:
    def gibberish(connection: socket.socket) -> None:
        read_frame(connection)
        connection.sendall(server_frame(TEXT, b"not json at all"))

    server = start(served, gibberish)
    with Devtools(server.url, timeout_s=5) as page:
        with pytest.raises(WebSocketError) as refused:
            page.call("Page.enable")
    assert refused.value.code == "protocol_error"


def test_each_command_is_numbered_so_answers_cannot_be_swapped(
    served: list[Server],
) -> None:
    asked: list[dict[str, object]] = []

    def record(connection: socket.socket) -> None:
        for _ in range(3):
            _opcode, payload = read_frame(connection)
            message = json.loads(payload)
            asked.append(message)
            connection.sendall(
                server_frame(TEXT, json.dumps({"id": message["id"], "result": {}}).encode())
            )

    server = start(served, record)
    with Devtools(server.url, timeout_s=5) as page:
        page.call("Page.enable")
        page.call("Runtime.enable")
        page.call("DOM.enable")
    assert [item["id"] for item in asked] == [1, 2, 3]
    assert [item["method"] for item in asked] == ["Page.enable", "Runtime.enable", "DOM.enable"]
