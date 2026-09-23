"""The GitHub Projects client over a scripted transport; no socket.

Requirements: `docs/phases/PHASE_7_MIGRATION.md`, slice 5. The replies have
the shape the real board answered with on 2026-09-23, and none of its
content: this repository is public, and the board names customers and
colleagues. What is reproduced is the structure, including the one thing that
structure does badly, which is to omit what the token may not read instead of
saying so.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from typing import Any

import pytest

from common.assets import SecretRef
from integrations.github_project import (
    GitHubError,
    GitHubProjectClient,
    GitHubProjectConnection,
)
from models.credentials import StaticCredentials

TOKEN = "a-token-nobody-should-ever-see-in-a-message"
SECRET = SecretRef(name="github_token")


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
                "body": json.loads(body) if body else None,
                "headers": dict(headers),
            }
        )
        if not self.replies:
            raise AssertionError("the client asked for more than the test scripted")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        assert isinstance(reply, Reply)
        return reply


def client(transport: ScriptedTransport, **overrides: Any) -> GitHubProjectClient:
    settings: dict[str, Any] = {
        "owner": "an-owner",
        "project_number": 1,
        "credential": SECRET,
    }
    settings.update(overrides)
    return GitHubProjectClient(
        GitHubProjectConnection(**settings),
        StaticCredentials({"github_token": TOKEN}),
        transport=transport,
        sleep=lambda _seconds: None,
        backoff_seconds=0.0,
    )


def item(
    number: int, *, comments: list[dict[str, Any]] | None = None, total: int | None = None
) -> dict[str, Any]:
    thread = comments if comments is not None else []
    return {
        "id": f"PVTI_{number}",
        "type": "ISSUE",
        "fieldValues": {
            "nodes": [
                {
                    "__typename": "ProjectV2ItemFieldTextValue",
                    "text": f"[KEY-{number}] a title",
                    "field": {"name": "Title"},
                },
                {
                    "__typename": "ProjectV2ItemFieldSingleSelectValue",
                    "name": "In Progress",
                    "field": {"name": "Status"},
                },
                {
                    "__typename": "ProjectV2ItemFieldTextValue",
                    "text": "A Company",
                    "field": {"name": "Company"},
                },
                {
                    "__typename": "ProjectV2ItemFieldTextValue",
                    "text": "An Engineer",
                    "field": {"name": "SDE Assignee"},
                },
                {
                    "__typename": "ProjectV2ItemFieldDateValue",
                    "date": "2026-09-17",
                    "field": {"name": "GTM Create date"},
                },
                {
                    "__typename": "ProjectV2ItemFieldNumberValue",
                    "number": 3,
                    "field": {"name": "A Number"},
                },
                {"__typename": "ProjectV2ItemFieldTextValue", "text": "ignored", "field": None},
            ]
        },
        "content": {
            "__typename": "Issue",
            "number": number,
            "title": f"[KEY-{number}] a title",
            "url": f"https://github.com/an-owner/a-repo/issues/{number}",
            "state": "OPEN",
            "updatedAt": "2026-09-23T07:48:31Z",
            "repository": {"nameWithOwner": "an-owner/a-repo"},
            "comments": {
                "totalCount": total if total is not None else len(thread),
                "nodes": thread,
            },
        },
    }


def page(nodes: list[dict[str, Any]], *, cursor: str | None = None) -> Reply:
    return Reply(
        200,
        {
            "data": {
                "user": {
                    "projectV2": {
                        "title": "a board",
                        "items": {
                            "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor},
                            "nodes": nodes,
                        },
                    }
                }
            }
        },
    )


def test_a_board_row_carries_its_fields_its_issue_and_its_thread() -> None:
    comment = {
        "createdAt": "2026-09-23T07:48:31Z",
        "author": {"login": "an-author"},
        "body": "\n[Completed]\n1. the first thing\n2. the second thing\n",
    }
    transport = ScriptedTransport([page([item(4, comments=[comment])])])
    rows = client(transport).items()
    assert len(rows) == 1
    row = rows[0]
    assert row.key == "an-owner/a-repo#4"
    assert row.title == "[KEY-4] a title"
    assert row.updated == "2026-09-23T07:48:31Z"
    assert row.fields["Company"] == "A Company"
    assert row.fields["Status"] == "In Progress", "a single-select reads by its name"
    assert row.fields["GTM Create date"] == "2026-09-17", "a date reads as the date"
    assert row.fields["A Number"] == "3", "a number reads as its text"
    assert "ignored" not in row.fields.values(), "a value whose field has no name is not a field"
    assert [c.author for c in row.comments] == ["an-author"]
    assert "[Completed]" in row.comments[0].body
    assert row.comments_truncated is False


def test_a_thread_longer_than_this_client_asked_for_says_so() -> None:
    """Truncating a week's notes in silence would report a week that did not
    happen."""
    transport = ScriptedTransport([page([item(4, comments=[], total=7)])])
    assert client(transport).items()[0].comments_truncated is True


def test_an_issue_the_token_may_not_read_is_a_refusal_not_an_empty_week() -> None:
    """The board and the issues on it are two permissions. GitHub answers a
    token that has only the first with the item present and its content
    simply absent, and no error anywhere: every row would arrive with no
    title and no comments, which reads exactly like a week in which nobody
    wrote anything."""
    hidden = item(4)
    hidden["content"] = None
    transport = ScriptedTransport([page([hidden])])
    with pytest.raises(GitHubError) as refused:
        client(transport).items()
    assert refused.value.code == "github_issue_unreadable"
    assert "repository access" in str(refused.value)


def test_every_page_is_followed() -> None:
    transport = ScriptedTransport([page([item(1)], cursor="CURSOR"), page([item(2)])])
    rows = client(transport).items()
    assert [row.key for row in rows] == ["an-owner/a-repo#1", "an-owner/a-repo#2"]
    assert transport.calls[1]["body"]["variables"]["after"] == "CURSOR"


def test_a_cap_stops_reading_pages() -> None:
    transport = ScriptedTransport([page([item(1), item(2)], cursor="CURSOR")])
    assert len(client(transport).items(max_items=1)) == 1
    assert len(transport.calls) == 1, "the second page is never asked for"


def test_the_secret_is_resolved_per_call_and_never_stored() -> None:
    transport = ScriptedTransport([page([item(1)])])
    reader = client(transport)
    assert TOKEN not in json.dumps(reader.connection.model_dump(mode="json"))
    reader.items()
    assert transport.calls[0]["headers"]["Authorization"] == f"Bearer {TOKEN}"


def test_a_refused_credential_is_its_own_kind_of_failure() -> None:
    for status in (401, 403):
        transport = ScriptedTransport([Reply(status, {"message": "Bad credentials"})])
        with pytest.raises(GitHubError) as refused:
            client(transport).items()
        assert refused.value.code == "github_auth"
        assert refused.value.status == status


def test_a_throttle_is_waited_out_and_then_answered() -> None:
    waited: list[float] = []
    transport = ScriptedTransport(
        [Reply(429, {"message": "slow down"}, {"Retry-After": "2"}), page([item(1)])]
    )
    reader = GitHubProjectClient(
        GitHubProjectConnection(owner="an-owner", project_number=1, credential=SECRET),
        StaticCredentials({"github_token": TOKEN}),
        transport=transport,
        sleep=waited.append,
        backoff_seconds=0.0,
    )
    assert len(reader.items()) == 1
    assert waited == [2.0], "the header is honoured"


def test_a_throttle_that_asks_for_an_hour_is_bounded() -> None:
    waited: list[float] = []
    transport = ScriptedTransport([Reply(503, None, {"Retry-After": "3600"}), page([item(1)])])
    reader = GitHubProjectClient(
        GitHubProjectConnection(owner="an-owner", project_number=1, credential=SECRET),
        StaticCredentials({"github_token": TOKEN}),
        transport=transport,
        sleep=waited.append,
        backoff_seconds=0.0,
    )
    reader.items()
    assert waited == [60.0], "one header must not park a run past every timeout above it"


@pytest.mark.parametrize(
    "kind, expected",
    [
        ("INSUFFICIENT_SCOPES", "github_scope_missing"),
        ("FORBIDDEN", "github_auth"),
        ("NOT_FOUND", "github_not_found"),
        ("RATE_LIMITED", "github_rate_limited"),
        ("SOMETHING_NEW", "github_bad_reply"),
    ],
)
def test_a_query_github_refused_is_named_from_the_body_not_the_status(
    kind: str, expected: str
) -> None:
    """GitHub answers a query it would not run with 200 and a typed error, so
    a status code says nothing. Only the code travels to whoever asked, so it
    has to carry the meaning: "the reply was bad" and "this token has no
    project access" are the same sentence otherwise, and only one of them
    tells somebody what to do."""
    transport = ScriptedTransport(
        [Reply(200, {"data": None, "errors": [{"type": kind, "message": "GitHub said why"}]})]
    )
    with pytest.raises(GitHubError) as refused:
        client(transport).items()
    assert refused.value.code == expected
    assert "GitHub said why" in str(refused.value), "its own words stay in the message"


def test_an_error_with_no_type_is_still_an_answer() -> None:
    transport = ScriptedTransport(
        [Reply(200, {"data": None, "errors": [{"message": "something went wrong"}]})]
    )
    with pytest.raises(GitHubError) as refused:
        client(transport).items()
    assert refused.value.code == "github_bad_reply"


def test_a_board_that_is_not_there_says_which_number() -> None:
    transport = ScriptedTransport([Reply(200, {"data": {"user": {"projectV2": None}}})])
    with pytest.raises(GitHubError) as refused:
        client(transport, project_number=9).items()
    assert refused.value.code == "github_project_missing"
    assert "9" in str(refused.value)


def test_an_organizations_board_is_a_different_query() -> None:
    transport = ScriptedTransport(
        [
            Reply(
                200,
                {
                    "data": {
                        "organization": {
                            "projectV2": {
                                "title": "a board",
                                "items": {
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    "nodes": [item(1)],
                                },
                            }
                        }
                    }
                },
            )
        ]
    )
    reader = client(transport, owner_kind="organization")
    assert len(reader.items()) == 1
    assert "organization(login:" in transport.calls[0]["body"]["query"].replace(" ", "")


def test_an_answer_that_is_not_json_is_refused() -> None:
    class Broken(Reply):
        def chunks(self) -> Iterator[bytes]:
            yield b"<html>a proxy said no</html>"

    transport = ScriptedTransport([Broken(200, None)])
    with pytest.raises(GitHubError) as refused:
        client(transport).items()
    assert refused.value.code == "github_bad_reply"


def test_a_transport_that_keeps_failing_is_unavailable_not_a_crash() -> None:
    transport = ScriptedTransport([OSError("the network went away")] * 4)
    with pytest.raises(GitHubError) as refused:
        client(transport).items()
    assert refused.value.code == "github_unavailable"


def test_a_credential_the_host_cannot_resolve_says_so() -> None:
    transport = ScriptedTransport([page([item(1)])])
    reader = GitHubProjectClient(
        GitHubProjectConnection(owner="an-owner", project_number=1, credential=SECRET),
        StaticCredentials({}),
        transport=transport,
    )
    with pytest.raises(GitHubError) as refused:
        reader.items()
    assert refused.value.code == "github_credential"
    assert transport.calls == [], "nothing is sent without a credential"
