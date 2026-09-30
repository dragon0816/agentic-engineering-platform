"""One deployable composition for the shared platform's HTTP entry points.

The Bridge wire and the interactive member portal remain separate transports
and credentials.  This module gives them one lifecycle and, more importantly,
the same enrollment, authorization, package and session state.
"""

from __future__ import annotations

import ssl
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Literal, Self

from pydantic import Field, model_validator

from common.base import Contract, Symbol, Text
from common.enrollment import Invitation
from common.identity import IssuedInvitationProof
from control_plane.authorization import InMemoryAuthorizationRegistry
from control_plane.distribution import InMemoryPackageRegistry, InMemoryRemoteControl
from control_plane.enrollment import InMemoryEnrollmentRegistry
from control_plane.http import ControlPlaneServer
from control_plane.identity import InMemoryAccessTokens
from control_plane.member import InMemoryMemberSessions, MemberService
from control_plane.member_http import MemberPortalServer
from control_plane.member_signin import InMemoryInvitationSignIn
from control_plane.service import ControlPlaneService

LOOPBACK = frozenset(("127.0.0.1", "localhost", "::1"))


class BootstrapInvitation(Contract):
    """Secret-free invitation metadata created when the reference host starts."""

    invitation: Invitation
    valid_for_minutes: int = Field(ge=1, le=7 * 24 * 60, strict=True)

    @model_validator(mode="after")
    def pending_only(self) -> Self:
        if self.invitation.status != "pending":
            raise ValueError("a bootstrap invitation must be pending")
        return self


class SharedPlatformConfiguration(Contract):
    """Non-secret process configuration for the reference shared platform.

    The certificate fields are filesystem paths.  Invitation proofs and TLS
    private-key contents never belong in this contract.
    """

    schema_version: Literal["1"] = "1"
    administrators: tuple[Symbol, ...]
    listen_host: Text = "127.0.0.1"
    control_port: int = Field(default=8765, ge=0, le=65535, strict=True)
    member_port: int = Field(default=8766, ge=0, le=65535, strict=True)
    tls_certificate_path: Text | None = None
    tls_private_key_path: Text | None = None
    invitations: tuple[BootstrapInvitation, ...] = ()

    @model_validator(mode="after")
    def coherent_listener(self) -> Self:
        if not self.administrators or len(self.administrators) != len(set(self.administrators)):
            raise ValueError("administrators must be non-empty and unique")
        if self.control_port == self.member_port and self.control_port != 0:
            raise ValueError("control and member entry points need different ports")
        certificate = self.tls_certificate_path is not None
        private_key = self.tls_private_key_path is not None
        if certificate != private_key:
            raise ValueError("TLS certificate and private-key paths are configured together")
        if self.listen_host not in LOOPBACK and not certificate:
            raise ValueError("a shared platform exposed beyond loopback requires TLS")
        ids = [item.invitation.invitation_id for item in self.invitations]
        actors = [item.invitation.actor for item in self.invitations]
        if len(ids) != len(set(ids)) or len(actors) != len(set(actors)):
            raise ValueError("bootstrap invitations need unique ids and actors")
        if any(item.invitation.issued_by not in self.administrators for item in self.invitations):
            raise ValueError("a bootstrap invitation is issued by a configured administrator")
        return self


@dataclass(slots=True)
class SharedPlatformState:
    """The reference stores shared by every ingress in one platform process."""

    enrollment: InMemoryEnrollmentRegistry
    tokens: InMemoryAccessTokens
    packages: InMemoryPackageRegistry
    authorization: InMemoryAuthorizationRegistry
    control: InMemoryRemoteControl
    artifacts: Mapping[str, bytes]
    sessions: InMemoryMemberSessions = field(default_factory=InMemoryMemberSessions)

    @classmethod
    def empty(cls, *, administrators: tuple[Symbol, ...]) -> Self:
        enrollment = InMemoryEnrollmentRegistry(administrators=administrators)
        packages = InMemoryPackageRegistry()
        return cls(
            enrollment=enrollment,
            tokens=InMemoryAccessTokens(enrollment),
            packages=packages,
            authorization=InMemoryAuthorizationRegistry(enrollment, packages),
            control=InMemoryRemoteControl(admission=enrollment.admit),
            artifacts={},
            sessions=InMemoryMemberSessions(),
        )


class SharedPlatformApplication:
    """Bridge and member servers with one state and one process lifecycle."""

    def __init__(
        self,
        state: SharedPlatformState,
        *,
        host: str = "127.0.0.1",
        control_port: int = 0,
        member_port: int = 0,
        ssl_context: ssl.SSLContext | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.state = state
        moment = clock if clock is not None else lambda: datetime.now(UTC)
        sessions = state.sessions
        self.sign_in = InMemoryInvitationSignIn(
            enrollment=state.enrollment,
            sessions=sessions,
            clock=moment,
        )
        self.control_service = ControlPlaneService(
            enrollment=state.enrollment,
            tokens=state.tokens,
            packages=state.packages,
            authorization=state.authorization,
            control=state.control,
            artifacts=state.artifacts,
            clock=moment,
        )
        self.member_service = MemberService(
            enrollment=state.enrollment,
            authorization=state.authorization,
            sessions=sessions,
            clock=moment,
        )
        self.control_server = ControlPlaneServer(
            self.control_service,
            host=host,
            port=control_port,
            ssl_context=ssl_context,
        )
        try:
            self.member_server = MemberPortalServer(
                self.member_service,
                host=host,
                port=member_port,
                ssl_context=ssl_context,
                sign_in=self.sign_in,
            )
        except BaseException:
            self.control_server.server_close()
            raise
        self._started = False

    @classmethod
    def empty(
        cls,
        *,
        administrators: tuple[Symbol, ...],
        host: str = "127.0.0.1",
        control_port: int = 0,
        member_port: int = 0,
        ssl_context: ssl.SSLContext | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> Self:
        return cls(
            SharedPlatformState.empty(administrators=administrators),
            host=host,
            control_port=control_port,
            member_port=member_port,
            ssl_context=ssl_context,
            clock=clock,
        )

    @property
    def control_base_url(self) -> str:
        return self.control_server.base_url

    @property
    def member_base_url(self) -> str:
        return self.member_server.base_url

    def issue_invitation(
        self,
        invitation: Invitation,
        *,
        expires_at: datetime,
        secret: str | None = None,
    ) -> IssuedInvitationProof:
        return self.sign_in.invite(invitation, expires_at=expires_at, secret=secret)

    def invitation_url(self, proof: IssuedInvitationProof) -> str:
        return self.member_server.invitation_url(proof)

    def start(self) -> Self:
        if self._started:
            return self
        self.control_server.start()
        try:
            self.member_server.start()
        except BaseException:
            self.control_server.stop()
            raise
        self._started = True
        return self

    def stop(self) -> None:
        if self._started:
            self.member_server.stop()
            self.control_server.stop()
            self._started = False
            return
        self.member_server.server_close()
        self.control_server.server_close()

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()


def server_ssl_context(configuration: SharedPlatformConfiguration) -> ssl.SSLContext | None:
    """Load TLS only from local paths named by process configuration."""

    if configuration.tls_certificate_path is None:
        return None
    if configuration.tls_private_key_path is None:
        raise ValueError("TLS private-key path is required")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(
        configuration.tls_certificate_path,
        configuration.tls_private_key_path,
    )
    return context


def application_from_config(
    configuration: SharedPlatformConfiguration,
    *,
    clock: Callable[[], datetime] | None = None,
) -> tuple[SharedPlatformApplication, tuple[IssuedInvitationProof, ...]]:
    """Build the empty reference host and issue its configured invitations."""

    config = SharedPlatformConfiguration.model_validate(configuration)
    moment = clock if clock is not None else lambda: datetime.now(UTC)
    application = SharedPlatformApplication.empty(
        administrators=config.administrators,
        host=config.listen_host,
        control_port=config.control_port,
        member_port=config.member_port,
        ssl_context=server_ssl_context(config),
        clock=moment,
    )
    issued: list[IssuedInvitationProof] = []
    try:
        for bootstrap in config.invitations:
            now = moment()
            issued.append(
                application.issue_invitation(
                    bootstrap.invitation,
                    expires_at=now + timedelta(minutes=bootstrap.valid_for_minutes),
                )
            )
    except BaseException:
        application.stop()
        raise
    return application, tuple(issued)
