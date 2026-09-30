"""Deployable composition for the two shared-platform entry points."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_platform_transport import WORKFLOW, Platform, trace

from capabilities.files import READ_FILE_SPEC
from common.enrollment import BridgeBinding, BridgeDevice, Invitation
from control_plane.app import (
    BootstrapInvitation,
    SharedPlatformApplication,
    SharedPlatformConfiguration,
    SharedPlatformState,
    application_from_config,
)
from control_plane.cli import _write_invitations
from workflow.host_bridge import BridgeRegistration

NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
PROOF = "a-new-member-invitation-proof-that-is-long-enough"
ROOT = Path(__file__).parents[1]


def request(
    url: str,
    *,
    authorization: str | None = None,
    body: object | None = None,
    method: str | None = None,
) -> tuple[int, dict[str, Any]]:
    raw = None if body is None else json.dumps(body).encode("utf-8")
    sent = urllib.request.Request(
        url, method=method or ("POST" if raw is not None else "GET"), data=raw
    )
    if authorization is not None:
        sent.add_header("Authorization", authorization)
    if raw is not None:
        sent.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(sent, timeout=20) as answer:
            return answer.status, json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        return refused.code, json.loads(refused.read())


def state(platform: Platform) -> SharedPlatformState:
    return SharedPlatformState(
        enrollment=platform.enrollment,
        tokens=platform.tokens,
        packages=platform.packages,
        authorization=platform.authorization,
        control=platform.control,
        artifacts=platform.artifacts,
    )


def test_configuration_is_secret_free_and_requires_tls_beyond_loopback() -> None:
    configured = SharedPlatformConfiguration(
        administrators=("platform-admin",),
        control_port=8765,
        member_port=8766,
        invitations=(
            BootstrapInvitation(
                invitation=Invitation(
                    invitation_id="invite-engineer",
                    actor="engineer",
                    issued_by="platform-admin",
                    groups=("engineering",),
                ),
                valid_for_minutes=60,
            ),
        ),
    )
    serialized = configured.model_dump_json()
    assert PROOF not in serialized
    assert "secret" not in serialized.lower()

    with pytest.raises(ValidationError, match="requires TLS"):
        SharedPlatformConfiguration(
            administrators=("platform-admin",),
            listen_host="platform.internal",
            control_port=8765,
            member_port=8766,
        )
    with pytest.raises(ValidationError, match="different ports"):
        SharedPlatformConfiguration(
            administrators=("platform-admin",), control_port=8765, member_port=8765
        )


def test_documented_shared_platform_configuration_is_valid() -> None:
    configured = SharedPlatformConfiguration.model_validate_json(
        (ROOT / "examples" / "shared-platform.json").read_text(encoding="utf-8")
    )
    assert configured.administrators == ("platform-admin",)
    assert configured.invitations[0].invitation.actor == "engineer"


def test_composition_shares_enrollment_between_member_and_bridge_http() -> None:
    platform = Platform()
    application = SharedPlatformApplication(state(platform), clock=lambda: NOW)
    proof = application.issue_invitation(
        Invitation(
            invitation_id="invite-new-member",
            actor="new-member",
            issued_by="platform-admin",
            groups=("engineering",),
        ),
        expires_at=NOW + timedelta(hours=1),
        secret=PROOF,
    )

    with application:
        assert request(application.control_base_url + "/v1/health") == (200, {"ok": True})
        assert request(application.member_base_url + "/v1/member/health") == (200, {"ok": True})

        status, signed_in = request(
            application.member_base_url + "/v1/member/sign-in",
            authorization=f"Invitation {proof.bearer}",
            method="POST",
        )
        assert status == 200

        device = BridgeDevice(
            bridge_id="bridge-new-member",
            registered_by="new-member",
            device_kind="company_workstation",
            windows_account_mode="dedicated_user",
            resource_scope="corporate_internal",
            local_isolation="single_user",
        )
        platform.enrollment.register_device(
            device,
            BridgeRegistration(
                bridge_id=device.bridge_id,
                owner_id="new-member",
                trace=trace("new-member"),
                capabilities=(READ_FILE_SPEC,),
            ),
        )
        platform.enrollment.bind(
            "new-member",
            BridgeBinding(bridge_id=device.bridge_id, actor="new-member", role="device_admin"),
        )
        token = platform.tokens.issue(
            "new-member",
            "new-member",
            device.bridge_id,
            issued_at=NOW,
            secret="a-new-member-bridge-secret-that-is-long-enough",
        )

        status, probed = request(
            application.control_base_url + "/v1/probe",
            authorization=f"Bearer {token.grant.token_id}:{token.secret}",
            body={},
        )
        assert status == 200
        assert probed["identity"]["actor"] == "new-member"
        assert probed["identity"]["bridge_id"] == device.bridge_id

        status, catalog = request(
            application.member_base_url + "/v1/member/catalog",
            authorization=f"Bearer {signed_in['session']}",
            body={"bridge_id": device.bridge_id},
        )
        assert status == 200
        workflow = next(
            entry for entry in catalog["entries"] if entry["package"]["kind"] == "workflow"
        )
        assert workflow["package"]["metadata"]["identity"] == WORKFLOW.model_dump()
        assert workflow["selected"] is False


def test_empty_composition_owns_all_reference_stores() -> None:
    application = SharedPlatformApplication.empty(administrators=("platform-admin",))
    assert application.state.tokens.enrollment is application.state.enrollment
    assert application.state.authorization.enrollment is application.state.enrollment
    assert application.state.authorization.packages is application.state.packages
    assert application.member_service.sessions is application.state.sessions
    assert application.sign_in.enrollment is application.state.enrollment


def test_bootstrap_proof_is_written_once_outside_the_secret_free_config(tmp_path: Path) -> None:
    configuration = SharedPlatformConfiguration(
        administrators=("platform-admin",),
        control_port=0,
        member_port=0,
        invitations=(
            BootstrapInvitation(
                invitation=Invitation(
                    invitation_id="invite-engineer",
                    actor="engineer",
                    issued_by="platform-admin",
                    groups=("engineering",),
                ),
                valid_for_minutes=60,
            ),
        ),
    )
    application, issued = application_from_config(configuration, clock=lambda: NOW)
    output = tmp_path / "invitation-links.json"
    try:
        _write_invitations(output, application.member_base_url, issued)
        delivery = json.loads(output.read_text(encoding="utf-8"))
        assert delivery["member_portal_url"] == application.member_base_url
        assert delivery["invitations"][0]["actor"] == "engineer"
        assert delivery["invitations"][0]["url"].startswith(
            application.member_base_url + "/#invitation=invite-engineer:"
        )
        with pytest.raises(FileExistsError):
            _write_invitations(output, application.member_base_url, issued)
    finally:
        application.stop()
