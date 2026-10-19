"""The Personal Agent code from Agent Web, and its automatic renewal (owner
2026-10-19, "Option A"; `docs/phases/PASSWORD_SIGN_IN.md`).

Getting a code: the person types their platform account and password in
Settings → Shared platform. The Host signs in once (`sign-in/password`), asks
for a code with that session (`logins/issue-agent`), stores the code exactly as
the paste path does (this Windows user's environment), revokes the browser
login the sign-in created, and drops the session. The password is used in one
request and kept nowhere: not in a file, the environment, a log, the task list,
a telemetry event, a reply or a conversation.

Renewal: when the code has under `RENEW_BEFORE` left, the Host uses a session
from the still-valid code to get a new one, stores it and revokes the old one
(`logins/revoke`). A platform without that route answers `invalid_request`; the
new code is kept anyway and the old one simply expires (noted without the
secret).

What is recorded (`personal-agent-code.json` in the workspace): the code's
`login_id`, `expires_at`, where it came from and how often it was renewed.
Never the secret.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import AwareDatetime, Field, ValidationError

from common.base import Contract, Symbol, Text
from host_runtime.shared_platform import LOGIN_SHAPE
from host_runtime.workspace import write_atomically

RECORD_FILE = "personal-agent-code.json"
#: A code with less than this left is renewed.
RENEW_BEFORE = timedelta(days=7)
#: Settings reminds the person to enroll again when the Bridge token has less left.
BRIDGE_TOKEN_REMINDER = timedelta(days=14)
#: How long a pasted code is assumed to last (the platform's `DEFAULT_LOGIN_TTL`).
ASSUMED_CODE_LIFETIME = timedelta(days=30)
#: How often the Host checks whether the code is due.
CHECK_INTERVAL_SECONDS = 3600.0

CodeSource = Literal["sign_in", "pasted", "renewed"]
_LOG = logging.getLogger(__name__)


class AgentCodeError(Exception):
    """A step the card explains by its code; never carries a credential."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class AgentCodeRecord(Contract):
    """What this PC knows about its Personal Agent code. No secret."""

    login_id: Symbol
    expires_at: AwareDatetime
    issued_at: AwareDatetime
    source: CodeSource
    #: A pasted code's expiry is assumed (30 days from the paste).
    estimated: bool = False
    renewals: int = Field(default=0, ge=0, strict=True)
    #: The platform refused this code (revoked or expired early).
    refused: Text | None = None
    #: The last old code that could not be revoked, and why (no secret).
    unrevoked: Text | None = None


class CodeIssuer(Protocol):
    """The Member Portal calls renewal needs (`MemberPortalPublisher`)."""

    def issue_agent_login(self, session: str | None = None) -> dict[str, Any]: ...

    def revoke_login(self, login_id: str, session: str | None = None) -> dict[str, Any]: ...


class CodeSigner(CodeIssuer, Protocol):
    def password_sign_in(self, account: str, password: str) -> tuple[str, str | None]: ...


def login_id_of(code: str) -> str:
    return code.partition(":")[0]


def issued_code(reply: dict[str, Any]) -> tuple[str, str, datetime]:
    """The code, its login id and expiry from a `logins/issue-agent` reply."""
    code, login_id, expires_raw = reply.get("login"), reply.get("login_id"), reply.get("expires_at")
    if (
        not isinstance(code, str)
        or not LOGIN_SHAPE.fullmatch(code)
        or login_id != login_id_of(code)
        or not isinstance(expires_raw, str)
    ):
        raise AgentCodeError("bad_reply")
    try:
        expires = datetime.fromisoformat(expires_raw)
    except ValueError:
        raise AgentCodeError("bad_reply") from None
    if expires.tzinfo is None:
        raise AgentCodeError("bad_reply")
    return code, str(login_id), expires


def read_record(workspace_root: Path) -> AgentCodeRecord | None:
    try:
        return AgentCodeRecord.model_validate_json((workspace_root / RECORD_FILE).read_bytes())
    except (OSError, ValidationError, ValueError):
        return None


def write_record(workspace_root: Path, record: AgentCodeRecord) -> None:
    write_atomically(
        workspace_root / RECORD_FILE, record.model_dump_json(indent=2).encode("utf-8") + b"\n"
    )


def pasted_record(code: str, now: datetime) -> AgentCodeRecord:
    """A code pasted from the Member Portal: its id is in the code, its expiry
    is assumed from the platform's default lifetime."""
    return AgentCodeRecord(
        login_id=login_id_of(code),
        expires_at=now + ASSUMED_CODE_LIFETIME,
        issued_at=now,
        source="pasted",
        estimated=True,
    )


def code_status(record: AgentCodeRecord | None, saved: bool, now: datetime) -> dict[str, Any]:
    """What Settings shows about the code: `none`, `unknown` (saved before
    this PC kept a record), `valid`, `renew_soon` or `expired` (also when the
    platform refused it). No secret."""
    if not saved:
        return {"state": "none"}
    if record is None:
        return {"state": "unknown"}
    if record.refused is not None or record.expires_at <= now:
        state = "expired"
    elif record.expires_at - now <= RENEW_BEFORE:
        state = "renew_soon"
    else:
        state = "valid"
    return {
        "state": state,
        "login_id": record.login_id,
        "expires_at": record.expires_at.isoformat(),
        "estimated": record.estimated,
        "source": record.source,
        "renewals": record.renewals,
        "unrevoked": record.unrevoked,
    }


def bridge_token_status(expires_at: datetime | None, now: datetime) -> dict[str, Any]:
    """The Bridge token's expiry and whether to remind the person to enroll again."""
    if expires_at is None:
        return {"expires_at": None, "remind": False}
    left = expires_at - now
    return {
        "expires_at": expires_at.isoformat(),
        "days_left": max(0, left.days),
        "remind": left <= BRIDGE_TOKEN_REMINDER,
        "expired": left.total_seconds() <= 0,
    }


def sign_in(
    client: CodeSigner, account: str, password: str, now: datetime
) -> tuple[str, AgentCodeRecord, str | None]:
    """Sign in once and get a code. Returns the code, its record and, when
    the browser login the sign-in created could not be revoked, why."""
    session, browser_login = client.password_sign_in(account, password)
    code, login_id, expires = issued_code(client.issue_agent_login(session))
    problem = None
    if browser_login:
        try:
            client.revoke_login(login_id_of(browser_login), session)
        except Exception as error:  # noqa: BLE001 - the code is what matters
            problem = str(getattr(error, "code", "") or "revoke_failed")
            _LOG.warning(
                "the browser login of the Personal Agent sign-in could not be revoked (%s)",
                problem,
            )
    record = AgentCodeRecord(login_id=login_id, expires_at=expires, issued_at=now, source="sign_in")
    return code, record, problem


def due(record: AgentCodeRecord | None, saved: bool, now: datetime) -> bool:
    """Whether the code should be renewed now: a saved code with no record
    (renewal gives it a known expiry), or under `RENEW_BEFORE` left. An
    expired or refused code cannot renew itself."""
    if not saved:
        return False
    if record is None:
        return True
    if record.refused is not None or record.expires_at <= now:
        return False
    return record.expires_at - now <= RENEW_BEFORE


def renew(
    client: CodeIssuer,
    record: AgentCodeRecord | None,
    store: Callable[[str], None],
    now: datetime,
    old_code_login_id: str | None = None,
) -> AgentCodeRecord:
    """Get a new code with the current one, store it, revoke the old one.
    Raises the platform's error when no new code was issued (the record is
    then marked refused by the caller for an authentication refusal)."""
    code, login_id, expires = issued_code(client.issue_agent_login())
    store(code)
    old = record.login_id if record is not None else old_code_login_id
    unrevoked = None
    if old is not None and old != login_id:
        try:
            client.revoke_login(old)
        except Exception as error:  # noqa: BLE001 - the new code is already stored
            reason = str(getattr(error, "code", "") or "revoke_failed")
            unrevoked = f"{old} ({reason})"
            _LOG.warning(
                "the replaced Personal Agent code %s could not be revoked (%s); "
                "it expires on its own",
                old,
                reason,
            )
    return AgentCodeRecord(
        login_id=login_id,
        expires_at=expires,
        issued_at=now,
        source="renewed",
        renewals=(record.renewals if record is not None else 0) + 1,
        unrevoked=unrevoked,
    )


#: What the card says for a sign-in refusal; the platform's own words win.
SIGN_IN_PROBLEMS = {
    "authentication_failed": "Account or password is wrong, or there were too many attempts "
    "(wait 15 minutes). First time? Open your invitation link in the Member Portal and set a "
    "password there.",
    "actor_disabled": "Your platform account is disabled.",
    "account_invalid": "Enter your platform account (letters, digits, . - _ only).",
    "password_missing": "Enter your password.",
    "bad_reply": "The shared platform's answer was not a Personal Agent code.",
    "code_expired": "Your Personal Agent code has expired: sign in to get a new code.",
}
