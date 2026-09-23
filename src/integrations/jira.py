"""A Jira REST client over the platform's transport.

Ported from the pinned Host Bridge's `_jira_client` (`docs/PHASE_7_MIGRATION.md`,
"Workflow 7"): Basic `email:token` for Cloud and Bearer for Server, token-paged
`POST search/jql` on Cloud with a remembered fall-back to offset paging where
a site lacks it, offset-paged `POST search` otherwise, comment threads read
page by page, bounded retries on throttles and transient 5xx honouring
`Retry-After`, and 401/403 a refusal of its own kind.

What is deliberately different: the secret is a `SecretRef` resolved through
the host's `CredentialResolver` on every call and held nowhere on this
object; there is no session, no `requests`, and no configuration file with a
placeholder token in it. Every failure is a `JiraError` with a code and a
redacted message; nothing here raises a transport exception at a caller.
"""

import base64
import json
from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
from typing import Any, Literal, Self
from urllib.parse import urlencode, urlsplit

from pydantic import Field, field_validator, model_validator

from common.assets import SecretRef, reject_embedded_secrets
from common.base import Contract, Text
from models.credentials import CredentialMisconfigured, CredentialResolver
from models.wire import MethodTransport, UrllibTransport, close_quietly, describe, redacted

AuthMode = Literal["cloud", "server"]
JiraErrorCode = Literal[
    "jira_credential",
    "jira_auth",
    "jira_http",
    "jira_unavailable",
    "jira_bad_reply",
]

DEFAULT_PAGE_SIZE = 100
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
# A throttle is waited out, not obeyed without limit: one header must not
# park the worker for an hour past every timeout above it.
MAX_RETRY_AFTER_SECONDS = 60.0
# A site without `search/jql` answers one of these to the probe.
FALLBACK_STATUSES = frozenset({404, 410})


class JiraError(Exception):
    """Why a Jira call did not produce an answer. `jira_auth` is the one a
    person has to act on; `jira_unavailable` is the one worth trying later."""

    def __init__(self, code: JiraErrorCode, message: str, *, status: int | None = None) -> None:
        self.code: JiraErrorCode = code
        self.status = status
        super().__init__(redacted(message))


class JiraConnection(Contract):
    """How a host reaches its Jira site, without the secret. Cloud needs the
    account email beside the API token; Server needs only the token."""

    base_url: Text
    auth_mode: AuthMode = "cloud"
    email: Text | None = None
    credential: SecretRef
    api_version: int | None = Field(default=None, ge=1, le=3, strict=True)
    timeout_seconds: int = Field(default=60, ge=1, le=600, strict=True)
    max_retries: int = Field(default=4, ge=0, le=8, strict=True)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=100, strict=True)

    @field_validator("base_url")
    @classmethod
    def site_root(cls, value: str) -> str:
        """Trailing slashes and a trailing `/rest` are tolerated, as the
        source tolerated them."""
        return value.strip().rstrip("/").removesuffix("/rest").rstrip("/")

    @model_validator(mode="after")
    def complete_and_secret_free(self) -> Self:
        parts = urlsplit(self.base_url)
        if parts.scheme != "https" or not parts.hostname or parts.query or parts.fragment:
            raise ValueError("base_url is the https origin of the Jira site")
        if parts.username is not None or parts.password is not None:
            raise ValueError("base_url carries no credential; the token is a SecretRef")
        if self.auth_mode == "cloud" and not self.email:
            raise ValueError("Jira Cloud authenticates with an account email and an API token")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self

    @property
    def version(self) -> int:
        return self.api_version or (3 if self.auth_mode == "cloud" else 2)


class JiraClient:
    """One site, one credential, every call resolved fresh."""

    def __init__(
        self,
        connection: JiraConnection,
        resolver: CredentialResolver,
        *,
        transport: MethodTransport | None = None,
        sleep: Callable[[float], None] | None = None,
        backoff_seconds: float = 1.0,
    ) -> None:
        self.connection = JiraConnection.model_validate(connection)
        self._resolver = resolver
        self._transport = transport if transport is not None else UrllibTransport()
        self._sleep = sleep if sleep is not None else _sleep
        self._backoff = backoff_seconds
        # Set once the site has said which search endpoint it supports.
        self._search_style: Literal["token", "offset"] | None = None

    # -- construction ---------------------------------------------------

    def _authorization(self) -> str:
        try:
            secret = self._resolver.resolve(self.connection.credential)
        except CredentialMisconfigured as error:
            raise JiraError("jira_credential", describe(error)) from None
        except Exception as error:  # noqa: BLE001 - a store's failure is a status here
            raise JiraError("jira_unavailable", describe(error)) from None
        if self.connection.auth_mode == "cloud":
            raw = f"{self.connection.email}:{secret}".encode()
            return "Basic " + base64.b64encode(raw).decode("ascii")
        return f"Bearer {secret}"

    def url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        if path.startswith("/rest/"):
            return f"{self.connection.base_url}{path}"
        return f"{self.connection.base_url}/rest/api/{self.connection.version}/{path.lstrip('/')}"

    def browse_url(self, key: str) -> str:
        return f"{self.connection.base_url}/browse/{key}"

    # -- transport ------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        allow_status: Collection[int] = (),
    ) -> Any:
        """One Jira call, retrying throttles and transient 5xx with a doubling
        delay that honours `Retry-After`. `allow_status` lets a caller treat
        specific error codes as "no answer" (the search-endpoint probe)."""
        target = self.url(path)
        if params:
            target = f"{target}?{urlencode(dict(params))}"
        allowed = set(allow_status)
        payload = json.dumps(dict(body)).encode("utf-8") if body is not None else None
        attempts = self.connection.max_retries + 1
        last: str = ""
        for attempt in range(attempts):
            headers = {
                "Authorization": self._authorization(),
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            try:
                reply = self._transport.request(
                    method, target, payload, headers, float(self.connection.timeout_seconds)
                )
            except Exception as error:  # noqa: BLE001 - every transport fault is one answer
                last = describe(error)
                if attempt + 1 >= attempts:
                    raise JiraError(
                        "jira_unavailable",
                        f"{method} {target} failed after {attempts} attempt(s): {last}",
                    ) from None
                self._sleep(self._delay(attempt, None))
                continue
            try:
                raw = b"".join(reply.chunks())
            except Exception as error:  # noqa: BLE001 - a body cut short
                last = describe(error)
                if attempt + 1 >= attempts:
                    raise JiraError("jira_unavailable", last) from None
                self._sleep(self._delay(attempt, None))
                continue
            finally:
                close_quietly(reply)
            status = reply.status
            if status in (401, 403):
                which = "email and API token" if self.connection.auth_mode == "cloud" else "token"
                raise JiraError(
                    "jira_auth",
                    f"Jira rejected the credentials ({status}); check the {which} and that the "
                    "account can browse the project",
                    status=status,
                )
            if status in allowed:
                return None
            if status in RETRY_STATUSES and attempt + 1 < attempts:
                self._sleep(self._delay(attempt, _retry_after(reply)))
                continue
            if status >= 500 or status == 429:
                raise JiraError(
                    "jira_unavailable",
                    f"Jira {method} {path} returned {status} after {attempt + 1} attempt(s)",
                    status=status,
                )
            if status >= 400:
                # The body is not echoed: Jira quotes the request back in its
                # error messages, and the request carried the credential.
                raise JiraError(
                    "jira_http", f"Jira {method} {path} returned {status}", status=status
                )
            if status == 204:
                return None
            if not raw:
                # An answer with nothing in it is not an answer: a proxy or
                # a hiccup, never a site saying it lacks an endpoint.
                raise JiraError("jira_bad_reply", f"Jira {method} {path} returned an empty body")
            try:
                return json.loads(raw)
            except ValueError:
                raise JiraError(
                    "jira_bad_reply", f"Jira {method} {path} returned a body that is not JSON"
                ) from None
        raise JiraError("jira_unavailable", f"{method} {path} exhausted retries: {last}")

    def _delay(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return min(max(retry_after, 0.0), MAX_RETRY_AFTER_SECONDS)
        return float(self._backoff * (2**attempt))

    # -- search ---------------------------------------------------------

    def search_issues(
        self,
        jql: str,
        fields: Sequence[str] | None = None,
        *,
        page_size: int | None = None,
        max_issues: int | None = None,
    ) -> list[dict[str, Any]]:
        """Every issue matching the JQL, all pages, under the cap."""
        return list(self.iter_issues(jql, fields, page_size=page_size, max_issues=max_issues))

    def iter_issues(
        self,
        jql: str,
        fields: Sequence[str] | None = None,
        *,
        page_size: int | None = None,
        max_issues: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Issues page by page, so a big result never sits in memory twice."""
        field_list = list(fields) if fields else ["*navigable"]
        size = page_size or self.connection.page_size
        style = self._search_style or (
            "token" if self.connection.auth_mode == "cloud" else "offset"
        )
        if style == "token":
            probe = self.request(
                "POST",
                "search/jql",
                body={"jql": jql, "fields": field_list, "maxResults": size},
                allow_status=FALLBACK_STATUSES,
            )
            if probe is None:
                # This site has not got `search/jql`; remember that.
                self._search_style = "offset"
                yield from self._offset_paged(jql, field_list, size, max_issues)
                return
            self._search_style = "token"
            yield from self._token_paged(jql, field_list, size, max_issues, first=probe)
            return
        yield from self._offset_paged(jql, field_list, size, max_issues)

    def _token_paged(
        self,
        jql: str,
        fields: list[str],
        page_size: int,
        max_issues: int | None,
        *,
        first: Any,
    ) -> Iterator[dict[str, Any]]:
        """Cloud: `POST search/jql` with `nextPageToken`."""
        payload = first
        seen = 0
        while True:
            page = payload if isinstance(payload, dict) else {}
            issues = page.get("issues") or []
            for issue in issues:
                if isinstance(issue, dict):
                    yield issue
                    seen += 1
                    if max_issues is not None and seen >= max_issues:
                        return
            token = page.get("nextPageToken")
            if page.get("isLast") or not token or not issues:
                return
            payload = self.request(
                "POST",
                "search/jql",
                body={
                    "jql": jql,
                    "fields": fields,
                    "maxResults": page_size,
                    "nextPageToken": token,
                },
            )

    def _offset_paged(
        self, jql: str, fields: list[str], page_size: int, max_issues: int | None
    ) -> Iterator[dict[str, Any]]:
        """Server, and a Cloud site without `search/jql`: `POST search` with
        `startAt`."""
        start_at = 0
        seen = 0
        while True:
            payload = self.request(
                "POST",
                "search",
                body={"jql": jql, "fields": fields, "maxResults": page_size, "startAt": start_at},
            )
            page = payload if isinstance(payload, dict) else {}
            issues = page.get("issues") or []
            if not issues:
                return
            for issue in issues:
                if isinstance(issue, dict):
                    yield issue
                    seen += 1
                    if max_issues is not None and seen >= max_issues:
                        return
            start_at += len(issues)
            total = page.get("total")
            if total is not None:
                # The site says how many there are; a page shorter than asked
                # for is the site's own cap, not the end.
                if start_at >= int(total):
                    return
            elif len(issues) < page_size:
                return

    # -- single issue ---------------------------------------------------

    def comments(self, key: str, *, page_size: int | None = None) -> list[dict[str, Any]]:
        """All comments on an issue, oldest first, following pagination. The
        search endpoint caps embedded comments, so the report asks here
        whenever an issue looks like it has more than the search handed back."""
        size = page_size or self.connection.page_size
        out: list[dict[str, Any]] = []
        start_at = 0
        while True:
            payload = self.request(
                "GET",
                f"issue/{key}/comment",
                params={"startAt": start_at, "maxResults": size, "orderBy": "created"},
            )
            page = payload if isinstance(payload, dict) else {}
            batch = [item for item in page.get("comments") or [] if isinstance(item, dict)]
            out.extend(batch)
            if not batch:
                break
            start_at += len(batch)
            total = page.get("total")
            if total is not None:
                if start_at >= int(total):
                    break
            elif len(batch) < size:
                break
        return out

    def myself(self) -> dict[str, Any]:
        payload = self.request("GET", "myself")
        return payload if isinstance(payload, dict) else {}


def _retry_after(reply: Any) -> float | None:
    headers = getattr(reply, "headers", None)
    if not isinstance(headers, Mapping):
        return None
    value = headers.get("Retry-After") or headers.get("retry-after")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)
