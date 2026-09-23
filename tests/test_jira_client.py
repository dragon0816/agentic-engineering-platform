"""The Jira client over a scripted transport; no socket, no `requests`.

Requirements: `docs/phases/PHASE_7_MIGRATION.md`, slice 3a. The cases are the
pinned Host Bridge's own, with the platform's differences: the secret is a
`SecretRef` resolved per call and the failures are typed codes.
"""

import base64
import json
from collections.abc import Iterator, Mapping
from typing import Any

import pytest
from pydantic import ValidationError

from integrations.jira import JiraClient, JiraConnection, JiraError
from models.credentials import StaticCredentials

CLOUD = "https://example-team.atlassian.net"
SERVER = "https://jira.example.internal"
TOKEN = "an-api-token-nobody-should-ever-see-in-a-message"


class Reply:
    def __init__(self, status: int, payload: Any, headers: Mapping[str, str] | None = None) -> None:
        self.status = status
        self.headers = dict(headers or {})
        self._body = (json.dumps(payload) if payload is not None else "").encode("utf-8")

    def chunks(self) -> Iterator[bytes]:
        yield self._body

    def close(self) -> None:
        return None


class ScriptedTransport:
    """Answers each request from a queue; an exception in the queue is
    raised as the transport's own failure."""

    def __init__(self, replies: list[Any]) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout_s: float,
    ) -> Reply:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "json": json.loads(body) if body else None,
                "headers": dict(headers),
            }
        )
        if not self.replies:
            raise AssertionError(f"unexpected extra request: {method} {url}")
        item = self.replies.pop(0)
        if isinstance(item, BaseException):
            raise item
        assert isinstance(item, Reply)
        return item


def page(keys: list[str], *, next_token: str | None = None, is_last: bool = False) -> Reply:
    payload: dict[str, Any] = {"issues": [{"key": key, "fields": {}} for key in keys]}
    if next_token:
        payload["nextPageToken"] = next_token
    if is_last:
        payload["isLast"] = True
    return Reply(200, payload)


def connection(**changes: Any) -> JiraConnection:
    return JiraConnection.model_validate(
        {
            "base_url": CLOUD,
            "auth_mode": "cloud",
            "email": "a@example.com",
            "credential": {"name": "jira_token"},
            **changes,
        }
    )


def cloud(replies: list[Any], **changes: Any) -> tuple[JiraClient, ScriptedTransport, list[float]]:
    transport = ScriptedTransport(replies)
    slept: list[float] = []
    client = JiraClient(
        connection(**changes),
        StaticCredentials({"jira_token": TOKEN}),
        transport=transport,
        sleep=slept.append,
    )
    return client, transport, slept


def server(replies: list[Any], **changes: Any) -> tuple[JiraClient, ScriptedTransport]:
    transport = ScriptedTransport(replies)
    client = JiraClient(
        connection(base_url=SERVER, auth_mode="server", email=None, **changes),
        StaticCredentials({"jira_token": TOKEN}),
        transport=transport,
        sleep=lambda _: None,
    )
    return client, transport


def test_the_connection_is_an_https_site_without_a_credential_in_it() -> None:
    assert connection(base_url=f"{CLOUD}/").base_url == CLOUD
    assert connection(base_url=f"{CLOUD}/rest/").base_url == CLOUD
    with pytest.raises(ValidationError, match="https origin"):
        connection(base_url="http://jira.example.internal")
    with pytest.raises(ValidationError, match="no credential"):
        connection(base_url="https://user:secret@jira.example.internal")
    with pytest.raises(ValidationError, match="account email"):
        connection(email=None)
    with pytest.raises(ValidationError):
        connection(api_token="pasted")
    assert connection(auth_mode="server", email=None).version == 2
    assert connection().version == 3
    assert connection(api_version=2).version == 2


def test_each_auth_mode_sends_its_own_header_and_holds_no_secret() -> None:
    client, transport, _ = cloud([Reply(200, {"displayName": "X"})])
    assert client.myself()["displayName"] == "X"
    sent = transport.calls[0]["headers"]["Authorization"]
    assert base64.b64decode(sent.removeprefix("Basic ")).decode() == f"a@example.com:{TOKEN}"
    (
        other,
        transport,
    ) = server([Reply(200, {"displayName": "Y"})])
    other.myself()
    assert transport.calls[0]["headers"]["Authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in repr(vars(client)) and TOKEN not in repr(vars(other))
    assert client.url("search/jql") == f"{CLOUD}/rest/api/3/search/jql"
    assert other.url("search") == f"{SERVER}/rest/api/2/search"
    assert client.url("/rest/api/2/myself") == f"{CLOUD}/rest/api/2/myself"
    assert client.url("https://x.invalid/a") == "https://x.invalid/a"
    assert client.browse_url("GTM-727") == f"{CLOUD}/browse/GTM-727"


def test_cloud_follows_the_page_token_to_the_end_under_the_cap() -> None:
    client, transport, _ = cloud(
        [page(["GTM-1", "GTM-2"], next_token="tok-2"), page(["GTM-3"], is_last=True)]
    )
    keys = [i["key"] for i in client.search_issues("project = GTM", ["summary"])]
    assert keys == ["GTM-1", "GTM-2", "GTM-3"] and len(transport.calls) == 2
    first, second = transport.calls
    assert first["method"] == "POST" and first["url"].endswith("/rest/api/3/search/jql")
    assert "nextPageToken" not in first["json"] and second["json"]["nextPageToken"] == "tok-2"
    assert first["json"]["jql"] == "project = GTM" and first["json"]["fields"] == ["summary"]
    client, transport, _ = cloud([page(["GTM-1"], is_last=True)])
    client.search_issues("project = GTM", page_size=25)
    assert transport.calls[0]["json"]["maxResults"] == 25
    assert transport.calls[0]["json"]["fields"] == ["*navigable"]
    client, transport, _ = cloud([page(["GTM-1", "GTM-2", "GTM-3"], next_token="t")])
    capped = [i["key"] for i in client.search_issues("project = GTM", max_issues=2)]
    assert capped == ["GTM-1", "GTM-2"] and len(transport.calls) == 1
    client, _, _ = cloud([page([], next_token="still-here")])
    assert client.search_issues("project = GTM") == []
    client, transport, _ = cloud([page(["GTM-1"], next_token="t", is_last=True)])
    assert len(client.search_issues("project = GTM")) == 1 and len(transport.calls) == 1
    client, transport, _ = cloud([page(["GTM-1"], next_token="t"), page(["GTM-2"], is_last=True)])
    lazy = client.iter_issues("project = GTM")
    next(lazy)
    assert len(transport.calls) == 1


def test_server_pages_by_offset_and_a_cloud_site_without_search_jql_falls_back() -> None:
    client, transport = server(
        [
            Reply(200, {"issues": [{"key": "M-1"}, {"key": "M-2"}], "total": 3}),
            Reply(200, {"issues": [{"key": "M-3"}], "total": 3}),
        ]
    )
    keys = [i["key"] for i in client.search_issues("project = M", page_size=2)]
    assert keys == ["M-1", "M-2", "M-3"]
    assert [call["json"]["startAt"] for call in transport.calls] == [0, 2]
    assert transport.calls[0]["url"].endswith("/rest/api/2/search")
    client, transport = server([Reply(200, {"issues": [{"key": "M-1"}]})])
    assert len(client.search_issues("project = M", page_size=2)) == 1
    # A Cloud site that has not got `search/jql` still works, and the
    # fall-back is remembered.
    client, transport, _ = cloud(
        [
            Reply(404, {"errorMessages": ["not found"]}),
            Reply(200, {"issues": [{"key": "GTM-1"}], "total": 1}),
            Reply(200, {"issues": [{"key": "GTM-2"}], "total": 1}),
        ]
    )
    assert [i["key"] for i in client.search_issues("a")] == ["GTM-1"]
    assert transport.calls[0]["url"].endswith("/search/jql")
    assert transport.calls[1]["url"].endswith("/rest/api/3/search")
    assert [i["key"] for i in client.search_issues("b")] == ["GTM-2"]
    assert len(transport.calls) == 3


def test_comment_threads_are_read_page_by_page() -> None:
    client, transport, _ = cloud(
        [
            Reply(200, {"comments": [{"id": "1"}, {"id": "2"}], "total": 3}),
            Reply(200, {"comments": [{"id": "3"}], "total": 3}),
        ]
    )
    assert [c["id"] for c in client.comments("GTM-1", page_size=2)] == ["1", "2", "3"]
    assert transport.calls[0]["method"] == "GET"
    assert "/rest/api/3/issue/GTM-1/comment?" in transport.calls[0]["url"]
    assert "orderBy=created" in transport.calls[0]["url"]


def test_throttles_and_transient_errors_are_waited_out_and_the_rest_are_not() -> None:
    client, _, slept = cloud([Reply(429, {}, {"Retry-After": "2"}), page(["GTM-1"], is_last=True)])
    assert len(client.search_issues("project = GTM")) == 1
    assert slept == [2.0]
    for status in (500, 502, 503, 504):
        client, _, slept = cloud([Reply(status, {}), page(["GTM-1"], is_last=True)])
        assert len(client.search_issues("project = GTM")) == 1 and slept == [1.0]
    client, transport, _ = cloud([Reply(503, {}) for _ in range(3)], max_retries=2)
    with pytest.raises(JiraError, match="503") as gave_up:
        client.request("GET", "myself")
    assert gave_up.value.code == "jira_unavailable" and len(transport.calls) == 3
    client, _, _ = cloud([ConnectionError("dns"), Reply(200, {"displayName": "X"})])
    assert client.myself()["displayName"] == "X"
    client, _, _ = cloud([ConnectionError("dns")] * 3, max_retries=2)
    with pytest.raises(JiraError, match="failed after 3 attempt") as dead:
        client.myself()
    assert dead.value.code == "jira_unavailable"
    client, transport, _ = cloud([Reply(400, {"errorMessages": ["bad jql"]})])
    with pytest.raises(JiraError, match="400") as bad:
        client.request("GET", "myself")
    assert bad.value.code == "jira_http" and len(transport.calls) == 1
    client, _, _ = cloud([Reply(200, None)])
    assert client.request("GET", "myself") is None


def test_a_rejected_credential_is_a_refusal_of_its_own_kind() -> None:
    for status in (401, 403):
        client, transport, _ = cloud([Reply(status, {"message": "nope"})])
        with pytest.raises(JiraError) as refused:
            client.myself()
        assert refused.value.code == "jira_auth" and refused.value.status == status
        assert len(transport.calls) == 1
        assert TOKEN not in str(refused.value)
    # A secret the host cannot produce is its own answer, before any call.
    client = JiraClient(
        connection(), StaticCredentials({}), transport=ScriptedTransport([]), sleep=lambda _: None
    )
    with pytest.raises(JiraError) as missing:
        client.myself()
    assert missing.value.code == "jira_credential"


def test_no_failure_carries_the_secret() -> None:
    client, _, _ = cloud([Reply(400, {"errorMessages": [f"token {TOKEN} rejected"]})])
    with pytest.raises(JiraError) as error:
        client.myself()
    assert TOKEN not in str(error.value)
