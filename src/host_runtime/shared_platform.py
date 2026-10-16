"""The Agent Web "Shared platform" settings card (owner 2026-10-15,
`docs/phases/BRIDGE_ENROLLMENT.md`).

One Member Portal URL feeds both `publishing` and `platform`, the Bridge API
URL is `platform.base_url`, and "Enroll this PC" asks the portal, as the
member, for this computer's Bridge token. host.json is backed up before it is
rewritten and validated before anything is written.

Credentials:
- the member's Personal Agent login and the Bridge token are saved for this
  Windows user only (and in this process's environment), never in a file;
- the Bridge token gets its own variable, `AEP_SHARED_PLATFORM_TOKEN`, so the
  token of an older platform this PC used is left where it is;
- neither value is logged, put in the task list or returned to the page.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import AwareDatetime, ValidationError

from common.base import Contract, Symbol
from host_runtime.contracts import (
    CompanyHostConfiguration,
    HostLayout,
    PlatformBinding,
    PlatformPublishBinding,
)
from host_runtime.workspace import write_atomically

# The Bridge token's secret name and the variable it is saved under.
PLATFORM_SECRET = "shared_platform_token"
TOKEN_VARIABLE = "AEP_SHARED_PLATFORM_TOKEN"
# The member's Personal Agent login, when host.json names none yet.
LOGIN_SECRET = "platform_member_login"
LOGIN_VARIABLE = "AEP_PLATFORM_MEMBER_LOGIN"
# What the portal hands out under "Connect a Personal Agent".
LOGIN_SHAPE = re.compile(r"login-[0-9a-f]{16}:[A-Za-z0-9_-]{32,}")
# Non-secret facts about the last enrollment, for the card's status line.
RECORD_FILE = "shared-platform.json"

UserEnvironmentWriter = Callable[[str, str], None]


class SharedPlatformError(Exception):
    """A step the card explains by its code; never carries a credential."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class EnrollmentRecord(Contract):
    """What the card shows about this PC's enrollment. No secret."""

    bridge_id: Symbol
    token_id: Symbol
    actor: Symbol
    enrolled_at: AwareDatetime
    expires_at: AwareDatetime | None = None


def read_config(path: Path) -> CompanyHostConfiguration:
    return CompanyHostConfiguration.model_validate_json(path.read_text(encoding="utf-8-sig"))


def portal_url(value: str) -> str:
    """A Member Portal origin: https, or http on this computer only."""
    try:
        return PlatformPublishBinding(
            member_portal_url=value.strip(), credential={"name": LOGIN_SECRET}
        ).member_portal_url
    except (ValidationError, ValueError):
        raise SharedPlatformError("portal_url_invalid") from None


def bridge_url(value: str) -> str:
    """A Bridge API origin, under the same rule."""
    try:
        return PlatformBinding(
            base_url=value.strip(), token_id="token-check", credential={"name": PLATFORM_SECRET}
        ).base_url
    except (ValidationError, ValueError):
        raise SharedPlatformError("bridge_url_invalid") from None


def check_bridge(
    base_url: str, certificate_sha256: str | None = None, timeout: float = 8.0
) -> None:
    """Refuse unless a Shared Platform Bridge API answers at this origin,
    with the certificate this PC trusts. Checked before enrolling, so a wrong
    address is refused instead of saved (owner 2026-10-15: an old address was
    saved and only shown as unreachable); a certificate this PC does not
    trust is said as such (owner 2026-10-16)."""
    import urllib.request

    from common.certificates import certificate_problem, https_handler

    opener = urllib.request.build_opener(https_handler(certificate_sha256))
    try:
        with opener.open(f"{base_url}/v1/health", timeout=timeout) as answer:
            if answer.status == 200 and json.loads(answer.read()).get("ok") is True:
                return
    except (OSError, ValueError) as error:
        if certificate_problem(error) is not None:
            raise SharedPlatformError("certificate_untrusted") from None
    raise SharedPlatformError("bridge_unreachable")


# `KEEP` leaves the pinned certificate as it is; None removes it.
KEEP = "keep"


def certificate_pin(value: object) -> str | None:
    """The card's "Trust this certificate" value: a SHA-256 fingerprint, or
    empty to forget the pin."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        raise SharedPlatformError("certificate_pin_invalid")
    from common.certificates import normalize_fingerprint

    try:
        return normalize_fingerprint(value)
    except ValueError:
        raise SharedPlatformError("certificate_pin_invalid") from None


def certificate_of(url: str, timeout: float = 8.0) -> dict[str, Any]:
    """What an https origin presents, for the card's "Fetch & show
    fingerprint". Public facts only; nothing is trusted by reading it."""
    from common.certificates import presented_certificate

    try:
        presented = presented_certificate(url, timeout=timeout)
    except ValueError:
        raise SharedPlatformError("certificate_needs_https") from None
    except OSError:
        raise SharedPlatformError("certificate_unreachable") from None
    return {
        "url": url,
        "fingerprint": presented.fingerprint,
        "pem": presented.pem,
        "trusted_by_system": presented.trusted_by_system,
    }


def _mapped(candidate: dict[str, Any], secret: str, variable: str) -> None:
    """Map `secret` to `variable` in the candidate's credentials, replacing
    whatever variable that secret had before and nothing else."""
    kept = [item for item in candidate.get("credentials", []) if item["secret"] != secret]
    candidate["credentials"] = [*kept, {"secret": secret, "environment_variable": variable}]


def with_settings(
    current: CompanyHostConfiguration,
    *,
    member_portal_url: str,
    base_url: str | None,
    certificate_sha256: str | None = KEEP,
) -> CompanyHostConfiguration:
    """host.json with the card's URLs: the one Member Portal URL in both
    `publishing` and `platform`, and the Bridge API URL in `platform` when
    this PC already has one (a new `platform` needs a token: Enroll). A
    pinned certificate (owner 2026-10-16) goes into both as well; `KEEP`
    leaves the trust as it is, None forgets the pin."""
    candidate = current.model_dump(mode="json")
    publishing = current.publishing
    login = publishing.credential.name if publishing is not None else LOGIN_SECRET
    pin: str | None
    if certificate_sha256 == KEEP:
        source = publishing if publishing is not None else current.platform
        pin = source.certificate_sha256 if source is not None else None
        ca_file = source.ca_file if source is not None else None
    else:
        # A pin the member chose replaces a CA file; forgetting it leaves
        # the system's trust store.
        pin, ca_file = certificate_sha256, None
    candidate["publishing"] = {
        "member_portal_url": member_portal_url,
        "credential": {"name": login},
        "timeout_seconds": publishing.timeout_seconds if publishing is not None else 30,
        "certificate_sha256": pin,
        "ca_file": ca_file,
    }
    if login not in current.credential_environment():
        _mapped(candidate, login, LOGIN_VARIABLE)
    if current.platform is not None:
        candidate["platform"]["member_portal_url"] = member_portal_url
        candidate["platform"]["certificate_sha256"] = pin
        candidate["platform"]["ca_file"] = ca_file
        if base_url:
            candidate["platform"]["base_url"] = base_url
    return CompanyHostConfiguration.model_validate(candidate)


def with_enrollment(
    current: CompanyHostConfiguration, *, base_url: str, member_portal_url: str, token_id: str
) -> CompanyHostConfiguration:
    """host.json pointing `platform` at the new Bridge token. Only this
    token's own mapping is added; an older platform's mapping stays. The
    certificate trust is the one `publishing` has (the card sets both)."""
    candidate = current.model_dump(mode="json")
    timeout = current.platform.timeout_seconds if current.platform is not None else 30
    publishing = current.publishing
    candidate["platform"] = {
        "base_url": base_url,
        "member_portal_url": member_portal_url,
        "token_id": token_id,
        "credential": {"name": PLATFORM_SECRET},
        "timeout_seconds": timeout,
        "certificate_sha256": publishing.certificate_sha256 if publishing else None,
        "ca_file": publishing.ca_file if publishing else None,
    }
    _mapped(candidate, PLATFORM_SECRET, TOKEN_VARIABLE)
    return CompanyHostConfiguration.model_validate(candidate)


def save_config(path: Path, updated: CompanyHostConfiguration, *, now: datetime) -> Path:
    """Back the file up, then write the validated configuration whole."""
    checked = CompanyHostConfiguration.model_validate(updated)
    stamp = now.strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.bak-{stamp}-before-shared-platform")
    shutil.copy2(path, backup)
    write_atomically(path, checked.model_dump_json(indent=2).encode("utf-8") + b"\n")
    return backup


def save_secret(store: UserEnvironmentWriter, variable: str, value: str) -> None:
    """Keep a secret for this Windows user and for this process at once, so
    the running Agent uses it without a restart."""
    try:
        store(variable, value)
    except Exception:  # noqa: BLE001 - the reason must not carry the value
        raise SharedPlatformError("secret_not_saved") from None
    os.environ[variable] = value


def enrolled_token(reply: dict[str, Any], bridge_id: str) -> tuple[str, str, datetime | None]:
    """The token id, secret and expiry from a `bridges/enroll` reply, checked
    to be for this computer."""
    token_id, secret = reply.get("token_id"), reply.get("secret")
    if (
        reply.get("bridge_id") != bridge_id
        or not isinstance(token_id, str)
        or not re.fullmatch(r"token-[0-9a-f]{16}", token_id)
        or not isinstance(secret, str)
        or len(secret) < 32
        or not re.fullmatch(r"[A-Za-z0-9_-]+", secret)
    ):
        raise SharedPlatformError("bad_reply")
    expires_raw = reply.get("expires_at")
    try:
        expires = datetime.fromisoformat(expires_raw) if isinstance(expires_raw, str) else None
    except ValueError:
        raise SharedPlatformError("bad_reply") from None
    return token_id, secret, expires


def write_record(layout: HostLayout, record: EnrollmentRecord) -> None:
    write_atomically(
        layout.workspace_root / RECORD_FILE,
        record.model_dump_json(indent=2).encode("utf-8") + b"\n",
    )


def read_record(layout: HostLayout) -> EnrollmentRecord | None:
    try:
        raw = (layout.workspace_root / RECORD_FILE).read_text(encoding="utf-8")
        return EnrollmentRecord.model_validate(json.loads(raw))
    except (OSError, ValueError, ValidationError):
        return None


def now() -> datetime:
    return datetime.now(UTC)


# What the card says for each code.
PROBLEMS = {
    "portal_url_invalid": "The Member Portal URL must be an address like "
    "https://platform.example or, on this computer, http://127.0.0.1:28776.",
    "bridge_url_invalid": "The Bridge API URL must be an address like "
    "https://platform.example or, on this computer, http://127.0.0.1:28775.",
    "bridge_url_missing": "Enter the Bridge API URL before enrolling.",
    "bridge_unreachable": "The Bridge API URL did not answer, so this PC was not enrolled and "
    "nothing was saved. Check the address (and the SSH tunnel, if you use one).",
    "login_malformed": "That is not a Personal Agent code; copy it again from the Member "
    "Portal ('Connect a Personal Agent').",
    "secret_not_saved": "Windows did not save the value for this user.",
    "settings_read_only": "This Agent Web was started without its host file.",
    "settings_invalid": "host.json would not be valid with these values; nothing was saved.",
    "settings_not_saved": "host.json could not be written; nothing changed in this Agent.",
    "bad_reply": "The shared platform's answer was not an enrollment for this PC.",
    # A platform with a self-signed certificate (owner 2026-10-16).
    "certificate_untrusted": "The Bridge API's certificate is not trusted by this PC, so this "
    "PC was not enrolled. Press 'Fetch & show fingerprint', compare it with the fingerprint "
    "your administrator gave you, then 'Trust this certificate' and enroll again.",
    "certificate_pin_invalid": "A certificate fingerprint is a SHA-256: 64 hexadecimal digits "
    "(colons allowed).",
    "certificate_needs_https": "Only an https:// address has a certificate to show.",
    "certificate_unreachable": "That address did not answer a TLS handshake. Check the address "
    "and that this PC can reach it.",
    "certificate_mismatch": "The Member Portal and the Bridge API presented different "
    "certificates; ask your administrator which one is right before trusting either.",
}
