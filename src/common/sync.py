"""The messages a Bridge and the shared platform exchange.

Six operations, each presented with the Bridge's access token and each
answered with a closed contract: a read-only probe, an advertisement of what
the Bridge can run, a synchronization of what its member decided it may run,
a report of its authoritative state, a poll for the jobs waiting for it, and
the settlement of one of them. Nothing member-facing is here: a Bridge acts as
the one member it is bound to, and a member signs in somewhere else.

No contract on this wire has a field a secret could be put in. The token's
secret travels in a header and nowhere else, and the artifact bytes a sync
carries are Skill and Workflow manifests, which the Registry already refuses
to hold with a credential in them.
"""

import base64
import binascii
from typing import Literal, Self

from pydantic import AwareDatetime, Field, StrictBool, field_validator, model_validator

from common.assets import AssetIdentity, reject_embedded_secrets
from common.authorization import DeviceAuthorization
from common.base import Contract, Symbol, Text
from common.distribution import (
    BridgeStateSnapshot,
    InstallationPlan,
    LocalRunSummary,
    RemoteJobRecord,
)
from common.identity import AuthenticatedActor
from workflow.host_bridge import BridgeRegistration

# The operations, as they appear in a path. A name not in this list is not an
# operation, whatever the caller thinks.
Operation = Literal["probe", "advertise", "sync", "report", "poll", "settle"]
OPERATIONS: tuple[Operation, ...] = ("probe", "advertise", "sync", "report", "poll", "settle")

WireErrorCode = Literal[
    # Who is asking. The first is the only answer somebody without the secret
    # ever gets; the next three are told only to a Bridge that proved it.
    "authentication_failed",
    "token_revoked",
    "token_expired",
    "binding_withdrawn",
    # The token is real and the payload names another machine.
    "device_mismatch",
    # The request itself.
    "invalid_request",
    "unknown_operation",
    "request_too_large",
    # The platform's own records.
    "package_missing",
    "artifact_missing",
    "job_missing",
    "job_settled",
    "job_mismatch",
    "internal_error",
]

# Told only to a Bridge that proved its secret: the platform no longer lets
# this machine act as this member. These, and nothing else, mean revoked.
WITHDRAWN: frozenset[str] = frozenset({"token_revoked", "token_expired", "binding_withdrawn"})


class WireFailure(Contract):
    """Why the platform declined. The code is the whole message: nothing a
    Bridge sent is echoed back, and nothing about another device is said."""

    code: WireErrorCode
    retryable: StrictBool = False


class ProbeReply(Contract):
    """Who the platform decided this Bridge is, and its own clock, so an
    operator can see both at once. Read-only on both sides."""

    identity: AuthenticatedActor
    platform_time: AwareDatetime

    @model_validator(mode="after")
    def made_on_a_device(self) -> Self:
        if self.identity.bridge_id is None:
            raise ValueError("a Bridge's authentication names the Bridge")
        return self


class AdvertiseRequest(Contract):
    registration: BridgeRegistration


class AdvertiseReply(Contract):
    bridge_id: Symbol
    capabilities: int = Field(ge=0, strict=True)


class SyncRequest(Contract):
    """What this Bridge has installed already, so the platform sends only
    what it lacks. Saying so is not a claim of authority: the platform still
    decides what the device may run, and the Bridge still verifies the bytes."""

    installed: tuple[AssetIdentity, ...] = ()

    @model_validator(mode="after")
    def each_once(self) -> Self:
        keys = [item.key for item in self.installed]
        if len(keys) != len(set(keys)):
            raise ValueError("an installed asset is listed once")
        return self


class ArtifactPayload(Contract):
    """The bytes of one package artifact, base64 in both directions so the
    contract reads the same in Python and on the wire. The Bridge verifies
    the digest before it looks at the content."""

    artifact_ref: Text
    content: str

    @field_validator("content")
    @classmethod
    def base64_text(cls, value: str) -> str:
        try:
            base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("artifact content is base64") from None
        return value

    @classmethod
    def of(cls, artifact_ref: str, raw: bytes) -> Self:
        return cls(artifact_ref=artifact_ref, content=base64.b64encode(raw).decode("ascii"))

    @property
    def raw(self) -> bytes:
        return base64.b64decode(self.content, validate=True)


class SyncReply(Contract):
    """The device's decisions in force, and what to install to honour them.

    The plan covers what the Bridge said it does not have; the artifacts are
    exactly the plan's bytes. A plan with no bytes could not be verified and
    bytes with no plan could not be placed, so both are refused here rather
    than discovered on the Bridge."""

    authorization: DeviceAuthorization
    plan: InstallationPlan | None = None
    artifacts: tuple[ArtifactPayload, ...] = ()

    @model_validator(mode="after")
    def bytes_for_the_plan_and_nothing_else(self) -> Self:
        refs = [item.artifact_ref for item in self.artifacts]
        if len(refs) != len(set(refs)):
            raise ValueError("an artifact is carried once")
        if self.plan is None:
            if self.artifacts:
                raise ValueError("artifacts without a plan have nowhere to go")
            return self
        if self.plan.bridge_id != self.authorization.bridge_id:
            raise ValueError("a plan installs onto the device the authorization is for")
        wanted = {
            item.metadata.package.artifact_ref
            for item in self.plan.packages
            if item.metadata.package is not None
        }
        if wanted != set(refs):
            raise ValueError("a sync carries the bytes of every planned package and no others")
        return self


class ReportRequest(Contract):
    snapshot: BridgeStateSnapshot


class ReportReply(Contract):
    received_at: AwareDatetime


class PollRequest(Contract):
    limit: int = Field(default=10, ge=1, le=50, strict=True)


class PollReply(Contract):
    jobs: tuple[RemoteJobRecord, ...] = ()

    @model_validator(mode="after")
    def open_jobs_only(self) -> Self:
        if any(not item.open for item in self.jobs):
            raise ValueError("a poll offers the jobs still waiting to be done")
        return self


JobDisposition = Literal["ran", "rejected", "cancelled"]


class SettleRequest(Contract):
    """How one job ended on the Bridge. `ran` carries the run the Bridge
    recorded; `rejected` means the Agent refused it or the engine answered
    before starting anything; `cancelled` means the platform had asked for
    that before the Bridge got to it."""

    job_id: Symbol
    disposition: JobDisposition
    run: LocalRunSummary | None = None

    @model_validator(mode="after")
    def a_run_when_it_ran(self) -> Self:
        if (self.disposition == "ran") != (self.run is not None):
            raise ValueError("a job that ran carries its run, and only that one does")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class SettleReply(Contract):
    job: RemoteJobRecord
