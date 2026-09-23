"""A GitHub Projects client over the platform's transport.

Jira was switched off and the team's project information moved to a GitHub
Projects board whose items are issues in a private repository
(`docs/PHASE_7_MIGRATION.md`, "Workflow 11, second source"). This reads that
board: each item's field values, and the comments on the issue behind it.

Two permissions, not one. Reading the board needs project access and reading
the issues needs repository access, and GitHub does not say so when only one
is granted: an item whose issue the token may not see comes back with its
content simply missing, no error anywhere. That silence would read as a week
in which nobody wrote anything, so it is a refusal here
(`github_issue_unreadable`).

As with the Jira client it replaces: the secret is a `SecretRef` resolved on
every call and held nowhere on this object, there is no session and no
configuration file with a token in it, and every failure is an error with a
code and a redacted message.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any, Literal

from pydantic import Field

from common.assets import SecretRef
from common.base import Contract, Text
from models.credentials import CredentialMisconfigured, CredentialResolver
from models.wire import MethodTransport, UrllibTransport, close_quietly, describe, redacted

GitHubErrorCode = Literal[
    "github_credential",
    "github_auth",
    "github_http",
    "github_unavailable",
    "github_bad_reply",
    "github_scope_missing",
    "github_not_found",
    "github_rate_limited",
    "github_project_missing",
    "github_issue_unreadable",
]

#: What GitHub calls a refusal, and what this platform calls it. GraphQL
#: answers a query it would not run with `200` and a typed error, so the
#: kind is in the body and a status code says nothing. Naming each one is
#: the difference between "the reply was bad" and "this token has no project
#: access", which is the only form of it an operator can act on.
REFUSAL_CODES: Mapping[str, GitHubErrorCode] = {
    "INSUFFICIENT_SCOPES": "github_scope_missing",
    "FORBIDDEN": "github_auth",
    "NOT_FOUND": "github_not_found",
    "RATE_LIMITED": "github_rate_limited",
}

DEFAULT_API_URL = "https://api.github.com/graphql"
#: GitHub's own maximum for a connection page.
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
#: A throttle is waited out, not obeyed without limit.
MAX_RETRY_AFTER_SECONDS = 60.0


class GitHubError(Exception):
    """Why a call did not produce an answer. `github_auth` is the one a
    person has to act on; `github_unavailable` is the one worth trying
    later; `github_issue_unreadable` means the token reads the board but not
    what is on it."""

    def __init__(self, code: GitHubErrorCode, message: str, *, status: int | None = None) -> None:
        self.code: GitHubErrorCode = code
        self.status = status
        super().__init__(redacted(message))


class GitHubProjectConnection(Contract):
    """Which board to read, and the name of the secret that opens it. The
    value of the secret is never here."""

    owner: Text
    project_number: int = Field(ge=1, strict=True)
    #: A user's project or an organization's. The two are different queries
    #: and nothing in the number says which.
    owner_kind: Literal["user", "organization"] = "user"
    api_url: Text = DEFAULT_API_URL
    credential: SecretRef
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, strict=True)
    #: How many comments to read per issue. The report reads the whole
    #: thread; a thread longer than this is reported rather than truncated
    #: in silence.
    comment_page_size: int = Field(default=MAX_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, strict=True)
    timeout_s: float = Field(default=30.0, gt=0)


class ProjectItem(Contract):
    """One row of the board as this client reads it."""

    #: The board's own identifier for the row, which is not the issue's.
    item_id: Text
    #: `owner/repo#number`, or nothing for a row that is not an issue.
    key: str = ""
    title: str = ""
    url: str = ""
    state: str = ""
    updated: str = ""
    fields: Mapping[str, str] = {}
    comments: tuple[ProjectComment, ...] = ()
    #: True when the thread was longer than this client asked for.
    comments_truncated: bool = False


class ProjectComment(Contract):
    created: str = ""
    author: str = ""
    body: str = ""


ProjectItem.model_rebuild()


_ITEMS_QUERY = """
query($owner: String!, $number: Int!, $size: Int!, $comments: Int!, $after: String) {
  %(root)s(login: $owner) {
    projectV2(number: $number) {
      title
      items(first: $size, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          type
          fieldValues(first: 50) {
            nodes {
              __typename
              ... on ProjectV2ItemFieldTextValue {
                text
                field { ... on ProjectV2FieldCommon { name } }
              }
              ... on ProjectV2ItemFieldNumberValue {
                number
                field { ... on ProjectV2FieldCommon { name } }
              }
              ... on ProjectV2ItemFieldDateValue {
                date
                field { ... on ProjectV2FieldCommon { name } }
              }
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2FieldCommon { name } }
              }
            }
          }
          content {
            __typename
            ... on Issue {
              number
              title
              url
              state
              updatedAt
              repository { nameWithOwner }
              comments(first: $comments) {
                totalCount
                nodes { createdAt author { login } body }
              }
            }
          }
        }
      }
    }
  }
}
"""


def _query_for(owner_kind: str) -> str:
    return _ITEMS_QUERY % {"root": "user" if owner_kind == "user" else "organization"}


class GitHubProjectClient:
    """One board, one credential, every call resolved fresh."""

    def __init__(
        self,
        connection: GitHubProjectConnection,
        resolver: CredentialResolver,
        *,
        transport: MethodTransport | None = None,
        sleep: Callable[[float], None] | None = None,
        backoff_seconds: float = 1.0,
    ) -> None:
        self.connection = GitHubProjectConnection.model_validate(connection)
        self._resolver = resolver
        self._transport = transport or UrllibTransport()
        self._sleep = sleep or _no_sleep
        self._backoff = backoff_seconds

    # -- the wire ------------------------------------------------------

    def _token(self) -> str:
        try:
            return self._resolver.resolve(self.connection.credential)
        except CredentialMisconfigured as missing:
            raise GitHubError("github_credential", str(missing)) from None

    def post(self, query: str, variables: Mapping[str, Any]) -> dict[str, Any]:
        """One GraphQL call, with the retries a shared API needs.

        GitHub answers a query it partly refused with 200 and an `errors`
        block, so a status code is not the whole answer and the body is read
        either way.
        """
        body = json.dumps({"query": query, "variables": dict(variables)}).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._token()}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
        }
        attempt = 0
        while True:
            attempt += 1
            reply = None
            try:
                reply = self._transport.request(
                    "POST", self.connection.api_url, body, headers, self.connection.timeout_s
                )
                status = int(reply.status)
                text = b"".join(reply.chunks()).decode("utf-8", "replace")
                retry_after = _retry_after(reply)
            except Exception as failure:  # noqa: BLE001 - whatever a transport raises
                if attempt <= 3:
                    self._sleep(self._backoff * attempt)
                    continue
                raise GitHubError("github_unavailable", describe(failure)) from None
            finally:
                if reply is not None:
                    close_quietly(reply)

            if status in (401, 403):
                raise GitHubError(
                    "github_auth", f"GitHub refused the credential ({status})", status=status
                )
            if status in RETRY_STATUSES and attempt <= 3:
                self._sleep(_bounded(retry_after, self._backoff * attempt))
                continue
            if status >= 400:
                raise GitHubError("github_http", f"GitHub answered {status}", status=status)
            try:
                payload = json.loads(text)
            except ValueError:
                raise GitHubError("github_bad_reply", "GitHub's answer was not JSON") from None
            if not isinstance(payload, dict):
                raise GitHubError("github_bad_reply", "GitHub's answer was not an object")
            errors = payload.get("errors")
            if errors:
                code, message = _refusal(errors)
                raise GitHubError(code, message)
            data = payload.get("data")
            if not isinstance(data, dict):
                raise GitHubError("github_bad_reply", "GitHub's answer carried no data")
            return data

    # -- the board -----------------------------------------------------

    def items(self, *, max_items: int | None = None) -> list[ProjectItem]:
        """Every row of the board, following its pages."""
        return list(self.iter_items(max_items=max_items))

    def iter_items(self, *, max_items: int | None = None) -> Iterator[ProjectItem]:
        query = _query_for(self.connection.owner_kind)
        cursor: str | None = None
        seen = 0
        while True:
            data = self.post(
                query,
                {
                    "owner": self.connection.owner,
                    "number": self.connection.project_number,
                    "size": self.connection.page_size,
                    "comments": self.connection.comment_page_size,
                    "after": cursor,
                },
            )
            root = data.get("user") or data.get("organization") or {}
            project = (root or {}).get("projectV2")
            if not isinstance(project, dict):
                raise GitHubError(
                    "github_project_missing",
                    f"no project number {self.connection.project_number} for this owner",
                )
            connection = project.get("items") or {}
            for node in connection.get("nodes") or []:
                if not isinstance(node, dict):
                    continue
                yield _item(node)
                seen += 1
                if max_items is not None and seen >= max_items:
                    return
            page = connection.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                return
            cursor = page.get("endCursor")
            if not cursor:
                return


def _item(node: Mapping[str, Any]) -> ProjectItem:
    fields: dict[str, str] = {}
    for value in (node.get("fieldValues") or {}).get("nodes") or []:
        if not isinstance(value, Mapping):
            continue
        name = ((value.get("field") or {}) or {}).get("name")
        if not name:
            continue
        for key in ("text", "name", "date", "number"):
            if value.get(key) is not None:
                fields[str(name)] = str(value[key])
                break

    content = node.get("content")
    item_id = str(node.get("id") or "")
    if node.get("type") == "ISSUE" and not isinstance(content, Mapping):
        # GitHub hides what the token may not read rather than refusing, and
        # an item with no content reads exactly like an item with nothing to
        # say. The report would then be a week in which nobody wrote
        # anything, which is why this is loud.
        raise GitHubError(
            "github_issue_unreadable",
            "the token reads this board but not the issues on it; "
            "it needs repository access as well as project access",
        )
    if not isinstance(content, Mapping):
        return ProjectItem(item_id=item_id, fields=fields)

    thread = content.get("comments") or {}
    nodes = thread.get("nodes") or []
    comments = tuple(
        ProjectComment(
            created=str(entry.get("createdAt") or ""),
            author=str(((entry.get("author") or {}) or {}).get("login") or ""),
            body=str(entry.get("body") or ""),
        )
        for entry in nodes
        if isinstance(entry, Mapping)
    )
    repository = ((content.get("repository") or {}) or {}).get("nameWithOwner") or ""
    number = content.get("number")
    return ProjectItem(
        item_id=item_id,
        key=f"{repository}#{number}" if repository and number is not None else "",
        title=str(content.get("title") or ""),
        url=str(content.get("url") or ""),
        state=str(content.get("state") or ""),
        updated=str(content.get("updatedAt") or ""),
        fields=fields,
        comments=comments,
        comments_truncated=int(thread.get("totalCount") or 0) > len(comments),
    )


def _refusal(errors: Sequence[Any]) -> tuple[GitHubErrorCode, str]:
    """The first error GitHub named, as a code this platform uses.

    GitHub's own words are kept in the message, which the host logs and
    never sends onward; the code is what travels, so it has to carry the
    meaning by itself.
    """
    for error in errors:
        if not isinstance(error, Mapping):
            continue
        kind = str(error.get("type") or "")
        message = str(error.get("message") or "") or "GitHub refused the query"
        if kind in REFUSAL_CODES:
            return REFUSAL_CODES[kind], message
        if message:
            return "github_bad_reply", message
    return "github_bad_reply", "GitHub refused the query"


def _retry_after(reply: Any) -> float | None:
    """`Retry-After`, if this transport carries headers at all. The reply
    protocol does not promise them, so asking is optional."""
    headers = getattr(reply, "headers", None)
    if not isinstance(headers, Mapping):
        return None
    value = headers.get("Retry-After") or headers.get("retry-after")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _bounded(seconds: float | None, fallback: float) -> float:
    """A throttle is waited out, not obeyed without limit: one header must
    not park a run for an hour past every timeout above it."""
    if seconds is None:
        return fallback
    return max(0.0, min(seconds, MAX_RETRY_AFTER_SECONDS))


def _no_sleep(_seconds: float) -> None:
    return None
