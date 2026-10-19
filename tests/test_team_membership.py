"""A member of the owning team revises a team-owned Workflow in place
(owner 2026-10-19, `docs/phases/WORKFLOW_REVISION.md`).

Membership comes from the Shared Platform when this PC is connected (cached
for offline use), else from "Teams I belong to on this PC" in Agent Web
Settings. It only decides the draft's name on this PC: installing is the
person's press and publishing is checked by the platform's own records.

Fakes and the repo's in-process platform fixtures only; never a live platform.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_asset_ownership import who
from test_member_publish import _signed_in, queue, submit, workflow_manifest
from test_platform_publish import _publisher
from test_shared_platform_app import request
from test_workflow_revision import (
    ACTOR,
    EDITED,
    call,
    edited_workflow,
    fixture_workflow,
    install_fixture,
    studio,
)

from common.enrollment import Invitation
from common.member import AssetApproveRequest
from control_plane.app import SharedPlatformApplication
from control_plane.submissions import SubmissionError, SubmissionService
from host_runtime.chat_authoring import ChatAuthoring
from host_runtime.draft_cards import DraftCards
from host_runtime.platform_publish import PublishError
from host_runtime.team_membership import TeamDeclaration, TeamMembershipStore

__all__ = ["queue"]  # the review-queue fixture, used below

TEAM_OWNED = {"owner": ("team", "engineering"), "visibility": "organization", "refs": ()}


class FakePortal:
    """The Member Portal's `me` as `MemberPortalPublisher.membership` gives it."""

    def __init__(self, account: str = ACTOR, groups: tuple[str, ...] = ("engineering",)) -> None:
        self.account = account
        self.groups = groups
        self.error: PublishError | None = None
        self.calls = 0

    def membership(self) -> tuple[str, tuple[str, ...]]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.account, self.groups


def _store(
    tmp_path: Path, portal: FakePortal | None = None, declared: tuple[str, ...] = ()
) -> TeamMembershipStore:
    store = TeamMembershipStore(
        tmp_path / "ws",
        client=lambda: portal,
        account=lambda: ACTOR,
        clock=lambda: datetime(2026, 10, 19, 9, 0, tzinfo=UTC),
    )
    if declared:
        store.save_declared(TeamDeclaration(declared_teams=declared))
    return store


def _team_studio(tmp_path: Path, store: TeamMembershipStore) -> ChatAuthoring:
    chat = studio(tmp_path)
    chat.teams = store.membership
    install_fixture(chat, fixture_workflow(tmp_path, **TEAM_OWNED))  # type: ignore[arg-type]
    return chat


def _revise_and_card(
    chat: ChatAuthoring, tmp_path: Path
) -> tuple[dict[str, Any], str, DraftCards, str]:
    revised = call(chat, "authoring__revise_workflow", {"workflow": "fixture-weekly-report"})
    assert revised.status == "succeeded", revised
    data = revised.data
    edited = edited_workflow(chat, data["candidate_id"], EDITED)
    saved = call(
        chat,
        "authoring__draft_workflow",
        {"title": "Issue Key", "workflow": edited, "candidate_id": data["candidate_id"]},
    )
    assert saved.status == "succeeded", saved
    cards = DraftCards(tmp_path / "cards", chat=lambda: chat, actor=lambda: ACTOR)
    (card,), _ = cards.for_turn("session-1", datetime.now(UTC) - timedelta(minutes=1))
    return data, str(card["preview"]), cards, str(card["card_id"])


def test_a_platform_confirmed_member_revises_in_place(tmp_path: Path) -> None:
    portal = FakePortal()
    chat = _team_studio(tmp_path, _store(tmp_path, portal))
    data, preview, _, _ = _revise_and_card(chat, tmp_path)
    assert data["forked"] is False
    assert data["workflow"] == "engineering/fixture-weekly-report@1.0.1"
    assert data["member_of_team"] == "engineering" and data["membership_source"] == "platform"
    item = chat.candidate(data["candidate_id"], ACTOR)
    # The team keeps the name; the draft stays under it after editing.
    assert (item.draft.metadata.owner.type, item.draft.metadata.owner.id) == (
        "team",
        "engineering",
    )
    assert "Revision of engineering/fixture-weekly-report 1.0.0 → 1.0.1" in preview
    assert "Revision as a member of team engineering (confirmed by the shared platform)" in preview
    # Nothing installed until the person presses Install.
    assert sorted(p.name for p in chat.workflows_dir.glob("*.json")) == [
        "engineering__fixture-weekly-report__1.0.0.json"
    ]


def test_a_locally_declared_member_revises_in_place_and_the_card_says_so(
    tmp_path: Path,
) -> None:
    chat = _team_studio(tmp_path, _store(tmp_path, None, declared=("engineering",)))
    data, preview, cards, card_id = _revise_and_card(chat, tmp_path)
    assert data["forked"] is False and data["membership_source"] == "declared"
    assert data["workflow"] == "engineering/fixture-weekly-report@1.0.1"
    assert "declared on this PC" in data["note_membership"]
    assert "Revision as a member of team engineering (declared on this PC)" in preview
    # Installing is still the person's press, through the existing path.
    assert cards.decide(card_id, "install")["ok"]
    assert (chat.workflows_dir / "engineering__fixture-weekly-report__1.0.1.json").is_file()


@pytest.mark.parametrize(
    ("portal", "declared"),
    [
        (None, ("qa",)),  # declared, another team
        (None, ()),  # nothing declared
        (FakePortal(groups=("qa",)), ("engineering",)),  # the platform wins over the PC
        (FakePortal(account="someone-else"), ()),  # the platform answers for another account
    ],
)
def test_a_non_member_forks(
    tmp_path: Path, portal: FakePortal | None, declared: tuple[str, ...]
) -> None:
    chat = _team_studio(tmp_path, _store(tmp_path, portal, declared))
    revised = call(chat, "authoring__revise_workflow", {"workflow": "fixture-weekly-report"})
    assert revised.data["forked"] is True
    assert revised.data["workflow"] == "engineering/fixture-weekly-report-owner@1.0.0"
    assert "member_of_team" not in revised.data


def test_the_cache_answers_while_the_platform_is_unreachable(tmp_path: Path) -> None:
    portal = FakePortal()
    online = _store(tmp_path, portal)
    assert online.membership(ACTOR).source == "platform"
    cached = online.cached()
    assert cached is not None and cached.teams == ("engineering",)
    assert cached.checked_at == "2026-10-19T09:00:00+00:00"
    # A new process, offline: the cache in the workspace answers.
    portal.error = PublishError("platform_unreachable")
    offline = _store(tmp_path, portal)
    answer = offline.membership(ACTOR)
    assert answer.source == "platform_cache" and answer.includes("engineering")
    chat = _team_studio(tmp_path, offline)
    revised = call(chat, "authoring__revise_workflow", {"workflow": "fixture-weekly-report"})
    assert revised.data["forked"] is False
    assert revised.data["membership_source"] == "platform_cache"


def test_a_platform_refusal_gives_no_teams_and_ignores_the_cache(tmp_path: Path) -> None:
    portal = FakePortal()
    _store(tmp_path, portal).membership(ACTOR)
    portal.error = PublishError("authentication_failed", 401)
    refused = _store(tmp_path, portal, declared=("engineering",)).membership(ACTOR)
    assert refused.source == "platform" and refused.teams == ()


def test_no_platform_login_falls_back_to_the_declaration(tmp_path: Path) -> None:
    portal = FakePortal()
    portal.error = PublishError("login_missing")
    answer = _store(tmp_path, portal, declared=("engineering",)).membership(ACTOR)
    assert answer.source == "declared" and answer.includes("engineering")
    # The declaration is the PC owner's, not another sender's.
    assert _store(tmp_path, None, declared=("engineering",)).membership("visitor").teams == ()


def test_a_live_answer_is_reused_briefly(tmp_path: Path) -> None:
    portal = FakePortal()
    store = _store(tmp_path, portal)
    store.membership(ACTOR)
    store.membership(ACTOR)
    assert portal.calls == 1


def test_the_declaration_is_validated_and_kept_out_of_host_json(tmp_path: Path) -> None:
    store = _store(tmp_path)
    saved = store.save_declared(TeamDeclaration(declared_teams=("engineering", "engineering")))
    assert saved.declared_teams == ("engineering",)
    assert store.settings_path.name == "team-membership.json"
    with pytest.raises(ValueError):
        TeamDeclaration(declared_teams=("not a team",))


# -- the platform's side ----------------------------------------------------------


def test_publishing_a_locally_declared_revision_is_still_refused(
    queue: SubmissionService,
) -> None:
    """carol declared team `quality` on her PC; the platform's records say she
    is in no team, so her next version of the team's name is refused."""
    team_owned = workflow_manifest()
    team_owned["metadata"]["owner"] = {"type": "team", "id": "quality"}
    first = submit(queue, "alice", manifest=team_owned)
    queue.approve(
        who("bob"),
        AssetApproveRequest(submission_id=first.submission_id, evidence="ok"),
    )
    assert first.identity.version == "1.0.0"
    revision = workflow_manifest(version="1.0.1")
    revision["metadata"]["owner"] = {"type": "team", "id": "quality"}
    with pytest.raises(SubmissionError, match="publisher_not_authorized"):
        submit(queue, "carol", manifest=revision, change="patch")
    # A platform-recorded member of the team may.
    assert submit(queue, "bob", manifest=revision, change="patch").identity.version == "1.0.1"


@pytest.fixture
def platform(tmp_path: Path) -> Iterator[SharedPlatformApplication]:
    app = SharedPlatformApplication.empty(
        administrators=("platform-admin",), registry_path=tmp_path / "registry.sqlite"
    )
    with app:
        yield app


def _member(app: SharedPlatformApplication, actor: str, groups: tuple[str, ...]) -> str:
    proof = app.issue_invitation(
        Invitation(
            invitation_id=f"invite-{actor}",
            actor=actor,
            issued_by="platform-admin",
            groups=groups,
        ),
        expires_at=app.member_service.now() + timedelta(days=1),
    )
    status, reply = request(
        app.member_base_url + "/v1/member/sign-in",
        authorization=f"Invitation {proof.bearer}",
        method="POST",
    )
    assert status == 200
    return f"Bearer {reply['session']}"


def test_the_portal_answers_each_member_only_their_own_teams(
    platform: SharedPlatformApplication,
) -> None:
    anna = _member(platform, "anna", ("engineering", "qa"))
    ben = _member(platform, "ben", ("sales",))
    me = platform.member_base_url + "/v1/member/me"
    status, reply = request(me, authorization=anna, body={})
    assert status == 200 and reply["actor"] == "anna"
    assert reply["groups"] == ["engineering", "qa"]
    # Naming someone else changes nothing: the session decides who is asked about.
    status, reply = request(me, authorization=ben, body={"actor": "anna"})
    assert status == 200 and reply["actor"] == "ben" and reply["groups"] == ["sales"]
    status, reply = request(me, authorization=ben, body={})
    assert reply["actor"] == "ben" and reply["groups"] == ["sales"]
    assert request(me, body={})[0] == 401
    assert request(me, authorization="Bearer nobody:wrong", body={})[0] == 401


def test_the_host_client_reads_its_own_teams_from_the_portal(
    platform: SharedPlatformApplication,
) -> None:
    session = _signed_in(platform, "leo", "member")  # invited into `engineering`
    status, issued = request(
        platform.member_base_url + "/v1/member/logins/issue-agent",
        authorization=session,
        body={},
    )
    assert status == 200
    publisher = _publisher(platform, str(issued["login"]))
    assert publisher.membership() == ("leo", ("engineering",))


# -- Agent Web Settings: "Teams I belong to on this PC" -------------------------------


def test_agent_web_keeps_the_declaration_in_the_workspace(tmp_path: Path) -> None:
    from test_host_wiring import host_json, ready

    from host_runtime.host import build_runtime
    from host_runtime.web import AgentWeb
    from host_runtime.web_page import PAGE

    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    before = path.read_text(encoding="utf-8")
    with build_runtime(config, layout=layout) as runtime:
        web = AgentWeb(runtime, config_path=path)
        assert web.team_settings()["source"] == "none"
        saved = web.update_team_settings({"declared_teams": "engineering, qa"})
        assert saved["declared_teams"] == ["engineering", "qa"]
        assert saved["source"] == "declared" and saved["teams"] == ["engineering", "qa"]
        bad = web.update_team_settings({"declared_teams": "not a team"})
        assert bad["ok"] is False and bad["code"] == "teams_invalid"
        # The chat authoring sees the same declaration.
        assert runtime.chat_authoring is not None and runtime.chat_authoring.teams is not None
        assert runtime.chat_authoring.teams(runtime.actor).includes("engineering")
    assert path.read_text(encoding="utf-8") == before  # never in host.json
    assert (layout.workspace_root / "team-membership.json").is_file()
    assert 'id="team-declared"' in PAGE and "Teams I belong to on this PC" in PAGE
