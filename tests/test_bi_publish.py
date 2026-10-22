"""`POST /api/bi/publish` and `GET /api/bi/publish/status` (BI dataset
sharing slice 1, owner 2026-10-22): the owner publishes an own dataset as
this PC's member. Checked here: the local refusals (a subscribed dataset, no
note, readers, 全公司 without confirmation, no publishing set up), a found
secret named by card and field without the value, the platform's refusals
explained, and the last publish remembered for the dataset bar; then the
same route against a real in-process Shared Platform.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from capabilities.bi_cards import service, snapshot
from capabilities.bi_cards.store import BiStore
from host_runtime.bi_cards_api import publish_route
from host_runtime.platform_publish import PublishError

SECRET = "hunter2-do-not-show"


class FakePublisher:
    """`MemberPortalPublisher`'s two BI calls, recorded."""

    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []
        self.latest: dict[tuple[str, str], str | None] = {}
        self.refuse: PublishError | None = None
        self.first_pending = True

    def bi_dataset_status(self, names: list[tuple[str, str]]) -> list[dict[str, Any]]:
        return [
            {
                "namespace": namespace,
                "name": name,
                "entitled": self.latest.get((namespace, name)) is not None,
                "latest_version": self.latest.get((namespace, name)),
                "published_by": None,
                "published_at": None,
                "note": None,
            }
            for namespace, name in names
        ]

    def publish_bi_dataset(
        self,
        namespace: str,
        name: str,
        snapshot: bytes,
        *,
        note: str,
        base_version: str | None,
        readers: str | None = None,
        confirm_organization: bool = False,
        team: str | None = None,
    ) -> dict[str, Any]:
        if self.refuse is not None:
            raise self.refuse
        self.published.append(
            {
                "namespace": namespace,
                "name": name,
                "size": len(snapshot),
                "note": note,
                "base_version": base_version,
                "readers": readers,
                "confirm_organization": confirm_organization,
                "team": team,
            }
        )
        held = self.latest.get((namespace, name))
        if held is None and self.first_pending:
            return {
                "status": "pending_review",
                "asset": {"namespace": namespace, "name": name, "version": "1.0.0"},
                "sha256": "a" * 64,
                "digest": "b" * 64,
                "size": len(snapshot),
                "submission_id": "sub-1",
            }
        major, minor, _ = (held or "0.-1.0").split(".")
        version = f"{int(major) or 1}.{int(minor) + 1}.0"
        self.latest[(namespace, name)] = version
        return {
            "status": "published",
            "asset": {"namespace": namespace, "name": name, "version": version},
            "sha256": "a" * 64,
            "digest": "b" * 64,
            "size": len(snapshot),
            "submission_id": None,
        }


def _web(workspace: Path, publisher: Any, namespace: str | None = "engineering") -> Any:
    runtime = SimpleNamespace(
        layout=SimpleNamespace(workspace_root=workspace),
        config=SimpleNamespace(namespace=namespace),
    )
    return SimpleNamespace(runtime=runtime, _publisher=lambda: publisher)


def _demo(workspace: Path) -> BiStore:
    store = BiStore(workspace, "demo")
    service.load_demo(store)
    return store


def _post(web: Any, **body: Any) -> tuple[int, dict[str, Any]]:
    return publish_route(web, "POST", "/api/bi/publish", {}, body)


def _status(web: Any, dataset: str = "demo") -> tuple[int, dict[str, Any]]:
    return publish_route(web, "GET", "/api/bi/publish/status", {"dataset": dataset}, None)


def test_local_refusals_come_before_anything_is_built_or_sent(tmp_path: Path) -> None:
    publisher = FakePublisher()
    web = _web(tmp_path, publisher)
    _demo(tmp_path)
    assert _post(web, dataset="demo", note="  ")[1]["code"] == "note_required"
    assert _post(web, dataset="demo", note="v", readers="public")[1]["code"] == (
        "visibility_not_allowed"
    )
    assert _post(web, dataset="demo", note="v", readers="everyone")[1]["code"] == (
        "readers_invalid"
    )
    status, answer = _post(web, dataset="demo", note="v", readers="organization")
    assert (status, answer["code"]) == (400, "organization_unconfirmed")
    status, answer = _post(web, dataset="engineering/robotics-bi", note="v")
    assert (status, answer["code"]) == (409, "dataset_read_only")
    status, answer = _post(web, dataset="nothing", note="v")
    assert (status, answer["code"]) == (404, "dataset_unknown")
    status, answer = _post(web, dataset="demo", note="v", name="Bad Name/x")
    assert answer["code"] == "name_invalid"
    BiStore(tmp_path, "empty").create("bi.schema/v1.1@1.1.0")
    assert _post(web, dataset="empty", note="v")[1]["code"] == "dataset_empty"
    assert _post(_web(tmp_path, publisher, None), dataset="demo", note="v")[1]["code"] == (
        "namespace_required"
    )
    status, answer = _post(_web(tmp_path, None), dataset="demo", note="v")
    assert (status, answer["code"]) == (409, "publishing_not_configured")
    assert publisher.published == []
    assert not (tmp_path / "bi" / "demo" / "published.json").exists()


def test_a_first_publish_waits_for_review_then_versions_follow(tmp_path: Path) -> None:
    publisher = FakePublisher()
    web = _web(tmp_path, publisher)
    _demo(tmp_path)
    status, before = _status(web)
    assert status == 200 and before["last"] is None
    assert before["name"] == "engineering/demo" and before["cards"] > 0
    assert before["configured"] is True

    status, answer = _post(web, dataset="demo", note="第一版")
    assert status == 200, answer
    assert answer["ok"] is True and answer["status"] == "pending_review"
    assert (answer["name"], answer["version"], answer["readers"]) == (
        "engineering/demo",
        "1.0.0",
        "team",
    )
    sent = publisher.published[-1]
    assert sent["base_version"] is None and sent["readers"] == "team"
    assert sent["confirm_organization"] is False and sent["size"] > 0
    last = _status(web)[1]["last"]
    assert last["status"] == "pending_review" and last["version"] == "1.0.0"

    # The administrator approves: the bar learns it from the platform.
    publisher.latest[("engineering", "demo")] = "1.0.0"
    last = _status(web)[1]["last"]
    assert last["status"] == "published" and last["version"] == "1.0.0"

    # The next one is direct, follows the newest version and keeps the name.
    status, answer = _post(
        web,
        dataset="demo",
        note="十月",
        readers="organization",
        confirm_organization=True,
        name="other/ignored",
    )
    assert status == 200 and answer["status"] == "published" and answer["version"] == "1.1.0"
    sent = publisher.published[-1]
    assert (sent["namespace"], sent["name"]) == ("engineering", "demo")
    assert sent["base_version"] == "1.0.0"
    assert sent["readers"] == "organization" and sent["confirm_organization"] is True
    record = json.loads((tmp_path / "bi" / "demo" / "published.json").read_text("utf-8"))
    assert record["last"]["version"] == "1.1.0" and record["last"]["readers"] == "organization"


def test_a_secret_is_named_by_card_and_field_never_by_value(tmp_path: Path) -> None:
    publisher = FakePublisher()
    web = _web(tmp_path, publisher)
    store = _demo(tmp_path)
    card = store.card_rows()[0]
    store.set_field(
        card["id"],
        "notes",
        f"password={SECRET}",
        base_version=int(card["version"]),
        actor="leo",
    )
    status, answer = _post(web, dataset="demo", note="v")
    assert (status, answer["code"]) == (400, "secret_found")
    assert answer["card"] and answer["field"]
    assert answer["card"] in answer["message"] and answer["field"] in answer["message"]
    assert SECRET not in json.dumps(answer, ensure_ascii=False)
    assert publisher.published == []


@pytest.mark.parametrize(
    ("code", "status", "words"),
    [
        ("version_superseded", 409, "請先更新"),
        ("publisher_not_authorized", 403, "共同維護者"),
        ("artifact_too_large", 413, "上限"),
        ("platform_unreachable", 503, "沒有回應"),
        ("review_pending", 409, "審核"),
    ],
)
def test_the_platform_refusals_are_explained(
    tmp_path: Path, code: str, status: int, words: str
) -> None:
    publisher = FakePublisher()
    publisher.refuse = PublishError(code, 409)
    web = _web(tmp_path, publisher)
    _demo(tmp_path)
    answered, answer = _post(web, dataset="demo", note="v")
    assert (answered, answer["code"]) == (status, code)
    assert words in answer["message"]
    assert _status(web)[1]["last"] is None


def test_a_snapshot_over_the_limit_is_refused_before_sending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    publisher = FakePublisher()
    _demo(tmp_path)

    def too_large(store: BiStore, **_: Any) -> bytes:
        raise snapshot.SnapshotError("artifact_too_large", "too large")

    monkeypatch.setattr(snapshot, "build_snapshot", too_large)
    status, answer = _post(_web(tmp_path, publisher), dataset="demo", note="v")
    assert (status, answer["code"]) == (413, "artifact_too_large")
    assert publisher.published == []


def test_the_status_of_a_subscribed_dataset_is_refused(tmp_path: Path) -> None:
    status, answer = _status(_web(tmp_path, FakePublisher()), "engineering/robotics-bi")
    assert (status, answer["code"]) == (409, "dataset_read_only")


# -- against a real in-process Shared Platform ------------------------------------------


def test_publishing_through_a_real_platform(tmp_path: Path) -> None:
    from test_platform_publish import _agent_login, _publisher
    from test_shared_platform_app import request

    from control_plane.app import SharedPlatformApplication

    app = SharedPlatformApplication.empty(
        administrators=("platform-admin",), registry_path=tmp_path / "registry.sqlite"
    )
    with app:
        publisher = _publisher(app, _agent_login(app))
        workspace = tmp_path / "workspace"
        store = _demo(workspace)
        web = _web(workspace, publisher)

        status, first = _post(web, dataset="demo", note="第一版", name="engineering/robotics-bi")
        assert status == 200, first
        assert (first["status"], first["version"]) == ("pending_review", "1.0.0")
        # While the first version waits, another publish is refused.
        status, waiting = _post(web, dataset="demo", note="再一次")
        assert (status, waiting["code"]) == (409, "review_pending")
        assert _status(web)[1]["last"]["status"] == "pending_review"

        record = json.loads((workspace / "bi" / "demo" / "published.json").read_text("utf-8"))
        reviewer = _admin(app)
        status, _ = request(
            app.member_base_url + "/v1/member/admin/submissions/approve",
            authorization=reviewer,
            body={"submission_id": record["last"]["submission_id"], "evidence": "ok"},
        )
        assert status == 200
        approved = _status(web)[1]["last"]
        assert (approved["status"], approved["version"]) == ("published", "1.0.0")

        card = store.card_rows()[0]
        store.set_field(
            card["id"], "notes", "十月補充", base_version=int(card["version"]), actor="leo"
        )
        status, second = _post(web, dataset="demo", note="十月")
        assert status == 200, second
        assert (second["name"], second["status"], second["version"]) == (
            "engineering/robotics-bi",
            "published",
            "1.1.0",
        )
        assert (
            publisher.bi_dataset_status([("engineering", "robotics-bi")])[0]["latest_version"]
            == "1.1.0"
        )

        # 全公司 without the confirmation never reaches the platform; public is refused.
        assert _post(web, dataset="demo", note="x", readers="organization")[1]["code"] == (
            "organization_unconfirmed"
        )
        assert _post(web, dataset="demo", note="x", readers="public")[1]["code"] == (
            "visibility_not_allowed"
        )


def _admin(app: Any) -> str:
    from test_member_publish import _signed_in

    return str(_signed_in(app, "leo-review", "platform_admin"))
