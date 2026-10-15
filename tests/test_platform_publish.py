"""The Personal Agent publishes an installed Skill or Workflow as its member.

Requirements: `docs/phases/MEMBER_PUBLISH.md` (owner 2026-10-15), against a
real in-process shared platform.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from test_member_publish import _signed_in, workflow_manifest
from test_shared_platform_app import request

from common.assets import AssetIdentity
from control_plane.app import SharedPlatformApplication
from host_runtime.contracts import HostLayout, PlatformPublishBinding
from host_runtime.platform_publish import (
    MemberPortalPublisher,
    PublishError,
    explain,
    installed_assets,
    installed_manifest,
)
from models.credentials import EnvironmentCredentials, StaticCredentials


@pytest.fixture
def platform(tmp_path: Path) -> Iterator[SharedPlatformApplication]:
    app = SharedPlatformApplication.empty(
        administrators=("platform-admin",), registry_path=tmp_path / "registry.sqlite"
    )
    with app:
        yield app


def _agent_login(app: SharedPlatformApplication) -> str:
    member = _signed_in(app, "leo", "member")
    status, issued = request(
        app.member_base_url + "/v1/member/logins/issue-agent", authorization=member, body={}
    )
    assert status == 200
    return str(issued["login"])


def _installed(tmp_path: Path) -> HostLayout:
    layout = HostLayout.under(tmp_path / "workspace")
    layout.workflows.mkdir(parents=True)
    (layout.workflows / "lab__weekly-check__0.3.0.json").write_text(
        json.dumps(workflow_manifest(), indent=2) + "\n", encoding="utf-8"
    )
    return layout


def _publisher(app: SharedPlatformApplication, login: str) -> MemberPortalPublisher:
    binding = PlatformPublishBinding(
        member_portal_url=app.member_base_url, credential={"name": "platform_member_login"}
    )
    return MemberPortalPublisher(binding, StaticCredentials({"platform_member_login": login}))


def test_an_installed_workflow_is_submitted_listed_and_approved(
    platform: SharedPlatformApplication, tmp_path: Path
) -> None:
    layout = _installed(tmp_path)
    assert installed_assets(layout) == [{"kind": "workflow", "asset": "lab/weekly-check@0.3.0"}]
    publisher = _publisher(platform, _agent_login(platform))

    manifest = installed_manifest(layout, "workflow", "lab/weekly-check@0.3.0")
    submitted = publisher.submit("workflow", manifest, "minor", note="weekly numbers")
    assert submitted["status"] == "pending" and submitted["identity"]["version"] == "1.0.0"
    assert submitted["submitter"] == "leo"
    assert [s["submission_id"] for s in publisher.submissions()] == [submitted["submission_id"]]

    reviewer = _signed_in(platform, "leo-review", "platform_admin")
    status, _ = request(
        platform.member_base_url + "/v1/member/admin/submissions/approve",
        authorization=reviewer,
        body={"submission_id": submitted["submission_id"], "evidence": "ok"},
    )
    assert status == 200
    assert publisher.submissions()[0]["status"] == "approved"
    published = platform.state.packages.get(
        AssetIdentity(namespace="lab", name="weekly-check", version="1.0.0")
    )
    assert published is not None and published.metadata.owner.id == "leo"


def test_a_pending_submission_can_be_withdrawn(
    platform: SharedPlatformApplication, tmp_path: Path
) -> None:
    publisher = _publisher(platform, _agent_login(platform))
    manifest = installed_manifest(_installed(tmp_path), "workflow", "lab/weekly-check@0.3.0")
    submitted = publisher.submit("workflow", manifest, "patch")
    assert publisher.withdraw(submitted["submission_id"])["status"] == "withdrawn"
    with pytest.raises(PublishError, match="submission_not_pending"):
        publisher.withdraw(submitted["submission_id"])


def test_a_session_is_reused_and_renewed_when_it_ends(
    platform: SharedPlatformApplication, tmp_path: Path
) -> None:
    login = _agent_login(platform)
    publisher = _publisher(platform, login)
    publisher.submissions()
    first = publisher._session
    publisher.submissions()
    assert publisher._session == first  # one session for several calls
    assert first is not None
    later = first[1] + timedelta(minutes=1)
    publisher._clock = lambda: later
    publisher.submissions()
    assert publisher._session != first


def test_without_a_login_or_a_platform_the_member_is_told_what_to_do(
    platform: SharedPlatformApplication, tmp_path: Path
) -> None:
    binding = PlatformPublishBinding(
        member_portal_url=platform.member_base_url, credential={"name": "platform_member_login"}
    )
    unmapped = MemberPortalPublisher(binding, EnvironmentCredentials({}, environ={}))
    with pytest.raises(PublishError, match="login_missing"):
        unmapped.submissions()
    assert "Connect a Personal Agent" in explain("login_missing")
    wrong = _publisher(platform, "login-0000000000000000:not-the-secret-of-any-login-at-all")
    with pytest.raises(PublishError, match="authentication_failed"):
        wrong.submissions()
    gone = MemberPortalPublisher(
        PlatformPublishBinding(
            member_portal_url="http://127.0.0.1:9", credential={"name": "x"}, timeout_seconds=2
        ),
        StaticCredentials({"x": "login-1:secret"}),
    )
    with pytest.raises(PublishError, match="platform_unreachable"):
        gone.submissions()


def test_the_asset_must_be_installed_and_named_exactly(tmp_path: Path) -> None:
    layout = _installed(tmp_path)
    for reference, code in (
        ("lab/weekly-check", "bad_reference"),
        ("lab/weekly-check@9.9.9", "not_installed"),
        ("lab/weekly-check@0.3.0", "not_installed"),
    ):
        kind = "skill" if reference.endswith("0.3.0") else "workflow"
        with pytest.raises(PublishError, match=code):
            installed_manifest(layout, kind, reference)  # type: ignore[arg-type]


def test_the_publish_binding_holds_no_secret_and_needs_https_beyond_loopback() -> None:
    with pytest.raises(ValueError, match="https"):
        PlatformPublishBinding(
            member_portal_url="http://172.25.228.141:8776",
            credential={"name": "platform_member_login"},
        )
    with pytest.raises(ValueError):
        PlatformPublishBinding.model_validate(
            {
                "member_portal_url": "http://127.0.0.1:28776",
                "credential": {"name": "platform_member_login", "value": "secret"},
            }
        )
    ok = PlatformPublishBinding(
        member_portal_url="http://127.0.0.1:28776/", credential={"name": "platform_member_login"}
    )
    assert ok.member_portal_url == "http://127.0.0.1:28776"


def test_the_cli_publishes_lists_and_withdraws(
    platform: SharedPlatformApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from test_host_runtime import config

    from host_runtime.cli import main

    layout = _installed(tmp_path)
    host = config(
        workspace_root=str(layout.workspace_root),
        credentials=[
            {"secret": "platform_member_login", "environment_variable": "AEP_TEST_MEMBER_LOGIN"}
        ],
        publishing={
            "member_portal_url": platform.member_base_url,
            "credential": {"name": "platform_member_login"},
        },
    )
    path = tmp_path / "host.json"
    path.write_text(host.model_dump_json(), encoding="utf-8")
    monkeypatch.setenv("AEP_TEST_MEMBER_LOGIN", _agent_login(platform))
    base = ["assets", "--config", str(path)]

    assert (
        main(
            [
                *base,
                "publish",
                "--kind",
                "workflow",
                "--asset",
                "lab/weekly-check@0.3.0",
                "--change",
                "patch",
                "--note",
                "first",
            ]
        )
        == 0
    )
    submitted = json.loads(capsys.readouterr().out)["result"]
    assert submitted["identity"]["version"] == "1.0.0" and submitted["note"] == "first"
    assert main([*base, "submissions"]) == 0
    assert len(json.loads(capsys.readouterr().out)["result"]) == 1
    assert main([*base, "withdraw", "--submission", submitted["submission_id"]]) == 0
    assert json.loads(capsys.readouterr().out)["result"]["status"] == "withdrawn"
    assert main([*base, "publish", "--kind", "skill", "--asset", "lab/none@1.0.0"]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "not_installed"


def test_agent_web_offers_publishing_beside_the_marketplace() -> None:
    from host_runtime.web_page import PAGE

    for hook in (
        'id="publish-card"',
        'id="publish-asset"',
        'id="publish-go"',
        "/api/publishing/submit",
        "/api/publishing/withdraw",
        "loadPublishing()",
    ):
        assert hook in PAGE


def test_a_login_saved_with_setx_is_found_without_a_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from host_runtime import platform_publish

    saved = {"AEP_TEST_SAVED_LOGIN": "login-1:saved-value"}
    monkeypatch.setattr(platform_publish, "_saved_user_variable", saved.get)
    environment = platform_publish.UserEnvironment({"PATH": "x"})
    assert environment.get("AEP_TEST_SAVED_LOGIN") == "login-1:saved-value"
    assert environment.get("PATH") == "x" and environment.get("MISSING") is None


def test_agent_web_saves_a_pasted_code_for_this_user_and_never_echoes_it() -> None:
    from types import SimpleNamespace

    from host_runtime.web import AgentWeb
    from host_runtime.web_page import PAGE

    saved: dict[str, str] = {}
    config = SimpleNamespace(
        publishing=PlatformPublishBinding(
            member_portal_url="http://127.0.0.1:28776", credential={"name": "platform_member_login"}
        ),
        credential_environment=lambda: {"platform_member_login": "AEP_PLATFORM_MEMBER_LOGIN"},
    )
    web = SimpleNamespace(
        runtime=SimpleNamespace(config=config),
        user_environment=lambda name, value: saved.__setitem__(name, value),
    )
    code = "login-0123456789abcdef:" + "S" * 43
    reply = AgentWeb.connect_publishing(web, "  " + code + "\n")  # type: ignore[arg-type]
    assert reply == {"ok": True} and saved == {"AEP_PLATFORM_MEMBER_LOGIN": code}
    refused = AgentWeb.connect_publishing(web, "not a code")  # type: ignore[arg-type]
    assert refused["code"] == "login_malformed" and "not a code" not in str(refused)
    # The paste box lives in Settings > Shared platform (owner 2026-10-15).
    assert 'id="shared-code"' in PAGE and 'type="password"' in PAGE
    assert "/api/settings/shared-platform" in PAGE


# -- owner decisions 2026-10-15: visibility at submit, publishing a file ------

SAMPLE = Path(__file__).resolve().parents[1] / "deploy" / "samples" / "sync-test.workflow.json"


def test_the_publisher_sends_the_chosen_visibility(
    platform: SharedPlatformApplication, tmp_path: Path
) -> None:
    publisher = _publisher(platform, _agent_login(platform))
    manifest = installed_manifest(_installed(tmp_path), "workflow", "lab/weekly-check@0.3.0")
    with pytest.raises(PublishError, match="bad_visibility"):
        publisher.submit("workflow", manifest, "minor", visibility="everyone")
    submitted = publisher.submit("workflow", manifest, "minor", visibility="team")
    assert submitted["visibility"] == "team"
    default = publisher.submit("workflow", manifest, "patch")
    assert default["visibility"] == "organization"  # what the manifest says


def test_the_cli_publishes_a_manifest_file_with_a_chosen_visibility(
    platform: SharedPlatformApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from test_host_runtime import config

    from host_runtime.cli import main

    host = config(
        workspace_root=str(tmp_path / "workspace"),
        credentials=[
            {"secret": "platform_member_login", "environment_variable": "AEP_TEST_MEMBER_LOGIN"}
        ],
        publishing={
            "member_portal_url": platform.member_base_url,
            "credential": {"name": "platform_member_login"},
        },
    )
    path = tmp_path / "host.json"
    path.write_text(host.model_dump_json(), encoding="utf-8")
    monkeypatch.setenv("AEP_TEST_MEMBER_LOGIN", _agent_login(platform))  # leo, engineering
    base = ["assets", "--config", str(path), "publish", "--kind", "workflow"]

    assert main([*base, "--file", str(SAMPLE), "--visibility", "team"]) == 0
    submitted = json.loads(capsys.readouterr().out)["result"]
    assert submitted["identity"] == {
        "namespace": "company-agent",
        "name": "sync-test",
        "version": "1.0.0",
    }
    # The sample names team engineering as owner, and leo belongs to it.
    assert submitted["owner"] == {"type": "team", "id": "engineering"}
    assert submitted["visibility"] == "team"
    assert main([*base, "--file", str(SAMPLE), "--change", "patch"]) == 0
    assert json.loads(capsys.readouterr().out)["result"]["visibility"] == "organization"

    broken = tmp_path / "broken.json"
    broken.write_text("not json", encoding="utf-8")
    assert main([*base, "--file", str(broken)]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "file_unreadable"
    with pytest.raises(SystemExit):  # one source only
        main([*base, "--file", str(SAMPLE), "--asset", "lab/x@1.0.0"])
    with pytest.raises(SystemExit):
        main([*base, "--file", str(SAMPLE), "--visibility", "everyone"])


def test_the_sync_test_sample_is_a_harmless_read_only_workflow(tmp_path: Path) -> None:
    from test_chat_authoring import Echo, Out, Recorder

    from capabilities.company_agent.manifest import personal_proof_fixture_read_spec
    from capabilities.runtime import InstalledCapabilities, LocalPolicy
    from common.assets import ExecutionDependencies, WorkflowManifest
    from host_runtime.chat_authoring import ChatAuthoring
    from host_runtime.external_authoring import ExternalAuthoring
    from workflow.dispatch import BridgeExecutor

    raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
    manifest = WorkflowManifest.model_validate(raw)
    metadata = manifest.metadata
    assert (metadata.identity.namespace, metadata.identity.name) == ("company-agent", "sync-test")
    assert metadata.owner.model_dump() == {"type": "team", "id": "engineering"}
    assert metadata.visibility == "organization"
    installed = InstalledCapabilities()
    installed.register(
        personal_proof_fixture_read_spec(),
        Recorder(),
        Echo,
        Out,
        ExecutionDependencies(central_required=False),
    )
    bridge = BridgeExecutor(installed, LocalPolicy(()))
    chat = ChatAuthoring(
        tmp_path / "chat",
        bridge=lambda: bridge,
        namespace="company-agent",
        workflows_dir=tmp_path / "workflows",
        grants_file=tmp_path / "grants.json",
        skills_dir=tmp_path / "skills",
    )
    checked = ExternalAuthoring(chat, "owner", "cli").check_workflow(raw)
    assert checked["ok"] is True and checked["read_only"] is True, checked


def test_agent_web_asks_who_can_use_it_and_passes_it_on(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from host_runtime.web import AgentWeb
    from host_runtime.web_page import PAGE

    for hook in (
        'id="publish-visibility"',
        '<option value="team">Only my team</option>',
        '<option value="organization">Everyone in the organization</option>',
        'id="publish-audience"',
        'visibility: el("publish-visibility").value',
    ):
        assert hook in PAGE, hook
    sent: list[Any] = []

    class Publisher:
        def submit(self, *args: Any) -> dict[str, Any]:
            sent.append(args)
            return {"identity": {"namespace": "lab", "name": "weekly-check", "version": "1.0.0"}}

    tasks = SimpleNamespace(start=lambda *a: "t", finish=lambda *a: None)
    web = SimpleNamespace(
        _publisher=lambda: Publisher(),
        tasks=lambda: tasks,
        runtime=SimpleNamespace(
            layout=_installed(tmp_path), config=SimpleNamespace(publishing=None)
        ),
    )
    reply = AgentWeb.publish_asset(
        web,
        "workflow",
        "lab/weekly-check@0.3.0",  # type: ignore[arg-type]
        "minor",
        "",
        "team",
    )
    assert reply["ok"] is True and sent[0][-1] == "team"
    AgentWeb.publish_asset(
        web,
        "workflow",
        "lab/weekly-check@0.3.0",  # type: ignore[arg-type]
        "minor",
        "",
    )
    assert sent[1][-1] is None


def _no_browser() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_no_browser(), reason="no Chromium browser is installed")
def test_the_who_can_use_it_choice_renders_in_a_real_browser(
    platform: SharedPlatformApplication,
    tmp_path: Path,
) -> None:
    import threading
    import time

    from test_host_wiring import host_json, ready

    from host_runtime.host import build_runtime
    from host_runtime.web import AgentWeb, AgentWebServer
    from integrations.browser import Browser

    config, layout = ready(
        tmp_path,
        config_changes={
            "publishing": {
                "member_portal_url": platform.member_base_url,
                "credential": {"name": "platform_member_login"},
            },
            "credentials": [
                {
                    "secret": "platform_member_login",
                    "environment_variable": "AEP_TEST_UNSET_MEMBER_LOGIN",
                }
            ],
        },
    )
    path = host_json(tmp_path, config)
    with build_runtime(config, layout=layout) as runtime:
        served = AgentWebServer(AgentWeb(runtime, config_path=path))
        thread = threading.Thread(target=served.serve_forever, daemon=True)
        thread.start()
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()
        try:
            browser.navigate(served.address)
            browser._evaluate('document.getElementById("nav-capabilities").click(); 0')
            measure = (
                'JSON.stringify(["publish-visibility","publish-audience"].map(id => {const r ='
                " document.getElementById(id).getBoundingClientRect(); return [r.width,"
                " r.height];}))"
            )
            deadline = time.monotonic() + 20
            size = [[0, 0], [0, 0]]
            while size[0][1] == 0 and time.monotonic() < deadline:
                time.sleep(0.2)  # the form shows once the publishing settings arrive
                size = json.loads(str(browser._evaluate(measure)))
            assert size[0][0] > 100 and size[0][1] > 20, size
            assert size[1][1] > 10, size
            browser._evaluate(
                'const s = document.getElementById("publish-visibility");'
                ' s.value = "team"; s.dispatchEvent(new Event("change")); 0'
            )
            text = str(browser._evaluate('document.getElementById("publish-audience").textContent'))
            assert "Only my team" in text and "Member Portal" in text
        finally:
            browser.close()
            browser.discard_profile()
            served.shutdown()
            served.server_close()
            thread.join(timeout=5)
