"""Account and password sign-in for platform members (owner 2026-10-15).

`docs/phases/PASSWORD_SIGN_IN.md`. The platform keeps a slow salted hash of
each member's password (`hashlib.scrypt`, cost recorded with every hash),
counts failed attempts per account and per client address, and issues
single-use password reset links the way it issues invitations: only a SHA-256
fingerprint of a random 32-byte secret is stored.

Nothing here logs, returns or stores a password. Values that carry one are
plain `str` arguments, never `Contract` fields, so no validation error, repr
or JSON dump can contain them.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from common.base import Contract, Sha256, Symbol
from control_plane.identity import fingerprint
from control_plane.identity_store import SqliteIdentityStorage

PASSWORD_METHOD = "password"
MIN_PASSWORD_CHARS = 12
MAX_PASSWORD_CHARS = 256
SALT_BYTES = 16
DIGEST_BYTES = 32
RESET_SECRET_BYTES = 32
MIN_RESET_SECRET_CHARS = 32
DEFAULT_RESET_MINUTES = 60
MAX_RESET_MINUTES = 24 * 60

MAX_ACCOUNT_FAILURES = 5
# Higher than the account limit: the live platform is reached through an SSH
# tunnel or relay, so every member may arrive from the same loopback address.
MAX_ADDRESS_FAILURES = 20
FAILURE_WINDOW = timedelta(minutes=15)
LOCKOUT = timedelta(minutes=15)

# Very common passwords of at least the minimum length, compared case-folded.
COMMON_PASSWORDS = frozenset(
    {
        "123456789012",
        "1234567890123",
        "12345678901234",
        "123456789123",
        "111111111111",
        "000000000000",
        "123123123123",
        "password1234",
        "password12345",
        "password123456",
        "passwordpassword",
        "password1!password",
        "qwertyuiopasdf",
        "qwertyuiop12",
        "qwertyuiop123",
        "qwerty123456",
        "qwertyqwerty",
        "1qaz2wsx3edc",
        "1q2w3e4r5t6y",
        "q1w2e3r4t5y6",
        "zaq12wsxcde3",
        "asdfghjkl123",
        "asdfasdfasdf",
        "abcdefghijkl",
        "abcd12345678",
        "abc123abc123",
        "iloveyou1234",
        "welcome12345",
        "welcome123456",
        "letmein12345",
        "changeme1234",
        "changemenow1",
        "administrator",
        "administrator1",
        "admin1234567",
        "adminadmin123",
        "superman1234",
        "baseball1234",
        "football1234",
        "princess1234",
        "sunshine1234",
        "trustno1trustno1",
        "correcthorsebatterystaple",
        "correct horse battery staple",
        "p@ssw0rd1234",
        "p@ssword1234",
        "passw0rd1234",
        "monkey123456",
        "dragon123456",
        "master123456",
        "whatever1234",
        "computer1234",
        "internet1234",
        "company12345",
    }
)

PasswordProblem = Literal["too_short", "too_long", "contains_account", "too_common", "repeated"]
PROBLEM_MESSAGES: dict[str, str] = {
    "too_short": f"Use at least {MIN_PASSWORD_CHARS} characters; a few words work well.",
    "too_long": f"Use at most {MAX_PASSWORD_CHARS} characters.",
    "contains_account": "The password must not contain your account name.",
    "too_common": "That password is too common; choose another.",
    "repeated": "The password must not be one character repeated.",
}

PasswordErrorCode = Literal[
    "authentication_failed",
    "password_rejected",
    "password_already_set",
    "password_not_set",
    "reset_link_used",
    "reset_link_expired",
    "reset_link_revoked",
    "invalid_request",
]


class PasswordError(Exception):
    """A refusal; `reason` only for `password_rejected`. Never holds a value."""

    def __init__(self, code: PasswordErrorCode, reason: PasswordProblem | None = None) -> None:
        self.code: PasswordErrorCode = code
        self.reason: PasswordProblem | None = reason
        super().__init__(code if reason is None else f"{code}: {reason}")


class PasswordCost(Contract):
    """scrypt parameters; `n` a power of two."""

    n: int = Field(ge=2, le=2**20)
    r: int = Field(ge=1, le=32)
    p: int = Field(ge=1, le=16)

    @model_validator(mode="after")
    def power_of_two(self) -> Self:
        if self.n & (self.n - 1):
            raise ValueError("scrypt n must be a power of two")
        return self


# 32 MiB of memory and about 0.1-0.3 s per check on the platform's PC; the
# cost is recorded with every hash, so raising it later keeps old ones valid.
DEFAULT_COST = PasswordCost(n=2**15, r=8, p=1)


class PasswordRecord(Contract):
    """What the platform keeps instead of a member's password."""

    actor: Symbol
    algorithm: Literal["scrypt"] = "scrypt"
    n: int
    r: int
    p: int
    salt: str = Field(pattern=r"^[a-f0-9]{32,128}$")
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    set_at: AwareDatetime
    set_by: Literal["invitation", "self", "change", "reset"]


class PasswordResetGrant(Contract):
    """Secret-free record of one administrator-issued password reset link."""

    reset_id: Symbol
    actor: Symbol
    fingerprint: Sha256
    issued_by: Symbol
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    status: Literal["active", "used", "revoked"] = "active"

    @model_validator(mode="after")
    def ends_after_issue(self) -> Self:
        if self.expires_at <= self.issued_at:
            raise ValueError("a reset link must expire after it is issued")
        return self


class IssuedPasswordReset:
    """The one return value that carries a reset link's secret."""

    __slots__ = ("grant", "secret")

    def __init__(self, grant: PasswordResetGrant, secret: str) -> None:
        self.grant = grant
        self.secret = secret

    @property
    def bearer(self) -> str:
        return f"{self.grant.reset_id}:{self.secret}"

    def __repr__(self) -> str:
        return f"IssuedPasswordReset(reset_id={self.grant.reset_id!r}, secret=[redacted])"


def password_problem(account: str, password: str) -> PasswordProblem | None:
    """Why this password is refused for this account, or None."""
    if len(password) < MIN_PASSWORD_CHARS:
        return "too_short"
    if len(password) > MAX_PASSWORD_CHARS:
        return "too_long"
    folded = password.casefold()
    name = account.casefold()
    if folded == name or (len(name) >= 3 and (name in folded or name.replace(".", "") in folded)):
        return "contains_account"
    if folded in COMMON_PASSWORDS or folded.strip() in COMMON_PASSWORDS:
        return "too_common"
    if len(set(password)) == 1:
        return "repeated"
    return None


def _scrypt(password: str, salt: bytes, cost: PasswordCost) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=cost.n,
        r=cost.r,
        p=cost.p,
        maxmem=128 * cost.r * cost.n * 2 + 1024 * 1024,
        dklen=DIGEST_BYTES,
    )


def hash_password(
    actor: str,
    password: str,
    *,
    cost: PasswordCost = DEFAULT_COST,
    now: datetime,
    set_by: Literal["invitation", "self", "change", "reset"],
    salt: bytes | None = None,
) -> PasswordRecord:
    """A new record with a fresh random salt."""
    value = salt if salt is not None else secrets.token_bytes(SALT_BYTES)
    return PasswordRecord(
        actor=actor,
        n=cost.n,
        r=cost.r,
        p=cost.p,
        salt=value.hex(),
        digest=_scrypt(password, value, cost).hex(),
        set_at=now,
        set_by=set_by,
    )


def verify_password(record: PasswordRecord, password: str) -> bool:
    """Constant-time check of a password against its record's own cost."""
    if len(password) > MAX_PASSWORD_CHARS:
        return False
    cost = PasswordCost(n=record.n, r=record.r, p=record.p)
    actual = _scrypt(password, bytes.fromhex(record.salt), cost)
    return hmac.compare_digest(actual, bytes.fromhex(record.digest))


@dataclass
class _Counter:
    failures: deque[datetime]
    locked_until: datetime | None = None


class FailureLimiter:
    """Failed attempts per key in a sliding window; too many lock the key."""

    def __init__(self, *, window: timedelta = FAILURE_WINDOW, lockout: timedelta = LOCKOUT) -> None:
        self._window = window
        self._lockout = lockout
        self._counters: dict[str, _Counter] = {}
        self._lock = threading.Lock()

    def locked(self, key: str, now: datetime) -> bool:
        with self._lock:
            counter = self._counters.get(key)
            if counter is None or counter.locked_until is None:
                return False
            if now >= counter.locked_until:
                del self._counters[key]
                return False
            return True

    def fail(self, key: str, limit: int, now: datetime) -> None:
        with self._lock:
            counter = self._counters.setdefault(key, _Counter(deque()))
            while counter.failures and now - counter.failures[0] >= self._window:
                counter.failures.popleft()
            counter.failures.append(now)
            if len(counter.failures) >= limit:
                counter.locked_until = now + self._lockout
                counter.failures.clear()

    def clear(self, key: str) -> None:
        with self._lock:
            self._counters.pop(key, None)


def _account_key(account: str) -> str:
    return f"account:{account.casefold()}"


def _address_key(address: str) -> str:
    return f"address:{address}"


class MemberPasswords:
    """Password hashes, attempt counters and reset links, optionally durable."""

    def __init__(
        self,
        *,
        storage: SqliteIdentityStorage | None = None,
        cost: PasswordCost = DEFAULT_COST,
        account_failures: int = MAX_ACCOUNT_FAILURES,
        address_failures: int = MAX_ADDRESS_FAILURES,
        limiter: FailureLimiter | None = None,
    ) -> None:
        self._storage = storage
        self.cost = PasswordCost.model_validate(cost)
        self._account_failures = account_failures
        self._address_failures = address_failures
        self.limiter = limiter if limiter is not None else FailureLimiter()
        self._records = {
            item.actor: item
            for item in (
                PasswordRecord.model_validate_json(raw)
                for raw in (() if storage is None else storage.records("identity_passwords"))
            )
        }
        self._resets = {
            item.reset_id: item
            for item in (
                PasswordResetGrant.model_validate_json(raw)
                for raw in (() if storage is None else storage.records("identity_password_resets"))
            )
        }
        # Verified against when there is no record, so an unknown account
        # takes about as long as a known one. Made on first use.
        self._dummy: PasswordRecord | None = None
        self._lock = threading.Lock()

    # -- Records -------------------------------------------------------

    def record(self, actor: str) -> PasswordRecord | None:
        """The stored record (hash, never the password), for status replies."""
        with self._lock:
            item = self._records.get(actor)
        return item.model_copy(deep=True) if item is not None else None

    def has_password(self, actor: str) -> bool:
        with self._lock:
            return actor in self._records

    def check_policy(self, actor: str, password: str) -> None:
        problem = password_problem(actor, password)
        if problem is not None:
            raise PasswordError("password_rejected", problem)

    def set(
        self,
        actor: str,
        password: str,
        *,
        now: datetime,
        set_by: Literal["invitation", "self", "change", "reset"],
    ) -> PasswordRecord:
        """Store a new hash after the policy check. Replaces an earlier one."""
        self.check_policy(actor, password)
        item = hash_password(actor, password, cost=self.cost, now=now, set_by=set_by)
        with self._lock:
            self._records[actor] = item
            if self._storage is not None:
                self._storage.put("identity_passwords", actor, item)
        return item.model_copy(deep=True)

    def set_first(self, actor: str, password: str, *, now: datetime) -> PasswordRecord:
        """A signed-in member without a password sets one."""
        if self.has_password(actor):
            raise PasswordError("password_already_set")
        return self.set(actor, password, now=now, set_by="self")

    # -- Checks ----------------------------------------------------------

    def authenticate(
        self,
        account: str,
        password: str,
        *,
        address: str,
        now: datetime,
        active: Callable[[str], bool],
    ) -> str:
        """The account, when the password is right and the member active.

        Every refusal is `authentication_failed`: an unknown account, a member
        without a password, a disabled member, a wrong password and a locked
        account or address look the same.
        """
        account_key, address_key = _account_key(account), _address_key(address)
        if self.limiter.locked(account_key, now) or self.limiter.locked(address_key, now):
            raise PasswordError("authentication_failed")
        record = self.record(account)
        if record is None:
            if self._dummy is None:
                self._dummy = hash_password(
                    "unknown",
                    secrets.token_urlsafe(24),
                    cost=self.cost,
                    now=datetime.now(UTC),
                    set_by="self",
                )
            verify_password(self._dummy, password)
            matched = False
        else:
            matched = verify_password(record, password)
        if not matched or not active(account):
            self.limiter.fail(account_key, self._account_failures, now)
            self.limiter.fail(address_key, self._address_failures, now)
            raise PasswordError("authentication_failed")
        self.limiter.clear(account_key)
        return account

    # -- Reset links -----------------------------------------------------

    def issue_reset(
        self,
        actor: str,
        *,
        issued_by: str,
        now: datetime,
        minutes: int = DEFAULT_RESET_MINUTES,
        secret: str | None = None,
    ) -> IssuedPasswordReset:
        if not 1 <= minutes <= MAX_RESET_MINUTES:
            raise PasswordError("invalid_request")
        value = secret if secret is not None else secrets.token_urlsafe(RESET_SECRET_BYTES)
        if len(value) < MIN_RESET_SECRET_CHARS:
            raise PasswordError("invalid_request")
        grant = PasswordResetGrant(
            reset_id=f"reset-{secrets.token_hex(8)}",
            actor=actor,
            fingerprint=fingerprint(value),
            issued_by=issued_by,
            issued_at=now,
            expires_at=now + timedelta(minutes=minutes),
        )
        with self._lock:
            for earlier in list(self._resets.values()):
                if earlier.actor == actor and earlier.status == "active":
                    self._save_reset(earlier.model_copy(update={"status": "revoked"}))
            self._save_reset(grant)
        return IssuedPasswordReset(grant.model_copy(deep=True), value)

    def _save_reset(self, grant: PasswordResetGrant) -> None:
        checked = PasswordResetGrant.model_validate(grant.model_dump())
        self._resets[checked.reset_id] = checked
        if self._storage is not None:
            self._storage.put("identity_password_resets", checked.reset_id, checked)

    def _usable(self, reset_id: str, secret: str, now: datetime) -> PasswordResetGrant:
        grant = self._resets.get(reset_id)
        expected = grant.fingerprint if grant is not None else fingerprint("")
        if grant is None or not hmac.compare_digest(expected, fingerprint(secret)):
            raise PasswordError("authentication_failed")
        if grant.status == "used":
            raise PasswordError("reset_link_used")
        if grant.status == "revoked":
            raise PasswordError("reset_link_revoked")
        if now >= grant.expires_at:
            raise PasswordError("reset_link_expired")
        return grant

    def check_reset(self, reset_id: str, secret: str, *, now: datetime) -> PasswordResetGrant:
        """The link's record when it can still be used; nothing is used up."""
        with self._lock:
            return self._usable(reset_id, secret, now).model_copy(deep=True)

    def redeem_reset(
        self,
        reset_id: str,
        secret: str,
        password: str,
        *,
        now: datetime,
        active: Callable[[str], bool],
    ) -> str:
        """Use the link once to set a new password; returns the account."""
        with self._lock:
            grant = self._usable(reset_id, secret, now)
        if not active(grant.actor):
            raise PasswordError("authentication_failed")
        self.check_policy(grant.actor, password)
        with self._lock:
            grant = self._usable(reset_id, secret, now)
            self._save_reset(grant.model_copy(update={"status": "used"}))
        self.set(grant.actor, password, now=now, set_by="reset")
        self.limiter.clear(_account_key(grant.actor))
        return grant.actor

    def pending_reset(self, actor: str, now: datetime) -> PasswordResetGrant | None:
        with self._lock:
            for grant in self._resets.values():
                if grant.actor == actor and grant.status == "active" and now < grant.expires_at:
                    return grant.model_copy(deep=True)
        return None
