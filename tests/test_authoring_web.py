"""SOP to Workflow authoring through Agent Web (SOP_TO_WORKFLOW W7)."""

from __future__ import annotations

import base64
from pathlib import Path

from test_agent_web import base, fetch, served  # noqa: F401 - the server fixture
from test_authoring_conversation import Scripted
from test_authoring_sessions import blocks, draft
from test_workflow_preview import Calls

from host_runtime.authoring import AuthoringStudio
from host_runtime.web import AgentWebServer
from host_runtime.web_page import PAGE
from host_runtime.workflow_settings import WorkflowSettingsStore


def use_studio(server: AgentWebServer, tmp_path: Path, model: Scripted) -> Calls:
    """The page's studio, with test building blocks and a scripted model."""
    calls = Calls()
    web = server.web
    installed = blocks(calls)
    web.authoring = AuthoringStudio(
        tmp_path / "authoring",
        installed=installed,
        model=lambda: model,
        model_alias="gateway",
        local_only=False,
        namespace="engineering",
        workflows_dir=tmp_path / "workflows",
        grants_file=tmp_path / "grants.json",
        settings_store=WorkflowSettingsStore(tmp_path / "settings.json"),
    )
    web.runtime.agent.gateway.bridge.installed = installed
    return calls


def test_start_discuss_preview_and_install_over_http(
    served: AgentWebServer,  # noqa: F811
    tmp_path: Path,
) -> None:
    calls = use_studio(
        served,
        tmp_path,
        Scripted(
            {"reply": "哪個客戶？", "questions": ["客戶代碼？"], "workflow": None},
            {"reply": "好了", "questions": [], "workflow": draft()},
        ),
    )
    url, token = base(served), served.token
    started = fetch(
        url + "/api/authoring/start",
        token=token,
        body={"title": "出貨", "sop_text": "每天查出貨。"},
    ).json()
    assert started["status"] == "needs_input" and started["questions"] == ["客戶代碼？"]
    session = started["session_id"]
    listed = fetch(url + "/api/authoring", token=token).json()
    assert [item["session_id"] for item in listed["sessions"]] == [session]

    early = fetch(url + "/api/authoring/install", token=token, body={"session_id": session})
    assert early.status == 409 and early.json()["code"] == "authoring_preview_required"

    ready = fetch(
        url + "/api/authoring/discuss",
        token=token,
        body={"session_id": session, "message": "每次輸入"},
    ).json()
    assert ready["status"] == "ready" and "read" in ready["draft_text"]
    assert [field["name"] for field in ready["settings_fields"]] == ["folder"]

    shown = fetch(
        url + "/api/authoring/preview",
        token=token,
        body={
            "session_id": session,
            "arguments": {"customer": "C1"},
            "settings": {"folder": "C:/out"},
        },
    ).json()
    assert shown["status"] == "previewed" and calls.ran == ["read"]
    assert [step["state"] for step in shown["preview"]["steps"]] == ["ran", "planned"]

    installed = fetch(
        url + "/api/authoring/install", token=token, body={"session_id": session}
    ).json()
    assert installed["status"] == "installed" and installed["restart_required"] is True
    assert (tmp_path / "workflows" / "engineering__daily-sop__1.0.0.json").is_file()


def test_requests_need_the_token_and_a_bad_pdf_is_refused(
    served: AgentWebServer,  # noqa: F811
    tmp_path: Path,
) -> None:
    use_studio(served, tmp_path, Scripted())
    url = base(served)
    assert fetch(url + "/api/authoring/start", body={"sop_text": "x"}).status == 401
    not_pdf = fetch(
        url + "/api/authoring/start",
        token=served.token,
        body={"title": "t", "pdf_base64": base64.b64encode(b"hello").decode()},
    )
    assert not_pdf.status == 409 and not_pdf.json()["code"] == "authoring_sop_not_a_pdf"
    garbled = fetch(
        url + "/api/authoring/start", token=served.token, body={"title": "t", "pdf_base64": "%%%"}
    )
    assert garbled.json()["code"] == "authoring_request_invalid"


def test_the_sop_form_is_gone_and_the_draft_list_builds_no_html_from_text() -> None:
    """Owner 2026-10-08: drafting happens in the conversation; the page lists
    drafts instead, built with text nodes only."""
    assert 'id="sop-authoring"' not in PAGE and 'id="authoring-install"' not in PAGE
    script = PAGE.split("<script>", 1)[1].split("</script>", 1)[0]
    section = script.split("async function loadDrafts()", 1)[1].split(
        "async function loadExternalApprovals()", 1
    )[0]
    for unsafe in ("innerHTML", "insertAdjacentHTML", "outerHTML"):
        assert unsafe not in section
