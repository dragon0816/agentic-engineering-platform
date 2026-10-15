"""A member's own Agent enrolls the company workstation it runs on.

Requirements: `docs/phases/BRIDGE_ENROLLMENT.md` (owner 2026-10-15). The
member portal route `bridges/enroll` registers or reuses the device, binds the
member as its device administrator and shows a fresh Bridge token once;
administrators list enrolled computers and can disable one. Exercised over
real HTTP against an in-process shared platform.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_member_publish import _signed_in
from test_shared_platform_app import request

from control_plane.app import SharedPlatformApplication
from control_plane.member import BRIDGE_TOKEN_LIFETIME


@pytest.fixture
def app(tmp_path: Path) -> Iterator[SharedPlatformApplication]:
    platform = SharedPlatformApplication.empty(
        administrators=("platform-admin",), registry_path=tmp_path / "registry.sqlite"
    )
    with platform:
        yield platform


def enrollment(
    actor: str, bridge_id: str = "bridge-leo-pc", *, shared: bool = False, owner: str | None = None
) -> dict[str, Any]:
    """What `aep-host enrollment-request` builds for a computer."""
    device = (
        {
            "device_kind": "shared_test_workstation",
            "windows_account_mode": "shared_user",
            "resource_scope": "external_only",
            "local_isolation": "cooperative_workspace",
        }
        if shared
        else {
            "device_kind": "company_workstation",
            "windows_account_mode": "dedicated_user",
            "resource_scope": "corporate_internal",
            "local_isolation": "single_user",
        }
    )
    return {
        "schema_version": "1",
        "device": {"bridge_id": bridge_id, "registered_by": actor, **device},
        "advertisement": {
            "bridge_id": bridge_id,
            "owner_id": owner or actor,
            "trace": {
                "trace_id": "trace-enroll",
                "request_id": "request-enroll",
                "span_id": "span-enroll",
            },
        },
    }


def enroll(
    app: SharedPlatformApplication, session: str, body: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    return request(
        app.member_base_url + "/v1/member/bridges/enroll", authorization=session, body=body
    )


def bridge(
    app: SharedPlatformApplication, operation: str, token: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    return request(
        app.control_base_url + f"/v1/{operation}",
        authorization=f"Bearer {token['token_id']}:{token['secret']}",
        body={},
    )


def test_a_member_enrolls_their_own_workstation_and_the_token_works_over_http(
    app: SharedPlatformApplication,
) -> None:
    leo = _signed_in(app, "leo", "member")
    before = datetime.now(UTC)
    status, token = enroll(app, leo, enrollment("leo"))
    assert status == 200, token
    assert token["bridge_id"] == "bridge-leo-pc" and token["token_id"].startswith("token-")
    assert len(token["secret"]) >= 32
    expires = datetime.fromisoformat(token["expires_at"])
    assert before + BRIDGE_TOKEN_LIFETIME <= expires <= datetime.now(UTC) + BRIDGE_TOKEN_LIFETIME

    # The member is the device administrator of a computer they registered.
    members = app.state.enrollment.members("bridge-leo-pc")
    assert [(item.actor, item.role) for item in members] == [("leo", "device_admin")]
    # The platform keeps a fingerprint, never the secret.
    assert token["secret"] not in app.state.tokens.grant(token["token_id"]).model_dump_json()

    status, probed = bridge(app, "probe", token)
    assert status == 200 and probed["identity"]["actor"] == "leo"
    assert probed["identity"]["bridge_id"] == "bridge-leo-pc"
    status, catalog = bridge(app, "catalog", token)
    assert status == 200 and catalog["packages"] == []

    # The member can now select for this Bridge in the portal.
    status, _ = request(
        app.member_base_url + "/v1/member/catalog",
        authorization=leo,
        body={"bridge_id": "bridge-leo-pc"},
    )
    assert status == 200


def test_enrolling_again_rotates_the_token(app: SharedPlatformApplication) -> None:
    leo = _signed_in(app, "leo", "member")
    first = enroll(app, leo, enrollment("leo"))[1]
    status, second = enroll(app, leo, enrollment("leo"))
    assert status == 200 and second["token_id"] != first["token_id"]
    status, refused = bridge(app, "probe", first)
    assert status != 200 and refused["code"] == "token_revoked"
    assert bridge(app, "probe", second)[0] == 200
    # Still one binding, and the device was reused, not duplicated.
    assert len(app.state.enrollment.members("bridge-leo-pc")) == 1
    assert [d.bridge_id for d in app.state.enrollment.devices()] == ["bridge-leo-pc"]


def test_a_member_cannot_enroll_somebody_elses_computer(app: SharedPlatformApplication) -> None:
    leo = _signed_in(app, "leo", "member")
    ann = _signed_in(app, "ann", "member")
    assert enroll(app, leo, enrollment("ann")) == (403, {"code": "device_owner_mismatch"})
    assert enroll(app, leo, enrollment("leo", owner="ann")) == (
        403,
        {"code": "device_owner_mismatch"},
    )
    # Ann's computer, once enrolled, cannot be claimed by Leo under his name.
    assert enroll(app, ann, enrollment("ann", "bridge-shared-id"))[0] == 200
    assert enroll(app, leo, enrollment("leo", "bridge-shared-id")) == (
        403,
        {"code": "device_owner_mismatch"},
    )
    assert [b.actor for b in app.state.enrollment.members("bridge-shared-id")] == ["ann"]


def test_a_shared_test_workstation_stays_an_administrators_act(
    app: SharedPlatformApplication,
) -> None:
    leo = _signed_in(app, "leo", "member")
    assert enroll(app, leo, enrollment("leo", shared=True)) == (
        403,
        {"code": "administrator_required"},
    )
    assert app.state.enrollment.devices() == ()


def test_a_disabled_member_cannot_enroll(app: SharedPlatformApplication) -> None:
    leo = _signed_in(app, "leo", "member")
    app.state.enrollment.disable_user("platform-admin", "leo")
    assert enroll(app, leo, enrollment("leo")) == (403, {"code": "actor_disabled"})
    assert app.state.enrollment.devices() == ()


def test_enrollment_needs_a_member_session_and_a_well_formed_body(
    app: SharedPlatformApplication,
) -> None:
    assert enroll(app, "Bearer nobody:nothing", enrollment("leo"))[0] == 401
    leo = _signed_in(app, "leo", "member")
    body = enrollment("leo")
    body["device"]["token"] = "smuggled"
    assert enroll(app, leo, body) == (400, {"code": "invalid_request"})


def test_administrators_list_and_disable_enrolled_bridges(
    app: SharedPlatformApplication,
) -> None:
    url = app.member_base_url + "/v1/member/admin/bridges/"
    leo = _signed_in(app, "leo", "member")
    admin = _signed_in(app, "leo-admin", "platform_admin")
    token = enroll(app, leo, enrollment("leo"))[1]

    assert request(url + "list", authorization=leo, body={})[0] == 403
    status, listed = request(url + "list", authorization=admin, body={})
    assert status == 200
    [entry] = listed["bridges"]
    assert entry["bridge_id"] == "bridge-leo-pc" and entry["members"] == ["leo"]
    assert entry["status"] == "active" and entry["registered_by"] == "leo"
    assert datetime.fromisoformat(entry["token_expires_at"]) == datetime.fromisoformat(
        token["expires_at"]
    )
    assert entry["enrolled_at"] is not None

    assert (
        request(url + "disable", authorization=leo, body={"bridge_id": "bridge-leo-pc"})[0] == 403
    )
    status, disabled = request(
        url + "disable", authorization=admin, body={"bridge_id": "bridge-leo-pc"}
    )
    assert status == 200 and disabled["status"] == "disabled"
    assert disabled["token_expires_at"] is None  # its token was revoked
    status, refused = bridge(app, "probe", token)
    assert status != 200 and refused["code"] in ("token_revoked", "binding_withdrawn")
    # Withdrawn means withdrawn: the member cannot enroll it again alone.
    assert enroll(app, leo, enrollment("leo")) == (409, {"code": "device_disabled"})
    assert request(url + "disable", authorization=admin, body={"bridge_id": "bridge-none"}) == (
        404,
        {"code": "device_missing"},
    )


def test_enrollment_survives_a_platform_restart(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    first = SharedPlatformApplication.empty(administrators=("platform-admin",), registry_path=path)
    with first:
        token = enroll(first, _signed_in(first, "leo", "member"), enrollment("leo"))[1]
    again = SharedPlatformApplication.empty(administrators=("platform-admin",), registry_path=path)
    with again:
        status, probed = bridge(again, "probe", token)
        assert status == 200 and probed["identity"]["actor"] == "leo"


def test_the_portal_lists_bridges_for_administrators_and_reads_the_agents_bridge() -> None:
    from control_plane.member_page import PAGE

    for hook in (
        'id="bridges"',
        'id="bridge-rows"',
        "/v1/member/admin/bridges/list",
        "/v1/member/admin/bridges/disable",
        'fragment.get("bridge")',
    ):
        assert hook in PAGE
    assert timedelta(days=30) < BRIDGE_TOKEN_LIFETIME
