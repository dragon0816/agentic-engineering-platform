"""A member publishes a Skill or Workflow through a review queue.

Requirements: `docs/phases/MEMBER_PUBLISH.md`, owner decisions of 2026-10-15:
the member submits as themselves, an administrator who is not the submitter
approves or rejects, and only an approval publishes, under the ownership and
version rules of `docs/phases/ASSET_OWNERSHIP.md`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from test_asset_ownership import NOW, REGISTRIES, enrollment, who
from test_shared_platform_app import request

from capabilities.files import READ_FILE_SPEC
from common.assets import AssetIdentity, ExecutionDependencies, WorkflowManifest
from common.enrollment import Invitation
from common.member import (
    AssetApproveRequest,
    AssetRejectRequest,
    AssetSubmitRequest,
)
from control_plane.app import SharedPlatformApplication
from control_plane.distribution import PackageRegistry
from control_plane.ownership import AssetOwnershipService
from control_plane.submissions import (
    MAX_ARTIFACT_BYTES,
    SubmissionError,
    SubmissionService,
    SubmissionStore,
)


def workflow_manifest(name: str = "weekly-check", version: str = "0.3.0") -> dict[str, Any]:
    """As an Agent has it: an author-chosen version and owner, and reviews the
    author marked approved themselves."""
    manifest = WorkflowManifest.model_validate(
        {
            "metadata": {
                "identity": {"namespace": "lab", "name": name, "version": version},
                "owner": {"type": "user", "id": "mallory"},
                "visibility": "organization",
                "lifecycle": "published",
                "business_approval": {
                    "status": "approved", "reviewer": "alice", "evidence": "I checked it"
                },
                "technical_policy": {
                    "status": "approved", "reviewer": "alice", "evidence": "fine",
                    "risk": "medium", "required_permissions": ["read_file"],
                },
            },
            "description": "Check the weekly numbers.",
            "execution": {"mode": "local"},
            "dependencies": ExecutionDependencies(
                local_capabilities=(READ_FILE_SPEC.name,), central_required=False
            ).model_dump(mode="json"),
            "input_contract": "lab.weekly.input.v1",
            "output_contract": "lab.weekly.output.v1",
            "steps": [READ_FILE_SPEC.identity.model_dump(mode="json")],
        }
    )
    return manifest.model_dump(mode="json")


def skill_manifest(target: AssetIdentity) -> dict[str, Any]:
    return {
        "metadata": {
            "identity": {"namespace": "lab", "name": "weekly-skill", "version": "1.0.0"},
            "owner": {"type": "user", "id": "alice"},
            "visibility": "organization",
        },
        "alias": "weekly",
        "instructions": "Run the weekly check.",
        "commands": [{"name": "run", "kind": "workflow", "target": target.model_dump()}],
        "default_command": "run",
    }


def submit(
    service: SubmissionService,
    actor: str = "alice",
    *,
    kind: str = "workflow",
    change: str = "minor",
    manifest: dict[str, Any] | None = None,
) -> Any:
    return service.submit(
        who(actor),
        AssetSubmitRequest.model_validate(
            {"kind": kind, "change": change, "manifest": manifest or workflow_manifest()}
        ),
    )


@pytest.fixture(params=sorted(REGISTRIES))
def queue(request: pytest.FixtureRequest, tmp_path: Path) -> SubmissionService:
    registry: PackageRegistry = REGISTRIES[request.param](tmp_path)
    artifacts: dict[str, bytes] = {}
    store = SubmissionStore(None if request.param == "memory" else tmp_path / "registry.sqlite")
    sqlite = request.param == "sqlite"
    ownership = AssetOwnershipService(enrollment(), registry, artifacts=artifacts)
    return SubmissionService(
        ownership,
        registry,
        store,
        artifacts=registry.artifacts if sqlite else artifacts,  # type: ignore[attr-defined]
        clock=lambda: NOW,
    )


def test_a_submission_waits_with_the_platforms_version_owner_and_pending_reviews(
    queue: SubmissionService,
) -> None:
    item = submit(queue)
    assert item.status == "pending"
    assert item.identity.version == "1.0.0"  # the platform's, not the author's 0.3.0
    assert item.submitter == "alice" and item.risk == "medium"
    detail = queue.detail(item.submission_id)
    metadata = detail.manifest["metadata"]
    assert metadata["owner"] == {"type": "user", "id": "alice"}  # not the claimed mallory
    assert metadata["business_approval"]["status"] == "pending"
    assert metadata["technical_policy"]["status"] == "pending"
    assert metadata["provenance"][-1] == {
        "source": "member-submission", "revision": None, "author": "alice"}
    assert queue.packages.discover() == ()  # nothing is published yet


def test_approval_publishes_as_the_submitter_with_the_reviewers_decision(
    queue: SubmissionService,
) -> None:
    item = submit(queue)
    approved = queue.approve(
        who("bob"), AssetApproveRequest(submission_id=item.submission_id, evidence="read it"))
    assert approved.status == "approved" and approved.reviewer == "bob"
    (package,) = queue.packages.discover()
    assert package.metadata.identity == item.identity
    assert package.metadata.owner.id == "alice"
    assert package.metadata.business_approval.reviewer == "bob"
    assert package.metadata.technical_policy.status == "approved"
    assert package.description == "Check the weekly numbers."
    record = queue.packages.ownership("lab", "weekly-check")
    assert record is not None and record.owner.id == "alice"
    # The artifact is the approved manifest, and its digest is the package's.
    assert queue._artifacts is not None
    artifact = queue._artifacts[package.metadata.package.artifact_ref]  # type: ignore[union-attr]
    assert hashlib.sha256(artifact).hexdigest() == package.metadata.package.sha256  # type: ignore[union-attr]
    assert json.loads(artifact)["metadata"]["business_approval"]["reviewer"] == "bob"


def test_nobody_reviews_their_own_submission(queue: SubmissionService) -> None:
    item = submit(queue)
    with pytest.raises(SubmissionError, match="self_review_refused"):
        queue.approve(who("alice"), AssetApproveRequest(
            submission_id=item.submission_id, evidence="mine"))
    assert queue.packages.discover() == ()


def test_a_rejection_needs_a_reason_and_publishes_nothing(queue: SubmissionService) -> None:
    item = submit(queue)
    with pytest.raises(ValueError):
        AssetRejectRequest.model_validate({"submission_id": item.submission_id, "reason": " "})
    rejected = queue.reject(who("bob"), AssetRejectRequest(
        submission_id=item.submission_id, reason="steps unclear"))
    assert (rejected.status, rejected.reason) == ("rejected", "steps unclear")
    assert queue.packages.discover() == ()
    with pytest.raises(SubmissionError, match="submission_not_pending"):
        queue.approve(who("bob"), AssetApproveRequest(
            submission_id=item.submission_id, evidence="late"))


def test_pending_submissions_of_one_name_get_distinct_versions(
    queue: SubmissionService,
) -> None:
    first = submit(queue)
    second = submit(queue, change="patch")
    assert (first.identity.version, second.identity.version) == ("1.0.0", "1.0.1")


def test_a_later_version_approved_first_supersedes_the_earlier_one(
    queue: SubmissionService,
) -> None:
    first = submit(queue)
    second = submit(queue, change="patch")
    queue.approve(who("bob"), AssetApproveRequest(
        submission_id=second.submission_id, evidence="ok"))
    with pytest.raises(SubmissionError, match="version_superseded"):
        queue.approve(who("bob"), AssetApproveRequest(
            submission_id=first.submission_id, evidence="ok"))


def test_only_the_owner_or_a_co_editor_submits_a_new_version(queue: SubmissionService) -> None:
    item = submit(queue)
    queue.approve(who("bob"), AssetApproveRequest(submission_id=item.submission_id, evidence="ok"))
    with pytest.raises(SubmissionError, match="publisher_not_authorized"):
        submit(queue, "carol")
    later = submit(queue, change="major")
    assert later.identity.version == "2.0.0"


def test_a_skill_needs_its_workflow_published_or_pending_from_the_same_member(
    queue: SubmissionService,
) -> None:
    target = AssetIdentity(namespace="lab", name="weekly-check", version="1.0.0")
    with pytest.raises(SubmissionError, match="missing_dependency"):
        submit(queue, kind="skill", manifest=skill_manifest(target))
    submit(queue)  # reserves weekly-check 1.0.0
    with pytest.raises(SubmissionError, match="missing_dependency"):
        submit(queue, "carol", kind="skill", manifest=skill_manifest(target))
    skill = submit(queue, kind="skill", manifest=skill_manifest(target))
    assert skill.kind == "skill" and skill.identity.name == "weekly-skill"


def test_invalid_oversized_and_withdrawn_submissions(queue: SubmissionService) -> None:
    with pytest.raises(SubmissionError, match="manifest_invalid"):
        submit(queue, manifest={"metadata": {}})
    large = workflow_manifest()
    large["description"] = "x" * MAX_ARTIFACT_BYTES
    with pytest.raises(SubmissionError, match="artifact_too_large"):
        submit(queue, manifest=large)
    item = submit(queue)
    with pytest.raises(SubmissionError, match="submission_missing"):
        queue.withdraw(who("carol"), item.submission_id)
    assert queue.withdraw(who("alice"), item.submission_id).status == "withdrawn"
    assert [entry.status for entry in queue.mine(who("alice")).submissions] == ["withdrawn"]


def test_the_queue_survives_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    first = SubmissionStore(path)
    item = submit(SubmissionService(
        AssetOwnershipService(enrollment(), REGISTRIES["sqlite"](tmp_path)),
        REGISTRIES["sqlite"](tmp_path), first, clock=lambda: NOW))
    first.close()
    again = SubmissionStore(path)
    held = again.get(item.submission_id)
    assert held is not None and held[0] == item
    assert again.list(status="pending") == (item,)
    again.close()


# -- over HTTP -----------------------------------------------------------------


def _signed_in(app: SharedPlatformApplication, actor: str, role: str) -> str:
    proof = app.issue_invitation(
        Invitation(invitation_id=f"invite-{actor}", actor=actor, issued_by="platform-admin",
                   groups=("engineering",), role=role),  # type: ignore[arg-type]
        expires_at=app.member_service.now() + timedelta(days=1),
    )
    status, reply = request(app.member_base_url + "/v1/member/sign-in",
                            authorization=f"Invitation {proof.bearer}", method="POST")
    assert status == 200
    return f"Bearer {reply['session']}"


def test_portal_routes_submit_review_and_issue_an_agent_login(tmp_path: Path) -> None:
    app = SharedPlatformApplication.empty(
        administrators=("platform-admin",), registry_path=tmp_path / "registry.sqlite",
        clock=lambda: NOW)
    with app:
        url = app.member_base_url + "/v1/member/"
        member = _signed_in(app, "leo", "member")
        reviewer = _signed_in(app, "leo-review", "platform_admin")

        # The member's Agent gets its own login and trades it for a session.
        status, issued = request(url + "logins/issue-agent", authorization=member, body={})
        assert status == 200 and issued["login_id"].startswith("login-")
        status, agent = request(url + "session", authorization=f"Login {issued['login']}",
                                method="POST")
        assert status == 200
        agent_session = f"Bearer {agent['session']}"

        status, submitted = request(url + "assets/submit", authorization=agent_session, body={
            "kind": "workflow", "change": "minor", "note": "first", "manifest":
            workflow_manifest()})
        assert status == 200, submitted
        submission_id = submitted["submission"]["submission_id"]

        # A member cannot see or decide the queue; nobody approves their own.
        assert request(url + "admin/submissions/list", authorization=member, body={})[0] == 403
        assert request(url + "admin/submissions/approve", authorization=member, body={
            "submission_id": submission_id, "evidence": "x"})[0] == 403
        status, queue = request(url + "admin/submissions/list", authorization=reviewer,
                                body={"status": "pending"})
        assert status == 200 and [s["submission_id"] for s in queue["submissions"]] == [
            submission_id]
        status, detail = request(url + "admin/submissions/get", authorization=reviewer,
                                 body={"submission_id": submission_id})
        assert status == 200 and detail["manifest"]["description"] == "Check the weekly numbers."

        status, approved = request(url + "admin/submissions/approve", authorization=reviewer,
                                   body={"submission_id": submission_id, "evidence": "read"})
        assert status == 200 and approved["submission"]["status"] == "approved"
        status, mine = request(url + "assets/submissions", authorization=agent_session, body={})
        assert status == 200 and mine["submissions"][0]["status"] == "approved"
        assert [p.metadata.identity.name for p in app.state.packages.discover()] == [
            "weekly-check"]

        status, refused = request(url + "assets/submit", authorization=agent_session, body={
            "kind": "workflow", "change": "minor", "manifest": {"metadata": {}}})
        assert (status, refused) == (400, {"code": "manifest_invalid"})
        assert request(url + "assets/submit", body={})[0] == 401


def test_the_portal_shows_the_review_queue_and_the_agent_connection() -> None:
    from control_plane.member_page import PAGE

    for hook in ('id="review"', 'id="review-rows"', "/v1/member/admin/submissions/",
                 'id="connect-agent"', "/v1/member/logins/issue-agent", 'id="mine-rows"',
                 "/v1/member/assets/submissions"):
        assert hook in PAGE
    # Submitted text is shown as text, never as markup.
    assert "review-manifest\").textContent" in PAGE and "innerHTML=JSON" not in PAGE
