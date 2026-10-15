"""Publish an installed Skill or Workflow to the shared platform as its member
(owner 2026-10-15, `docs/phases/MEMBER_PUBLISH.md`).

The Agent sends the manifest it has installed; the platform assigns the version
and owner, resets the reviews and keeps the submission in a review queue until
an administrator other than the member approves it. Nothing is published here.

The member's `Personal Agent` login is a `SecretRef` resolved per call and
traded for a one-hour session held only in memory. It goes to the Member
Portal and nowhere else: the Bridge token never goes there and this login
never goes to the Bridge API.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from host_runtime.contracts import HostLayout, PlatformPublishBinding
from models.credentials import CredentialResolver

PublishKind = Literal["skill", "workflow"]
CHANGES = ("patch", "minor", "major")
# An asset as a person names it: namespace/name@version.
ASSET_REFERENCE = re.compile(r"^([a-z0-9]+(?:-[a-z0-9]+)*)/([a-z0-9]+(?:-[a-z0-9]+)*)@(\S+)$")
# A session is renewed this long before the platform would end it.
SESSION_MARGIN = timedelta(minutes=2)


class PublishError(Exception):
    """A publish step that failed, with a code the page and CLI can explain.
    The message never carries a credential."""

    def __init__(self, code: str, status: int | None = None) -> None:
        self.code = code
        self.status = status
        super().__init__(code)


def installed_manifest(layout: HostLayout, kind: PublishKind, reference: str) -> dict[str, Any]:
    """The manifest this host installed for `namespace/name@version`."""
    match = ASSET_REFERENCE.match(reference.strip())
    if match is None:
        raise PublishError("bad_reference")
    namespace, name, version = match.groups()
    folder = layout.skills if kind == "skill" else layout.workflows
    path = folder / f"{namespace}__{name}__{version}.json"
    if not path.is_file():
        raise PublishError("not_installed")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PublishError("not_installed") from None
    if not isinstance(manifest, dict):
        raise PublishError("not_installed")
    return manifest


def installed_assets(layout: HostLayout) -> list[dict[str, str]]:
    """What this host could publish: every installed Skill and Workflow."""
    found: list[dict[str, str]] = []
    for kind, folder in (("skill", layout.skills), ("workflow", layout.workflows)):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*__*__*.json")):
            namespace, name, version = path.stem.split("__", 2)
            found.append({"kind": kind, "asset": f"{namespace}/{name}@{version}"})
    return found


class MemberPortalPublisher:
    """The member-portal calls that publishing needs, as this host's member."""

    def __init__(
        self,
        binding: PlatformPublishBinding,
        resolver: CredentialResolver,
        *,
        clock: Any = None,
    ) -> None:
        self.binding = PlatformPublishBinding.model_validate(binding)
        self._resolver = resolver
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._lock = threading.Lock()
        self._session: tuple[str, datetime] | None = None

    def _post(self, operation: str, authorization: str, body: object | None) -> dict[str, Any]:
        raw = b"" if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            f"{self.binding.member_portal_url}/v1/member/{operation}",
            method="POST",
            data=raw,
        )
        request.add_header("Authorization", authorization)
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.binding.timeout_seconds) as answer:
                reply = json.loads(answer.read())
        except urllib.error.HTTPError as refused:
            try:
                code = json.loads(refused.read()).get("code", "request_failed")
            except ValueError:
                code = "request_failed"
            raise PublishError(str(code), refused.code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise PublishError("platform_unreachable") from None
        except ValueError:
            raise PublishError("bad_reply") from None
        if not isinstance(reply, dict):
            raise PublishError("bad_reply")
        return reply

    def _bearer(self) -> str:
        with self._lock:
            now = self._clock()
            if self._session is not None and now < self._session[1] - SESSION_MARGIN:
                return self._session[0]
            try:
                login = self._resolver.resolve(self.binding.credential)
            except Exception:  # noqa: BLE001 - the reason may name the variable, not the value
                raise PublishError("login_missing") from None
            reply = self._post("session", f"Login {login}", None)
            try:
                session = str(reply["session"])
                expires = datetime.fromisoformat(str(reply["expires_at"]))
            except (KeyError, ValueError):
                raise PublishError("bad_reply") from None
            self._session = (session, expires)
            return session

    def _call(self, operation: str, body: object) -> dict[str, Any]:
        try:
            return self._post(operation, f"Bearer {self._bearer()}", body)
        except PublishError as error:
            renewable = error.code in ("session_expired", "authentication_failed")
            if not renewable or error.status is None:
                raise
            with self._lock:
                self._session = None  # one fresh session, then give up
            return self._post(operation, f"Bearer {self._bearer()}", body)

    def submit(
        self,
        kind: PublishKind,
        manifest: dict[str, Any],
        change: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        if change not in CHANGES:
            raise PublishError("bad_change")
        body: dict[str, Any] = {"kind": kind, "change": change, "manifest": manifest}
        if note and note.strip():
            body["note"] = note.strip()
        return self._call("assets/submit", body)["submission"]  # type: ignore[no-any-return]

    def submissions(self) -> list[dict[str, Any]]:
        return list(self._call("assets/submissions", {}).get("submissions", ()))

    def withdraw(self, submission_id: str) -> dict[str, Any]:
        return self._call(  # type: ignore[no-any-return]
            "assets/submissions/withdraw", {"submission_id": submission_id}
        )["submission"]

    def me(self) -> str:
        """The platform account this PC's Personal Agent login belongs to."""
        actor = self._call("me", {}).get("actor")
        if not isinstance(actor, str) or not actor:
            raise PublishError("bad_reply")
        return actor

    def enroll(self, request: dict[str, Any]) -> dict[str, Any]:
        """Enroll this computer as the member (`bridges/enroll`, owner
        2026-10-15). The reply carries this computer's Bridge token once; the
        caller stores it and drops it, and never logs or returns it."""
        return self._call("bridges/enroll", request)


# What a person sees for each code, in the page and the CLI.
EXPLANATIONS = {
    "login_missing": "This PC has no Personal Agent code for the shared platform yet. In the "
    "Member Portal press 'Connect a Personal Agent', copy the code and paste it into "
    "Settings > Shared platform > 'Personal Agent code', then Save.",
    "authentication_failed": "The shared platform did not accept this PC's login. Connect the "
    "Personal Agent again in the Member Portal.",
    "platform_unreachable": "The shared platform did not answer. Check the address in Settings "
    "(and the SSH tunnel, if you use one).",
    "not_installed": "That Skill or Workflow is not installed on this PC.",
    "bad_reference": "Name the asset as namespace/name@version.",
    "bad_change": "Choose patch, minor or major.",
    "manifest_invalid": "The platform could not read this manifest.",
    "artifact_too_large": "The manifest is larger than the platform accepts.",
    "missing_dependency": "Publish the Workflow this Skill runs first (or submit it now).",
    "publisher_not_authorized": "Another member owns this name; ask them to add you as a "
    "co-editor.",
    "submission_missing": "That submission does not exist or is not yours.",
    "submission_not_pending": "That submission has already been decided.",
    # Bridge self-enrollment (owner 2026-10-15).
    "device_owner_mismatch": "This PC is registered to another platform account. Its "
    "host.json device.registered_by must be the account you signed in to the portal with.",
    "administrator_required": "Only a platform administrator can enroll a shared test "
    "workstation.",
    "device_disabled": "An administrator disabled this PC on the shared platform; ask them "
    "to enable it again.",
    "device_in_use": "Another member is bound to this PC on the shared platform.",
    "actor_disabled": "Your platform account is disabled.",
    "session_expired": "The shared platform ended this PC's session; try again.",
}


def explain(code: str) -> str:
    return EXPLANATIONS.get(code, f"The shared platform refused it ({code}).")


class UserEnvironment(Mapping[str, str]):
    r"""This process's environment, then this Windows user's saved variables.

    A member sets their Personal Agent login once with `setx`; a running Agent
    Web or a shell opened before that does not see it in its own environment,
    so the user's saved value (HKCU\Environment) is read at the moment of use.
    """

    def __init__(self, base: Mapping[str, str] | None = None) -> None:
        self._base = base if base is not None else os.environ

    def __getitem__(self, name: str) -> str:
        if name in self._base:
            return self._base[name]
        value = _saved_user_variable(name)
        if value is None:
            raise KeyError(name)
        return value

    def __iter__(self) -> Iterator[str]:
        return iter(self._base)

    def __len__(self) -> int:
        return len(self._base)


def _saved_user_variable(name: str) -> str | None:
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
    except OSError:
        return None
    return value if isinstance(value, str) else None


def publisher_for(
    binding: PlatformPublishBinding | None,
    names: dict[str, str],
    environ: Mapping[str, str] | None = None,
) -> MemberPortalPublisher | None:
    """The publisher for a host's configuration, or None when publishing is
    not configured. `names` is the host's secret-to-variable mapping."""
    if binding is None:
        return None
    from models.credentials import EnvironmentCredentials

    return MemberPortalPublisher(
        binding, EnvironmentCredentials(names, environ if environ is not None
                                        else UserEnvironment()))
