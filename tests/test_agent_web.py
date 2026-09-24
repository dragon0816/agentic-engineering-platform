"""The web interface, over a real socket.

Nothing here stubs the server. It is started, spoken to over TCP the way a
browser speaks to it, and stopped -- because the things worth pinning are the
guards, and a guard tested through a function call is a guard that was never
asked the question an attacker asks.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_host_wiring import ready

from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer


class Reply:
    def __init__(self, status: int, body: bytes, headers: dict[str, str]) -> None:
        self.status = status
        self.body = body
        self.headers = headers

    def json(self) -> Any:
        return json.loads(self.body)


def fetch(
    url: str, *, token: str | None = None, body: Any = None, host: str | None = None
) -> Reply:
    request = urllib.request.Request(url, method="POST" if body is not None else "GET")
    if token is not None:
        request.add_header("Authorization", f"Bearer {token}")
    if host is not None:
        request.add_header("Host", host)
    if body is not None:
        request.add_header("Content-Type", "application/json")
        request.data = json.dumps(body).encode("utf-8")
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:
            return Reply(answer.status, answer.read(), dict(answer.headers))
    except urllib.error.HTTPError as refused:
        return Reply(refused.code, refused.read(), dict(refused.headers))


@pytest.fixture
def served(tmp_path: Path) -> Iterator[AgentWebServer]:
    config, _layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def base(server: AgentWebServer) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}"


def test_it_listens_on_the_loopback_address_only(served: AgentWebServer) -> None:
    """Not a setting. Nothing on the network can reach a machine's Agent."""
    assert served.server_address[0] == "127.0.0.1"
    assert "127.0.0.1" in served.address


def test_the_token_is_new_every_run_and_long(tmp_path: Path) -> None:
    """A token that outlived the process would be a standing key to this
    machine's Agent lying in somebody's shell history."""
    config, _layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        first = AgentWebServer(AgentWeb(runtime))
        second = AgentWebServer(AgentWeb(runtime))
        try:
            assert first.token != second.token
            assert len(first.token) >= 32
        finally:
            first.server_close()
            second.server_close()


def test_the_page_needs_the_token_in_the_address(served: AgentWebServer) -> None:
    """A browser cannot be asked to set a header on its first visit, so the
    page is let in by the address -- and only by the right one."""
    assert fetch(base(served) + "/").status == 401
    assert fetch(base(served) + "/?token=not-the-token").status == 401
    page = fetch(base(served) + f"/?token={served.token}")
    assert page.status == 200
    assert page.headers["Content-Type"].startswith("text/html")
    assert b"<!DOCTYPE html>" in page.body


def test_the_page_fetches_nothing_from_anywhere(served: AgentWebServer) -> None:
    """A company machine installs this behind a proxy that reaches no
    package index and no content delivery network. A page that went looking
    for one would render wrong exactly where it matters."""
    body = fetch(base(served) + f"/?token={served.token}").body.decode("utf-8")
    for outside in ("http://", "https://", "//cdn", "@import"):
        assert outside not in body, f"the page reaches for {outside}"


def test_every_api_call_needs_the_header(served: AgentWebServer) -> None:
    """The header is the whole cross-site defence: a page on another origin
    cannot set one without a preflight, and this server answers none."""
    for path in ("/api/about", "/api/assets", "/api/platform"):
        assert fetch(base(served) + path).status == 401
        assert fetch(base(served) + path, token="wrong").status == 401
        assert fetch(base(served) + path, token=served.token).status == 200
    assert fetch(base(served) + "/api/ask", body={"message": "x"}).status == 401


def test_the_token_in_the_address_does_not_open_the_api(served: AgentWebServer) -> None:
    """Otherwise any page that learned the address would drive the Agent."""
    assert fetch(base(served) + f"/api/assets?token={served.token}").status == 401


def test_a_name_that_resolves_here_is_still_refused(served: AgentWebServer) -> None:
    """DNS rebinding: a name an attacker controls can be made to resolve to
    127.0.0.1, and then their page is same-origin with this one."""
    refused = fetch(base(served) + "/api/about", token=served.token, host="agent.attacker.example")
    assert refused.status == 403
    assert "loopback" in refused.json()["error"]


def test_it_answers_no_cross_origin_header(served: AgentWebServer) -> None:
    reply = fetch(base(served) + "/api/about", token=served.token)
    assert not any(name.lower().startswith("access-control") for name in reply.headers)
    assert reply.headers["X-Frame-Options"] == "DENY"
    assert reply.headers["X-Content-Type-Options"] == "nosniff"


def test_it_says_who_and_where_it_is(served: AgentWebServer) -> None:
    about = fetch(base(served) + "/api/about", token=served.token).json()
    assert about["actor"] == "engineer"
    assert about["bridge_id"] == "bridge-company"
    assert about["namespace"] == "engineering"


def test_it_lists_what_this_machine_has_without_naming_any_one_of_them(
    served: AgentWebServer,
) -> None:
    """Generic on purpose: the listing is built from the manifests, so a new
    asset appears the day it is installed and no page is written for it."""
    assets = fetch(base(served) + "/api/assets", token=served.token).json()
    aliases = [skill["alias"] for skill in assets["skills"]]
    assert "files" in aliases
    names = [workflow["name"] for workflow in assets["workflows"]]
    assert "read-local-file" in names
    assert all("steps" in workflow for workflow in assets["workflows"])
    assert assets["runs"] == [], "nothing has run yet"


def test_a_machine_with_no_shared_platform_says_so(served: AgentWebServer) -> None:
    """And does not show an empty table that reads as "nobody published
    anything"."""
    platform = fetch(base(served) + "/api/platform", token=served.token).json()
    assert platform["configured"] is False
    assert "No shared platform is configured" in platform["note"]
    assert platform["decisions"] == []


def test_asking_runs_the_real_agent_and_the_run_is_recorded(served: AgentWebServer) -> None:
    """The same Agent the command line reaches, on the same ingress. The run
    then shows up in the listing, which is how a person sees what happened."""
    root = served.web.runtime.layout.workspace_root
    answer = fetch(
        base(served) + "/api/ask",
        token=served.token,
        body={"message": f"files.read {root / 'notes.txt'}"},
    ).json()
    assert answer["ok"] is True
    assert "succeeded" in answer["answer"]
    assert "first line" in answer["answer"]
    assert answer["outcome"]["ingress"] == "local"
    assert answer["outcome"]["actor"] == "engineer"
    assets = fetch(base(served) + "/api/assets", token=served.token).json()
    assert len(assets["runs"]) == 1
    assert assets["runs"][0]["status"] == "succeeded"


def test_an_empty_or_shapeless_request_is_refused_before_the_agent(
    served: AgentWebServer,
) -> None:
    ask = base(served) + "/api/ask"
    assert fetch(ask, token=served.token, body={}).status == 400
    assert fetch(ask, token=served.token, body={"message": "  "}).status == 400


def test_a_request_that_raises_is_answered_rather_than_dropped(served: AgentWebServer) -> None:
    """A browser waiting for ever on a dead request is worse than a message."""

    def explode(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("the board could not be reached")

    served.web.ask = explode  # type: ignore[method-assign]
    answer = fetch(
        base(served) + "/api/ask", token=served.token, body={"message": "anything"}
    ).json()
    assert answer["ok"] is False
    assert "did not finish" in answer["answer"]


def test_an_unknown_page_is_not_found(served: AgentWebServer) -> None:
    assert fetch(base(served) + "/api/whatever", token=served.token).status == 404
    assert fetch(base(served) + "/api/x", token=served.token, body={"message": "y"}).status == 404


def test_a_host_with_no_namespace_says_what_to_set(tmp_path: Path) -> None:
    """The same refusal the command line gives, because it is the same
    missing setting, and it is said rather than raised at the browser."""
    config, _layout = ready(tmp_path, config_changes={"namespace": None})
    with build_runtime(config) as runtime:
        answer = AgentWeb(runtime).ask("files.read x")
    assert answer["ok"] is False
    assert "No namespace is configured" in answer["answer"]
