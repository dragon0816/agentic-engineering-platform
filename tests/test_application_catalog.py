"""Productization 3 slice 4: independent, entitled Application discovery."""

import json
import urllib.error
import urllib.request
from datetime import timedelta
from typing import Any

from test_platform_transport import NOW, Platform

from common.identity import AuthenticatedActor
from control_plane.member import InMemoryMemberSessions, MemberService
from control_plane.member_http import MemberPortalServer
from software.evolution import SoftwareManifest
from software.marketplace import (
    ApplicationCatalog,
    ApplicationCatalogEntry,
    ApplicationIntegration,
)

REVISION = "a" * 64


def software(
    *,
    namespace: str = "engineering",
    name: str = "report-portal",
    version: str = "1.0.0",
    visibility: str = "organization",
    owner: str = "reporting",
) -> SoftwareManifest:
    return SoftwareManifest.model_validate(
        {
            "metadata": {
                "identity": {"namespace": namespace, "name": name, "version": version},
                "owner": {"type": "team", "id": owner},
                "visibility": visibility,
                "lifecycle": "published",
                "business_approval": {
                    "status": "approved",
                    "reviewer": "product-owner",
                    "evidence": "release accepted",
                },
                "validation_refs": [f"app:{name}:{version}"],
                "evaluation_refs": [f"app:{name}:{version}:e2e"],
            },
            "repository": {
                "provider": "github",
                "locator": f"dragon0816/{name}",
                "revision": REVISION,
            },
            "interfaces": [
                {
                    "name": "app_api",
                    "input_contract": "app.request.v1",
                    "output_contract": "app.response.v1",
                }
            ],
            "release": {
                "release_ref": f"release://{name}/{version}",
                "source_revision": REVISION,
                "evidence_refs": [f"ci://{name}/{version}"],
            },
        }
    )


def application(**software_changes: Any) -> ApplicationCatalogEntry:
    manifest = software(**software_changes)
    return ApplicationCatalogEntry(
        software=manifest,
        integrations=(
            ApplicationIntegration(
                name="portal", kind="web_ui", url="https://apps.example.invalid"
            ),
            ApplicationIntegration(
                name="api",
                kind="api",
                interface="app_api",
                url="https://apps.example.invalid/api",
            ),
        ),
    )


def signed_in() -> AuthenticatedActor:
    return AuthenticatedActor(
        actor="engineer",
        method="invitation-proof",
        authenticated_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
    )


def post(url: str, bearer: str, body: object) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(url, method="POST", data=json.dumps(body).encode("utf-8"))
    request.add_header("Authorization", f"Bearer {bearer}")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:
            return answer.status, json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        return refused.code, json.loads(refused.read())


def test_application_catalog_retains_exact_versions_without_install_semantics() -> None:
    catalog = ApplicationCatalog()
    catalog.register(application(version="1.0.0"))
    catalog.register(application(version="2.0.0"))

    entries = catalog.discover("engineering")
    assert [entry.software.metadata.identity.version for entry in entries] == ["1.0.0", "2.0.0"]
    assert all("package" not in entry.model_dump(mode="json") for entry in entries)


def test_member_discovers_only_entitled_apps_without_bridge_or_selection() -> None:
    platform = Platform()
    sessions = InMemoryMemberSessions()
    apps = ApplicationCatalog()
    apps.register(application())
    apps.register(
        application(
            namespace="private-space",
            name="private-portal",
            visibility="private",
            owner="another-team",
        )
    )
    service = MemberService(
        enrollment=platform.enrollment,
        authorization=platform.authorization,
        sessions=sessions,
        applications=apps,
        clock=lambda: NOW,
    )
    issued = sessions.issue(
        signed_in(), now=NOW, secret="member-session-secret-long-enough-to-be-safe"
    )
    grants_before = platform.authorization.grants("bridge-company")

    with MemberPortalServer(service) as server:
        status, result = post(server.base_url + "/v1/member/applications", issued.bearer, {})

    assert status == 200
    assert [item["identity"]["name"] for item in result["applications"]] == ["report-portal"]
    app = result["applications"][0]
    assert app["repository_locator"] == "dragon0816/report-portal"
    assert "package" not in app and "selected" not in app and "installed" not in app
    assert platform.authorization.grants("bridge-company") == grants_before


def test_application_endpoint_requires_a_member_session_and_filters_namespace() -> None:
    platform = Platform()
    sessions = InMemoryMemberSessions()
    apps = ApplicationCatalog()
    apps.register(application())
    apps.register(application(namespace="operations", name="ops-dashboard"))
    service = MemberService(
        enrollment=platform.enrollment,
        authorization=platform.authorization,
        sessions=sessions,
        applications=apps,
        clock=lambda: NOW,
    )
    issued = sessions.issue(
        signed_in(), now=NOW, secret="member-session-secret-long-enough-to-be-safe"
    )

    with MemberPortalServer(service) as server:
        denied, failure = post(server.base_url + "/v1/member/applications", "bad", {})
        status, result = post(
            server.base_url + "/v1/member/applications",
            issued.bearer,
            {"namespace": "operations"},
        )

    assert denied == 401 and failure == {"code": "authentication_failed"}
    assert status == 200
    assert [item["identity"]["namespace"] for item in result["applications"]] == ["operations"]
