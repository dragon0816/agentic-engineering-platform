"""The token a Bridge presents to say who it is acting for.

Requirements: `docs/phases/PHASE_7_MIGRATION.md`, slice 2b. Binding a member
to a machine issues a token for that pair; several members on one machine hold
several tokens. Nothing here opens a socket, and the platform never stores a
secret.
"""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from common.assets import AssetIdentity, AssetMetadata, Owner, PackageMetadata
from common.authorization import DeviceAssetSelection
from common.base import Contract
from common.distribution import PublishedAssetPackage
from common.enrollment import BridgeBinding, BridgeDevice, Invitation
from common.execution import TraceIdentifiers
from common.identity import ACCESS_TOKEN_METHOD, BridgeAccessGrant, IssuedAccessToken
from control_plane.authorization import InMemoryAuthorizationRegistry
from control_plane.distribution import InMemoryPackageRegistry
from control_plane.enrollment import EnrollmentError, InMemoryEnrollmentRegistry
from control_plane.identity import AccessError, InMemoryAccessTokens, fingerprint
from workflow.host_bridge import BridgeRegistration

NOW = datetime(2026, 9, 23, 9, 0, tzinfo=UTC)
REPORT = AssetIdentity(namespace="engineering", name="weekly-report", version="1.0.0")
LONG_ENOUGH = "a-supplied-secret-that-is-long-enough-to-be-one"


def device(kind: str) -> BridgeDevice:
    profile = {
        "company_workstation": (
            "bridge-company",
            "dedicated_user",
            "corporate_internal",
            "single_user",
        ),
        "shared_test_workstation": (
            "bridge-shared",
            "shared_user",
            "external_only",
            "cooperative_workspace",
        ),
    }[kind]
    return BridgeDevice.model_validate(
        {
            "bridge_id": profile[0],
            "registered_by": "engineer",
            "device_kind": kind,
            "windows_account_mode": profile[1],
            "resource_scope": profile[2],
            "local_isolation": profile[3],
        }
    )


def platform() -> tuple[InMemoryEnrollmentRegistry, InMemoryAccessTokens]:
    """Two invited members, a company machine bound to its owner and a shared
    machine bound to both of them."""
    enrollment = InMemoryEnrollmentRegistry(administrators=("platform-admin",))
    for actor in ("engineer", "tester"):
        enrollment.issue(
            Invitation(
                invitation_id=f"invite-{actor}",
                actor=actor,
                issued_by="platform-admin",
                groups=("engineering",),
            )
        )
        enrollment.accept(f"invite-{actor}", actor)
    for kind in ("company_workstation", "shared_test_workstation"):
        described = device(kind)
        enrollment.register_device(
            described,
            BridgeRegistration(
                bridge_id=described.bridge_id,
                owner_id="engineer",
                trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
            ),
        )
        enrollment.bind(
            "engineer",
            BridgeBinding(bridge_id=described.bridge_id, actor="engineer", role="device_admin"),
        )
    enrollment.bind(
        "engineer", BridgeBinding(bridge_id="bridge-shared", actor="tester", role="operator")
    )
    return enrollment, InMemoryAccessTokens(enrollment)


def issued(
    tokens: InMemoryAccessTokens, actor: str, bridge_id: str, **changes: Any
) -> IssuedAccessToken:
    return tokens.issue(actor, bridge_id, **{"issued_at": NOW, **changes})


def test_a_token_is_issued_only_for_a_member_the_platform_admits() -> None:
    enrollment, tokens = platform()
    # The tester is a member of the shared machine, not the company one.
    with pytest.raises(AccessError, match="actor_not_admitted"):
        issued(tokens, "tester", "bridge-company")
    with pytest.raises(AccessError, match="actor_not_admitted"):
        issued(tokens, "stranger", "bridge-shared")
    issued(tokens, "engineer", "bridge-company")
    with pytest.raises(AccessError, match="duplicate_token"):
        issued(tokens, "engineer", "bridge-company")
    # A short secret is a password wearing a token's name.
    with pytest.raises(AccessError, match="weak_secret"):
        issued(tokens, "tester", "bridge-shared", secret="hunter2")
    assert enrollment.members("bridge-shared")


def test_several_members_on_one_machine_hold_several_tokens() -> None:
    _, tokens = platform()
    mine = issued(tokens, "engineer", "bridge-shared")
    theirs = issued(tokens, "tester", "bridge-shared")
    assert mine.secret != theirs.secret
    assert mine.grant.fingerprint != theirs.grant.fingerprint
    assert mine.grant.token_id != theirs.grant.token_id
    held = tokens.grants_for("bridge-shared")
    assert {item.actor for item in held} == {"engineer", "tester"}
    assert all(item.bridge_id == "bridge-shared" for item in held)
    # Each one authenticates as exactly the member it was issued for.
    assert tokens.authenticate(mine.grant.token_id, mine.secret, now=NOW).actor == "engineer"
    assert tokens.authenticate(theirs.grant.token_id, theirs.secret, now=NOW).actor == "tester"


def test_the_platform_keeps_a_fingerprint_and_never_the_secret() -> None:
    _, tokens = platform()
    token = issued(tokens, "engineer", "bridge-company", secret=LONG_ENOUGH)
    assert token.grant.fingerprint == hashlib.sha256(LONG_ENOUGH.encode()).hexdigest()
    assert LONG_ENOUGH not in token.grant.model_dump_json()
    assert LONG_ENOUGH not in tokens.grant(token.grant.token_id).model_dump_json()
    # The value is not something the platform can serialize, validate or log.
    assert not isinstance(token, Contract)
    assert not hasattr(token, "model_dump")
    assert LONG_ENOUGH not in repr(token) and "[redacted]" in repr(token)
    with pytest.raises(AttributeError):
        token.stolen = LONG_ENOUGH  # type: ignore[attr-defined]
    # A grant that expired before it was issued was never usable.
    with pytest.raises(ValidationError, match="never usable"):
        BridgeAccessGrant.model_validate(
            {**token.grant.model_dump(), "expires_at": NOW - timedelta(hours=1)}
        )


def test_an_unknown_token_and_a_wrong_secret_are_the_same_answer() -> None:
    _, tokens = platform()
    token = issued(tokens, "engineer", "bridge-company", secret=LONG_ENOUGH)
    with pytest.raises(AccessError) as wrong:
        tokens.authenticate(token.grant.token_id, "not-the-secret-but-long-enough-to-try", now=NOW)
    with pytest.raises(AccessError) as unknown:
        tokens.authenticate("token-does-not-exist", LONG_ENOUGH, now=NOW)
    with pytest.raises(AccessError) as empty:
        tokens.authenticate("token-does-not-exist", "", now=NOW)
    assert wrong.value.code == unknown.value.code == empty.value.code == "authentication_failed"


def test_the_holder_of_a_real_secret_is_told_what_is_wrong() -> None:
    enrollment, tokens = platform()
    token = issued(tokens, "engineer", "bridge-shared", secret=LONG_ENOUGH)
    ending = issued(
        tokens,
        "tester",
        "bridge-shared",
        secret=LONG_ENOUGH + "-tester",
        expires_at=NOW + timedelta(hours=1),
    )
    with pytest.raises(AccessError, match="token_expired"):
        tokens.authenticate(ending.grant.token_id, ending.secret, now=NOW + timedelta(hours=2))
    tokens.revoke(token.grant.token_id)
    with pytest.raises(AccessError, match="token_revoked"):
        tokens.authenticate(token.grant.token_id, LONG_ENOUGH, now=NOW)
    # A member the platform no longer admits on that machine, whether the
    # binding was withdrawn or the member was disabled.
    enrollment.disable_user("platform-admin", "tester")
    with pytest.raises(AccessError, match="binding_withdrawn"):
        tokens.authenticate(ending.grant.token_id, ending.secret, now=NOW)
    # And the wrong secret still says nothing about any of that.
    with pytest.raises(AccessError, match="authentication_failed"):
        tokens.authenticate(token.grant.token_id, "another-secret-that-is-long-enough", now=NOW)


def test_a_session_ends_no_later_than_its_token() -> None:
    _, tokens = platform()
    token = issued(tokens, "engineer", "bridge-company", expires_at=NOW + timedelta(minutes=10))
    identity = tokens.authenticate(token.grant.token_id, token.secret, now=NOW)
    assert identity.expires_at == NOW + timedelta(minutes=10)
    assert identity.method == ACCESS_TOKEN_METHOD and identity.authenticated_at == NOW
    assert identity.valid_at(NOW) and not identity.valid_at(NOW + timedelta(minutes=11))
    # Without an expiry on the token the session is the default window.
    forever = issued(tokens, "engineer", "bridge-shared")
    assert tokens.authenticate(forever.grant.token_id, forever.secret, now=NOW).expires_at == (
        NOW + timedelta(hours=1)
    )


def test_unbinding_revokes_what_the_binding_justified() -> None:
    enrollment, tokens = platform()
    shared = issued(tokens, "tester", "bridge-shared", secret=LONG_ENOUGH)
    company = issued(tokens, "engineer", "bridge-company", secret=LONG_ENOUGH + "-mine")
    enrollment.unbind("engineer", "bridge-shared", "tester")
    assert tokens.revoke_for("tester", "bridge-shared")[0].status == "revoked"
    with pytest.raises(AccessError, match="token_revoked"):
        tokens.authenticate(shared.grant.token_id, shared.secret, now=NOW)
    assert tokens.grants_for("bridge-shared") == ()
    # A token for another pair is untouched: revocation is per member and
    # machine, which is the point of issuing one per pair.
    assert tokens.authenticate(company.grant.token_id, company.secret, now=NOW).actor == "engineer"
    with pytest.raises(EnrollmentError, match="binding_missing"):
        enrollment.unbind("engineer", "bridge-shared", "tester")
    with pytest.raises(EnrollmentError, match="binding_forbidden"):
        enrollment.unbind("tester", "bridge-company", "engineer")


def test_a_token_becomes_the_identity_that_decides_what_a_member_may_use() -> None:
    """The whole chain: a secret the Bridge holds becomes an authenticated
    actor, which decides what that member may use, which is what they may
    then choose for their machine."""
    enrollment, tokens = platform()
    packages = InMemoryPackageRegistry()
    packages.publish(
        PublishedAssetPackage(
            kind="workflow",
            metadata=AssetMetadata(
                identity=REPORT,
                owner=Owner(type="team", id="engineering"),
                visibility="organization",
                lifecycle="published",
                package=PackageMetadata(
                    artifact_ref="registry://engineering/weekly-report/1.0.0",
                    sha256=hashlib.sha256(b"report").hexdigest(),
                ),
            ),
        )
    )
    decisions = InMemoryAuthorizationRegistry(enrollment, packages)
    token = issued(tokens, "engineer", "bridge-company")
    identity = tokens.authenticate(token.grant.token_id, token.secret, now=NOW)
    assert [item.metadata.identity.name for item in decisions.available(identity, now=NOW)] == [
        "weekly-report"
    ]
    recorded = decisions.select(
        identity,
        DeviceAssetSelection(
            bridge_id="bridge-company",
            actor="engineer",
            kind="workflow",
            asset=REPORT,
            decided_at=NOW,
        ),
        now=NOW,
    )
    assert recorded.actor == "engineer"
    assert decisions.authorization("bridge-company", issued_at=NOW).selections == (recorded,)


def test_an_issued_token_is_only_ever_handed_over_once() -> None:
    """The platform has no way to answer `what was the secret`, because it
    never had it: only the fingerprint is kept."""
    _, tokens = platform()
    token = issued(tokens, "engineer", "bridge-company", secret=LONG_ENOUGH)
    stored = tokens.grant(token.grant.token_id)
    assert not hasattr(stored, "secret")
    assert stored.fingerprint == fingerprint(LONG_ENOUGH)
    assert isinstance(token, IssuedAccessToken)
