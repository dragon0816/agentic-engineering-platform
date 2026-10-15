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


def bridge_answers(base_url: str, timeout: float = 8.0) -> bool:
    """Whether a Shared Platform Bridge API answers at this origin. Checked
    before enrolling, so a wrong address is refused instead of saved (owner
    2026-10-15: an old address was saved and only shown as unreachable)."""
    import json
    import urllib.request

    try:
        with urllib.request.urlopen(f"{base_url}/v1/health", timeout=timeout) as answer:
            return answer.status == 200 and json.loads(answer.read()).get("ok") is True
    except (OSError, ValueError):
        return False


def _mapped(candidate: dict[str, Any], secret: str, variable: str) -> None:
    """Map `secret` to `variable` in the candidate's credentials, replacing
    whatever variable that secret had before and nothing else."""
    kept = [item for item in candidate.get("credentials", []) if item["secret"] != secret]
    candidate["credentials"] = [*kept, {"secret": secret, "environment_variable": variable}]


def with_settings(
    current: CompanyHostConfiguration, *, member_portal_url: str, base_url: str | None
) -> CompanyHostConfiguration:
    """host.json with the card's URLs: the one Member Portal URL in both
    `publishing` and `platform`, and the Bridge API URL in `platform` when
    this PC already has one (a new `platform` needs a token: Enroll)."""
    candidate = current.model_dump(mode="json")
    publishing = current.publishing
    login = publishing.credential.name if publishing is not None else LOGIN_SECRET
    candidate["publishing"] = {
        "member_portal_url": member_portal_url,
        "credential": {"name": login},
        "timeout_seconds": publishing.timeout_seconds if publishing is not None else 30,
    }
    if login not in current.credential_environment():
        _mapped(candidate, login, LOGIN_VARIABLE)
    if current.platform is not None:
        candidate["platform"]["member_portal_url"] = member_portal_url
        if base_url:
            candidate["platform"]["base_url"] = base_url
    return CompanyHostConfiguration.model_validate(candidate)


def with_enrollment(
    current: CompanyHostConfiguration, *, base_url: str, member_portal_url: str, token_id: str
) -> CompanyHostConfiguration:
    """host.json pointing `platform` at the new Bridge token. Only this
    token's own mapping is added; an older platform's mapping stays."""
    candidate = current.model_dump(mode="json")
    timeout = current.platform.timeout_seconds if current.platform is not None else 30
    candidate["platform"] = {
        "base_url": base_url,
        "member_portal_url": member_portal_url,
        "token_id": token_id,
        "credential": {"name": PLATFORM_SECRET},
        "timeout_seconds": timeout,
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
}
