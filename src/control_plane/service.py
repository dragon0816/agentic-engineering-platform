"""The shared platform's side of the Bridge wire, transport-agnostic.

Every operation takes a token id and a secret, decides who is asking through
the access-token reference, and acts only on the device that token was issued
for. The service knows nothing about HTTP: a test drives it directly, and the
server in `control_plane.http` hands it what it parsed. It serves the
in-memory references; a durable platform store is a later slice.

The rules that must hold whatever carries the request: a payload naming
another device is refused whatever it says; a Bridge that has not proved its
secret learns nothing but that; and nothing in an answer echoes a request.
"""

import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from pydantic import ValidationError

from common.base import Contract
from common.identity import AuthenticatedActor
from common.sync import (
    OPERATIONS,
    AdvertiseReply,
    AdvertiseRequest,
    ArtifactPayload,
    Operation,
    PollReply,
    PollRequest,
    ProbeReply,
    ReportReply,
    ReportRequest,
    SettleReply,
    SettleRequest,
    SyncReply,
    SyncRequest,
    WireErrorCode,
)
from control_plane.authorization import InMemoryAuthorizationRegistry
from control_plane.distribution import ControlError, InMemoryPackageRegistry, InMemoryRemoteControl
from control_plane.enrollment import EnrollmentError, InMemoryEnrollmentRegistry
from control_plane.identity import AccessError, InMemoryAccessTokens

# The HTTP status each refusal deserves, kept beside the codes so the server
# and a reader of the wire agree without a second table.
STATUS_FOR: dict[WireErrorCode, int] = {
    "authentication_failed": 401,
    "token_revoked": 401,
    "token_expired": 401,
    "binding_withdrawn": 401,
    "device_mismatch": 403,
    "invalid_request": 400,
    "unknown_operation": 404,
    "request_too_large": 413,
    "package_missing": 409,
    "artifact_missing": 409,
    "job_missing": 404,
    "job_settled": 409,
    "job_mismatch": 409,
    "internal_error": 500,
}

# The access reference's vocabulary, in the wire's.
_ACCESS_CODES: dict[str, WireErrorCode] = {
    "authentication_failed": "authentication_failed",
    "token_revoked": "token_revoked",
    "token_expired": "token_expired",
    "binding_withdrawn": "binding_withdrawn",
}

# The control reference's vocabulary, in the wire's.
_CONTROL_CODES: dict[str, WireErrorCode] = {
    "job_missing": "job_missing",
    "job_settled": "job_settled",
    "job_bridge_mismatch": "device_mismatch",
    "job_run_mismatch": "job_mismatch",
    "package_missing": "package_missing",
}


class ServiceError(Exception):
    def __init__(self, code: WireErrorCode) -> None:
        self.code: WireErrorCode = code
        super().__init__(code)


class ControlPlaneService:
    """One lock around the references, because the HTTP server answers on
    several threads and the references were written for one."""

    def __init__(
        self,
        *,
        enrollment: InMemoryEnrollmentRegistry,
        tokens: InMemoryAccessTokens,
        packages: InMemoryPackageRegistry,
        authorization: InMemoryAuthorizationRegistry,
        control: InMemoryRemoteControl,
        artifacts: Mapping[str, bytes],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.enrollment = enrollment
        self.tokens = tokens
        self.packages = packages
        self.authorization = authorization
        self.control = control
        self._artifacts = artifacts
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._lock = threading.Lock()

    def _who(self, token_id: str, secret: str, now: datetime) -> tuple[AuthenticatedActor, str]:
        try:
            who = self.tokens.authenticate(token_id, secret, now=now)
        except AccessError as error:
            # The access reference's answers are the wire's own: a Bridge
            # that did not prove the secret is told nothing else, and one
            # that did is told what is actually wrong.
            raise ServiceError(_ACCESS_CODES.get(error.code, "authentication_failed")) from None
        if who.bridge_id is None:  # a token is always issued for a device
            raise ServiceError("authentication_failed")
        return who, who.bridge_id

    def probe(self, token_id: str, secret: str) -> ProbeReply:
        """Read-only: who this Bridge is to the platform, and the platform's
        clock. Changes nothing on either side."""
        now = self._clock()
        with self._lock:
            who, _ = self._who(token_id, secret, now)
        return ProbeReply(identity=who, platform_time=now)

    def advertise(self, token_id: str, secret: str, request: AdvertiseRequest) -> AdvertiseReply:
        item = AdvertiseRequest.model_validate(request)
        with self._lock:
            _, device = self._who(token_id, secret, self._clock())
            if item.registration.bridge_id != device:
                raise ServiceError("device_mismatch")
            try:
                saved = self.enrollment.advertise(device, item.registration)
            except EnrollmentError as error:
                if error.code == "advertisement_identity_mismatch":
                    raise ServiceError("invalid_request") from None
                raise ServiceError("device_mismatch") from None
        return AdvertiseReply(bridge_id=saved.bridge_id, capabilities=len(saved.capabilities))

    def synchronize(self, token_id: str, secret: str, request: SyncRequest) -> SyncReply:
        """The device's decisions in force, and the bytes for whatever its
        member chose that the Bridge does not have yet."""
        item = SyncRequest.model_validate(request)
        now = self._clock()
        with self._lock:
            who, device = self._who(token_id, secret, now)
            bundle = self.authorization.authorization(device, issued_at=now)
            present = {asset.key for asset in item.installed}
            wanted = tuple(
                selection.asset
                for selection in bundle.installable()
                if selection.asset.key not in present
            )
            if not wanted:
                return SyncReply(authorization=bundle)
            try:
                plan = self.packages.plan(actor=who.actor, bridge_id=device, requested=wanted)
            except ControlError as error:
                raise ServiceError(_CONTROL_CODES.get(error.code, "internal_error")) from None
            payloads: list[ArtifactPayload] = []
            for package in plan.packages:
                artifact = package.metadata.package
                content = self._artifacts.get(artifact.artifact_ref) if artifact else None
                if artifact is None or content is None:
                    raise ServiceError("artifact_missing")
                payloads.append(ArtifactPayload.of(artifact.artifact_ref, content))
        return SyncReply(authorization=bundle, plan=plan, artifacts=tuple(payloads))

    def report(self, token_id: str, secret: str, request: ReportRequest) -> ReportReply:
        item = ReportRequest.model_validate(request)
        now = self._clock()
        with self._lock:
            _, device = self._who(token_id, secret, now)
            if item.snapshot.device.bridge_id != device:
                raise ServiceError("device_mismatch")
            try:
                projection = self.control.report(item.snapshot, received_at=now)
            except ValidationError:
                # A snapshot observed after the platform's own clock says
                # now; the projection contract refuses it.
                raise ServiceError("invalid_request") from None
        return ReportReply(received_at=projection.received_at)

    def poll(self, token_id: str, secret: str, request: PollRequest) -> PollReply:
        item = PollRequest.model_validate(request)
        with self._lock:
            _, device = self._who(token_id, secret, self._clock())
            jobs = self.control.poll(device, limit=item.limit)
        return PollReply(jobs=jobs)

    def settle(self, token_id: str, secret: str, request: SettleRequest) -> SettleReply:
        item = SettleRequest.model_validate(request)
        with self._lock:
            _, device = self._who(token_id, secret, self._clock())
            try:
                record = self.control.settle(
                    device, item.job_id, disposition=item.disposition, run=item.run
                )
            except ControlError as error:
                raise ServiceError(_CONTROL_CODES.get(error.code, "internal_error")) from None
        return SettleReply(job=record)

    def handle(self, operation: str, token_id: str, secret: str, body: object) -> Contract:
        """One entry for a transport: the operation by name, the credential
        as presented, the body as parsed. Every refusal is a `ServiceError`;
        a body that is not the operation's request is `invalid_request`."""
        if operation not in OPERATIONS:
            raise ServiceError("unknown_operation")
        named: Operation = operation
        try:
            if named == "probe":
                return self.probe(token_id, secret)
            if named == "advertise":
                return self.advertise(token_id, secret, AdvertiseRequest.model_validate(body))
            if named == "sync":
                return self.synchronize(token_id, secret, SyncRequest.model_validate(body))
            if named == "report":
                return self.report(token_id, secret, ReportRequest.model_validate(body))
            if named == "poll":
                return self.poll(token_id, secret, PollRequest.model_validate(body))
            return self.settle(token_id, secret, SettleRequest.model_validate(body))
        except ValidationError:
            raise ServiceError("invalid_request") from None
