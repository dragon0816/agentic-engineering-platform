"""Authenticated member selection service for the shared platform.

This is deliberately separate from the Bridge wire. A Bridge token proves a
machine/member binding for catalog and synchronization; it is never accepted
as a browser session. A trusted sign-in adapter may mint the short-lived
member session used here after it has produced an ``AuthenticatedActor``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Literal, Self, TypeVar

from pydantic import AwareDatetime, model_validator

from common.assets import AssetMetadata, RegistryContract
from common.authorization import DeviceAssetSelection
from common.base import Sha256, Symbol
from common.enrollment import BridgeBinding, BridgeExecutionSubject
from common.identity import (
    ACCESS_TOKEN_METHOD,
    AuthenticatedActor,
    IssuedAccessToken,
    entitled,
)
from common.member import (
    MAX_MANIFEST_BYTES,
    AdminBridgeEntry,
    AdminBridgeListReply,
    AdminBridgeRequest,
    AdminExtensionCatalogEntry,
    AdminExtensionCatalogReply,
    AdminMemberUpdateRequest,
    AssetAccessListReply,
    AssetAccessListRequest,
    AssetAccessReply,
    AssetAccessUpdateRequest,
    AssetApproveRequest,
    AssetCoEditorRequest,
    AssetDeprecateRequest,
    AssetManifestReply,
    AssetManifestRequest,
    AssetNameRequest,
    AssetNextVersionReply,
    AssetNextVersionRequest,
    AssetOwnershipReply,
    AssetRejectRequest,
    AssetSubmissionDetailReply,
    AssetSubmissionListReply,
    AssetSubmissionListRequest,
    AssetSubmissionReply,
    AssetSubmissionRequest,
    AssetSubmitRequest,
    AssetTransferRequest,
    BridgeEnrollRequest,
    MemberCatalogEntry,
    MemberCatalogReply,
    MemberCatalogRequest,
    MemberIdentityReply,
    MemberReplacementReply,
    MemberReplaceRequest,
    MemberRevokeRequest,
    MemberSelectionReply,
    MemberSelectRequest,
)
from common.ownership import AssetNameOwnership, version_key
from control_plane.activity import BridgeActivity
from control_plane.authorization import AuthorizationError, InMemoryAuthorizationRegistry
from control_plane.distribution import entitled_in
from control_plane.enrollment import EnrollmentError, InMemoryEnrollmentRegistry
from control_plane.identity import AccessError, InMemoryAccessTokens, fingerprint
from control_plane.identity_store import SqliteIdentityStorage
from control_plane.overview import (
    AdminMemberReply,
    AdminOverviewReply,
    bridge_entries,
    member_rows,
    overview,
)
from control_plane.ownership import AssetOwnershipService, OwnershipError
from control_plane.submissions import SubmissionService
from software.marketplace import (
    ApplicationCatalog,
    ApplicationCatalogReply,
    ApplicationCatalogRequest,
    project_application,
)

MIN_SESSION_SECRET_CHARS = 32
# How long a Bridge token issued by self-enrollment works. Enrolling again
# rotates it earlier; an administrator can withdraw the computer at any time.
BRIDGE_TOKEN_LIFETIME = timedelta(days=90)

MemberErrorCode = Literal[
    "authentication_failed",
    "session_expired",
    "actor_mismatch",
    "actor_unknown",
    "actor_disabled",
    "actor_not_admitted",
    "asset_not_published",
    "asset_not_entitled",
    "kind_mismatch",
    "duplicate_selection",
    "selection_missing",
    "decision_in_future",
    "invalid_request",
    "not_administrator",
    # Asset ownership (owner decisions 2026-10-07).
    "asset_deprecated",
    "publisher_not_authorized",
    "name_missing",
    "not_name_owner",
    "ownership_changed",
    "co_editor_unknown",
    "co_editor_exists",
    "co_editor_missing",
    "owner_unchanged",
    "new_owner_unknown",
    "version_missing",
    "version_deprecated",
    "access_member_unknown",
    # Bridge self-enrollment (owner 2026-10-15, docs/phases/BRIDGE_ENROLLMENT.md).
    "device_owner_mismatch",
    "administrator_required",
    "device_disabled",
    "device_in_use",
    "device_missing",
    # Platform overview (owner 2026-10-15).
    "last_administrator",
    "artifact_too_large",
    # One-click sign-in from Agent Web (owner 2026-10-15).
    "ticket_used",
    "ticket_expired",
]

T = TypeVar("T")


class MemberError(Exception):
    def __init__(self, code: MemberErrorCode) -> None:
        self.code: MemberErrorCode = code
        super().__init__(code)


class MemberSessionGrant(RegistryContract):
    """Secret-free record of a browser session created after direct sign-in."""

    session_id: Symbol
    actor: Symbol
    method: Symbol
    fingerprint: Sha256
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    status: Literal["active", "revoked"] = "active"

    @model_validator(mode="after")
    def ends_after_issue(self) -> Self:
        if self.expires_at <= self.issued_at:
            raise ValueError("a member session must expire after it is issued")
        return self


class IssuedMemberSession:
    """The one return value that carries the opaque session secret."""

    __slots__ = ("grant", "secret")

    def __init__(self, grant: MemberSessionGrant, secret: str) -> None:
        self.grant = grant
        self.secret = secret

    @property
    def bearer(self) -> str:
        return f"{self.grant.session_id}:{self.secret}"

    def __repr__(self) -> str:
        return f"IssuedMemberSession(session_id={self.grant.session_id!r}, secret=[redacted])"


class InMemoryMemberSessions:
    """Side-effect-free session reference used behind a trusted sign-in adapter."""

    def __init__(self, *, storage: SqliteIdentityStorage | None = None) -> None:
        self._storage = storage
        self._grants = {
            item.session_id: item
            for item in (
                MemberSessionGrant.model_validate_json(raw)
                for raw in (() if storage is None else storage.records("identity_member_sessions"))
            )
        }

    def _save(self, grant: MemberSessionGrant) -> None:
        if self._storage is not None:
            self._storage.put("identity_member_sessions", grant.session_id, grant)

    def issue(
        self,
        identity: AuthenticatedActor,
        *,
        now: datetime | None = None,
        secret: str | None = None,
    ) -> IssuedMemberSession:
        who = AuthenticatedActor.model_validate(identity)
        moment = now if now is not None else datetime.now(UTC)
        if who.bridge_id is not None or who.method == ACCESS_TOKEN_METHOD:
            raise ValueError("Bridge authentication cannot become a member browser session")
        if not who.valid_at(moment):
            raise ValueError("only a current authentication can create a member session")
        value = secret if secret is not None else secrets.token_urlsafe(32)
        if len(value) < MIN_SESSION_SECRET_CHARS:
            raise ValueError("member session secret is too short")
        grant = MemberSessionGrant(
            session_id=f"member-{secrets.token_hex(8)}",
            actor=who.actor,
            method=who.method,
            fingerprint=fingerprint(value),
            issued_at=moment,
            expires_at=who.expires_at,
        )
        self._grants[grant.session_id] = grant
        self._save(grant)
        return IssuedMemberSession(grant.model_copy(deep=True), value)

    def revoke_actor(self, actor: str) -> int:
        """End every active session of one member (password reset or change,
        force sign-out). Returns how many were ended."""
        ended = 0
        for grant in list(self._grants.values()):
            if grant.actor != actor or grant.status != "active":
                continue
            revoked = MemberSessionGrant.model_validate({**grant.model_dump(), "status": "revoked"})
            self._grants[grant.session_id] = revoked
            self._save(revoked)
            ended += 1
        return ended

    def authenticate(
        self, session_id: str, secret: str, *, now: datetime | None = None
    ) -> AuthenticatedActor:
        moment = now if now is not None else datetime.now(UTC)
        grant = self._grants.get(session_id)
        expected = grant.fingerprint if grant is not None else fingerprint("")
        if grant is None or not hmac.compare_digest(expected, fingerprint(secret)):
            raise MemberError("authentication_failed")
        if grant.status != "active" or moment >= grant.expires_at:
            raise MemberError("session_expired")
        return AuthenticatedActor(
            actor=grant.actor,
            method=grant.method,
            authenticated_at=grant.issued_at,
            expires_at=grant.expires_at,
        )


_AUTHORIZATION_CODES: dict[str, MemberErrorCode] = {
    "session_expired": "session_expired",
    "actor_mismatch": "actor_mismatch",
    "actor_unknown": "actor_unknown",
    "actor_disabled": "actor_disabled",
    "actor_not_admitted": "actor_not_admitted",
    "asset_not_published": "asset_not_published",
    "asset_not_entitled": "asset_not_entitled",
    "kind_mismatch": "kind_mismatch",
    "duplicate_selection": "duplicate_selection",
    "selection_missing": "selection_missing",
    "decision_in_future": "decision_in_future",
    "asset_deprecated": "asset_deprecated",
}

_ENROLLMENT_CODES: dict[str, MemberErrorCode] = {
    "user_missing": "actor_unknown",
    "user_disabled": "actor_disabled",
    "device_missing": "device_missing",
    "device_disabled": "device_disabled",
    "duplicate_device": "device_owner_mismatch",
    "advertisement_identity_mismatch": "device_owner_mismatch",
    "binding_forbidden": "device_owner_mismatch",
    "device_single_user": "device_in_use",
    "not_administrator": "not_administrator",
    "last_administrator": "last_administrator",
}

_OWNERSHIP_CODES: dict[str, MemberErrorCode] = {
    "session_expired": "session_expired",
    "actor_unknown": "actor_unknown",
    "actor_disabled": "actor_disabled",
    "publisher_not_authorized": "publisher_not_authorized",
    "name_missing": "name_missing",
    "not_name_owner": "not_name_owner",
    "ownership_changed": "ownership_changed",
    "co_editor_unknown": "co_editor_unknown",
    "co_editor_exists": "co_editor_exists",
    "co_editor_missing": "co_editor_missing",
    "owner_unchanged": "owner_unchanged",
    "new_owner_unknown": "new_owner_unknown",
    "version_missing": "version_missing",
    "version_deprecated": "version_deprecated",
    "access_member_unknown": "access_member_unknown",
}


class MemberService:
    """Member catalog and selection operations, independent of HTTP."""

    def __init__(
        self,
        *,
        enrollment: InMemoryEnrollmentRegistry,
        authorization: InMemoryAuthorizationRegistry,
        sessions: InMemoryMemberSessions,
        applications: ApplicationCatalog | None = None,
        ownership: AssetOwnershipService | None = None,
        submissions: SubmissionService | None = None,
        tokens: InMemoryAccessTokens | None = None,
        clock: Callable[[], datetime] | None = None,
        activity: BridgeActivity | None = None,
        artifacts: Mapping[str, bytes] | None = None,
    ) -> None:
        # Published artifact bytes, for `assets/manifest`.
        self.artifacts = artifacts
        self.enrollment = enrollment
        # When each Bridge last called the Bridge API (Platform overview).
        self.activity = activity
        self.authorization = authorization
        self.sessions = sessions
        self.applications = applications if applications is not None else ApplicationCatalog()
        # Name management needs the Registry that keeps ownership records;
        # without it the entry point answers invalid_request.
        self.ownership = ownership
        # Member publish with a review queue (owner 2026-10-15); without it the
        # submission operations answer invalid_request.
        self.submissions = submissions
        # Bridge self-enrollment issues tokens; without it `bridges/enroll`
        # answers invalid_request.
        self.tokens = tokens
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._lock = threading.Lock()

    def _who(self, session_id: str, secret: str, now: datetime) -> AuthenticatedActor:
        return self.sessions.authenticate(session_id, secret, now=now)

    def now(self) -> datetime:
        return self._clock()

    def _admitted(self, who: AuthenticatedActor, bridge_id: str) -> None:
        if not self.enrollment.admit(BridgeExecutionSubject(actor=who.actor, bridge_id=bridge_id)):
            raise MemberError("actor_not_admitted")

    def identity(self, session_id: str, secret: str) -> MemberIdentityReply:
        now = self._clock()
        with self._lock:
            who = self._who(session_id, secret, now)
            member = self.enrollment.user(who.actor)
        return MemberIdentityReply(
            actor=member.actor,
            role=member.role,
            groups=member.groups,
            session_expires_at=who.expires_at,
        )

    def administrator(self, session_id: str, secret: str) -> AuthenticatedActor:
        now = self._clock()
        with self._lock:
            who = self._who(session_id, secret, now)
            member = self.enrollment.user(who.actor)
            if member.role != "platform_admin":
                raise MemberError("not_administrator")
        return who

    def extension_catalog(self, session_id: str, secret: str) -> AdminExtensionCatalogReply:
        """List governed extension packages without staging or activating them."""

        now = self._clock()
        with self._lock:
            who = self._who(session_id, secret, now)
            member = self.enrollment.user(who.actor)
            if member.role != "platform_admin":
                raise MemberError("not_administrator")
            entries = tuple(
                AdminExtensionCatalogEntry(package=package)
                for package in self.authorization.packages.discover()
                if package.kind == "bridge_extension"
                and entitled_in(
                    self.authorization.packages, package.metadata, member.actor, member.groups
                )
            )
        return AdminExtensionCatalogReply(entries=entries)

    def catalog(
        self, session_id: str, secret: str, request: MemberCatalogRequest
    ) -> MemberCatalogReply:
        item = MemberCatalogRequest.model_validate(request)
        now = self._clock()
        with self._lock:
            who = self._who(session_id, secret, now)
            self._admitted(who, item.bridge_id)
            available = self.authorization.available(who, now=now)
            selected = {
                selection.asset.key
                for selection in self.authorization.authorization(
                    item.bridge_id, issued_at=now
                ).for_actor(who.actor)
                if selection.kind in ("workflow", "skill", "knowledge", "agent")
            }
            entries = tuple(
                MemberCatalogEntry(
                    package=package,
                    selected=package.metadata.identity.key in selected,
                )
                for package in available
            )
        return MemberCatalogReply(bridge_id=item.bridge_id, entries=entries)

    def application_catalog(
        self, session_id: str, secret: str, request: ApplicationCatalogRequest
    ) -> ApplicationCatalogReply:
        """Entitled external Applications, independent of every Bridge."""
        item = ApplicationCatalogRequest.model_validate(request)
        now = self._clock()
        with self._lock:
            who = self._who(session_id, secret, now)
            member = self.enrollment.user(who.actor)
            entries = tuple(
                project_application(entry)
                for entry in self.applications.discover(item.namespace)
                if entitled(entry.software.metadata, member.actor, member.groups)
            )
        return ApplicationCatalogReply(applications=entries)

    def select(
        self, session_id: str, secret: str, request: MemberSelectRequest
    ) -> MemberSelectionReply:
        item = MemberSelectRequest.model_validate(request)
        now = self._clock()
        with self._lock:
            who = self._who(session_id, secret, now)
            package = self.authorization.packages.get(item.asset)
            if package is None:
                raise MemberError("asset_not_published")
            if package.kind not in ("workflow", "skill", "knowledge", "agent"):
                raise MemberError("kind_mismatch")
            try:
                selected = self.authorization.select(
                    who,
                    DeviceAssetSelection(
                        bridge_id=item.bridge_id,
                        actor=who.actor,
                        kind=package.kind,
                        asset=item.asset,
                        decided_at=now,
                    ),
                    now=now,
                )
            except AuthorizationError as error:
                raise MemberError(_AUTHORIZATION_CODES.get(error.code, "invalid_request")) from None
        return MemberSelectionReply(selection=selected)

    def revoke(
        self, session_id: str, secret: str, request: MemberRevokeRequest
    ) -> MemberSelectionReply:
        item = MemberRevokeRequest.model_validate(request)
        now = self._clock()
        with self._lock:
            who = self._who(session_id, secret, now)
            self._admitted(who, item.bridge_id)
            try:
                revoked = self.authorization.revoke(who, item.bridge_id, item.asset, now=now)
            except AuthorizationError as error:
                raise MemberError(_AUTHORIZATION_CODES.get(error.code, "invalid_request")) from None
        return MemberSelectionReply(selection=revoked)

    def replace(
        self, session_id: str, secret: str, request: MemberReplaceRequest
    ) -> MemberReplacementReply:
        item = MemberReplaceRequest.model_validate(request)
        now = self._clock()
        with self._lock:
            who = self._who(session_id, secret, now)
            try:
                previous, selected = self.authorization.replace(
                    who,
                    item.bridge_id,
                    item.current,
                    item.replacement,
                    now=now,
                )
            except AuthorizationError as error:
                raise MemberError(_AUTHORIZATION_CODES.get(error.code, "invalid_request")) from None
        return MemberReplacementReply(previous=previous, selection=selected)

    # -- asset names: owner management (owner decisions 2026-10-07) -------

    def _owned(
        self,
        session_id: str,
        secret: str,
        operation: Callable[[AssetOwnershipService, AuthenticatedActor, datetime], T],
    ) -> T:
        if self.ownership is None:
            raise MemberError("invalid_request")
        now = self._clock()
        with self._lock:
            who = self._who(session_id, secret, now)
            try:
                return operation(self.ownership, who, now)
            except OwnershipError as error:
                raise MemberError(_OWNERSHIP_CODES.get(error.code, "invalid_request")) from None

    def asset_ownership(
        self, session_id: str, secret: str, request: AssetNameRequest
    ) -> AssetOwnershipReply:
        item = AssetNameRequest.model_validate(request)
        record, versions = self._owned(
            session_id,
            secret,
            lambda service, who, now: service.ownership(who, item.namespace, item.name, now=now),
        )
        return AssetOwnershipReply(ownership=record, versions=versions)

    def asset_next_version(
        self, session_id: str, secret: str, request: AssetNextVersionRequest
    ) -> AssetNextVersionReply:
        item = AssetNextVersionRequest.model_validate(request)
        version = self._owned(
            session_id,
            secret,
            lambda service, who, now: service.next_version(
                who, item.namespace, item.name, item.change, now=now
            ),
        )
        return AssetNextVersionReply(namespace=item.namespace, name=item.name, version=version)

    def _ownership_reply(
        self,
        session_id: str,
        secret: str,
        item: AssetNameRequest,
        operation: Callable[[AssetOwnershipService, AuthenticatedActor, datetime], object],
    ) -> AssetOwnershipReply:
        def run(
            service: AssetOwnershipService, who: AuthenticatedActor, now: datetime
        ) -> tuple[AssetNameOwnership, tuple[str, ...]]:
            operation(service, who, now)
            return service.ownership(who, item.namespace, item.name, now=now)

        record, versions = self._owned(session_id, secret, run)
        return AssetOwnershipReply(ownership=record, versions=versions)

    def asset_add_co_editor(
        self, session_id: str, secret: str, request: AssetCoEditorRequest
    ) -> AssetOwnershipReply:
        item = AssetCoEditorRequest.model_validate(request)
        return self._ownership_reply(
            session_id,
            secret,
            item,
            lambda service, who, now: service.add_co_editor(
                who, item.namespace, item.name, item.co_editor, now=now
            ),
        )

    def asset_remove_co_editor(
        self, session_id: str, secret: str, request: AssetCoEditorRequest
    ) -> AssetOwnershipReply:
        item = AssetCoEditorRequest.model_validate(request)
        return self._ownership_reply(
            session_id,
            secret,
            item,
            lambda service, who, now: service.remove_co_editor(
                who, item.namespace, item.name, item.co_editor, now=now
            ),
        )

    def asset_transfer(
        self, session_id: str, secret: str, request: AssetTransferRequest
    ) -> AssetOwnershipReply:
        """After a transfer the former owner may no longer be able to read
        the record, so the reply is the record as the transfer left it."""
        item = AssetTransferRequest.model_validate(request)
        record = self._owned(
            session_id,
            secret,
            lambda service, who, now: service.transfer(
                who, item.namespace, item.name, item.owner, now=now
            ),
        )
        return AssetOwnershipReply(ownership=record)

    def asset_deprecate(
        self, session_id: str, secret: str, request: AssetDeprecateRequest
    ) -> AssetOwnershipReply:
        item = AssetDeprecateRequest.model_validate(request)
        return self._ownership_reply(
            session_id,
            secret,
            item,
            lambda service, who, now: service.deprecate(
                who,
                item.namespace,
                item.name,
                item.version,
                item.reason,
                replacement=item.replacement,
                now=now,
            ),
        )

    # -- who can use a published name (owner decision 2026-10-15) ---------

    def asset_access(
        self, session_id: str, secret: str, request: AssetAccessListRequest
    ) -> AssetAccessListReply:
        item = AssetAccessListRequest.model_validate(request)
        entries = self._owned(
            session_id,
            secret,
            lambda service, who, now: service.access_list(
                who, everything=item.scope == "all", now=now
            ),
        )
        return AssetAccessListReply(entries=entries)

    def asset_access_update(
        self, session_id: str, secret: str, request: AssetAccessUpdateRequest
    ) -> AssetAccessReply:
        item = AssetAccessUpdateRequest.model_validate(request)
        entry = self._owned(
            session_id,
            secret,
            lambda service, who, now: service.set_access(
                who,
                item.namespace,
                item.name,
                visibility=item.visibility,
                members=item.members,
                groups=item.groups,
                now=now,
            ),
        )
        return AssetAccessReply(entry=entry)

    # -- member publish with a review queue (owner 2026-10-15) -------------

    def _submissions(self) -> SubmissionService:
        if self.submissions is None:
            raise MemberError("invalid_request")
        return self.submissions

    def _session(self, session_id: str, secret: str) -> AuthenticatedActor:
        now = self._clock()
        with self._lock:
            return self._who(session_id, secret, now)

    def asset_submit(
        self, session_id: str, secret: str, request: AssetSubmitRequest
    ) -> AssetSubmissionReply:
        service = self._submissions()
        who = self._session(session_id, secret)
        return AssetSubmissionReply(submission=service.submit(who, request))

    def asset_submissions(self, session_id: str, secret: str) -> AssetSubmissionListReply:
        service = self._submissions()
        return service.mine(self._session(session_id, secret))

    def asset_withdraw(
        self, session_id: str, secret: str, request: AssetSubmissionRequest
    ) -> AssetSubmissionReply:
        service = self._submissions()
        item = AssetSubmissionRequest.model_validate(request)
        who = self._session(session_id, secret)
        return AssetSubmissionReply(submission=service.withdraw(who, item.submission_id))

    def review_queue(
        self, session_id: str, secret: str, request: AssetSubmissionListRequest
    ) -> AssetSubmissionListReply:
        service = self._submissions()
        item = AssetSubmissionListRequest.model_validate(request)
        self.administrator(session_id, secret)
        return service.queue(item.status)

    def review_detail(
        self, session_id: str, secret: str, request: AssetSubmissionRequest
    ) -> AssetSubmissionDetailReply:
        service = self._submissions()
        item = AssetSubmissionRequest.model_validate(request)
        self.administrator(session_id, secret)
        return service.detail(item.submission_id)

    def review_approve(
        self, session_id: str, secret: str, request: AssetApproveRequest
    ) -> AssetSubmissionReply:
        service = self._submissions()
        who = self.administrator(session_id, secret)
        return AssetSubmissionReply(submission=service.approve(who, request))

    def review_reject(
        self, session_id: str, secret: str, request: AssetRejectRequest
    ) -> AssetSubmissionReply:
        service = self._submissions()
        who = self.administrator(session_id, secret)
        return AssetSubmissionReply(submission=service.reject(who, request))

    # -- Bridge self-enrollment (owner 2026-10-15) --------------------------
    # `docs/phases/BRIDGE_ENROLLMENT.md`: a member's own Agent enrolls the
    # company workstation it runs on and gets that computer's Bridge token,
    # shown once. A shared test workstation stays an administrator's act.

    def _tokens(self) -> InMemoryAccessTokens:
        if self.tokens is None:
            raise MemberError("invalid_request")
        return self.tokens

    def enroll_bridge(
        self, session_id: str, secret: str, request: BridgeEnrollRequest
    ) -> IssuedAccessToken:
        """Register (or reuse) the member's own computer, bind them as its
        device administrator, and issue a fresh token. A token that still
        works for the same pair is revoked first, so enrolling again rotates
        it. The secret leaves only in the returned value."""
        tokens = self._tokens()
        item = BridgeEnrollRequest.model_validate(request)
        now = self._clock()
        with self._lock:
            who = self._who(session_id, secret, now)
            member = self.enrollment.user(who.actor)
            if member.status != "active":
                raise MemberError("actor_disabled")
            device = item.device
            if device.registered_by != who.actor or item.advertisement.owner_id != who.actor:
                raise MemberError("device_owner_mismatch")
            if device.device_kind != "company_workstation":
                raise MemberError("administrator_required")
            try:
                existing = self.enrollment.device(device.bridge_id)
            except EnrollmentError:
                existing = None
            try:
                if existing is None:
                    self.enrollment.register_device(device, item.advertisement)
                elif existing.registered_by != who.actor:
                    raise MemberError("device_owner_mismatch")
                elif existing.status != "active":
                    raise MemberError("device_disabled")
                else:
                    self.enrollment.advertise(device.bridge_id, item.advertisement)
                bound = any(
                    binding.actor == who.actor
                    for binding in self.enrollment.members(device.bridge_id)
                )
                if not bound:
                    self.enrollment.bind(
                        who.actor,
                        BridgeBinding(
                            bridge_id=device.bridge_id, actor=who.actor, role="device_admin"
                        ),
                    )
            except EnrollmentError as error:
                raise MemberError(_ENROLLMENT_CODES.get(error.code, "invalid_request")) from None
            try:
                tokens.revoke_for(who.actor, who.actor, device.bridge_id)
                return tokens.issue(
                    who.actor,
                    who.actor,
                    device.bridge_id,
                    issued_at=now,
                    expires_at=now + BRIDGE_TOKEN_LIFETIME,
                )
            except AccessError:
                raise MemberError("actor_not_admitted") from None

    def bridges(self, session_id: str, secret: str) -> AdminBridgeListReply:
        """Every enrolled computer, for an administrator."""
        tokens = self._tokens()
        self.administrator(session_id, secret)
        now = self._clock()
        with self._lock:
            entries = bridge_entries(
                self.enrollment, tokens, self.authorization, self.activity, now
            )
        return AdminBridgeListReply(bridges=entries)

    def disable_bridge(
        self, session_id: str, secret: str, request: AdminBridgeRequest
    ) -> AdminBridgeEntry:
        """Withdraw a computer: the device is disabled and every token it
        holds is revoked, so its Bridge is told it was withdrawn at its next
        call and its member cannot enroll it again on their own."""
        tokens = self._tokens()
        item = AdminBridgeRequest.model_validate(request)
        who = self.administrator(session_id, secret)
        with self._lock:
            try:
                self.enrollment.disable_device(who.actor, item.bridge_id)
            except EnrollmentError as error:
                raise MemberError(_ENROLLMENT_CODES.get(error.code, "invalid_request")) from None
            for grant in tokens.grants_for(item.bridge_id, now=self._clock()):
                tokens.revoke(who.actor, grant.token_id)
        for entry in self.bridges(session_id, secret).bridges:
            if entry.bridge_id == item.bridge_id:
                return entry
        raise MemberError("device_missing")

    # -- Platform overview (owner 2026-10-15) --------------------------------
    # `docs/phases/PLATFORM_OVERVIEW.md`: one read-only view of everything on
    # the platform for an administrator, and the member role and groups an
    # administrator sets so team ownership works.

    def overview(
        self,
        session_id: str,
        secret: str,
        *,
        invitation_expiry: dict[str, datetime] | None = None,
    ) -> AdminOverviewReply:
        tokens = self._tokens()
        self.administrator(session_id, secret)
        submitted = self.submissions.store.list() if self.submissions is not None else ()
        now = self._clock()
        with self._lock:
            return overview(
                enrollment=self.enrollment,
                tokens=tokens,
                authorization=self.authorization,
                packages=self.authorization.packages,
                applications=self.applications,
                submissions=submitted,
                activity=self.activity,
                invitation_expiry=invitation_expiry or {},
                now=now,
            )

    def update_member(
        self, session_id: str, secret: str, request: AdminMemberUpdateRequest
    ) -> AdminMemberReply:
        """Set a member's role and groups; audited in the enrollment record."""
        item = AdminMemberUpdateRequest.model_validate(request)
        who = self.administrator(session_id, secret)
        now = self._clock()
        with self._lock:
            try:
                self.enrollment.update_user(
                    who.actor, item.actor, role=item.role, groups=item.groups, now=now
                )
            except EnrollmentError as error:
                raise MemberError(_ENROLLMENT_CODES.get(error.code, "invalid_request")) from None
            rows = member_rows(self.enrollment, {}, now)
        return AdminMemberReply(member=next(row for row in rows if row.actor == item.actor))

    def asset_manifest(
        self, session_id: str, secret: str, request: AssetManifestRequest
    ) -> AssetManifestReply:
        """One published version and its content, for a member it is shared
        with; an administrator always. Anything else is `asset_not_published`,
        so a name is not disclosed to somebody it is not shared with."""
        item = AssetManifestRequest.model_validate(request)
        now = self._clock()
        with self._lock:
            who = self._who(session_id, secret, now)
            member = self.enrollment.user(who.actor)
            if member.status != "active":
                raise MemberError("actor_disabled")
            admin = member.role == "platform_admin"
            packages = self.authorization.packages

            def shared(metadata: AssetMetadata) -> bool:
                return admin or entitled_in(packages, metadata, member.actor, member.groups)

            package = packages.get(item.asset)
            if package is None or not shared(package.metadata):
                raise MemberError("asset_not_published")
            identity = package.metadata.identity
            versions = tuple(
                sorted(
                    (
                        other.metadata.identity.version
                        for other in packages.discover(namespace=identity.namespace)
                        if other.metadata.identity.name == identity.name and shared(other.metadata)
                    ),
                    key=version_key,
                )
            )
            record = packages.ownership(identity.namespace, identity.name)
            access = packages.access(identity.namespace, identity.name)
        artifact = package.metadata.package
        content = (
            self.artifacts.get(artifact.artifact_ref)
            if artifact is not None and self.artifacts is not None
            else None
        )
        if content is not None and len(content) > MAX_MANIFEST_BYTES:
            raise MemberError("artifact_too_large")
        manifest: object = None
        if content is not None:
            try:
                manifest = json.loads(content.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                manifest = None
        published_at = None
        if self.submissions is not None:
            for submitted in self.submissions.store.list(status="approved"):
                if submitted.identity.key == identity.key:
                    published_at = submitted.decided_at
                    break
        declared = package.metadata.visibility
        return AssetManifestReply.model_validate(
            {
                "package": package,
                "manifest": manifest if isinstance(manifest, dict) else None,
                "artifact_sha256": (
                    hashlib.sha256(content).hexdigest() if content is not None else None
                ),
                "artifact_size": len(content) if content is not None else 0,
                "owner": record.owner if record is not None else package.metadata.owner,
                "co_editors": record.co_editors if record is not None else (),
                "versions": versions,
                "visibility": (
                    access.visibility
                    if access is not None and access.visibility is not None
                    else declared
                ),
                "deprecation": (
                    record.deprecation(identity.version) if record is not None else None
                ),
                "published_at": published_at,
            }
        )
